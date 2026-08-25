"""Communications Hub — email digest/triage/read-aloud, WhatsApp smart-reply
drafting, scheduled messages, and a birthday tracker.

Honesty & safety model:
- Email needs GMAIL_USER + GMAIL_APP_PASSWORD (IMAP). Missing creds → clear
  setup guidance, never crashes. Nothing is deleted or auto-sent.
- WhatsApp drafter only READS the visible chat (screen OCR) and DRAFTS a
  suggestion. Sending stays with you / existing explicit send tools.
"""

import asyncio
import logging
import os
import sqlite3
from datetime import datetime, timedelta
from email import policy
from email.parser import BytesParser

from livekit.agents import function_tool

logger = logging.getLogger(__name__)

DB_PATH = "data/zenith_memory.db"

DEFAULT_RULES = [
    ("invoice", "bills"), ("payment", "bills"), ("due", "bills"), ("emi", "bills"),
    ("deadline", "work"), ("assignment", "work"), ("interview", "work"),
    ("verify", "security"), ("otp", "security"), ("password", "security"),
    ("offer", "promotions"), ("sale", "promotions"), ("% off", "promotions"),
    ("newsletter", "newsletter"), ("unsubscribe", "newsletter"),
]

PRIORITY_WORDS = ["urgent", "asap", "today", "deadline", "action required",
                  "interview", "invoice", "payment due", "verify", "exam", "result"]


def _db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS email_triage_rules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            keyword TEXT UNIQUE,
            category TEXT
        );
        CREATE TABLE IF NOT EXISTS scheduled_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            channel TEXT,
            recipient TEXT,
            message TEXT,
            send_at TEXT,
            status TEXT DEFAULT 'pending',
            created_at TEXT
        );
        CREATE TABLE IF NOT EXISTS birthdays (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            month INTEGER,
            day INTEGER,
            relationship TEXT,
            gift_ideas TEXT
        );
        """
    )
    # seed default rules once
    cur = conn.execute("SELECT COUNT(*) c FROM email_triage_rules").fetchone()
    if cur["c"] == 0:
        conn.executemany("INSERT OR IGNORE INTO email_triage_rules (keyword,category) VALUES (?,?)", DEFAULT_RULES)
        conn.commit()
    return conn


# --------------------------------------------------------------- gmail -------

def _gmail_creds():
    user = os.getenv("GMAIL_USER", "").strip()
    pwd = os.getenv("GMAIL_APP_PASSWORD", "").strip()
    return user, pwd


def _fetch_emails(max_n: int = 25, unread_only: bool = True):
    """Fetch recent emails via IMAP. Returns list of dicts or raises RuntimeError with guidance."""
    user, pwd = _gmail_creds()
    if not user or not pwd:
        raise RuntimeError(
            "EMAIL_NOT_CONFIGURED: set GMAIL_USER and GMAIL_APP_PASSWORD in .env "
            "(Google Account → Security → 2-Step Verification → App passwords)"
        )
    import imaplib

    mail = imaplib.IMAP4_SSL("imap.gmail.com", 993)
    mail.login(user, pwd)
    mail.select("INBOX")
    crit = "(UNSEEN)" if unread_only else "(ALL)"
    status, data = mail.search(None, crit)
    ids = data[0].split()
    recent = ids[-max_n:] if len(ids) > max_n else ids
    emails = []
    for eid in reversed(recent):                      # newest first
        status, msg_data = mail.fetch(eid, "(RFC822)")
        if status != "OK":
            continue
        msg = BytesParser(policy=policy.default).parsebytes(msg_data[0][1])
        subj = str(msg.get("Subject", ""))[:120]
        frm = str(msg.get("From", ""))
        date_hdr = str(msg.get("Date", ""))
        body = ""
        try:
            if msg.is_multipart():
                for part in msg.walk():
                    if part.get_content_type() == "text/plain":
                        body = part.get_content()
                        break
            else:
                body = msg.get_content()
        except Exception:
            body = ""
        emails.append({
            "id": eid.decode(), "from": frm, "subject": subj,
            "snippet": " ".join(str(body).split())[:220], "date": date_hdr,
        })
    try:
        mail.logout()
    except Exception:
        pass
    return emails


def _classify(email: dict) -> tuple:
    """Rule-based classification using stored rules. Returns (category, priority_bool)."""
    text = (email["subject"] + " " + email["from"] + " " + email["snippet"]).lower()
    conn = _db()
    rules = conn.execute("SELECT keyword,category FROM email_triage_rules").fetchall()
    conn.close()
    cats = []
    for r in rules:
        if r["keyword"].lower() in text:
            cats.append(r["category"])
    category = cats[0] if cats else ("personal" if any(c.isalpha() for c in email["from"]) and "no-reply" not in text else "other")
    priority = any(w in text for w in PRIORITY_WORDS) or category in ("bills", "work", "security")
    return category, priority


@function_tool()
async def unread_digest(max_emails: int = 10) -> str:
    """UNIFIED INBOX DIGEST: fetches your unread Gmail, classifies each by rules
    (bills/work/security/promotions/personal), flags important ones.

    Args:
        max_emails: How many recent unread to include (default 10)
    """
    try:
        mails = _fetch_emails(max_n=max(1, min(int(max_emails), 30)), unread_only=True)
    except RuntimeError as e:
        if "EMAIL_NOT_CONFIGURED" in str(e):
            return f"📧 {e}"
        return f"❌ Gmail fetch failed: {e}"
    except Exception as e:
        return f"❌ Gmail fetch failed: {e}"

    if not mails:
        return "📧 Inbox zero! No unread emails."

    out = f"📧 UNREAD DIGEST ({len(mails)})\n════════════════════\n"
    important = []
    for m in mails:
        cat, prio = _classify(m)
        icon = {"bills": "💳", "work": "💼", "security": "🔐",
                "promotions": "🏷️", "newsletter": "📰"}.get(cat, "✉️")
        flag = " ⭐" if prio else ""
        out += f"{icon}{flag} [{cat}] {m['subject'][:70]}\n    from: {m['from'][:50]}\n"
        if prio:
            important.append(m)
    if important:
        out += f"\n⭐ {len(important)} need attention — say \"read my important emails\"."
    return out


@function_tool()
async def read_important_emails(count: int = 5) -> str:
    """Read-aloud briefing of your most important unread emails (priority-sorted),
    formatted for speech when your hands are busy.

    Args:
        count: Max emails to read out (default 5)
    """
    try:
        mails = _fetch_emails(max_n=25, unread_only=True)
    except RuntimeError as e:
        if "EMAIL_NOT_CONFIGURED" in str(e):
            return f"📧 {e}"
        return f"❌ Gmail fetch failed: {e}"
    except Exception as e:
        return f"❌ Gmail fetch failed: {e}"

    scored = []
    for m in mails:
        cat, prio = _classify(m)
        if prio:
            words = sum(1 for w in PRIORITY_WORDS if w in (m["subject"] + m["snippet"]).lower())
            scored.append((words, cat, m))
    scored.sort(key=lambda x: x[0], reverse=True)

    if not scored:
        return "📭 No important unread emails right now — you're all clear."
    out = f"🗣️ IMPORTANT EMAILS ({min(int(count), len(scored))}) — spoken briefing:\n\n"
    for i, (_, cat, m) in enumerate(scored[: int(count)], 1):
        sender = m["from"].split("<")[0].strip()[:30]
        out += (
            f"{i}. From {sender}: “{m['subject']}”.\n"
            f"   Category {cat}. Summary: {m['snippet'][:160]}…\n\n"
        )
    return out.strip()


# ------------------------------------------------------------ triage -------

@function_tool()
async def add_triage_rule(keyword: str, category: str) -> str:
    """Add an email classification rule: emails containing `keyword` get sorted
    into `category` (e.g., college→work, swiggy→orders).

    Args:
        keyword: Case-insensitive match against subject/from/body snippet
        category: Free-form bucket name
    """
    kw = keyword.strip().lower()
    cat = category.strip().lower() or "other"
    conn = _db()
    conn.execute("INSERT INTO email_triage_rules (keyword,category) VALUES (?,?) "
                 "ON CONFLICT(keyword) DO UPDATE SET category=excluded.category", (kw, cat))
    n = conn.execute("SELECT COUNT(*) c FROM email_triage_rules").fetchone()["c"]
    conn.commit(); conn.close()
    return f"✅ Rule saved: '{kw}' → {cat}. Total rules: {n}."


@function_tool()
async def list_triage_rules() -> str:
    """List all your email triage rules."""
    conn = _db()
    rows = conn.execute("SELECT keyword,category FROM email_triage_rules ORDER BY id").fetchall()
    conn.close()
    out = f"🗂️ {len(rows)} TRIAGE RULES:\n" + "\n".join(f"  • '{r['keyword']}' → {r['category']}" for r in rows)
    return out


# ------------------------------------------------- whatsapp smart drafts ----

@function_tool()
async def draft_whatsapp_reply(style_hint: str = "") -> str:
    """WHATSAPP SMART REPLY: reads the currently open WhatsApp chat from your
    screen (OCR), understands context, and DRAFTS a suggested reply.
    Nothing is sent or typed automatically — you stay in control.

    Args:
        style_hint: Optional tone override e.g. "formal", "short", "funny"
    """
    try:
        import pygetwindow as gw
        import pyautogui
        import pytesseract

        win = None
        for w in gw.getAllWindows():
            if w.title and "whatsapp" in w.title.lower():
                win = w
                break
        if win is None:
            return "❌ Open WhatsApp (desktop/web) with the chat visible, then ask again."

        try:
            await asyncio.to_thread(win.activate)
            await asyncio.sleep(1.2)
        except Exception:
            pass
        box = (win.box.left, win.box.top, win.box.width, win.box.height)
        shot = await asyncio.to_thread(pyautogui.screenshot, region=box)
        text = await asyncio.to_thread(pytesseract.image_to_string, shot)
        lines = [l.strip() for l in text.splitlines() if len(l.strip()) > 2]
        chat_context = "\n".join(lines[-18:])          # last visible chunk
        if len(chat_context) < 20:
            return "❌ Couldn't read enough chat text on screen. Scroll slightly and retry."

        from Tools._llm_client import chat_complete
        from Tools.fun_personality import persona_system_line

        sysline = persona_system_line()
        style = f"Tone: {style_hint}." if style_hint else "Match the chat's natural tone."
        prompt = (
            "Here is OCR text from an open WhatsApp chat (may contain UI noise):\n"
            f"{chat_context}\n\nWrite ONE natural reply message I could send next. "
            f"{style} Output ONLY the message text, nothing else. Keep it under 60 words."
        )
        draft = await chat_complete(prompt, system=sysline or "You draft short human-like chat replies.", temperature=0.6, max_tokens=500)
        if draft.startswith("ERROR"):
            return f"❌ Draft generation failed: {draft}\nChat context captured:\n{chat_context[-300:]}"
        draft = draft.strip().strip('"')
        return (
            f"💬 SUGGESTED REPLY (not sent):\n──────────\n{draft}\n──────────\n"
            "➡ Say \"send it\" to have me type+send, or \"type it\" to just type without sending."
        )
    except Exception as e:
        return f"❌ Drafting failed: {e}"


# --------------------------------------------------- scheduled messages -----

@function_tool()
async def schedule_message(channel: str, recipient: str, message: str, send_at: str) -> str:
    """Schedule a WhatsApp message for later. The background dispatcher sends it
    automatically at the chosen time (uses the normal WhatsApp desktop flow).

    Args:
        channel: Only "whatsapp" supported today
        recipient: Contact name as saved in WhatsApp
        message: Text to deliver
        send_at: ISO time "2025-12-31T09:00" or friendly "tomorrow 9am"/"in 2 hours"
    """
    ch = channel.strip().lower()
    if ch != "whatsapp":
        return "⚠️ Only 'whatsapp' channel is wired today. Email scheduling coming with SMTP creds."
    when = _parse_time(send_at)
    if not when:
        return f"❌ Couldn't understand time '{send_at}'. Try '2025-12-31T09:00' or 'in 2 hours'."
    conn = _db()
    cur = conn.execute(
        "INSERT INTO scheduled_messages (channel,recipient,message,send_at,status,created_at) VALUES (?,?,?,?,?,?)",
        (ch, recipient, message, when.isoformat(), "pending", datetime.now().isoformat()),
    )
    conn.commit(); conn.close()
    return (f"⏰ Scheduled #{cur.lastrowid}: WhatsApp to '{recipient}' at {when.strftime('%d %b %Y %I:%M %p')}\n"
            f"📝 \"{message[:80]}\"")


def _parse_time(s: str):
    s = s.strip().lower()
    now = datetime.now()
    try:
        return datetime.fromisoformat(s)
    except ValueError:
        pass
    import re
    m = re.search(r"in\s+(\d+)\s*(minute|min|hour|hr|day)", s)
    if m:
        n = int(m.group(1)); unit = m.group(2)
        delta = timedelta(minutes=n) if unit.startswith("mi") else \
                timedelta(hours=n) if unit.startswith(("h",)) else timedelta(days=n)
        return now + delta
    m = re.search(r"(tomorrow|today)\s*(\d{1,2})(?::(\d{2}))?\s*(am|pm)?", s)
    if m:
        day = now + (timedelta(days=1) if m.group(1) == "tomorrow" else timedelta(0))
        hh = int(m.group(2)); mm = int(m.group(3) or 0); ap = m.group(4)
        if ap == "pm" and hh < 12: hh += 12
        if ap == "am" and hh == 12: hh = 0
        try:
            return day.replace(hour=hh, minute=mm, second=0, microsecond=0)
        except ValueError:
            return None
    return None


async def dispatch_due_messages():
    """Send any due scheduled WhatsApp messages (called by agent loop)."""
    conn = _db()
    rows = conn.execute(
        "SELECT * FROM scheduled_messages WHERE status='pending' AND send_at <= ?",
        (datetime.now().isoformat(),),
    ).fetchall()
    conn.close()
    if not rows:
        return 0
    from Tools.send_whatsapp_message import send_whatsapp_message as _wa

    sent = 0
    for r in rows:
        try:
            res = await _wa(contact=r["recipient"], message=r["message"])
            ok = not str(res).startswith("❌")
            status = "sent" if ok else "failed"
        except Exception as e:
            status = "failed"; res = str(e)
        c2 = _db()
        c2.execute("UPDATE scheduled_messages SET status=? WHERE id=?", (status, r["id"]))
        c2.commit(); c2.close()
        print(f"📨 Scheduled #{r['id']} → {status}")
        sent += ok
        await asyncio.sleep(2)
    return sent


@function_tool()
async def list_scheduled_messages() -> str:
    """List all pending scheduled messages."""
    conn = _db()
    rows = conn.execute(
        "SELECT * FROM scheduled_messages WHERE status='pending' ORDER BY send_at").fetchall()
    conn.close()
    if not rows:
        return "⏰ No pending scheduled messages."
    out = f"⏰ {len(rows)} PENDING:\n"
    for r in rows:
        dt = str(r["send_at"])[:16].replace("T", " ")
        out += f"  #{r['id']} {dt} → WhatsApp '{r['recipient']}': {r['message'][:50]}\n"
    return out


@function_tool()
async def cancel_scheduled_message(message_id: int) -> str:
    """Cancel a pending scheduled message by its ID."""
    conn = _db()
    cur = conn.execute("UPDATE scheduled_messages SET status='cancelled' WHERE id=? AND status='pending'", (int(message_id),))
    conn.commit(); n = cur.rowcount; conn.close()
    return f"✅ Cancelled #{message_id}." if n else f"❌ No pending message #{message_id}."


# ------------------------------------------------------------ birthdays -----

@function_tool()
async def add_birthday(name: str, date_text: str, relationship: str = "", gift_ideas: str = "") -> str:
    """Remember someone's birthday. Accepts 'DD-MM', 'DD/MM', '15 Aug'.

    Args:
        name: Person's name
        date_text: e.g. "15-08", "15/08", or "15 aug"
        relationship: friend/brother/colleague…
        gift_ideas: Notes for future gifting
    """
    m, d = _parse_birthday(date_text)
    if not m:
        return f"❌ Couldn't parse '{date_text}'. Use DD-MM, DD/MM or '15 aug'."
    conn = _db()
    conn.execute("INSERT INTO birthdays (name,month,day,relationship,gift_ideas) VALUES (?,?,?,?,?)",
                 (name.strip(), m, d, relationship.strip(), gift_ideas.strip()))
    conn.commit(); conn.close()
    return f"🎂 Saved: {name}'s birthday on {_month_name(m)} {d}." + (f" Gift ideas noted." if gift_ideas else "")


def _parse_birthday(s: str):
    """Accepts 'DD-MM'/'DD/MM' (per docs), 'MM-DD' style numbers auto-swapped
    when unambiguous, and 'DD mon' text forms."""
    s = s.strip().lower()
    import re
    m = re.match(r"(\d{1,2})[\-/](\d{1,2})$", s)
    if m:
        a, b = int(m.group(1)), int(m.group(2))
        if a > 12 and b <= 12:
            dy, mo = a, b                      # was MM-DD style; treat b as month
        elif b > 12 and a <= 12:
            mo, dy = a, b                      # a is month, b day
        else:
            mo, dy = b, a                      # default: DD-MM per documented format
    else:
        months = {mn: i + 1 for i, mn in enumerate(
            ["jan","feb","mar","apr","may","jun","jul","aug","sep","oct","nov","dec"])}
        m2 = re.match(r"(\d{1,2})\s*([a-z]{3}).*$", s)
        if m2 and m2.group(2)[:3] in months:
            dy, mo = int(m2.group(1)), months[m2.group(2)[:3]]
        else:
            return None, None
    if 1 <= mo <= 12 and 1 <= dy <= 31:
        return mo, dy
    return None, None


def _month_name(m):
    return ["January","February","March","April","May","June","July","August",
            "September","October","November","December"][m - 1]


@function_tool()
async def check_birthdays(days_ahead: int = 14) -> str:
    """Which birthdays are coming up in the next N days? Also reminds of TODAY's.

    Args:
        days_ahead: Look-ahead window (default 14)
    """
    conn = _db()
    rows = conn.execute("SELECT * FROM birthdays").fetchall()
    conn.close()
    if not rows:
        return "🎂 No birthdays saved yet. Add with: add_birthday(name, 'DD-MM')."

    today = datetime.now().date()
    upcoming, todays = [], []
    for r in rows:
        try:
            bday_this = today.replace(month=r["month"], day=r["day"])
        except ValueError:                     # Feb 29 etc.
            bday_this = today.replace(month=r["month"], day=28)
        delta = (bday_this - today).days
        target = bday_this if delta >= 0 else bday_this.replace(year=today.year + 1)
        delta = (target - today).days
        entry = (delta, target, dict(r))
        if delta == 0:
            todays.append(entry)
        elif delta <= int(days_ahead):
            upcoming.append(entry)

    out = "🎂 BIRTHDAY RADAR\n════════════════════\n"
    for _, t, r in sorted(todays):
        out += f"🎉 TODAY: {r['name']}!" + (f" ({r['relationship']})" if r['relationship'] else "") + "\n"
        if r["gift_ideas"]:
            out += f"   💡 Gift ideas: {r['gift_ideas']}\n"
        out += "   ➡ Say \"draft greeting for NAME\".\n"
    for delta, t, r in sorted(upcoming):
        rel = f" ({r['relationship']})" if r["relationship"] else ""
        out += f"🎈 {t.strftime('%d %b')} in {delta} day(s): {r['name']}{rel}\n"
    if not todays and not upcoming:
        out += f"No birthdays in the next {days_ahead} days."
    return out.rstrip()


@function_tool()
async def draft_birthday_greeting(name: str) -> str:
    """Draft a warm, personal birthday message for someone (uses your persona
    style; works offline too). Not sent anywhere — copy/send it yourself or use
    the WhatsApp tools explicitly."""
    conn = _db()
    r = conn.execute("SELECT * FROM birthdays WHERE name LIKE ?", (f"%{name}%",)).fetchone()
    conn.close()
    rel = r["relationship"] if r else ""
    gifts = r["gift_ideas"] if r else ""

    from Tools._llm_client import chat_complete
    from Tools.fun_personality import persona_system_line

    extra = f" Mention gift idea subtly: {gifts}." if gifts else ""
    reltxt = f" They are my {rel}." if rel else ""
    prompt = f"Write ONE heartfelt but short WhatsApp birthday wish for {name}.{reltxt}{extra} Under 45 words, no quotes."
    msg = await chat_complete(prompt, system=persona_system_line() or "Warm friendly helper.", temperature=0.7, max_tokens=500)
    if msg.startswith("ERROR"):
        fallback = f"Happy Birthday, {name}! 🎉 Wishing you a fantastic year ahead filled with success and good health. Celebrate well!"
        return f"🎂 GREETING (offline template — LLM unavailable):\n{fallback}"
    return f"🎂 BIRTHDAY GREETING for {name} (not sent):\n──────────\n{msg.strip()}\n──────────"
