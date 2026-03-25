"""ExecMind - Tool: open_browser — signals the frontend to open a URL in a new tab."""

from app.tools.base import BaseTool, ToolContext, ToolResult


class OpenBrowserTool(BaseTool):
    """Sends an SSE action to the chat frontend to open a URL in a new browser tab.

    The actual tab opening is handled client-side to avoid popup blockers.
    """

    @property
    def name(self) -> str:
        return "open_browser"

    @property
    def description(self) -> str:
        return (
            "Buka tab browser baru di komputer pengguna untuk mengakses URL tertentu. "
            "Gunakan HANYA JIKA pengguna secara eksplisit meminta membuka browser, "
            "mengunjungi situs web, mencari video di YouTube, atau mengakses URL tertentu."
        )

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": (
                        "URL lengkap yang akan dibuka "
                        "(contoh: https://www.youtube.com/results?search_query=kucing)."
                    ),
                }
            },
            "required": ["url"],
        }

    async def execute(self, arguments: dict, context: ToolContext) -> ToolResult:
        url = arguments.get("url", "").strip()
        if not url:
            return ToolResult(
                success=False,
                content="URL tidak diberikan.",
                error="missing_url",
            )

        if not url.startswith(("http://", "https://")):
            url = f"https://{url}"

        return ToolResult(
            success=True,
            content=f"Berhasil memerintahkan client membuka URL: {url}. Beritahukan singkat bahwa halaman sudah dibuka.",
            action={"action_name": "open_browser", "payload": {"url": url}},
        )
