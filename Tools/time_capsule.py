"""Time Capsules — sealed notes to your future self.

Store a message with an unlock date. Locked ones show only "sealed" info;
when the date arrives they open (revealed via check tool AND surfaced in the
morning brief). Opened capsules stay readable forever.
"""

import logging
import sqlite3
import re
from datetime import datetime, timedelta

from livekit.agents import function_tool

logger = logging.getLogger(__name__)

DB_PATH = "data/zenith_memory.db"


def _db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute(
        """CREATE TABLE IF NOT EXISTS time_capsules (
               id INTEGER PRIMARY KEY AUTOINCREMENT,
               title TEXT,
               message TEXT,
               open_at TEXT,
               created_at TEXT,
               opened INTEGER DEFAULT 0
           )"""
    )
    return conn


def _parse_open_date(s: str):
    s = s.strip().lower()
    # Full ISO datetime / date-only / DD-MM-YYYY / DD/MM/YYYY
    for fmt in ("%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S",
                "%Y-%m-%dT%H:%M", "%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    m = re.search(r"in\s+(\d+)\s*(day|days|week|weeks|month|months|year|years)", s)
    if m:
        n = int(m.group(1)); u = m.group(2)
        if u.startswith("day"):   return datetime.now() + timedelta(days=n)
        if u.startswith("week"):  return datetime.now() + timedelta(weeks=n)
        if u.startswith("month"): return datetime.now() + timedelta(days=30 * n)
        return datetime.now() + timedelta(days=365 * n)
    # "on 15-08" style → next occurrence
    m = re.match(r"(?:on\s+)?(\d{1,2})[\-/](\d{1,2})$", s)
    if m:
        d, mo = int(m.group(1)), int(m.group(2))
        try:
            cand = datetime.now().replace(month=mo, day=d)
        except ValueError:
            return None
        if cand <= datetime.now():
            cand = cand.replace(year=cand.year + 1)
        return cand
    return None


@function_tool()
async def create_time_capsule(title: str, message: str, open_date: str) -> str:
    """Seal a note to your future self — it stays locked until the date arrives.

    Args:
        title: Short label, e.g. "goals after graduation"
        message: The letter/content to seal
        open_date: e.g. "2027-05-20", "20-05-2027", "in 6 months", "15-08"
    """
    when = _parse_open_date(open_date)
    if not when:
        return ("❌ Couldn't understand that date. Try: 2027-05-20 · 20-05-2027 · "
                "'in 6 months' · 'in 30 days' · '15-08' (next occurrence).")
    if (when - datetime.now()).total_seconds() < 3600:
        return "⏳ Unlock date must be at least 1 hour in the future."
    conn = _db()
    cur = conn.execute(
        "INSERT INTO time_capsules (title,message,open_at,created_at) VALUES (?,?,?,?)",
        (title.strip(), message.strip(), when.isoformat(), datetime.now().isoformat()),
    )
    n = conn.execute("SELECT COUNT(*) c FROM time_capsules").fetchone()["c"]
    conn.commit(); conn.close()
    days = int((when - datetime.now()).days)
    return (
        f"🔒 TIME CAPSULE SEALED #{cur.lastrowid}\n"
        f"   📛 {title}\n"
        f"   🔓 Opens: {when.strftime('%d %b %Y')} ({days} day(s) from now)\n"
        f"You have {n} capsule(s). Future-you says thanks."
    )


@function_tool()
async def check_time_capsules() -> str:
    """List all time capsules. Due ones OPEN here (content revealed once, then
    kept as 'opened'); future ones stay sealed."""
    conn = _db()
    rows = conn.execute("SELECT * FROM time_capsules ORDER BY open_at").fetchall()
    now_iso = datetime.now().isoformat()

    newly_due = [r for r in rows if not r["opened"] and r["open_at"] <= now_iso]
    if newly_due:
        conn.execute(
            f"UPDATE time_capsules SET opened=1 WHERE id IN ({','.join('?'*len(newly_due))})",
            [r["id"] for r in newly_due],
        )
    conn.commit(); conn.close()

    if not rows:
        return ("⏳ No time capsules yet. Seal one: create_time_capsule(\"title\", "
                "\"message\", \"in 6 months\").")

    out = "⏳ YOUR TIME CAPSULES\n════════════════════\n"
    for r in rows:
        due = datetime.fromisoformat(r["open_at"])
        if r["opened"] or r["open_at"] <= now_iso:
            out += (f"\n🔓 #{r['id']} {r['title']} (opened)\n"
                    f"   “{r['message'][:400]}”\n"
                    f"   📅 Sealed {str(r['created_at'])[:10]} → opened {due.strftime('%d %b %Y')}\n")
        else:
            days = (due - datetime.now()).days
            out += (f"\n🔒 #{r['id']} {r['title']} — SEALED\n"
                    f"   Opens in {days} day(s): {due.strftime('%d %b %Y')}\n")
    if newly_due:
        out += "\n🎉 Capsule(s) above just UNLOCKED — also announced in morning briefs!"
    return out


@function_tool()
async def delete_time_capsule(capsule_id: int, confirm: bool = False) -> str:
    """Delete a capsule permanently (requires confirm=True).

    Args:
        capsule_id: The #id shown in check_time_capsules
        confirm: MUST be True
    """
    if not confirm:
        return "⛔ Confirmation required to destroy a capsule forever."
    conn = _db()
    cur = conn.execute("DELETE FROM time_capsules WHERE id=?", (int(capsule_id),))
    conn.commit(); ok = cur.rowcount; conn.close()
    return f"🗑️ Capsule #{capsule_id} destroyed." if ok else f"❌ No capsule #{capsule_id}."


def newly_unlocked_brief_line() -> str:
    """For morning brief: announce capsules that unlocked since last seen.
    Marks them opened so we don't nag repeatedly."""
    try:
        conn = _db()
        rows = conn.execute(
            "SELECT id,title FROM time_capsules WHERE opened=0 AND open_at<=?",
            (datetime.now().isoformat(),),
        ).fetchall()
        if not rows:
            return ""
        titles = ", ".join(f"“{r['title']}”" for r in rows[:3])
        conn.execute(
            f"UPDATE time_capsules SET opened=1 WHERE id IN ({','.join('?'*len(rows))})",
            [r["id"] for r in rows],
        )
        conn.commit(); conn.close()
        more = f" (+{len(rows)-3} more)" if len(rows) > 3 else ""
        return f"📬 Time capsule(s) unlocked overnight: {titles}{more}. Ask me to read them."
    except Exception:
        return ""
