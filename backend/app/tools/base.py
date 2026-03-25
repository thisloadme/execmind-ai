"""ExecMind - Base tool abstractions for the agentic tool system."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID


@dataclass
class ToolContext:
    """Runtime context passed to every tool execution.

    Provides identity and DB access for audit logging and memory operations.
    """

    user_id: UUID
    session_id: UUID
    db_session: Any  # AsyncSession — typed as Any to avoid circular imports


@dataclass
class ToolResult:
    """Structured result returned by any tool execution."""

    success: bool
    content: str  # Human-readable output injected back into LLM context
    action: dict | None = None  # Optional SSE action payload sent to frontend
    error: str | None = None


class BaseTool(ABC):
    """Abstract base class that every tool must implement.

    Subclasses declare their name, description, and JSON Schema parameters,
    then implement the execute() coroutine with their actual logic.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique tool identifier (matches Ollama function name)."""

    @property
    @abstractmethod
    def description(self) -> str:
        """LLM-facing description of what this tool does and when to use it."""

    @property
    @abstractmethod
    def parameters(self) -> dict:
        """JSON Schema object describing accepted arguments."""

    @abstractmethod
    async def execute(self, arguments: dict, context: ToolContext) -> ToolResult:
        """Run the tool with the given arguments.

        Args:
            arguments: Parsed arguments from the LLM tool_call.
            context: Runtime context with user identity and DB session.

        Returns:
            ToolResult with success status, content for LLM, and optional action.
        """

    def to_ollama_schema(self) -> dict:
        """Render this tool as an Ollama-compatible function schema."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }
