"""ExecMind - Tool registry: loads and manages all registered tools."""

import yaml
from pathlib import Path
from typing import TYPE_CHECKING

from app.tools.base import BaseTool
from app.utils.logging import get_logger

if TYPE_CHECKING:
    pass

logger = get_logger("tool_registry")

_DEFAULT_CONFIG: dict = {
    "tools": {
        "open_browser": {"enabled": True},
        "web_search": {"enabled": True},
        "play_music": {"enabled": True},
        "shell_exec": {
            "enabled": False,  # Disabled by default for security
            "sandbox": True,
            "allowed_commands": ["ls", "cat", "grep", "head", "tail", "wc", "find", "df", "free", "uptime"],
            "timeout_seconds": 30,
        },
        "file_read": {
            "enabled": False,
            "allowed_paths": ["/tmp"],
            "max_file_size_mb": 10,
        },
        "file_write": {
            "enabled": False,
            "allowed_paths": ["/tmp"],
        },
        "http_request": {
            "enabled": True,
            "allowed_domains": [],  # Empty = all allowed; list domains to restrict
            "timeout_seconds": 15,
        },
        "memory_read": {"enabled": True},
        "memory_write": {"enabled": True},
    },
    "agent": {
        "max_tool_iterations": 5,
    },
}


class ToolRegistry:
    """Central registry for all agentic tools.

    Loads tool configuration from config.yaml and instantiates enabled tools.
    The registry is passed to the agent runtime so tools can be swapped
    without touching the agent loop logic.
    """

    def __init__(self, config_path: str | None = None):
        self._tools: dict[str, BaseTool] = {}
        self._config: dict = {}
        self._agent_config: dict = {}
        self._load_config(config_path)
        self._register_tools()

    def _load_config(self, config_path: str | None) -> None:
        """Load tool configuration from YAML file, falling back to defaults."""
        resolved = _DEFAULT_CONFIG.copy()

        if config_path:
            path = Path(config_path)
            if path.exists():
                try:
                    with path.open() as f:
                        file_cfg = yaml.safe_load(f) or {}
                    # Deep-merge file config over defaults
                    for section in ("tools", "agent"):
                        if section in file_cfg:
                            resolved[section].update(file_cfg[section])
                    logger.info("tool_config_loaded", path=str(path))
                except Exception as e:
                    logger.warning("tool_config_load_failed", error=str(e))

        self._config = resolved.get("tools", {})
        self._agent_config = resolved.get("agent", {})

    def _tool_cfg(self, name: str) -> dict:
        """Return configuration dict for a specific tool."""
        return self._config.get(name, {})

    def _is_enabled(self, name: str) -> bool:
        return self._tool_cfg(name).get("enabled", False)

    def _register_tools(self) -> None:
        """Instantiate and register all enabled tools."""
        # Import here to avoid circular imports at module load time
        from app.tools.open_browser import OpenBrowserTool
        from app.tools.web_search import WebSearchTool
        from app.tools.play_music import PlayMusicTool
        from app.tools.shell_exec import ShellExecTool
        from app.tools.file_ops import FileReadTool, FileWriteTool
        from app.tools.http_request import HttpRequestTool
        from app.tools.memory_ops import MemoryReadTool, MemoryWriteTool

        candidate_tools: list[BaseTool] = [
            OpenBrowserTool(),
            WebSearchTool(),
            PlayMusicTool(),
            ShellExecTool(
                allowed_commands=self._tool_cfg("shell_exec").get(
                    "allowed_commands", []
                ),
                timeout_seconds=self._tool_cfg("shell_exec").get("timeout_seconds", 30),
            ),
            FileReadTool(
                allowed_paths=self._tool_cfg("file_read").get("allowed_paths", ["/tmp"]),
                max_file_size_mb=self._tool_cfg("file_read").get("max_file_size_mb", 10),
            ),
            FileWriteTool(
                allowed_paths=self._tool_cfg("file_write").get("allowed_paths", ["/tmp"]),
            ),
            HttpRequestTool(
                allowed_domains=self._tool_cfg("http_request").get("allowed_domains", []),
                timeout_seconds=self._tool_cfg("http_request").get("timeout_seconds", 15),
            ),
            MemoryReadTool(),
            MemoryWriteTool(),
        ]

        for tool in candidate_tools:
            if self._is_enabled(tool.name):
                self._tools[tool.name] = tool
                logger.info("tool_registered", tool=tool.name)

    @property
    def max_tool_iterations(self) -> int:
        """Maximum number of tool-calling turns the agent may take."""
        return self._agent_config.get("max_tool_iterations", 5)

    def get_enabled_tools(self) -> list[BaseTool]:
        """Return all currently enabled tool instances."""
        return list(self._tools.values())

    def get_tool(self, name: str) -> BaseTool | None:
        """Return a specific tool by name, or None if not enabled."""
        return self._tools.get(name)

    def get_ollama_tools_schema(self) -> list[dict]:
        """Return the tools list in Ollama /api/chat format."""
        return [tool.to_ollama_schema() for tool in self._tools.values()]
