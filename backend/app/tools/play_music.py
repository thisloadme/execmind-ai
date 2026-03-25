"""ExecMind - Tool: play_music — opens YouTube Music and plays the last track."""

from app.tools.base import BaseTool, ToolContext, ToolResult
from app.utils.logging import get_logger

logger = get_logger("tool.play_music")


class PlayMusicTool(BaseTool):
    """Triggers browser automation via Playwright to open and play YouTube Music.

    Runs on the server machine (where the backend is deployed).
    """

    @property
    def name(self) -> str:
        return "play_music"

    @property
    def description(self) -> str:
        return (
            "Buka YouTube Music di browser server dan putar lagu terakhir yang diputar. "
            "Gunakan HANYA JIKA pengguna secara eksplisit meminta memutar musik, lagu, "
            "atau membuka YouTube Music."
        )

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {},
            "required": [],
        }

    async def execute(self, arguments: dict, context: ToolContext) -> ToolResult:
        try:
            from app.services.browser_service import BrowserService

            svc = BrowserService()
            result = await svc.play_youtube_music()

            success = result.get("status") in ("success", "partial_success")
            logger.info("play_music_executed", status=result.get("status"), user_id=str(context.user_id))

            return ToolResult(
                success=success,
                content=f"Status otomatisasi musik: {result.get('message', 'Selesai')}",
                action={"action_name": "play_music", "payload": {}},
            )
        except Exception as e:
            logger.error("play_music_failed", error=str(e))
            return ToolResult(
                success=False,
                content=f"Gagal menjalankan otomatisasi musik: {str(e)}",
                error=str(e),
            )
