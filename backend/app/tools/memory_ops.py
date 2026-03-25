"""ExecMind - Tool: memory_ops — persistent key-value fact storage per user."""

from sqlalchemy import text
from app.tools.base import BaseTool, ToolContext, ToolResult
from app.utils.logging import get_logger

logger = get_logger("tool.memory_ops")


class MemoryWriteTool(BaseTool):
    """Stores a key-value fact for the current user in agent_memory table."""

    @property
    def name(self) -> str:
        return "memory_write"

    @property
    def description(self) -> str:
        return (
            "Simpan fakta atau informasi penting ke memori jangka panjang pengguna. "
            "Gunakan ketika pengguna meminta untuk 'ingat', 'catat', atau 'simpan' suatu informasi "
            "agar dapat diakses kembali di percakapan mendatang."
        )

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "key": {
                    "type": "string",
                    "description": "Nama kunci/label untuk fakta yang disimpan (contoh: 'password_wifi', 'nama_direktur').",
                },
                "value": {
                    "type": "string",
                    "description": "Nilai/konten fakta yang akan disimpan.",
                },
            },
            "required": ["key", "value"],
        }

    async def execute(self, arguments: dict, context: ToolContext) -> ToolResult:
        key = arguments.get("key", "").strip()
        value = arguments.get("value", "").strip()

        if not key or not value:
            return ToolResult(success=False, content="Key dan value keduanya wajib diisi.", error="missing_args")

        try:
            await context.db_session.execute(
                text("""
                    INSERT INTO agent_memory (user_id, key, value)
                    VALUES (:user_id, :key, :value)
                    ON CONFLICT (user_id, key) DO UPDATE SET value = EXCLUDED.value, updated_at = NOW()
                """),
                {"user_id": str(context.user_id), "key": key, "value": value},
            )
            await context.db_session.commit()
            logger.info("memory_write_success", key=key, user_id=str(context.user_id))
            return ToolResult(
                success=True,
                content=f"Informasi '{key}' berhasil disimpan ke memori.",
                action={"action_name": "memory_write", "payload": {"key": key}},
            )
        except Exception as e:
            logger.error("memory_write_failed", key=key, error=str(e))
            return ToolResult(success=False, content=f"Gagal menyimpan memori: {e}", error=str(e))


class MemoryReadTool(BaseTool):
    """Retrieves stored facts for the current user from agent_memory table."""

    @property
    def name(self) -> str:
        return "memory_read"

    @property
    def description(self) -> str:
        return (
            "Ambil fakta atau informasi yang sebelumnya disimpan ke memori pengguna. "
            "Gunakan ketika pengguna bertanya tentang sesuatu yang pernah diminta untuk diingat."
        )

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "key": {
                    "type": "string",
                    "description": "Nama kunci yang ingin diambil. Gunakan '*' untuk mengambil semua memori.",
                }
            },
            "required": ["key"],
        }

    async def execute(self, arguments: dict, context: ToolContext) -> ToolResult:
        key = arguments.get("key", "").strip()
        if not key:
            return ToolResult(success=False, content="Key tidak diberikan.", error="missing_key")

        try:
            if key == "*":
                result = await context.db_session.execute(
                    text("SELECT key, value FROM agent_memory WHERE user_id = :uid ORDER BY updated_at DESC"),
                    {"uid": str(context.user_id)},
                )
                rows = result.fetchall()
                if not rows:
                    return ToolResult(success=True, content="Belum ada memori yang tersimpan untuk pengguna ini.")
                facts = "\n".join(f"- **{r[0]}**: {r[1]}" for r in rows)
                return ToolResult(success=True, content=f"Semua memori tersimpan:\n{facts}")
            else:
                result = await context.db_session.execute(
                    text("SELECT value FROM agent_memory WHERE user_id = :uid AND key = :key"),
                    {"uid": str(context.user_id), "key": key},
                )
                row = result.fetchone()
                if not row:
                    return ToolResult(
                        success=True,
                        content=f"Tidak ditemukan memori dengan kunci '{key}'. Coba referensikan kunci lain atau gunakan '*' untuk melihat semua.",
                    )
                return ToolResult(
                    success=True,
                    content=f"Nilai untuk '{key}': {row[0]}",
                    action={"action_name": "memory_read", "payload": {"key": key}},
                )
        except Exception as e:
            logger.error("memory_read_failed", key=key, error=str(e))
            return ToolResult(success=False, content=f"Gagal membaca memori: {e}", error=str(e))
