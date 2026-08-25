"""Persistent, recurring reminder scheduler for Zenith.

SQLite-backed reminders that survive restarts and support one-time plus
natural-language recurrence ("every day 9am", "every Monday 3pm",
"every 30 minutes"). A monitor loop fires due reminders through a
notifier callback (typically session.generate_reply) and rolls
recurring ones forward to their next occurrence.
"""

import json
import logging
import re
import sqlite3
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

WEEKDAYS = {
    "monday": 0, "mon": 0, "tuesday": 1, "tue": 1, "wednesday": 2,
    "wed": 2, "thursday": 3, "thu": 3, "friday": 4, "fri": 4,
    "saturday": 5, "sat": 5, "sunday": 6, "sun": 6,
}

_HOUR_WORDS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
    "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12,
}

_CONTEXT_HOURS = {"morning": 7, "early": 7, "evening": 19, "night": 21,
                  "noon": 12, "midnight": 0}

_UNIT_SECONDS = {"second": 1, "sec": 1, "minute": 60, "min": 60,
                 "hour": 3600, "hr": 3600, "day": 86400}


def _now() -> datetime:
    return datetime.now()


def _next_daily(hour: int, minute: int) -> datetime:
    base = _now().replace(hour=hour, minute=minute, second=0, microsecond=0)
    if base <= _now():
        base += timedelta(days=1)
    return base


def _next_weekday(target: int, hour: int, minute: int) -> datetime:
    now = _now()
    days_ahead = (target - now.weekday()) % 7
    nxt = now.replace(hour=hour, minute=minute, second=0, microsecond=0) + timedelta(days=days_ahead)
    if nxt <= now:
        nxt += timedelta(days=7)
    return nxt


def _parse_clock(text: str):
    """Return (hour, minute) or (None, 0) if no clock time is found."""
    m = re.search(r"(\d{1,2}):(\d{2})", text)
    if m:
        return int(m.group(1)) % 24, int(m.group(2))
    m = re.search(r"(\d{1,2})\s*(am|pm|a\.m\.|p\.m\.)", text)
    if m:
        hr = int(m.group(1))
        if m.group(2).lstrip().rstrip(".").lower() in ("pm",):
            if hr != 12:
                hr += 12
        else:
            if hr == 12:
                hr = 0
        return hr, 0
    for word, hr in _CONTEXT_HOURS.items():
        if word in text:
            return hr, 0
    m = re.search(r"(\d{1,2})(?:\s*(?:o'?clock|hrs?\b))?", text)
    if m:
        return int(m.group(1)) % 24, 0
    return None, None


def parse_schedule(text: str) -> Dict[str, Any]:
    """Parse a natural-language schedule into a repeat rule + next time."""
    t = text.lower().strip()
    hour, minute = _parse_clock(t)

    # Interval recurrence: "every 30 minutes"
    m = re.search(r"every\s+(\d+)\s+(second|sec|minute|min|hour|hr|day)s?", t)
    if m:
        n = int(m.group(1))
        secs = n * _UNIT_SECONDS[m.group(2)]
        return {"type": "interval", "every_seconds": secs,
                "rule": "interval", "next": _now() + timedelta(seconds=secs)}

    # Offset: "in 10 minutes", "after 1 hour" (check before clock so bare
    # numbers like "2 seconds" are not read as clock hours).
    m = re.search(r"(?:in|after)\s+(\d+)\s*(second|minute|min|hour|hr|day)s?", t)
    if m:
        n = int(m.group(1))
        secs = n * _UNIT_SECONDS[m.group(2)]
        return {"type": "once", "rule": "once",
                "next": _now() + timedelta(seconds=secs)}

    # Weekly recurrence: "every tuesday 3pm"
    for day, w in WEEKDAYS.items():
        if day in t:
            h = hour if hour is not None else 9
            return {"type": "weekly", "weekday": w, "hour": h,
                    "minute": minute, "rule": "weekly",
                    "next": _next_weekday(w, h, minute)}

    # Daily recurrence: "every day 9am", "daily", "every morning"
    if "every day" in t or "daily" in t or "every morning" in t:
        h = hour if hour is not None else (7 if "morning" in t else 9)
        return {"type": "daily", "hour": h, "minute": minute,
                "rule": "daily", "next": _next_daily(h, minute)}

# Plain clock time that already passed -> next occurrence (once, roll-next-day)
    if hour is not None:
        base = _now().replace(hour=hour, minute=minute, second=0, microsecond=0)
        if base <= _now():
            base += timedelta(days=1)
        return {"type": "once", "rule": "once", "next": base}

    return {"type": "once", "rule": "once", "next": _now() + timedelta(minutes=1)}


class ReminderScheduler:
    def __init__(self, db_path: str = "data/zenith_scheduler.db"):
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._lock = threading.Lock()
        self._notifier: Optional[Callable[[str], Any]] = None
        self._init_schema()

    def _init_schema(self) -> None:
        cur = self._conn.cursor()
        cur.executescript(
            """
            CREATE TABLE IF NOT EXISTS reminders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                text TEXT NOT NULL,
                remind_at TEXT NOT NULL,
                type TEXT DEFAULT 'once',
                repeat_data TEXT DEFAULT '{}',
                enabled INTEGER DEFAULT 1,
                created_at TEXT
            );
            """
        )
        self._conn.commit()

    def add(self, text: str, schedule: Dict[str, Any]) -> Dict[str, Any]:
        repeat_type = schedule.get("type", "once")
        repeat_data = {k: v for k, v in schedule.items()
                       if k not in ("type", "rule", "next")}
        remind_at = schedule.get("next", _now()).isoformat()
        with self._lock:
            cur = self._conn.cursor()
            cur.execute(
                "INSERT INTO reminders (text, remind_at, type, repeat_data, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (text, remind_at, repeat_type, json.dumps(repeat_data), _now().isoformat()),
            )
            rid = cur.lastrowid
            self._conn.commit()
        return {"id": rid, "text": text, "remind_at": remind_at, "type": repeat_type}

    def cancel(self, rid: int) -> bool:
        with self._lock:
            cur = self._conn.cursor()
            cur.execute("DELETE FROM reminders WHERE id = ?", (rid,))
            self._conn.commit()
            return cur.rowcount > 0

    def list(self, enabled_only: bool = True) -> List[Dict[str, Any]]:
        q = "SELECT * FROM reminders"
        if enabled_only:
            q += " WHERE enabled = 1"
        q += " ORDER BY remind_at ASC"
        with self._lock:
            rows = self._conn.execute(q).fetchall()
        return [dict(r) for r in rows]

    def _due(self) -> List[Dict[str, Any]]:
        now = _now().isoformat()
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM reminders WHERE enabled = 1 AND remind_at <= ? ORDER BY remind_at ASC",
                (now,),
            ).fetchall()
        return [dict(r) for r in rows]

    def _next_occurrence(self, rem: Dict[str, Any]) -> Optional[datetime]:
        rtype = rem.get("type", "once")
        if rtype == "once":
            return None
        rd = json.loads(rem.get("repeat_data") or "{}")
        if rtype == "interval":
            secs = int(rd.get("every_seconds", 0))
            if secs:
                base = datetime.fromisoformat(rem["remind_at"]) if rem.get("remind_at") else _now()
                return base + timedelta(seconds=secs)
        elif rtype == "daily":
            return _next_daily(int(rd.get("hour", 9)), int(rd.get("minute", 0)))
        elif rtype == "weekly":
            return _next_weekday(int(rd.get("weekday", 0)),
                                 int(rd.get("hour", 9)), int(rd.get("minute", 0)))
        return None

    def set_notifier(self, fn: Callable[[str], Any]) -> None:
        self._notifier = fn

    def process_due(self) -> int:
        fired = 0
        for rem in self._due():
            msg = rem["text"]
            if self._notifier:
                try:
                    self._notifier(msg)
                except Exception as e:
                    logger.warning(f"notifier failed: {e}")
            nxt = self._next_occurrence(rem)
            with self._lock:
                cur = self._conn.cursor()
                if nxt is None:
                    cur.execute("DELETE FROM reminders WHERE id = ?", (rem["id"],))
                else:
                    cur.execute("UPDATE reminders SET remind_at = ? WHERE id = ?",
                                (nxt.isoformat(), rem["id"]))
                self._conn.commit()
            fired += 1
        return fired

    def stats(self) -> Dict[str, Any]:
        with self._lock:
            total = self._conn.execute("SELECT COUNT(*) AS c FROM reminders").fetchone()["c"]
        return {"total": total,
                "due_now": sum(1 for r in self.list(True)
                               if r["remind_at"] <= _now().isoformat())}