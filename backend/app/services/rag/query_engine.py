"""ExecMind - RAG query engine for document-grounded chat responses."""

import re
import time
from typing import AsyncGenerator

import httpx

from app.core.config import settings
from app.services.rag.embedder import OllamaEmbedder
from app.utils.logging import get_logger

logger = get_logger("query_engine")

SYSTEM_PROMPT = """Kamu adalah ExecMind, asisten AI yang membantu pejabat eksekutif lembaga
untuk mencari informasi dari dokumen internal.

ATURAN KETAT:
1. HANYA jawab berdasarkan konteks dokumen yang diberikan di bawah
2. Jika informasi tidak ditemukan di dokumen, katakan:
   "Informasi tersebut tidak tersedia dalam dokumen yang saya akses."
3. Selalu sebutkan nama dokumen sumber untuk setiap klaim
4. Gunakan Bahasa Indonesia yang formal dan profesional
5. Jangan berspekulasi atau menambahkan informasi di luar konteks
6. Jika ada tabel atau data numerik, sajikan dengan format yang rapi"""

DANGEROUS_PATTERNS = [
    r"ignore previous instructions",
    r"disregard all",
    r"system:",
    r"<\|im_start\|>",
    r"<\|im_end\|>",
]


def sanitize_user_query(query: str) -> str:
    """Remove potential prompt injection patterns from user input.

    Args:
        query: Raw user query.

    Returns:
        Sanitized query with dangerous patterns removed and length capped.
    """
    sanitized = query
    for pattern in DANGEROUS_PATTERNS:
        sanitized = re.sub(pattern, "", sanitized, flags=re.IGNORECASE)
    return sanitized[:2000]


def parse_embedded_tool_call(content: str) -> list[dict]:
    """Fallback parser for models that output tool calls as JSON in content.
    
    Returns a list of tool_calls formatted identically to Ollama's native tool_calls.
    """
    if not content:
        return []
    import json
    try:
        # Check if content looks like JSON
        content_stripped = content.strip()
        if content_stripped.startswith("{") and content_stripped.endswith("}"):
            data = json.loads(content_stripped)
            if isinstance(data, dict) and "name" in data and "arguments" in data:
                return [{
                    "function": {
                        "name": data["name"],
                        "arguments": data["arguments"]
                    }
                }]
    except Exception:
        pass
    return []


class RAGQueryEngine:
    """Orchestrates RAG queries: embed → retrieve → augment → generate.

    Uses Ollama for both embedding (nomic-embed-text) and LLM inference
    (qwen2.5-coder:14b) with Qdrant for vector search.
    """

    def __init__(
        self,
        qdrant_client=None,
        embedder: OllamaEmbedder | None = None,
    ):
        self.embedder = embedder or OllamaEmbedder()
        self.qdrant_client = qdrant_client
        self.ollama_url = settings.OLLAMA_URL.rstrip("/")
        self.llm_model = settings.LLM_MODEL
        self.top_k = settings.QDRANT_SIMILARITY_TOP_K

    async def query_streaming(
        self,
        query: str,
        collection_name: str,
        collection_id: str,
        conversation_history: list[dict] | None = None,
        images: list[str] | None = None,
    ) -> AsyncGenerator[dict, None]:
        """Stream a RAG-augmented response from the LLM.

        Pipeline: sanitize → embed query → Qdrant search → build prompt → stream LLM.

        Args:
            query: User question.
            collection_name: Qdrant collection name.
            collection_id: UUID of the KB collection.
            conversation_history: Recent chat messages for context.

        Yields:
            Dicts with type 'token', 'sources', or 'done'.
        """
        start_time = time.time()
        sanitized_query = sanitize_user_query(query)

        # Step 1: Embed query
        query_embedding = await self.embedder.embed_text(sanitized_query)

        # Step 2: Search Qdrant
        sources = []
        context_text = ""

        # We bypass qdrant_client for searching since qdrant-client 1.17.0 removed .search()
        try:
            url = f"{settings.QDRANT_URL.rstrip('/')}/collections/{collection_name}/points/search"
            payload = {
                "vector": query_embedding,
                "limit": self.top_k,
                "filter": {
                    "must": [
                        {
                            "key": "collection_id",
                            "match": {"value": collection_id}
                        }
                    ]
                },
                "with_payload": True
            }

            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(url, json=payload)
                resp.raise_for_status()
                data = resp.json()

            for hit in data.get("result", []):
                hit_payload = hit.get("payload", {})
                score = hit.get("score", 0.0)
                
                context_text += f"\n---\nDokumen: {hit_payload.get('doc_title', 'Unknown')}"
                context_text += f" (Halaman {hit_payload.get('page_number', '?')})\n"
                context_text += hit_payload.get("text", "")

                sources.append({
                    "doc_id": hit_payload.get("document_id", ""),
                    "doc_title": hit_payload.get("doc_title", "Unknown"),
                    "page": hit_payload.get("page_number", 0),
                    "score": round(score, 4),
                    "text_preview": (hit_payload.get("text", ""))[:200],
                })

        except Exception as e:
            logger.error("qdrant_search_failed", error=str(e))
            context_text = "(Tidak dapat mengakses dokumen. Sistem akan mencoba menjawab tanpa konteks dokumen.)"

        # Step 3: Build messages
        messages = self._build_messages(
            sanitized_query,
            context_text,
            conversation_history or [],
            images,
        )

        tools = [
            {
                "type": "function",
                "function": {
                    "name": "web_search",
                    "description": "Cari informasi di internet menggunakan mesin pencari. Gunakan ini JIKA DAN HANYA JIKA informasi tidak ada di dokumen atau pengguna meminta data terbaru.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "Kata kunci pencarian internet."
                            }
                        },
                        "required": ["query"]
                    }
                }
            }
        ]

        # Step 4: Stream LLM response
        full_response = ""
        token_count = 0

        try:
            async with httpx.AsyncClient(timeout=300.0) as client:
                # Agent loop: Send without stream first to check if a tool is called
                response = await client.post(
                    f"{self.ollama_url}/api/chat",
                    json={
                        "model": self.llm_model,
                        "messages": messages,
                        "stream": False,
                        "tools": tools,
                        "options": {"temperature": settings.LLM_TEMPERATURE, "num_ctx": settings.LLM_CONTEXT_WINDOW}
                    }
                )
                response.raise_for_status()
                data = response.json()
                msg = data.get("message", {})
                
                # Check for tool usage
                tool_calls_list = msg.get("tool_calls", [])
                
                # Fallback for models that output tool JSON in content
                if not tool_calls_list and msg.get("content"):
                    parsed_tools = parse_embedded_tool_call(msg.get("content", ""))
                    if parsed_tools:
                        tool_calls_list = parsed_tools
                        msg["tool_calls"] = parsed_tools
                        msg["content"] = ""

                if tool_calls_list:
                    # Add assistent tool_call intent to messages
                    messages.append(msg)
                    
                    for tool_call in tool_calls_list:
                        func = tool_call.get("function", {})
                        if func.get("name") == "web_search":
                            args = func.get("arguments", {})
                            search_q = args.get("query", "")
                            
                            # Stream a status
                            yield {"type": "token", "content": f"\n\n*🔍 Mencari di internet: '{search_q}'...*\n\n"}
                            
                            from ollama import AsyncClient
                            try:
                                # Run native Ollama web search
                                client_kwargs = {"host": self.ollama_url}
                                if settings.OLLAMA_API_KEY:
                                    client_kwargs["headers"] = {"Authorization": f"Bearer {settings.OLLAMA_API_KEY}"}
                                    
                                client = AsyncClient(**client_kwargs)
                                response = await client.web_search(search_q, max_results=3)
                                
                                # Ollama new web_search returns WebSearchResponse object or list
                                if isinstance(response, list):
                                    search_str = "\n".join([f"- {r.get('title', 'Unknown')}:\n{(r.get('content', ''))[:1500]}" for r in response])
                                elif hasattr(response, 'results') and response.results:
                                    search_str = "\n".join([f"- {r.get('title', 'Unknown') if isinstance(r, dict) else r.title}:\n{(r.get('content', '') if isinstance(r, dict) else r.content)[:1500]}" for r in response.results])
                                elif getattr(response, 'body', None):
                                    search_str = str(response.body)[:3000]
                                else:
                                    search_str = str(response)[:3000]
                            except Exception as e:
                                search_str = f"Pencarian Error: {e}\n(Mungkin memerlukan OLLAMA_API_KEY di .env)"
                                
                            context_prompt = (
                                f"Gunakan informasi dari hasil pencarian internet berikut untuk '{search_q}':\n\n"
                                f"<search_results>\n{search_str}\n</search_results>\n\n"
                                "Kamu WAJIB menjawab berdasarkan informasi di atas, tulis dengan ringkas dan terstruktur."
                            )
                                
                            messages.append({
                                "role": "tool",
                                "content": context_prompt
                            })
                            
                    # Stream the final conclusion back
                    async with client.stream(
                        "POST",
                        f"{self.ollama_url}/api/chat",
                        json={
                            "model": self.llm_model,
                            "messages": messages,
                            "stream": True,
                            "options": {"temperature": settings.LLM_TEMPERATURE, "num_ctx": settings.LLM_CONTEXT_WINDOW}
                        }
                    ) as stream_resp:
                        stream_resp.raise_for_status()
                        async for line in stream_resp.aiter_lines():
                            if not line: continue
                            import json
                            chunk = json.loads(line)
                            token = chunk.get("message", {}).get("content", "")
                            if token:
                                full_response += token
                                token_count += 1
                                yield {"type": "token", "content": token}
                            if chunk.get("done", False): break
                else:
                    # No tool called, fake-stream the result for good UX
                    content = msg.get("content", "")
                    if content:
                        import asyncio
                        # Using space yields instead of single character for speed 
                        words = content.split(" ")
                        for i, word in enumerate(words):
                            suffix = " " if i < len(words) - 1 else ""
                            token = word + suffix
                            yield {"type": "token", "content": token}
                            full_response += token
                            token_count += 1
                            await asyncio.sleep(0.02)

        except Exception as e:
            logger.error("llm_streaming_failed", error=str(e))
            yield {"type": "token", "content": f"\n\n⚠️ Terjadi kesalahan saat memproses jawaban: {str(e)}"}

        # Step 5: Yield sources
        if sources:
            yield {"type": "sources", "sources": sources}

        # Step 6: Yield done
        elapsed_ms = int((time.time() - start_time) * 1000)
        yield {
            "type": "done",
            "tokens_used": token_count,
            "latency_ms": elapsed_ms,
            "full_response": full_response,
        }

    def _build_messages(
        self,
        query: str,
        context: str,
        history: list[dict],
        images: list[str] | None = None,
    ) -> list[dict]:
        """Assemble the chat messages with system instruction and context."""
        system_content = SYSTEM_PROMPT
        if context:
            system_content += f"\n\nKONTEKS DOKUMEN:\n{context}"
            
        messages = [{"role": "system", "content": system_content}]
        
        for msg in history[-settings.CONVERSATION_CONTEXT_WINDOW:]:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role in ["user", "assistant", "system", "tool"]:
                messages.append({"role": role, "content": content})
                
        user_msg = {"role": "user", "content": query}
        if images:
            user_msg["images"] = images
        messages.append(user_msg)
        return messages

    async def simple_chat(
        self,
        query: str,
        conversation_history: list[dict] | None = None,
        images: list[str] | None = None,
    ) -> AsyncGenerator[dict, None]:
        """Stream a simple chat response without RAG (direct LLM).

        Used when no collection is selected.
        """
        start_time = time.time()
        sanitized_query = sanitize_user_query(query)

        messages = [{"role": "system", "content": "Kamu adalah ExecMind, asisten AI yang cerdas dan membantu. Jawab dengan Bahasa Indonesia yang formal dan profesional."}]
        for msg in (conversation_history or [])[-settings.CONVERSATION_CONTEXT_WINDOW:]:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role in ["user", "assistant", "system", "tool"]:
                messages.append({"role": role, "content": content})
                
        user_msg = {"role": "user", "content": sanitized_query}
        if images:
            user_msg["images"] = images
        messages.append(user_msg)

        tools = [
            {
                "type": "function",
                "function": {
                    "name": "web_search",
                    "description": "Cari informasi di internet menggunakan mesin pencari. Gunakan ini JIKA DAN HANYA JIKA pengguna bertanya tentang informasi terkini/saat ini, kurs mata uang, atau data yang tidak Anda ketahui.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "Kata kunci pencarian internet."
                            }
                        },
                        "required": ["query"]
                    }
                }
            }
        ]

        full_response = ""
        token_count = 0

        try:
            async with httpx.AsyncClient(timeout=300.0) as client:
                # Agent loop: Send without stream first to check if a tool is called
                response = await client.post(
                    f"{self.ollama_url}/api/chat",
                    json={
                        "model": self.llm_model,
                        "messages": messages,
                        "stream": False,
                        "tools": tools,
                        "options": {"temperature": settings.LLM_TEMPERATURE, "num_ctx": settings.LLM_CONTEXT_WINDOW}
                    }
                )
                response.raise_for_status()
                data = response.json()
                msg = data.get("message", {})
                
                # Check for tool usage
                tool_calls_list = msg.get("tool_calls", [])
                
                # Fallback for models that output tool JSON in content
                if not tool_calls_list and msg.get("content"):
                    parsed_tools = parse_embedded_tool_call(msg.get("content", ""))
                    if parsed_tools:
                        tool_calls_list = parsed_tools
                        msg["tool_calls"] = parsed_tools
                        msg["content"] = ""

                if tool_calls_list:
                    # Add assistent tool_call intent to messages
                    messages.append(msg)
                    
                    for tool_call in tool_calls_list:
                        func = tool_call.get("function", {})
                        if func.get("name") == "web_search":
                            args = func.get("arguments", {})
                            search_q = args.get("query", "")
                            
                            # Stream a status
                            yield {"type": "token", "content": f"\n\n*🔍 Mencari di internet: '{search_q}'...*\n\n"}
                            
                            from ollama import AsyncClient
                            try:
                                # Run native Ollama web search
                                client_kwargs = {"host": self.ollama_url}
                                if settings.OLLAMA_API_KEY:
                                    client_kwargs["headers"] = {"Authorization": f"Bearer {settings.OLLAMA_API_KEY}"}
                                    
                                ollama_client = AsyncClient(**client_kwargs)
                                response = await ollama_client.web_search(search_q, max_results=3)
                                
                                # Ollama new web_search returns WebSearchResponse object or list
                                if isinstance(response, list):
                                    search_str = "\n".join([f"- {r.get('title', 'Unknown')}:\n{(r.get('content', ''))[:1500]}" for r in response])
                                elif hasattr(response, 'results') and response.results:
                                    search_str = "\n".join([f"- {r.get('title', 'Unknown') if isinstance(r, dict) else r.title}:\n{(r.get('content', '') if isinstance(r, dict) else r.content)[:1500]}" for r in response.results])
                                elif getattr(response, 'body', None):
                                    search_str = str(response.body)[:3000]
                                else:
                                    search_str = str(response)[:3000]
                            except Exception as e:
                                search_str = f"Pencarian Error: {e}\n(Mungkin memerlukan OLLAMA_API_KEY di .env)"
                                
                            context_prompt = (
                                f"Gunakan informasi dari hasil pencarian internet berikut untuk '{search_q}':\n\n"
                                f"<search_results>\n{search_str}\n</search_results>\n\n"
                                "Kamu WAJIB menjawab berdasarkan informasi di atas, tulis dengan ringkas dan terstruktur."
                            )
                                
                            messages.append({
                                "role": "tool",
                                "content": context_prompt
                            })
                            
                    # Stream the final conclusion back
                    async with client.stream(
                        "POST",
                        f"{self.ollama_url}/api/chat",
                        json={
                            "model": self.llm_model,
                            "messages": messages,
                            "stream": True,
                            "options": {"temperature": settings.LLM_TEMPERATURE, "num_ctx": settings.LLM_CONTEXT_WINDOW}
                        }
                    ) as stream_resp:
                        stream_resp.raise_for_status()
                        async for line in stream_resp.aiter_lines():
                            if not line: continue
                            import json
                            chunk = json.loads(line)
                            token = chunk.get("message", {}).get("content", "")
                            if token:
                                full_response += token
                                token_count += 1
                                yield {"type": "token", "content": token}
                            if chunk.get("done", False): break
                else:
                    # No tool called, fake-stream the result
                    content = msg.get("content", "")
                    if content:
                        import asyncio
                        words = content.split(" ")
                        for i, word in enumerate(words):
                            suffix = " " if i < len(words) - 1 else ""
                            token = word + suffix
                            yield {"type": "token", "content": token}
                            full_response += token
                            token_count += 1
                            await asyncio.sleep(0.02)

        except Exception as e:
            logger.error("llm_simple_chat_failed", error=str(e))
            yield {"type": "token", "content": f"\n\n⚠️ Terjadi kesalahan. Silakan coba lagi. Error: {e}"}

        elapsed_ms = int((time.time() - start_time) * 1000)
        yield {
            "type": "done",
            "tokens_used": token_count,
            "latency_ms": elapsed_ms,
            "full_response": full_response,
        }
