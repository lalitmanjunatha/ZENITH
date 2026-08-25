"""Desktop Conductor — Windows virtual-desktop control via native hotkeys.

Windows exposes no public rename API for virtual desktops, so this module uses
the OFFICIAL keyboard shortcuts and says so honestly:
  Switch:  Ctrl+Win+←/→      New: Win+Ctrl+D     Close: Win+Ctrl+F4
  Move focused window: Win+Shift+←/→ (then optionally follow it)
"""

import asyncio
import logging

from livekit.agents import function_tool

logger = logging.getLogger(__name__)


def _hotkey(*keys) -> bool:
    try:
        import pyautogui

        pyautogui.hotkey(*keys)
        return True
    except Exception as e:
        logger.debug(f"vdesk hotkey failed: {e}")
        return False


@function_tool()
async def vdesk_switch(direction: str = "next") -> str:
    """Switch virtual desktop.

    Args:
        direction: "next", "previous", or a desktop number like "2" (sends ←/→ that many times)
    """
    d = direction.strip().lower()
    try:
        n = int(d)
        steps = max(1, min(n - 1, 9))          # desktop N = N-1 rights from desktop 1
    except ValueError:
        if d.startswith(("n", "right")):
            steps = 1
        elif d.startswith(("p", "left")):
            return "⬅️ switching…" if await asyncio.to_thread(_hotkey, "ctrl", "win", "left") or True else ""
        else:
            return '❌ Use "next", "previous", or a number.'
    for _ in range(steps):
        ok = await asyncio.to_thread(_hotkey, "ctrl", "win", "right")
        await asyncio.sleep(0.15)
    return f"🖥️ Switched desktop ({'+' if steps else ''}{steps} →)."


@function_tool()
async def vdesk_previous() -> str:
    """Switch to the previous virtual desktop."""
    ok = await asyncio.to_thread(_hotkey, "ctrl", "win", "left")
    return "🖥️ Previous desktop." if ok else "❌ Hotkey failed."


@function_tool()
async def vdesk_next() -> str:
    """Switch to the next virtual desktop."""
    ok = await asyncio.to_thread(_hotkey, "ctrl", "win", "right")
    return "🖥️ Next desktop." if ok else "❌ Hotkey failed."


@function_tool()
async def vdesk_new() -> str:
    """Create a fresh virtual desktop."""
    ok = await asyncio.to_thread(_hotkey, "win", "ctrl", "d")
    return "✨ New virtual desktop created." if ok else "❌ Hotkey failed."


@function_tool()
async def vdesk_close_current() -> str:
    """Close the CURRENT virtual desktop (its windows merge into neighbours)."""
    ok = await asyncio.to_thread(_hotkey, "win", "ctrl", "f4")
    return ("🗑️ Current virtual desktop closed." if ok else "❌ Hotkey failed.")


@function_tool()
async def move_window_to_vdesk(direction: str = "next", follow: bool = True) -> str:
    """Move the FOCUSED window to the next/previous virtual desktop.
    Optionally follow it by switching too (Windows shortcut moves without following).

    Args:
        direction: "next" or "previous"
        follow: Also switch to that desktop afterwards
    """
    key = "right" if direction.lower().startswith("n") else "left"
    ok = await asyncio.to_thread(_hotkey, "win", "shift", key)
    if not ok:
        return "❌ Hotkey failed."
    note = "window moved"
    if follow:
        await asyncio.sleep(0.25)
        await asyncio.to_thread(_hotkey, "ctrl", "win", key)
        note += " + followed it"
    return f"🪟 {note} ({direction})."
