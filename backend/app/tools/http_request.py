"""ExecMind - Tool: http_request — makes outbound HTTP GET/POST requests."""

from urllib.parse import urlparse
import httpx

from app.tools.base import BaseTool, ToolContext, ToolResult
from app.utils.logging import get_logger

logger = get_logger("tool.http_request")

MAX_RESPONSE_CHARS = 8000


class HttpRequestTool(BaseTool):
    """Makes outbound HTTP requests and injects response content into LLM context.

    Optionally restricted to a configured list of allowed domains.
    Response body is capped to avoid flooding the context window.
    """

    def __init__(self, allowed_domains: list[str], timeout_seconds: int = 15):
        self._allowed_domains = [d.lower() for d in allowed_domains]
        self._timeout = timeout_seconds

    @property
    def name(self) -> str:
        return "http_request"

    @property
    def description(self) -> str:
        return (
            "Lakukan permintaan HTTP GET atau POST ke URL tertentu untuk mengambil data "
            "dari API internal atau layanan web. Gunakan untuk mengambil data real-time "
            "dari endpoint yang dikenal."
        )

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "URL endpoint yang akan diakses.",
                },
                "method": {
                    "type": "string",
                    "enum": ["GET", "POST"],
                    "description": "HTTP method (default: GET).",
                },
                "body": {
                    "type": "object",
                    "description": "JSON body untuk POST request (opsional).",
                },
                "headers": {
                    "type": "object",
                    "description": "HTTP headers tambahan (opsional).",
                },
            },
            "required": ["url"],
        }

    def _is_domain_allowed(self, url: str) -> bool:
        """Return True if domain allowlist is empty (all allowed) or URL matches."""
        if not self._allowed_domains:
            return True
        parsed = urlparse(url)
        domain = (parsed.hostname or "").lower()
        return any(domain == d or domain.endswith(f".{d}") for d in self._allowed_domains)

    async def execute(self, arguments: dict, context: ToolContext) -> ToolResult:
        url = arguments.get("url", "").strip()
        method = arguments.get("method", "GET").upper()
        body = arguments.get("body")
        headers = arguments.get("headers", {})

        if not url:
            return ToolResult(success=False, content="URL tidak diberikan.", error="missing_url")

        if not url.startswith(("http://", "https://")):
            url = f"https://{url}"

        if not self._is_domain_allowed(url):
            logger.warning("http_request_blocked", url=url, user_id=str(context.user_id))
            return ToolResult(
                success=False,
                content=f"Domain '{urlparse(url).hostname}' tidak ada dalam daftar yang diizinkan.",
                error="domain_not_allowed",
            )

        logger.info("http_request_sending", url=url, method=method, user_id=str(context.user_id))

        try:
            async with httpx.AsyncClient(timeout=self._timeout, follow_redirects=True) as client:
                if method == "POST":
                    response = await client.post(url, json=body, headers=headers)
                else:
                    response = await client.get(url, headers=headers)

            status = response.status_code
            content_type = response.headers.get("content-type", "")

            try:
                response_text = response.text[:MAX_RESPONSE_CHARS]
            except Exception:
                response_text = "(binary response — tidak dapat ditampilkan)"

            content = (
                f"HTTP {method} {url}\n"
                f"Status: {status}\n"
                f"Content-Type: {content_type}\n\n"
                f"Response:\n```\n{response_text}\n```"
            )

            return ToolResult(
                success=200 <= status < 300,
                content=content,
                action={"action_name": "http_request", "payload": {"url": url, "method": method, "status": status}},
            )

        except httpx.TimeoutException:
            return ToolResult(
                success=False,
                content=f"Request ke '{url}' timeout setelah {self._timeout} detik.",
                error="timeout",
            )
        except Exception as e:
            logger.error("http_request_failed", url=url, error=str(e))
            return ToolResult(success=False, content=f"Request gagal: {e}", error=str(e))
