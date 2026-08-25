"""Privacy / memory controls for Zenith.

Lets the user pause or resume long-term memory at any time, and mark a
just-said exchange as 'forget this' so it is removed.
"""

import logging
from livekit.agents import function_tool

logger = logging.getLogger(__name__)


def _get_memory():
    from memory_manager import MemoryManager
    return MemoryManager()


@function_tool()
async def pause_memory() -> str:
    """Stop recording new conversations into long-term memory."""
    try:
        _get_memory().set_paused(True)
        return "🛡️ Memory paused. I will not save anything new until you say resume memory."
    except Exception as e:
        return f"Failed to pause memory: {e}"


@function_tool()
async def resume_memory() -> str:
    """Resume recording conversations into long-term memory."""
    try:
        _get_memory().set_paused(False)
        return "✅ Memory resumed. I'll start learning again starting now."
    except Exception as e:
        return f"Failed to resume memory: {e}"


@function_tool()
async def do_not_remember_that() -> str:
    """Forget the very last thing that was said in this conversation."""
    try:
        result = _get_memory().forget_last()
        return ("✅ Forgot that last bit." if result.get("forgot")
                else "Nothing to forget.")
    except Exception as e:
        return f"Failed to forget: {e}"


@function_tool()
async def memory_status() -> str:
    """Report whether long-term memory recording is currently on or paused."""
    try:
        mem = _get_memory()
        state = "paused" if mem.is_paused() else "active"
        stats = mem.stats()
        return (f"Memory is {state}. "
                f"Stored so far: {stats.get('messages', 0)} exchanges, "
                f"{stats.get('facts', 0)} facts, {stats.get('vectors', 0)} vectors.")
    except Exception as e:
        return f"Could not read memory status: {e}"