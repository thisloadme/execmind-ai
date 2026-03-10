"""ExecMind - Background task utilities for async document processing."""

import asyncio
from typing import Callable, Coroutine

from app.utils.logging import get_logger

logger = get_logger("background_tasks")

MAX_RETRY_ATTEMPTS = 3
RETRY_BACKOFF_BASE = 2  # seconds


async def run_with_retry(
    task_fn: Callable[..., Coroutine],
    *args,
    max_attempts: int = MAX_RETRY_ATTEMPTS,
    task_name: str = "background_task",
    **kwargs,
) -> None:
    """Execute an async function with exponential backoff retry.

    Args:
        task_fn: Async function to execute.
        max_attempts: Maximum number of retry attempts.
        task_name: Name for logging purposes.
        *args, **kwargs: Arguments passed to task_fn.
    """
    for attempt in range(1, max_attempts + 1):
        try:
            await task_fn(*args, **kwargs)
            logger.info(
                "background_task_completed",
                task=task_name,
                attempt=attempt,
            )
            return
        except Exception as e:
            if attempt < max_attempts:
                wait_time = RETRY_BACKOFF_BASE ** attempt
                logger.warning(
                    "background_task_retry",
                    task=task_name,
                    attempt=attempt,
                    error=str(e),
                    retry_in=wait_time,
                )
                await asyncio.sleep(wait_time)
            else:
                logger.error(
                    "background_task_failed",
                    task=task_name,
                    attempt=attempt,
                    error=str(e),
                )
                raise
