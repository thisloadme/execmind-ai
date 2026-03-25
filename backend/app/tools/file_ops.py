"""ExecMind - Tool: file_ops — safe file read and write within allowed paths."""

import os
from pathlib import Path
from app.tools.base import BaseTool, ToolContext, ToolResult
from app.utils.logging import get_logger

logger = get_logger("tool.file_ops")

MAX_READ_CHARS = 8000


def _is_path_allowed(target_path: str, allowed_paths: list[str]) -> bool:
    """Check that the resolved absolute path is within one of the allowed root paths.

    Uses realpath to prevent directory traversal attacks (e.g. ../../etc/passwd).
    """
    resolved = os.path.realpath(target_path)
    return any(resolved.startswith(os.path.realpath(p)) for p in allowed_paths)


class FileReadTool(BaseTool):
    """Reads a file's contents from within allowed directory paths.

    Prevents path traversal by resolving symlinks before checking the allowlist.
    """

    def __init__(self, allowed_paths: list[str], max_file_size_mb: int = 10):
        self._allowed_paths = allowed_paths
        self._max_bytes = max_file_size_mb * 1024 * 1024

    @property
    def name(self) -> str:
        return "file_read"

    @property
    def description(self) -> str:
        return (
            "Baca isi file teks dari direktori yang diizinkan di server. "
            "Gunakan untuk membaca laporan, log, atau file konfigurasi yang relevan."
        )

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path absolut ke file yang ingin dibaca (contoh: /data/reports/laporan.txt).",
                }
            },
            "required": ["path"],
        }

    async def execute(self, arguments: dict, context: ToolContext) -> ToolResult:
        file_path = arguments.get("path", "").strip()
        if not file_path:
            return ToolResult(success=False, content="Path file tidak diberikan.", error="missing_path")

        if not _is_path_allowed(file_path, self._allowed_paths):
            logger.warning("file_read_blocked", path=file_path, user_id=str(context.user_id))
            return ToolResult(
                success=False,
                content=f"Akses ke '{file_path}' tidak diizinkan.",
                error="path_not_allowed",
            )

        resolved = os.path.realpath(file_path)
        if not os.path.isfile(resolved):
            return ToolResult(success=False, content=f"File '{file_path}' tidak ditemukan.", error="not_found")

        file_size = os.path.getsize(resolved)
        if file_size > self._max_bytes:
            max_mb = self._max_bytes / (1024 * 1024)
            return ToolResult(
                success=False,
                content=f"File terlalu besar ({file_size / (1024*1024):.1f}MB). Batas: {max_mb:.0f}MB.",
                error="file_too_large",
            )

        try:
            text = Path(resolved).read_text(encoding="utf-8", errors="replace")
            truncated = text[:MAX_READ_CHARS]
            suffix = f"\n\n... (terpotong, {len(text) - MAX_READ_CHARS} karakter tersisa)" if len(text) > MAX_READ_CHARS else ""
            content = f"Isi file `{file_path}`:\n\n```\n{truncated}{suffix}\n```"

            logger.info("file_read_success", path=file_path, user_id=str(context.user_id))
            return ToolResult(
                success=True,
                content=content,
                action={"action_name": "file_read", "payload": {"path": file_path}},
            )
        except Exception as e:
            logger.error("file_read_failed", path=file_path, error=str(e))
            return ToolResult(success=False, content=f"Gagal membaca file: {e}", error=str(e))


class FileWriteTool(BaseTool):
    """Writes content to a file within allowed directory paths."""

    def __init__(self, allowed_paths: list[str]):
        self._allowed_paths = allowed_paths

    @property
    def name(self) -> str:
        return "file_write"

    @property
    def description(self) -> str:
        return (
            "Tulis konten ke file di direktori yang diizinkan di server. "
            "Gunakan untuk menyimpan hasil analisis, laporan, atau data sementara."
        )

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path absolut tujuan penulisan file (contoh: /tmp/laporan.txt).",
                },
                "content": {
                    "type": "string",
                    "description": "Konten teks yang akan ditulis ke file.",
                },
            },
            "required": ["path", "content"],
        }

    async def execute(self, arguments: dict, context: ToolContext) -> ToolResult:
        file_path = arguments.get("path", "").strip()
        file_content = arguments.get("content", "")

        if not file_path:
            return ToolResult(success=False, content="Path file tidak diberikan.", error="missing_path")

        if not _is_path_allowed(file_path, self._allowed_paths):
            logger.warning("file_write_blocked", path=file_path, user_id=str(context.user_id))
            return ToolResult(
                success=False,
                content=f"Penulisan ke '{file_path}' tidak diizinkan.",
                error="path_not_allowed",
            )

        try:
            resolved = os.path.realpath(file_path)
            os.makedirs(os.path.dirname(resolved), exist_ok=True)
            Path(resolved).write_text(file_content, encoding="utf-8")

            byte_count = len(file_content.encode("utf-8"))
            logger.info("file_write_success", path=file_path, bytes=byte_count, user_id=str(context.user_id))
            return ToolResult(
                success=True,
                content=f"File `{file_path}` berhasil ditulis ({byte_count} bytes).",
                action={"action_name": "file_write", "payload": {"path": file_path}},
            )
        except Exception as e:
            logger.error("file_write_failed", path=file_path, error=str(e))
            return ToolResult(success=False, content=f"Gagal menulis file: {e}", error=str(e))
