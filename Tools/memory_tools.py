"""Memory tools exposed to the voice agent.

The LLM calls these to remember facts, recall past conversations, and to
"train" from accumulated conversation data.
"""

import asyncio
import json
import logging

from livekit.agents import function_tool

logger = logging.getLogger(__name__)


def _get_memory():
    from memory_manager import MemoryManager

    return MemoryManager()


@function_tool()
async def store_memory(content: str, category: str = "general") -> str:
    """Permanently remember a fact or detail about the user.

    Args:
        content: The fact to remember (e.g. "User's name is Lalit").
        category: Optional category (personal, preference, work, etc).
    """
    try:
        mem = _get_memory()
        mem.record_fact(content, category=category, source="user")
        return f"Remembered: {content} (category: {category})"
    except Exception as e:
        return f"Failed to remember: {e}"


@function_tool()
async def recall_memory(query: str) -> str:
    """Recall past conversations or stored facts relevant to a query.

    Args:
        query: What to remember / look up from prior conversations.
    """
    try:
        mem = _get_memory()
        result = mem.recall(query, top_k=5)
        lines = ["### What I remember"]
        for m in result.get("messages", []):
            lines.append(f"- (past, {m.get('role', 'user')}): {m.get('content', '')}")
        for f in result.get("facts", []):
            lines.append(f"- FACT [{f.get('category', 'general')}]: {f.get('content', '')}")
        if len(lines) == 1:
            lines.append("(Nothing relevant stored yet.)")
        return "\n".join(lines)
    except Exception as e:
        return f"Recall failed: {e}"


@function_tool()
async def what_do_you_remember() -> str:
    """List every fact Zenith has stored about the user."""
    try:
        mem = _get_memory()
        facts = mem.all_facts()
        if not facts:
            return "I haven't stored any facts yet."
        return "\n".join(
            f"- [{f.get('category', 'general')}] {f.get('content', '')}"
            for f in facts
        )
    except Exception as e:
        return f"Failed to read memory: {e}"


@function_tool()
async def train_from_conversations() -> str:
    """Train the memory index from all conversations and facts so far."""
    try:
        mem = _get_memory()
        result = mem.train_from_conversations()
        return json.dumps(result, indent=2, default=str)
    except Exception as e:
        return f"Training failed: {e}"


@function_tool()
async def get_memory_stats() -> str:
    """Return statistics about stored memory (messages, facts, vectors)."""
    try:
        mem = _get_memory()
        return json.dumps(mem.stats(), indent=2, default=str)
    except Exception as e:
        return f"Stats failed: {e}"