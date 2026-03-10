"""ExecMind - Document processor for text extraction and chunking."""

import os
import io
from typing import Optional

from app.core.config import settings
from app.services.rag.embedder import OllamaEmbedder
from app.utils.logging import get_logger

logger = get_logger("document_processor")

# Supported MIME types
ALLOWED_MIME_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "text/plain",
    "image/png",
    "image/jpeg",
    "image/jpg",
}

MAX_CHUNK_SIZE = 1024   # tokens approx (chars / 4)
CHUNK_OVERLAP = 100     # token overlap


class DocumentProcessor:
    """Extracts text from documents, chunks them, and generates embeddings.

    Supports PDF (via PyMuPDF), DOCX, XLSX, PPTX, and TXT files.
    """

    def __init__(self, embedder: OllamaEmbedder | None = None):
        self.embedder = embedder or OllamaEmbedder()

    async def process_document(
        self,
        file_path: str,
        mime_type: str,
        document_id: str,
        collection_id: str,
        doc_title: str,
        doc_category: Optional[str] = None,
        sensitivity: str = "confidential",
    ) -> list[dict]:
        """Full pipeline: extract → chunk → embed → return points for Qdrant.

        Args:
            file_path: Path to the document file.
            mime_type: MIME type of the document.
            document_id: UUID of the document record.
            collection_id: UUID of the KB collection.
            doc_title: Document title for metadata.
            doc_category: Optional category tag.
            sensitivity: Sensitivity level.

        Returns:
            List of dicts with 'vector', 'payload' ready for Qdrant upsert.
        """
        logger.info(
            "processing_document",
            document_id=document_id,
            mime_type=mime_type,
            file_path=file_path,
        )

        # Step 1: Extract text
        pages = self._extract_text(file_path, mime_type)

        # Step 2: Chunk text
        chunks = self._chunk_text(pages)

        logger.info(
            "document_chunked",
            document_id=document_id,
            total_chunks=len(chunks),
        )

        # Step 3: Generate embeddings and build points
        points = []
        for idx, chunk in enumerate(chunks):
            try:
                embedding = await self.embedder.embed_text(chunk["text"])
            except Exception as e:
                logger.error(
                    "embedding_chunk_failed",
                    document_id=document_id,
                    chunk_index=idx,
                    error=str(e),
                )
                continue

            point = {
                "vector": embedding,
                "payload": {
                    "document_id": document_id,
                    "collection_id": collection_id,
                    "chunk_index": idx,
                    "page_number": chunk.get("page", 0),
                    "doc_title": doc_title,
                    "doc_category": doc_category or "",
                    "doc_sensitivity": sensitivity,
                    "text": chunk["text"],
                    "char_count": len(chunk["text"]),
                },
            }
            points.append(point)

        logger.info(
            "document_processed",
            document_id=document_id,
            total_points=len(points),
        )
        return points

    def extract_text_from_bytes(self, file_bytes: bytes, filename: str, mime_type: str) -> str:
        """Extract text from file bytes directly in memory.
        Used for chat attachments.
        
        Returns:
            The extracted text as a single string.
        """
        import tempfile
        
        # Try image OCR directly from bytes first
        if mime_type.startswith("image/"):
            return self._extract_image(file_bytes)
            
        # For other types, we'll write to a tempfile to reuse existing extraction code
        # Some libraries like pymupdf or unstructured prefer a file path
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(filename)[1]) as tmp:
                tmp.write(file_bytes)
                tmp_path = tmp.name
                
            pages = self._extract_text(tmp_path, mime_type)
            extracted = "\n".join(p["text"] for p in pages if p.get("text"))
            return extracted
        except Exception as e:
            logger.error("extract_bytes_failed", filename=filename, error=str(e))
            return ""
        finally:
            if 'tmp_path' in locals() and os.path.exists(tmp_path):
                os.remove(tmp_path)

    def _extract_text(self, file_path: str, mime_type: str) -> list[dict]:
        """Extract text from a document based on its MIME type.

        Returns:
            List of dicts with 'text' and 'page' keys.
        """
        if mime_type == "application/pdf":
            return self._extract_pdf(file_path)
        elif mime_type == "text/plain":
            return self._extract_txt(file_path)
        elif mime_type.startswith("image/"):
            with open(file_path, "rb") as f:
                text = self._extract_image(f.read())
            return [{"text": text, "page": 1}] if text else []
        else:
            return self._extract_generic(file_path)

    def _extract_image(self, file_bytes: bytes) -> str:
        """Extract text from an image using OCR."""
        try:
            import pytesseract
            from PIL import Image
            img = Image.open(io.BytesIO(file_bytes))
            # Run OCR (Indonesian + English)
            ocr_text = pytesseract.image_to_string(img, lang="ind+eng").strip()
            return ocr_text
        except ImportError:
            logger.warning("pytesseract_not_available")
            return ""
        except Exception as e:
            logger.warning("ocr_image_failed", error=str(e))
            return ""

    def _extract_pdf(self, file_path: str) -> list[dict]:
        """Extract text from PDF using PyMuPDF, with OCR fallback for scanned pages."""
        try:
            import pymupdf
            try:
                import pytesseract
                from PIL import Image
                import io
                has_tesseract = True
            except ImportError:
                has_tesseract = False

            doc = pymupdf.open(file_path)
            pages = []
            for page_num, page in enumerate(doc):
                text = page.get_text().strip()
                
                # Fallback to OCR if text is suspiciously short (likely a scanned image)
                if len(text) < 50 and has_tesseract:
                    try:
                        # Render page to an image (dpi=150 is good enough for OCR without blowing up memory)
                        pix = page.get_pixmap(dpi=150)
                        img_bytes = pix.tobytes("png")
                        img = Image.open(io.BytesIO(img_bytes))
                        # Run OCR (Indonesian + English)
                        ocr_text = pytesseract.image_to_string(img, lang="ind+eng").strip()
                        if ocr_text:
                            text = text + "\n" + ocr_text if text else ocr_text
                            text = text.strip()
                    except Exception as e:
                        logger.warning("ocr_failed", page=page_num + 1, error=str(e))

                if text:
                    pages.append({"text": text, "page": page_num + 1})
            doc.close()
            return pages
        except ImportError:
            logger.warning("pymupdf_not_available", fallback="generic")
            return self._extract_generic(file_path)

    def _extract_txt(self, file_path: str) -> list[dict]:
        """Extract text from plain text files."""
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            text = f.read().strip()
        return [{"text": text, "page": 1}] if text else []

    def _extract_generic(self, file_path: str) -> list[dict]:
        """Extract text from DOCX/XLSX/PPTX using unstructured (if available)."""
        try:
            from unstructured.partition.auto import partition

            elements = partition(filename=file_path)
            pages = []
            for element in elements:
                text = str(element).strip()
                if text:
                    page_num = getattr(element.metadata, "page_number", 1) or 1
                    pages.append({"text": text, "page": page_num})
            return pages
        except ImportError:
            logger.warning("unstructured_not_available")
            # Fallback: try to read as text
            return self._extract_txt(file_path)

    def _chunk_text(self, pages: list[dict]) -> list[dict]:
        """Split extracted pages into overlapping chunks.

        Uses recursive character splitting with overlap for context preservation.

        Returns:
            List of dicts with 'text' and 'page' keys.
        """
        chunks = []
        max_chars = MAX_CHUNK_SIZE * 4  # Approximate 4 chars per token
        overlap_chars = CHUNK_OVERLAP * 4

        for page_data in pages:
            text = page_data["text"]
            page = page_data["page"]

            if len(text) <= max_chars:
                chunks.append({"text": text, "page": page})
                continue

            # Split by paragraphs first, then by sentences
            start = 0
            while start < len(text):
                end = min(start + max_chars, len(text))

                # Try to break at paragraph or sentence boundary
                if end < len(text):
                    last_para = text.rfind("\n\n", start, end)
                    if last_para > start + max_chars // 2:
                        end = last_para
                    else:
                        last_sentence = text.rfind(". ", start, end)
                        if last_sentence > start + max_chars // 2:
                            end = last_sentence + 1

                chunk_text = text[start:end].strip()
                if chunk_text:
                    chunks.append({"text": chunk_text, "page": page})

                start = max(start + 1, end - overlap_chars)

        return chunks
