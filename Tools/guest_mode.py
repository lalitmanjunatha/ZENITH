"""Guest Mode — lend your laptop without lending your life.

When enabled, a restriction directive is injected into the agent's instructions
(read live at instruction-build time) forbidding personal/dangerous tools, and
a status tool reports the active window. Auto-expires; persists across restart
until expiry passes. Honest scope: it gates the AI's behavior layer — OS-level
user accounts remain the real security boundary (we say so).
"""

import logging
import sqlite3
from datetime import datetime, timedelta

from livekit.agents import function_tool

logger = logging.getLogger(__name__)

DB_PATH = "data/zenith_memory.db"

FORBIDDEN_FOR_GUESTS = [
    "self-edit / source modification", "file janitor execution", "system power actions",
    "email reading or sending", "WhatsApp sending", "memory recall of the owner",
    "SIH project data", "time capsules", "screen monitors", "scheduled messages",
    "any tool that reads owner files beyond what the guest explicitly opens",
]


def _db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("CREATE TABLE IF NOT EXISTS guest_mode (key TEXT PRIMARY KEY, value TEXT)")
    return conn


def _read_state() -> tuple:
    try:
        conn = _db()
        row = conn.execute("SELECT value FROM guest_mode WHERE key='on_until'").fetchone()
        conn.close()
        if row:
            until = datetime.fromisoformat(row["value"])
            if datetime.now() < until:
                return True, until
            # expired → clean up lazily
            conn = _db(); conn.execute("DELETE FROM guest_mode"); conn.commit(); conn.close()
            return False, None
    except Exception as e:
        logger.debug(f"guest read failed: {e}")
    return False, None


def is_guest() -> bool:
    on, _ = _read_state()
    return on


def guest_instruction_block() -> str:
    """Injected into agent._build_instructions when guest mode is active."""
    on, until = _read_state()
    if not on:
        return ""
    hrs = max(1, int((until - datetime.now()).total_seconds() // 3600))
    mins = int(((until - datetime.now()).total_seconds() % 3600) // 60)
    return (
        f"\n# 🧑‍💼 GUEST MODE ACTIVE (until {until.strftime('%d %b %H:%M')}, {hrs}h{mins:02d}m left)\n"
        "You are serving a GUEST on the owner's laptop. STRICTLY REFUSE anything involving: "
        + "; ".join(FORBIDDEN_FOR_GUESTS)
        + ".\nAllowed: general questions, fun modes, weather/time/news, calculator-style help.\n"
        "Never reveal owner facts, memories, files, projects, or personal data. "
        "If asked who owns this laptop: 'That's private.' Stay polite."
    )


@function_tool()
async def enable_guest_mode(hours: float = 2.0) -> str:
    """Enable GUEST MODE for a duration — the AI will refuse personal tools,
    hide owner memories/files/projects, and keep chats non-personal.

    Args:
        hours: How long guests may use it (default 2, max 24)
    """
    h = max(0.25, min(float(hours), 24))
    until = datetime.now() + timedelta(hours=h)
    conn = _db()
    conn.execute(
        "INSERT INTO guest_mode (key,value) VALUES ('on_until',?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (until.isoformat(),),
    )
    conn.commit(); conn.close()
    return (
        f"🧑‍💼 GUEST MODE ON until {until.strftime('%d %b %H:%M')} ({g(h)}).\n"
        f"Blocked for guests: {', '.join(FORBIDDEN_FOR_GUESTS[:6])}…\n"
        "Voice style applies immediately for new replies; full lock-in after restart.\n"
        "ℹ️ Honest note: this gates MY behavior. For hard security, use a separate Windows account."
    )


def g(h: float) -> str:
    hh = int(h); mm = int(round((h - hh) * 60))
    return f"{hh}h{mm:02d}m"


@function_tool()
async def disable_guest_mode() -> str:
    """Turn guest mode off and restore full owner access."""
    conn = _db(); conn.execute("DELETE FROM guest_mode"); conn.commit(); conn.close()
    return "🔓 Guest mode OFF. Welcome back — everything restored."


@function_tool()
async def guest_status() -> str:
    """Is guest mode currently active? Until when?"""
    on, until = _read_state()
    if not on:
        return "🧑‍💼 Guest mode: inactive (owner has full access)."
    left = until - datetime.now()
    hrs = int(left.total_seconds() // 3600); mins = int((left.total_seconds() % 3600) // 60)
    return f"🧑‍💼 Guest mode ACTIVE — {hrs}h{mins:02d}m remaining (till {until.strftime('%H:%M')})."
