"""Zenith Laptop Watcher — monitors device power/bridge state, notifies owner.

Tools:
  laptop_status()      — is the bridge server reachable? (ONLINE/OFFLINE)
  watch_laptop()       — start persistent monitor; announces offline→online
  stop_laptop_watch()  — stop the monitor
  laptop_watch_status()— is a watch active?

When the bridge server comes up after being down, Zenith SPEAKS:
  "Sir, your laptop just came online."
Works even when checked FROM the phone via LiveKit — the check is a plain
HTTP ping to the bridge address, not a local function call.
"""

import asyncio
import logging
import os
import socket
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from livekit.agents import function_tool

logger = logging.getLogger(__name__)

BRIDGE_HOST = os.getenv("ZENITH_BRIDGE_CHECK_HOST", "")   # empty = self
BRIDGE_PORT = int(os.getenv("ZENITH_BRIDGE_PORT", "8990"))
POLL_SEC = float(os.getenv("ZENITH_LAPTOP_POLL", "10"))

_state = {
    "watching": False,
    "last_online": None,       # datetime | None
    "was_online": None,        # last known bool
    "transitions": [],         # list of {ts, event}
    "session": None,
    "task": None,
}


def _bridge_host() -> str:
    """If explicitly set, use that host. Otherwise detect our own LAN IP."""
    if BRIDGE_HOST:
        return BRIDGE_HOST
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


async def _ping_bridge(timeout: float = 3.0) -> bool:
    """TCP connect check to the bridge port."""
    def _check():
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(timeout)
            result = s.connect_ex((_bridge_host(), BRIDGE_PORT))
            s.close()
            return result == 0
        except Exception:
            return False
    return await asyncio.to_thread(_check)


def _set_session(session):
    _state["session"] = session


async def _announce(text: str):
    sess = _state.get("session")
    if sess:
        try:
            await sess.generate_reply(
                instructions=f'Say EXACTLY this naturally: "{text}"')
        except Exception as e:
            logger.debug(f"announce failed: {e}")
    print(f"📢 {text}")


# ------------------------------------------------------------ main loop -----

async def _watch_loop():
    """Persistent poll loop — detects offline→online transitions."""
    logger.info(f"👁️ Laptop watcher polling {_bridge_host()}:{BRIDGE_PORT} every {POLL_SEC}s")
    while _state["watching"]:
        online = await _ping_bridge()
        now = datetime.now()

        prev = _state["was_online"]
        if prev is not None and online != prev:
            event = "online" if online else "offline"
            _state["transitions"].append({"ts": now.isoformat(), "event": event})
            # keep only last 50
            _state["transitions"] = _state["transitions"][-50:]

            if online:
                await _announce("Sir, your laptop just came online.")
                # Broadcast to any connected phone clients
                try:
                    from Tools.device_bridge import broadcast
                    await broadcast({"event": "laptop_online", "ts": now.isoformat()})
                except Exception:
                    pass
            else:
                await _announce("Your laptop just went offline, sir.")

        if online:
            _state["last_online"] = now

        _state["was_online"] = online
        await asyncio.sleep(POLL_SEC)


# ============================================================== TOOLS =======

@function_tool()
async def laptop_status() -> str:
    """LAPTOP STATUS: is the bridge server reachable right now?
    Returns ONLINE/OFFLINE with details (uptime, battery, RAM if reachable)."""
    online = await _ping_bridge()
    if not online:
        return (
            "💻 LAPTOP: 🔴 OFFLINE\n"
            f"Bridge at {_bridge_host()}:{BRIDGE_PORT} did not respond.\n"
            "Either the laptop is powered off, or the Zenith bridge server "
            "hasn't started yet.\n"
            'Say "watch my laptop" and I\'ll tell you the moment it comes online.'
        )

    # Bridge reachable → get detailed stats
    import aiohttp
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=5)) as s:
            async with s.get(f"http://{_bridge_host()}:{BRIDGE_PORT}/api/status") as r:
                data = await r.json()
        uptime_min = data.get("uptime_s", 0) // 60
        batt = data.get("battery_pct")
        batt_s = f"{batt}% ({'charging' if data.get('charging') else 'on battery'})" if batt else "N/A"
        return (
            f"💻 LAPTOP: 🟢 ONLINE\n"
            f"   Hostname: {data.get('hostname', '?')}\n"
            f"   IP: {data.get('ip', '?')}\n"
            f"   Uptime: {uptime_min} min\n"
            f"   CPU: {data.get('cpu_pct', '?')}% | RAM: {data.get('ram_pct', '?')}%\n"
            f"   Disk: {data.get('disk_free_gb', '?')} GB free\n"
            f"   Battery: {batt_s}"
        )
    except Exception:
        return f"💻 LAPTOP: 🟢 ONLINE (port open but stats unavailable)"


@function_tool()
async def watch_laptop() -> str:
    """NOTIFY ME WHEN LAPTOP TURNS ON: starts a persistent monitor that
    announces the moment the laptop bridge server comes online after being off.
    Also announces when it goes offline."""
    if _state["watching"]:
        return ("👀 Already watching. I'll notify you the moment it changes state. "
                "Say \"stop laptop watch\" to cancel.")
    _state["watching"] = True
    _state["was_online"] = await _ping_bridge()   # seed initial state
    _state["task"] = asyncio.create_task(_watch_loop())
    init = "🟢 currently ONLINE" if _state["was_online"] else "🔴 currently OFFLINE"
    return (
        f"👀 LAPTOP WATCH ACTIVE — polling every {POLL_SEC:.0f}s.\n"
        f"Current: {init}\n"
        "I'll announce the moment it goes online or offline.\n"
        'Say "stop laptop watch" anytime.'
    )


@function_tool()
async def stop_laptop_watch() -> str:
    """Stop the laptop power-state watcher."""
    if not _state["watching"]:
        return "ℹ️ No active laptop watch."
    _state["watching"] = False
    if _state["task"]:
        _state["task"].cancel()
        _state["task"] = None
    return "👋 Laptop watcher stopped."


@function_tool()
async def laptop_watch_status() -> str:
    """Is a laptop watch currently running? What transitions have been seen?"""
    if not _state["watching"]:
        return "👀 No laptop watch active. Say \"watch my laptop\" to start one."
    trans = _state.get("transitions", [])
    out = f"👀 WATCH ACTIVE (polling every {POLL_SEC:.0f}s)\n"
    out += f"Was online: {_state['was_online']}\n"
    if trans:
        out += "Recent transitions:\n"
        for t in trans[-5:]:
            out += f"   • {t['ts'][:19]} → {t['event']}\n"
    else:
        out += "No transitions yet."
    return out


def set_session(session):
    _state["session"] = session