"""Shutdown Ritual — a safe end-of-day sequence with real countdown.

Preview what would happen → confirm → Windows-native delayed shutdown
(`shutdown /s /t N`), fully cancellable with `shutdown /a` via cancel_shutdown().
Never shuts down without explicit confirmation. Day-summary pulls REAL stats
from your memory DB, not invented ones.
"""

import logging
import os
import sqlite3
import subprocess
from datetime import datetime

from livekit.agents import function_tool

logger = logging.getLogger(__name__)

DB_PATH = "data/zenith_memory.db"


def _today_stats() -> dict:
    out = {"messages_today": 0, "facts": 0, "conversations": 0}
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        today = datetime.now().strftime("%Y-%m-%d")
        row = conn.execute(
            "SELECT COUNT(*) c FROM messages WHERE created_at LIKE ?", (f"{today}%",)
        ).fetchone()
        out["messages_today"] = row["c"]
        out["facts"] = conn.execute("SELECT COUNT(*) c FROM facts").fetchone()["c"]
        out["conversations"] = conn.execute("SELECT COUNT(*) c FROM conversations").fetchone()["c"]
        conn.close()
    except Exception as e:
        logger.debug(f"stats failed: {e}")
    return out


def _open_app_names(limit: int = 12) -> list:
    try:
        import pygetwindow as gw

        names = []
        for w in gw.getAllWindows():
            t = (w.title or "").strip()
            if t and " - " in t:
                name = t.split(" - ")[-1].strip()
                if name and name.lower() not in ("program manager", "settings", "nvidia geforce overlay"):
                    if name not in names:
                        names.append(name[:40])
            if len(names) >= limit:
                break
        return names
    except Exception:
        return []


@function_tool()
async def shutdown_preview() -> str:
    """SHUTDOWN RITUAL PREVIEW: see today's real activity summary and which apps
    are open — before deciding to shut down. Nothing happens in preview."""
    s = _today_stats()
    apps = _open_app_names()
    from Tools.laptop_health import collect_snapshot  # battery check before sleep
    snap = collect_snapshot()
    batt = snap.get("battery") or {}
    line = ""
    if batt.get("pct") is not None:
        plug = "charging ⚡" if batt.get("plugged") else "on battery 🔋"
        line = f"🔋 Battery: {batt['pct']}% ({plug})"
        if batt.get("pct") is None or batt.get("pct", 100) < 20:
            pass
    out = (
        "🌙 SHUTDOWN RITUAL — PREVIEW\n════════════════════\n"
        f"🗣️ Conversations today: {s['messages_today']} messages\n"
        f"🧠 Long-term facts banked: {s['facts']} across {s['conversations']} sessions\n"
        f"🪟 Open apps: {', '.join(apps) if apps else 'none notable'}\n"
        f"{line}\n\n"
        "➡ Say \"shutdown in 5 minutes\" to schedule (Windows-native delay, "
        "cancellable anytime with \"cancel shutdown\"). I will NOT close apps "
        "forcefully — save your work first."
    )
    return out


@function_tool()
async def execute_shutdown(delay_minutes: int = 5, confirm: bool = False) -> str:
    """Schedule a full Windows shutdown after a delay.

    Args:
        delay_minutes: Grace period so you can save work (default 5)
        confirm: MUST be True to actually schedule
    """
    try:
        if not confirm:
            return ("⛔ Confirmation required. Run shutdown_preview first, then "
                    'ask: "shutdown in N minutes, confirmed".')
        secs = max(60, min(int(delay_minutes), 240)) * 60
        r = subprocess.run(["shutdown", "/s", "/t", str(secs)],
                           capture_output=True, text=True, timeout=10)
        if r.returncode != 0:
            return f"❌ Windows refused: {r.stderr.strip() or r.stdout.strip()}"
        at_time = datetime.fromtimestamp(__import__("time").time() + secs).strftime("%H:%M")
        return (f"🌙 Shutdown scheduled in {delay_minutes} min (at {at_time}).\n"
                "💤 Zenith will consolidate memory on the way down.\n"
                'Changed your mind? Say "cancel shutdown".')
    except Exception as e:
        return f"❌ Scheduling failed: {e}"


@function_tool()
async def cancel_shutdown() -> str:
    """Cancel a scheduled Windows shutdown."""
    try:
        r = subprocess.run(["shutdown", "/a"], capture_output=True, text=True, timeout=10)
        if r.returncode == 0:
            return "✅ Scheduled shutdown cancelled. We keep going 😄"
        return "ℹ️ No pending shutdown to cancel."
    except Exception as e:
        return f"❌ Cancel failed: {e}"
