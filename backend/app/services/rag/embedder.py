"""ExecMind - Ollama embedding wrapper for document vectorization."""

import httpx

from app.core.config import settings
from app.utils.logging import get_logger

logger = get_logger("embedder")


class OllamaEmbedder:
    """Wrapper for generating text embeddings via Ollama API.

    Uses nomic-embed-text model by default, producing 768-dimensional vectors.
    """

    def __init__(
        self,
        ollama_url: str | None = None,
        model: str | None = None,
    ):
        self.ollama_url = (ollama_url or settings.OLLAMA_URL).rstrip("/")
        self.model = model or settings.EMBEDDING_MODEL
        self.embed_endpoint = f"{self.ollama_url}/api/embeddings"

    async def embed_text(self, text: str) -> list[float]:
        """Generate embedding vector for a single text string.

        Args:
            text: Input text to embed.

        Returns:
            List of float values (768-dimensional vector).

        Raises:
            RuntimeError: If Ollama API call fails.
        """
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                self.embed_endpoint,
                json={"model": self.model, "prompt": text},
            )

            if response.status_code != 200:
                error_detail = response.text
                logger.error("embedding_failed", status=response.status_code, detail=error_detail)
                raise RuntimeError(f"Ollama embedding failed: {error_detail}")

            data = response.json()
            return data["embedding"]

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for a batch of texts.

        Args:
            texts: List of input texts.

        Returns:
            List of embedding vectors.
        """
        embeddings = []
        for text in texts:
            embedding = await self.embed_text(text)
            embeddings.append(embedding)
        return embeddings

    async def is_available(self) -> bool:
        """Check if Ollama embedding service is reachable."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self.ollama_url}/api/tags")
                return response.status_code == 200
        except Exception:
            return False
