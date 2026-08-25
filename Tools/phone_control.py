"""Zenith Phone Control — laptop controls the connected phone remotely.

Uses the device bridge WebSocket to send commands to the Flutter app
which executes them natively (flashlight, vibrate, notifications, etc.).
"""

import logging

from livekit.agents import function_tool

logger = logging.getLogger(__name__)


async def _phone_cmd(tool: str, args: dict = None) -> str:
    from Tools.device_bridge import send_to_phone
    return await send_to_phone(tool, args or {})


@function_tool()
async def phone_battery() -> str:
    """Check your PHONE's battery level and charging state."""
    return await _phone_cmd("phone_battery")


@function_tool()
async def phone_flashlight(on: bool = True) -> str:
    """Turn your PHONE's flashlight ON or OFF.

    Args:
        on: True to turn on, False to turn off
    """
    return await _phone_cmd("phone_flashlight", {"on": on})


@function_tool()
async def phone_vibrate() -> str:
    """Make your PHONE vibrate once."""
    return await _phone_cmd("phone_vibrate")


@function_tool()
async def phone_notify(title: str, body: str = "") -> str:
    """Send a notification TO your PHONE screen.

    Args:
        title: Notification title
        body: Notification body text
    """
    return await _phone_cmd("phone_notify", {"title": title, "body": body})


@function_tool()
async def phone_status() -> str:
    """Get your PHONE's current status (battery, connectivity, etc.)."""
    from Tools.device_bridge import _phone_status, _clients
    if not _clients:
        return "📱 No phone connected via bridge."
    if not _phone_status:
        return "📱 Phone connected but hasn't reported status yet."
    import json
    return "📱 PHONE STATUS:\n" + json.dumps(_phone_status, indent=2)