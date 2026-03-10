"""ExecMind - Structured JSON logging configuration."""

import logging
import sys

import structlog

from app.core.config import settings


def setup_logging() -> None:
    """Configure structured JSON logging with structlog."""
    log_level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str = "execmind"):
    """Get a structured logger instance.

    Args:
        name: Logger name for context.

    Returns:
        Bound structlog logger.
    """
    return structlog.get_logger(name)
