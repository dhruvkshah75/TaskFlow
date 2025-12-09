import asyncio
from dataclasses import dataclass
from typing import Any, Dict

@dataclass
class TaskResult:
    success: bool
    message: str = ""
    data: Dict[str, Any] = None


# Example handlers
async def dummy_handler(payload: Dict[str, Any]) -> TaskResult:
    """An async dummy task that sleeps and returns success."""
    await asyncio.sleep(1)
    return TaskResult(success=True, message="dummy completed")


def sync_echo_handler(payload: Dict[str, Any]) -> TaskResult:
    """A simple sync handler that echoes payload."""
    return TaskResult(success=True, message=f"echo: {payload}")


# Registry: keys correspond to payload.type or task.title fallback
HANDLERS = {
    "dummy": dummy_handler,
    "echo": sync_echo_handler,
}

# Provide a default handler key so the worker can fall back when no type/title matches.
HANDLERS.setdefault("default", dummy_handler)
