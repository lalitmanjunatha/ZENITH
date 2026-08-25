"""Smart Monitors — timed screenshot surveillance sessions.

Start a monitor ("watch this download for 10 min, shot every 30s") and Zenith
captures periodic screenshots into a session folder. Fully local, capped at
MAX_SHOTS per session, stoppable anytime, with an OCR peek of the latest frame.
"""

import asyncio
import logging
import os
import time
from datetime import datetime
from pathlib import Path

from livekit.agents import function_tool

logger = logging.getLogger(__name__)

ROOT = Path("data/screen_monitor")
MAX_SHOTS = 200

_monitors = {}          # id -> {"task","dir","interval","purpose","count","started"}
_next_id = [1]


async def _capture_loop(mid: str):
    m = _monitors.get(mid)
    if not m:
        return
    import pyautogui
    while m["active"] and m["count"] < MAX_SHOTS:
        try:
            ts = datetime.now().strftime("%H%M%S_%f")[:-3]
            path = await asyncio.to_thread(
                pyautogui.screenshot if False else lambda: pyautogui.screenshot()
            )
            await asyncio.to_thread(path.save, str(m["dir"] / f"shot_{m['count']+1:03d}_{ts}.png"))
            m["count"] += 1
        except Exception as e:
            logger.debug(f"monitor {mid} shot failed: {e}")
        # sleep in small slices so stop is responsive
        end = time.time() + m["interval"]
        while time.time() < end and m["active"]:
            await asyncio.sleep(min(1.0, end - time.time()))
    m["active"] = False


@function_tool()
async def start_screen_monitor(interval_seconds: int = 30, duration_minutes: int = 10,
                               purpose: str = "") -> str:
    """Start TIMED SCREENSHOT MONITORING (e.g., watching a download progress bar,
    stock chart, or live counter). Captures a screenshot every N seconds into a
    private local folder. Fully offline; nothing uploaded.

    Args:
        interval_seconds: Seconds between shots (min 5, max 3600)
        duration_minutes: Total monitoring window (min 1, max 180)
        purpose: Optional label, e.g. "download progress"
    """
    interval = max(5, min(int(interval_seconds), 3600))
    dur = max(1, min(int(duration_minutes), 180))
    mid = f"mon{_next_id[0]}"; _next_id[0] += 1
    d = ROOT / f"{datetime.now().strftime('%Y%m%d')}_{mid}"
    d.mkdir(parents=True, exist_ok=True)
    m = {"dir": d, "interval": interval, "purpose": purpose or "general",
         "count": 0, "started": datetime.now(), "active": True}
    _monitors[mid] = m

    async def timed_stop():
        await asyncio.sleep(dur * 60)
        m["active"] = False

    m["task"] = asyncio.create_task(_capture_loop(mid))
    asyncio.create_task(timed_stop())
    est_shots = min(MAX_SHOTS, int(dur * 60 / interval))
    return (f"📸 MONITOR {mid} STARTED\n"
            f"   Every {interval}s for {dur} min (~{est_shots} shots, cap {MAX_SHOTS})\n"
            f"   Purpose: {m['purpose']}\n   Folder: {d}\n"
            f'Say "stop screen monitor {mid}" or "screen monitor status" anytime.')


@function_tool()
async def stop_screen_monitor(monitor_id: str = "") -> str:
    """Stop one (or all) running screenshot monitor(s).

    Args:
        monitor_id: e.g. "mon1"; empty string stops ALL monitors
    """
    stopped = []
    for k, m in list(_monitors.items()):
        if not monitor_id or k == monitor_id.strip():
            m["active"] = False
            stopped.append(f"{k}: {m['count']} shots saved → {m['dir']}")
    if not stopped:
        return f"❌ No matching active monitor '{monitor_id}'. Active: {[k for k,v in _monitors.items() if v['active']] or 'none'}"
    return "🛑 Stopped:\n" + "\n".join(f"  • {s}" for s in stopped)


@function_tool()
async def screen_monitor_status(monitor_id: str = "") -> str:
    """Check screenshot monitor progress, including an OCR peek at the newest frame."""
    mid = monitor_id.strip()
    targets = [(k, v) for k, v in _monitors.items() if (not mid or k == mid)]
    if not targets:
        return f"❌ No such monitor '{mid or '(any)'}'. Active: {[k for k,v in _monitors.items() if v['active']] or 'none'}"
    out = []
    for k, m in targets:
        state = "🟢 RUNNING" if m["active"] else "⏹️ finished"
        out.append(f"{k} [{state}] {m['count']} shots | every {m['interval']}s | {m['dir']}")
    result = "📸 MONITOR STATUS\n" + "\n".join(out)

    # OCR peek at latest shot of first requested monitor
    k, m = targets[0]
    shots = sorted(m["dir"].glob("shot_*.png"))
    if shots:
        try:
            import pytesseract
            from PIL import Image
            txt = await asyncio.to_thread(pytesseract.image_to_string, Image.open(shots[-1]))
            clean = " ".join(txt.split())[:220]
            if clean:
                result += f"\n🔍 Latest frame text ({k}): “{clean}…”"
        except Exception:
            pass
    return result


def latest_monitor_text_snippet() -> str:
    """One-liner about active monitors (for morning/day summaries)."""
    act = [(k, v) for k, v in _monitors.items() if v["active"]]
    if not act:
        return ""
    k, v = act[0]
    return f"A screen monitor ({k}) is capturing every {v['interval']}s ({v['count']} so far)."
