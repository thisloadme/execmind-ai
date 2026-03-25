"""ExecMind - Tool: shell_exec — runs sandboxed shell commands in a subprocess."""

import asyncio
import shlex
from app.tools.base import BaseTool, ToolContext, ToolResult
from app.utils.logging import get_logger

logger = get_logger("tool.shell_exec")

MAX_OUTPUT_CHARS = 4000


class ShellExecTool(BaseTool):
    """Executes allowed shell commands in a sandboxed subprocess.

    Security measures:
    - Only commands in the configured allowlist can be executed.
    - Uses asyncio.create_subprocess_exec (never shell=True) to prevent injection.
    - Output is capped to avoid flooding the LLM context window.
    - Execution is time-limited by timeout_seconds.
    """

    def __init__(self, allowed_commands: list[str], timeout_seconds: int = 30):
        self._allowed_commands = set(allowed_commands)
        self._timeout = timeout_seconds

    @property
    def name(self) -> str:
        return "shell_exec"

    @property
    def description(self) -> str:
        return (
            "Jalankan perintah shell di server untuk mendapatkan informasi sistem atau "
            "mengotomatisasi tugas. Hanya perintah yang diizinkan yang dapat dieksekusi."
        )

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": (
                        "Perintah shell lengkap beserta argumennya "
                        "(contoh: 'ls -la /tmp' atau 'df -h')."
                    ),
                }
            },
            "required": ["command"],
        }

    async def execute(self, arguments: dict, context: ToolContext) -> ToolResult:
        raw_command = arguments.get("command", "").strip()
        if not raw_command:
            return ToolResult(success=False, content="Perintah tidak diberikan.", error="missing_command")

        try:
            parts = shlex.split(raw_command)
        except ValueError as e:
            return ToolResult(success=False, content=f"Format perintah tidak valid: {e}", error=str(e))

        base_command = parts[0] if parts else ""
        if base_command not in self._allowed_commands:
            logger.warning(
                "shell_exec_blocked",
                command=base_command,
                user_id=str(context.user_id),
            )
            allowed_list = ", ".join(sorted(self._allowed_commands))
            return ToolResult(
                success=False,
                content=(
                    f"Perintah '{base_command}' tidak diizinkan. "
                    f"Perintah yang tersedia: {allowed_list}."
                ),
                error="command_not_allowed",
            )

        logger.info(
            "shell_exec_running",
            command=raw_command,
            user_id=str(context.user_id),
            session_id=str(context.session_id),
        )

        try:
            proc = await asyncio.create_subprocess_exec(
                *parts,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                proc.communicate(), timeout=self._timeout
            )
        except asyncio.TimeoutError:
            return ToolResult(
                success=False,
                content=f"Perintah '{raw_command}' melebihi batas waktu {self._timeout} detik.",
                error="timeout",
            )
        except Exception as e:
            logger.error("shell_exec_failed", command=raw_command, error=str(e))
            return ToolResult(success=False, content=f"Gagal menjalankan perintah: {e}", error=str(e))

        stdout = stdout_bytes.decode("utf-8", errors="replace").strip()
        stderr = stderr_bytes.decode("utf-8", errors="replace").strip()
        returncode = proc.returncode or 0

        output_parts = []
        if stdout:
            output_parts.append(f"STDOUT:\n{stdout[:MAX_OUTPUT_CHARS]}")
        if stderr:
            output_parts.append(f"STDERR:\n{stderr[:MAX_OUTPUT_CHARS // 2]}")

        combined = "\n".join(output_parts) or "(tidak ada output)"

        content = (
            f"Hasil eksekusi `{raw_command}` (exit code: {returncode}):\n\n"
            f"```\n{combined}\n```"
        )

        return ToolResult(
            success=returncode == 0,
            content=content,
            action={"action_name": "shell_exec", "payload": {"command": raw_command}},
        )
