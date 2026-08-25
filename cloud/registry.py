"""Zenith Cloud Brain - tool registry.

Classification rule: a tool is PHONE-class only if its name is listed here
(or starts with `phone_`). Everything else in Zenith's catalog is treated as
LAPTOP-class, which drives the "Laptop based tool" confirmation flow.
"""

PHONE_TOOLS = {
    "phone_battery": "Phone battery level and charging state",
    "phone_flashlight": "Toggle phone flashlight/torch on or off",
    "phone_vibrate": "Make the phone vibrate once",
    "phone_notify": "Show a local notification on the phone",
    "phone_wifi_status": "Phone Wi-Fi connectivity status",
    "phone_device_info": "Phone model, OS version, device info",
    "phone_location": "Get current GPS location of the phone",
    "phone_camera_photo": "Capture a photo with rear camera",
    "phone_selfie": "Capture a photo with front camera",
    "phone_brightness": "Read or set screen brightness (0-255)",
    "phone_volume_media": "Read or set media volume (0-100)",
    "phone_volume_ring": "Read or set ring volume (0-100)",
    "phone_send_sms": "Send an SMS to a contact or number",
    "phone_read_sms": "Read recent SMS inbox messages",
    "phone_call_log": "Read recent call log entries",
    "phone_place_call": "Place a phone call to a number or contact",
    "phone_contacts_search": "Search phone contacts by name",
    "phone_bluetooth_status": "Bluetooth on/off and paired devices",
    "phone_installed_apps": "List installed apps",
    "phone_open_app": "Open an installed app by name",
    "phone_open_url": "Open a URL in the browser",
    "phone_set_alarm": "Set an alarm or timer",
    "phone_calendar_add": "Add a calendar event",
    "phone_calendar_read": "Read today's/upcoming calendar events",
    "phone_clipboard_get": "Read clipboard content",
    "phone_clipboard_set": "Copy text to clipboard",
    "phone_share_text": "Open Android share sheet with text",
    "phone_sensors": "Snapshot of accelerometer/gyroscope sensors",
    "phone_screen_state": "Whether screen is on/off/locked",
    "phone_storage_stats": "Internal storage usage stats",
    "phone_record_note": "Record a short audio note",
    "phone_network_info": "IP address, SSID, network details",
    "phone_battery_saver": "Battery saver / power save state",
    "phone_tts_speak": "Speak text aloud via TTS on the phone",
}

LAPTOP_TOOL_HINTS = (
    "battery_coach", "daily_threat_board", "damage_report", "get_laptop_health",
    "smart_status", "disk", "file", "window", "screen", "process", "email",
    "wifi_profile", "focus", "protocol", "clean slate", "study mode",
    "laptop_watch", "whole_disk", "radar", "heatmap", "catch_me_up",
)


def tool_class(tool: str) -> str:
    if not tool:
        return "none"
    t = tool.lower().strip()
    if t in PHONE_TOOLS or t.startswith("phone_"):
        return "phone"
    return "laptop"


def prompt_block() -> str:
    names = "\n".join(f"- {n}: {d}" for n, d in sorted(PHONE_TOOLS.items()))
    hints = ", ".join(LAPTOP_TOOL_HINTS)
    return (
        "PHONE-CLASS TOOLS (execute directly on the user's phone):\n"
        f"{names}\n\n"
        f"LAPTOP TOOLS examples: {hints}.\n"
        "RULES FOR LAPTOP INTENTS (files, disk health, battery coach, screen, "
        "windows, processes, emails, wifi profiles, focus sessions, protocols, "
        "threats, damage report, catch me up, etc.):\n"
        "- ALWAYS set device=laptop AND tool=<closest name from the list above>.\n"
        "- NEVER claim you ran it. NEVER say 'checking now'. The system will "
        "report laptop connectivity and ask the user to confirm first.\n"
        "- Your reply for laptop intents should be empty string.\n"
        "Example: user says 'check my disk health' -> "
        '{"reply": "", "tool": "get_laptop_health", "args": {}, "device": "laptop"}\n'
        "Example: user says 'turn on flashlight' -> "
        '{"reply": "", "tool": "phone_flashlight", "args": {"on": true}, "device": "phone"}\n'
        "Special value tool=get_status with device=status returns live "
        "connectivity info about both devices."
    )
