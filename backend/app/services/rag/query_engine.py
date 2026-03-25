"""ExecMind - Agent runtime: orchestrates RAG retrieval and agentic tool execution."""

import json
import re
import time
from typing import AsyncGenerator

import httpx

from app.core.config import settings
from app.services.rag.embedder import OllamaEmbedder
from app.tools.base import ToolContext
from app.tools.registry import ToolRegistry
from app.utils.logging import get_logger

logger = get_logger("query_engine")

# ── System Prompts ────────────────────────────────────────────────────────────

RAG_SYSTEM_PROMPT = """Kamu adalah ExecMind, asisten AI yang membantu pejabat eksekutif lembaga
untuk mencari informasi dari dokumen internal dan mengotomatisasi berbagai tugas di komputer server.

Kamu memiliki akses ke TOOLS berikut (daftar tergantung konfigurasi aktif):
{tool_names_section}

ATURAN KETAT:
1. Jika pengguna meminta sebuah aksi (buka file, jalankan perintah, simpan catatan, cari internet, dll) 
   yang dapat diselesaikan oleh tool di atas — GUNAKAN TOOLNYA, jangan bilang "saya tidak bisa".
2. Untuk pertanyaan informasi dari dokumen: jawab berdasarkan konteks dokumen yang diberikan.
3. Jika informasi tidak ditemukan di dokumen, nyatakan dengan jelas.
4. Selalu sebutkan nama dokumen sumber jika mengutip dari dokumen.
5. Gunakan Bahasa Indonesia yang formal dan profesional.
6. Setelah menggunakan tool, berikan ringkasan singkat hasilnya kepada pengguna."""

SIMPLE_SYSTEM_PROMPT = (
    "Kamu adalah ExecMind, asisten AI yang cerdas dan membantu dengan akses ke sistem komputer server melalui tools.\n"
    "Kamu memiliki akses ke TOOLS berikut (daftar tergantung konfigurasi aktif):\n"
    "{tool_names_section}\n\n"
    "Jika pengguna meminta sesuatu yang bisa diselesaikan oleh tool (membuka file, menjalankan perintah, "
    "menyimpan informasi, mencari internet, dll) — GUNAKAN TOOLNYA, jangan bilang tidak bisa.\n"
    "Jawab dengan Bahasa Indonesia yang formal dan profesional."
)

DANGEROUS_PATTERNS = [
    r"ignore previous instructions",
    r"disregard all",
    r"system:",
    r"<\|im_start\|>",
    r"<\|im_end\|>",
]

# ── Helpers ───────────────────────────────────────────────────────────────────


def sanitize_user_query(query: str) -> str:
    """Remove potential prompt injection patterns from user input."""
    sanitized = query
    for pattern in DANGEROUS_PATTERNS:
        sanitized = re.sub(pattern, "", sanitized, flags=re.IGNORECASE)
    return sanitized[:2000]


def parse_embedded_tool_call(content: str) -> list[dict]:
    """Fallback parser for models that output tool calls as JSON in content field."""
    if not content:
        return []
    try:
        stripped = content.strip()
        if stripped.startswith("{") and stripped.endswith("}"):
            data = json.loads(stripped)
            if isinstance(data, dict) and "name" in data and "arguments" in data:
                return [{"function": {"name": data["name"], "arguments": data["arguments"]}}]
    except Exception:
        pass
    return []


# ── Core Agent Loop ───────────────────────────────────────────────────────────


class RAGQueryEngine:
    """Orchestrates RAG queries and agentic tool execution.

    Uses Ollama for both embedding (nomic-embed-text) and LLM inference.
    Tools are provided by ToolRegistry loaded from config.yaml.
    """

    def __init__(
        self,
        qdrant_client=None,
        embedder: OllamaEmbedder | None = None,
        tool_registry: ToolRegistry | None = None,
    ):
        self.embedder = embedder or OllamaEmbedder()
        self.qdrant_client = qdrant_client
        self.ollama_url = settings.OLLAMA_URL.rstrip("/")
        self.llm_model = settings.LLM_MODEL
        self.top_k = settings.QDRANT_SIMILARITY_TOP_K
        self.tool_registry = tool_registry or ToolRegistry(settings.TOOLS_CONFIG_PATH)

    # ── Public Entry Points ───────────────────────────────────────────────────

    async def query_streaming(
        self,
        query: str,
        collection_name: str,
        collection_id: str,
        conversation_history: list[dict] | None = None,
        images: list[str] | None = None,
        tool_context: ToolContext | None = None,
    ) -> AsyncGenerator[dict, None]:
        """Stream a RAG-augmented response.

        Pipeline: sanitize → embed → Qdrant search → build messages → agent loop → stream.

        Yields dicts with type: 'token' | 'sources' | 'action' | 'done'.
        """
        start_time = time.time()
        sanitized = sanitize_user_query(query)

        # Step 1: Embed query
        query_embedding = await self.embedder.embed_text(sanitized)

        # Step 2: Search Qdrant via HTTP (qdrant-client 1.17+ removed .search())
        sources, context_text = await self._qdrant_search(
            query_embedding, collection_name, collection_id
        )

        # Step 3: Assemble messages (inject active tool names into system prompt)
        tool_names = [t.name for t in self.tool_registry.get_enabled_tools()]
        messages = self._build_messages(
            query=sanitized,
            context=context_text,
            history=conversation_history or [],
            images=images,
            system_prompt=RAG_SYSTEM_PROMPT,
            tool_names=tool_names,
        )

        # Step 4: Run agent loop
        full_response = ""
        token_count = 0
        any_tool_called = False

        async for chunk in self._run_agent_loop(messages, tool_context):
            chunk_type = chunk.get("type")
            if chunk_type == "token":
                full_response += chunk.get("content", "")
                token_count += 1
                yield chunk
            elif chunk_type == "action":
                any_tool_called = True
                yield chunk
            elif chunk_type == "tool_used":
                any_tool_called = True

        # Step 5: Yield sources only when no tool was used (sources become irrelevant after tool calls)
        if sources and not any_tool_called:
            yield {"type": "sources", "sources": sources}

        # Step 6: Done
        yield {
            "type": "done",
            "tokens_used": token_count,
            "latency_ms": int((time.time() - start_time) * 1000),
            "full_response": full_response,
        }

    async def simple_chat(
        self,
        query: str,
        conversation_history: list[dict] | None = None,
        images: list[str] | None = None,
        tool_context: ToolContext | None = None,
    ) -> AsyncGenerator[dict, None]:
        """Stream a direct LLM response without RAG (no collection selected).

        Yields dicts with type: 'token' | 'action' | 'done'.
        """
        start_time = time.time()
        sanitized = sanitize_user_query(query)

        tool_names = [t.name for t in self.tool_registry.get_enabled_tools()]
        messages = self._build_messages(
            query=sanitized,
            context="",
            history=conversation_history or [],
            images=images,
            system_prompt=SIMPLE_SYSTEM_PROMPT,
            tool_names=tool_names,
        )

        full_response = ""
        token_count = 0

        async for chunk in self._run_agent_loop(messages, tool_context):
            chunk_type = chunk.get("type")
            if chunk_type == "token":
                full_response += chunk.get("content", "")
                token_count += 1
                yield chunk
            elif chunk_type == "action":
                yield chunk

        yield {
            "type": "done",
            "tokens_used": token_count,
            "latency_ms": int((time.time() - start_time) * 1000),
            "full_response": full_response,
        }

    # ── Agent Loop ────────────────────────────────────────────────────────────

    async def _run_agent_loop(
        self,
        messages: list[dict],
        tool_context: ToolContext | None,
    ) -> AsyncGenerator[dict, None]:
        """Core agentic loop: call LLM → dispatch tool → repeat → stream final answer.

        Runs for up to max_tool_iterations turns. Each turn either:
        - Dispatches one or more tool calls, appends results, and retries.
        - Produces a final text answer, which is streamed token by token.

        Yields:
            {'type': 'token', 'content': str}   — streaming response tokens
            {'type': 'action', ...}              — SSE action sent to frontend
            {'type': 'tool_used'}                — signals at least one tool ran
        """
        tools_schema = self.tool_registry.get_ollama_tools_schema()
        max_turns = self.tool_registry.max_tool_iterations
        req_ctx = min(settings.LLM_CONTEXT_WINDOW, 131072)

        try:
            async with httpx.AsyncClient(timeout=600.0) as client:
                for turn in range(max_turns):
                    # Non-streaming call to check for tool use
                    response = await client.post(
                        f"{self.ollama_url}/api/chat",
                        json={
                            "model": self.llm_model,
                            "messages": messages,
                            "stream": False,
                            "tools": tools_schema,
                            "options": {
                                "temperature": settings.LLM_TEMPERATURE,
                                "num_ctx": req_ctx,
                            },
                        },
                    )
                    response.raise_for_status()
                    data = response.json()
                    msg = data.get("message", {})

                    # Detect tool calls (native or embedded JSON fallback)
                    tool_calls = msg.get("tool_calls", [])
                    if not tool_calls and msg.get("content"):
                        embedded = parse_embedded_tool_call(msg["content"])
                        if embedded:
                            tool_calls = embedded
                            msg["tool_calls"] = embedded
                            msg["content"] = ""

                    if tool_calls:
                        messages.append(msg)
                        async for event in self._dispatch_tools(tool_calls, tool_context, messages):
                            yield event
                        yield {"type": "tool_used"}
                        continue  # Let LLM decide next action based on tool results

                    # No tools in this turn → stream the final text answer
                    # Still send tools so model can call one if final analysis requires it
                    async with client.stream(
                        "POST",
                        f"{self.ollama_url}/api/chat",
                        json={
                            "model": self.llm_model,
                            "messages": messages,
                            "stream": True,
                            "tools": tools_schema,
                            "options": {
                                "temperature": settings.LLM_TEMPERATURE,
                                "num_ctx": req_ctx,
                            },
                        },
                    ) as stream_resp:
                        stream_resp.raise_for_status()
                        async for line in stream_resp.aiter_lines():
                            if not line:
                                continue
                            chunk = json.loads(line)
                            token = chunk.get("message", {}).get("content", "")
                            if token:
                                yield {"type": "token", "content": token}
                            if chunk.get("done", False):
                                break
                    break  # Final answer delivered, exit loop

        except Exception as e:
            logger.error("agent_loop_failed", error=str(e))
            yield {"type": "token", "content": f"\n\n⚠️ Terjadi kesalahan: {e}"}

    async def _dispatch_tools(
        self,
        tool_calls: list[dict],
        tool_context: ToolContext | None,
        messages: list[dict],
    ) -> AsyncGenerator[dict, None]:
        """Execute each tool call and append results to the message history.

        Yields action events to be forwarded to the frontend via SSE.
        """
        for tool_call in tool_calls:
            func = tool_call.get("function", {})
            func_name = func.get("name", "")
            arguments = func.get("arguments", {})

            tool = self.tool_registry.get_tool(func_name)
            if tool is None:
                logger.warning("unknown_tool_called", tool=func_name)
                messages.append({
                    "role": "tool",
                    "content": f"Tool '{func_name}' tidak tersedia atau tidak diaktifkan.",
                    "tool_call_id": tool_call.get("id"),
                })
                continue

            # Emit status token immediately so user sees progress
            status_label = self._tool_status_label(func_name, arguments)
            yield {"type": "token", "content": f"\n\n{status_label}\n\n"}

            # Execute the tool
            if tool_context:
                result = await tool.execute(arguments, tool_context)
            else:
                # No DB context available — create a minimal stub context
                from uuid import UUID
                stub_ctx = ToolContext(
                    user_id=UUID(int=0),
                    session_id=UUID(int=0),
                    db_session=None,
                )
                result = await tool.execute(arguments, stub_ctx)

            # If the tool produced a frontend action, yield it
            if result.action:
                yield {"type": "action", **result.action}

            # Append tool result to message history for LLM
            messages.append({
                "role": "tool",
                "content": result.content,
                "tool_call_id": tool_call.get("id"),
            })

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _tool_status_label(self, tool_name: str, arguments: dict) -> str:
        """Return a user-friendly Markdown status line for a tool being invoked."""
        labels = {
            "open_browser": f"🌐 Membuka {arguments.get('url', '')} di tab baru...",
            "web_search": f"🔍 Mencari di internet: *'{arguments.get('query', '')}'*...",
            "play_music": "🎵 Menjalankan otomatisasi YouTube Music...",
            "shell_exec": f"⚡ Menjalankan perintah: `{arguments.get('command', '')}`...",
            "file_read": f"📄 Membaca file: `{arguments.get('path', '')}`...",
            "file_write": f"💾 Menulis file: `{arguments.get('path', '')}`...",
            "http_request": f"🌐 HTTP {arguments.get('method', 'GET')} ke {arguments.get('url', '')}...",
            "memory_write": f"🧠 Menyimpan ke memori: *{arguments.get('key', '')}*...",
            "memory_read": f"🧠 Membaca dari memori: *{arguments.get('key', '')}*...",
        }
        return f"*{labels.get(tool_name, f'🔧 Menjalankan tool: {tool_name}...')}*"

    async def _qdrant_search(
        self, embedding: list[float], collection_name: str, collection_id: str
    ) -> tuple[list[dict], str]:
        """Search Qdrant via HTTP and return sources list and formatted context text."""
        sources: list[dict] = []
        context_text = ""

        try:
            url = f"{settings.QDRANT_URL.rstrip('/')}/collections/{collection_name}/points/search"
            payload = {
                "vector": embedding,
                "limit": self.top_k,
                "filter": {
                    "must": [{"key": "collection_id", "match": {"value": collection_id}}]
                },
                "with_payload": True,
            }

            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(url, json=payload)
                resp.raise_for_status()
                data = resp.json()

            for hit in data.get("result", []):
                payload_data = hit.get("payload", {})
                score = hit.get("score", 0.0)
                context_text += (
                    f"\n---\nDokumen: {payload_data.get('doc_title', 'Unknown')}"
                    f" (Halaman {payload_data.get('page_number', '?')})\n"
                    f"{payload_data.get('text', '')}"
                )
                sources.append({
                    "doc_id": payload_data.get("document_id", ""),
                    "doc_title": payload_data.get("doc_title", "Unknown"),
                    "page": payload_data.get("page_number", 0),
                    "score": round(score, 4),
                    "text_preview": payload_data.get("text", "")[:200],
                })

        except Exception as e:
            logger.error("qdrant_search_failed", error=str(e))
            context_text = "(Tidak dapat mengakses dokumen. Sistem akan mencoba menjawab tanpa konteks dokumen.)"

        return sources, context_text

    def _build_messages(
        self,
        query: str,
        context: str,
        history: list[dict],
        images: list[str] | None,
        system_prompt: str,
        tool_names: list[str] | None = None,
    ) -> list[dict]:
        """Assemble the messages list with system prompt, document context, history, and query.

        Dynamically injects the list of currently enabled tool names into the system prompt
        so the model knows what tools are available and is more likely to call them.
        """
        # Build tool names section for the system prompt
        if tool_names:
            tool_lines = "\n".join(f"  - {name}" for name in tool_names)
            tool_names_section = tool_lines
        else:
            tool_names_section = "  (tidak ada tool yang aktif)"

        system_content = system_prompt.format(tool_names_section=tool_names_section)
        if context:
            system_content += f"\n\nKONTEKS DOKUMEN:\n{context}"

        messages: list[dict] = [{"role": "system", "content": system_content}]

        for msg in history[-settings.CONVERSATION_CONTEXT_WINDOW:]:
            role = msg.get("role", "user")
            if role in ("user", "assistant", "system", "tool"):
                messages.append({"role": role, "content": msg.get("content", "")})

        user_msg: dict = {"role": "user", "content": query}
        if images:
            user_msg["images"] = images
        messages.append(user_msg)
        return messages
