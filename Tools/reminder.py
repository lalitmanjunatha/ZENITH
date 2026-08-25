"""Persistent reminder tools (scheduler-backed).

Backs the voice-facing set_reminder / set_recurring_reminder /
view_reminders / cancel_reminder tools with the SQLite scheduler so
reminders survive restarts.
"""

import asyncio
import json
from datetime import datetime
from livekit.agents import function_tool


def _scheduler():
    from scheduler import ReminderScheduler
    return ReminderScheduler()


@function_tool()
async def set_reminder(reminder_text: str, when: str = "10 minutes") -> str:
    """Set a one-time reminder.

    Args:
        reminder_text: What to be reminded about.
        when: When, e.g. 'in 5 minutes', 'at 6pm today', 'tomorrow 9am'.
    """
    try:
        from scheduler import ReminderScheduler, parse_schedule
        sch = _scheduler()
        schedule = parse_schedule(when)
        result = sch.add(reminder_text, schedule)
        return (
            f"✅ Reminder set!\n📝 {reminder_text}\n"
            f"⏰ {result['remind_at']} (id {result['id']})"
        )
    except Exception as e:
        return f"❌ Failed to set reminder: {e}"


@function_tool()
async def set_recurring_reminder(reminder_text: str, schedule_text: str) -> str:
    """Set a recurring reminder.

    Args:
        reminder_text: What to be reminded about.
        schedule_text: e.g. 'every day 9am', 'every Monday 3pm', 'every 30 minutes'.
    """
    try:
        from scheduler import parse_schedule
        sch = _scheduler()
        schedule = parse_schedule(schedule_text)
        result = sch.add(reminder_text, schedule)
        return (
            f"🔁 Recurring reminder set!\n📝 {reminder_text}\n"
            f"⏰ {schedule['rule']} (ID {result['id']})"
        )
    except Exception as e:
        return f"❌ Failed: {e}"


@function_tool()
async def view_reminders() -> str:
    """List all active reminders."""
    try:
        sch = _scheduler()
        rems = sch.list()
        if not rems:
            return "📋 No active reminders."
        now = datetime.now()
        lines = ["📋 Active Reminders:"]
        for r in rems:
            at = datetime.fromisoformat(r["remind_at"])
            left = at - now if at > now else 0
            mins = int(left.total_seconds() // 60) if at > now else 0
            kind = r["type"]
            lines.append(
                f"  • [{r['id']}] {r['text']} — {kind}, in ~{mins}m"
            )
        return "\n".join(lines)
    except Exception as e:
        return f"❌ Failed to list reminders: {e}"


@function_tool()
async def cancel_reminder(reminder_id: str) -> str:
    """Cancel a reminder by its id.

    Args:
        reminder_id: The numeric id shown when the reminder was set.
    """
    try:
        sch = _scheduler()
        ok = sch.cancel(int(reminder_id))
        return f"✅ Reminder {reminder_id} cancelled." if ok else f"❌ Reminder {reminder_id} not found."
    except Exception as e:
        return f"❌ Failed: {e}"