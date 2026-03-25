"""ExecMind - Tool: web_search — searches the internet using Ollama's web search API."""

from app.tools.base import BaseTool, ToolContext, ToolResult
from app.core.config import settings
from app.utils.logging import get_logger

logger = get_logger("tool.web_search")

MAX_RESULT_CONTENT_CHARS = 1500
MAX_RESULTS = 3


class WebSearchTool(BaseTool):
    """Searches the internet and injects results into LLM context.

    Uses Ollama's native web_search method when available.
    Falls back to a formatted error message if search fails.
    """

    @property
    def name(self) -> str:
        return "web_search"

    @property
    def description(self) -> str:
        return (
            "Cari informasi di internet menggunakan mesin pencari. "
            "Gunakan HANYA JIKA informasi tidak tersedia di dokumen internal "
            "atau pengguna secara eksplisit meminta data terkini / berita terbaru."
        )

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Kata kunci pencarian internet yang spesifik dan relevan.",
                }
            },
            "required": ["query"],
        }

    async def execute(self, arguments: dict, context: ToolContext) -> ToolResult:
        query = arguments.get("query", "").strip()
        if not query:
            return ToolResult(success=False, content="Query pencarian tidak diberikan.", error="missing_query")

        try:
            from ollama import AsyncClient

            client_kwargs: dict = {"host": settings.OLLAMA_URL}
            if settings.OLLAMA_API_KEY:
                client_kwargs["headers"] = {"Authorization": f"Bearer {settings.OLLAMA_API_KEY}"}

            ollama_client = AsyncClient(**client_kwargs)
            response = await ollama_client.web_search(query, max_results=MAX_RESULTS)

            search_str = self._parse_response(response)

            content = (
                f"Gunakan informasi dari hasil pencarian internet berikut untuk '{query}':\n\n"
                f"<search_results>\n{search_str}\n</search_results>\n\n"
                "Jawab berdasarkan informasi di atas, tulis dengan ringkas dan terstruktur."
            )

            logger.info("web_search_success", query=query, user_id=str(context.user_id))
            return ToolResult(
                success=True,
                content=content,
                action={"action_name": "web_search", "payload": {"query": query}},
            )

        except Exception as e:
            error_msg = str(e)
            logger.error("web_search_failed", query=query, error=error_msg)
            fallback = (
                f"Pencarian untuk '{query}' gagal: {error_msg}. "
                "Jawab berdasarkan pengetahuan yang ada atau minta pengguna mencari secara manual."
            )
            return ToolResult(success=False, content=fallback, error=error_msg)

    def _parse_response(self, response) -> str:
        """Normalize different Ollama web_search response shapes to a string."""
        if isinstance(response, list):
            return "\n".join(
                f"- {r.get('title', 'Unknown')}:\n{r.get('content', '')[:MAX_RESULT_CONTENT_CHARS]}"
                for r in response
            )
        if hasattr(response, "results") and response.results:
            return "\n".join(
                f"- {r.title if hasattr(r, 'title') else r.get('title', 'Unknown')}:\n"
                f"{(r.content if hasattr(r, 'content') else r.get('content', ''))[:MAX_RESULT_CONTENT_CHARS]}"
                for r in response.results
            )
        if getattr(response, "body", None):
            return str(response.body)[:3000]
        return str(response)[:3000]
