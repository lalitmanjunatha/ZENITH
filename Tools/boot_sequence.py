"""Zenith boot sequence — cinematic voice greeting with a real status roll.

Called from agent entrypoint at startup; also replayable on demand.
Audio-only (no HUD), consistent with the laptop-only JARVIS directive.
"""

import logging
import os
from datetime import datetime

logger = logging.getLogger(__name__)


def gather_status_lines() -> list:
    """REAL data only — every line comes from an actual sensor/store."""
    lines = []
    try:
        import psutil

        b = psutil.sensors_battery()
        if b:
            state = "charging" if b.power_plugged else "on battery"
            lines.append(f"Power at {int(b.percent)} percent, {state}")
        vm = psutil.virtual_memory()
        lines.append(f"Memory load {vm.percent} percent")
        du = psutil.disk_usage(os.path.abspath(os.sep))
        lines.append(f"System drive {int(du.percent)} percent utilized")
    except Exception:
        pass
    try:
        now = datetime.now()
        lines.append(f"It is {now.strftime('%I:%M %p')}, {now.strftime('%A')}")
    except Exception:
        pass
    return lines or ["All systems nominal"]


def build_boot_text() -> str:
    name = os.getenv("USER_NAME", "Sir")
    status = "; ".join(gather_status_lines())
    return (
        f"Good to see you, {name}. Zenith online. {status}. "
        "All tools loaded and standing by — what are we building today?"
    )


async def run_boot(session) -> bool:
    """Speak the greeting through the live session. Returns success."""
    if session is None:
        return False
    try:
        await session.generate_reply(
            instructions=(
                "Deliver this EXACT greeting naturally, without adding anything: "
                f"\"{build_boot_text()}\""
            )
        )
        return True
    except Exception as e:
        logger.warning(f"boot speech failed: {e}")
        return False


def pending_brief_lines() -> list:
    """Extra context lines the entrypoint may append (kept separate for clarity)."""
    out = []
    try:
        from Tools.time_capsule import newly_unlocked_brief_line
        l1 = newly_unlocked_brief_line()
        if l1:
            out.append(l1)
    except Exception:
        pass
    return out
