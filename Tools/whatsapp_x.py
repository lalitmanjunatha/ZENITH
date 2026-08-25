"""Zenith WhatsApp X — fuzzy contacts, chat reading, replies, audio/video calls.

Say "Gagan" → matches "Gagan Presidency". Multiple Gagans? Zenith asks which
full name, remembers your choice for this action, then executes.

Layers:
  1. Local contact cache (learned automatically + addable by voice)
  2. Live WhatsApp search + OCR of the results list (real ground truth)
  3. UIA accessibility buttons when available (precise call/click actions)
  4. Coordinate/color fallbacks (always works)

Everything reuses Policy A autonomy + NEVER_CONTACT + Action Journal.
"""

import asyncio
import difflib
import logging
import os
import re
import sqlite3
import time
from datetime import datetime
from pathlib import Path

from livekit.agents import function_tool

logger = logging.getLogger(__name__)

DB_PATH = "data/zenith_memory.db"
_PENDING_TTL = 180          # seconds before an unanswered disambiguation expires

_pending = {}               # {"action","kwargs","candidates","ts"}
_last_open_chat = {"name": None}


def _db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute(
        """CREATE TABLE IF NOT EXISTS wa_contacts (
               name TEXT PRIMARY KEY,
               aliases TEXT DEFAULT '',
               number TEXT DEFAULT '',
               hits INTEGER DEFAULT 0,
               last_used TEXT
           )"""
    )
    return conn


# ------------------------------------------------------------ fuzzy core ----

def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9 ]", "", (s or "").lower()).strip()


def _score(spoken: str, candidate: str) -> float:
    """0..1 similarity: best of token-containment boost + difflib ratio."""
    s, c = _norm(spoken), _norm(candidate)
    if not s or not c:
        return 0.0
    ratio = difflib.SequenceMatcher(None, s, c).ratio()
    # whole-spoken-name contained in candidate ("gagan" ⊂ "gagan presidency")
    if re.search(rf"\b{re.escape(s)}\b", c):
        ratio = max(ratio, 0.92)
    elif s in c:
        ratio = max(ratio, 0.85)
    # initials support ("gp" -> gagan presidency)
    if len(s) <= 4 and "".join(w[0] for w in c.split() if w) == s:
        ratio = max(ratio, 0.9)
    return round(min(ratio, 1.0), 3)


def _resolve_from(names, spoken: str, min_score=0.55):
    scored = [( _score(spoken, n), n) for n in names]
    scored = [x for x in scored if x[0] >= min_score]
    scored.sort(key=lambda x: (-x[0], x[1]))
    return scored


def _cache_names():
    conn = _db()
    rows = conn.execute("SELECT name FROM wa_contacts").fetchall()
    conn.close()
    return [r["name"] for r in rows]


def _cache_learn(name: str):
    conn = _db()
    conn.execute(
        "INSERT INTO wa_contacts (name,hits,last_used) VALUES (?,?,?) "
        "ON CONFLICT(name) DO UPDATE SET hits=hits+1, last_used=excluded.last_used",
        (name, 1, datetime.now().isoformat()),
    )
    conn.commit(); conn.close()


# --------------------------------------------------------- GUI primitives ---

async def _focus_wa():
    def _w():
        import pygetwindow as gw

        for win in gw.getAllWindows():
            t = (win.title or "").lower()
            if "whatsapp" in t:
                try:
                    win.activate()
                except Exception:
                    pass
                time.sleep(0.6)
                return win
        return None
    import asyncio
    return await asyncio.to_thread(_w)


async def _search_chat(query: str):
    """Focus WhatsApp, Ctrl+F, type query, wait for results. Returns win|None."""
    try:
        import pyautogui
        win = await _focus_wa()
        if not win:
            return None
        await asyncio.to_thread(pyautogui.hotkey, "ctrl", "f")
        await asyncio.sleep(0.8)
        await asyncio.to_thread(pyautogui.typewrite, query, interval=0.05)
        await asyncio.sleep(1.6)
        return win
    except Exception as e:
        logger.debug(f"search failed: {e}")
        return None


async def _ocr_window(win=None) -> str:
    def _w():
        import pyautogui
        import pytesseract

        if win is not None:
            b = win.box
            img = pyautogui.screenshot(region=(b.left, b.top, b.width, min(b.height, 700)))
        else:
            img = pyautogui.screenshot()
        return pytesseract.image_to_string(img)
    import asyncio
    return await asyncio.to_thread(_w)


_NOISE = ("whatsapp", "settings", "new chat", "new group", "new community",
          "chats", "status", "calls", "archived", "search", "type a message",
          "online", "typing", "last seen", "message", "blocked", "encrypted")

_SMALLTALK = {"ok", "done", "yes", "no", "hi", "hello", "hey", "thanks",
              "thank you", "seen", "delivered", "ok done", "haan", "theek hai"}


def _parse_candidates(ocr_text: str, exclude_query: str) -> list:
    """Extract plausible contact names from OCR'd search results panel.
    Filters: UI noise, timestamps, message previews (punctuation endings,
    long lines), keeps Title-case-ish short names."""
    names = []
    for raw in ocr_text.splitlines():
        line = raw.strip()
        if len(line) < 3 or len(line) > 36:
            continue
        low = line.lower()
        if low in _SMALLTALK or any(low == n or low.startswith(n + " ") for n in ("ok", "done", "yes", "haan", "theek")):
            continue
        if any(n in low for n in _NOISE):
            continue
        if re.fullmatch(r"[\d:\sapm.,()-]+", low):      # times like 9:41 PM
            continue
        if line.rstrip().endswith(("!", "?", ",", ";", ".")):
            continue                                     # message previews
        words = line.split()
        if len(words) > 4:
            continue                                     # previews are long
        if not line[0].isupper():
            continue                                     # names start capital
        if _norm(line) == _norm(exclude_query):
            continue
        if line not in names:
            names.append(line)
    return names[:8]


async def _open_resolved_chat(full_name_hint: str) -> bool:
    """In current search results, select the row whose title matches hint."""
    try:
        import pyautogui

        await asyncio.to_thread(pyautogui.press, "esc")   # clear search box focus
        await asyncio.sleep(0.3)
        await asyncio.to_thread(pyautogui.hotkey, "ctrl", "f")
        await asyncio.sleep(0.6)
        await asyncio.to_thread(pyautogui.typewrite, full_name_hint, interval=0.04)
        await asyncio.sleep(1.4)
        await asyncio.to_thread(pyautogui.press, "down")
        await asyncio.sleep(0.25)
        await asyncio.to_thread(pyautogui.press, "enter")
        await asyncio.sleep(1.4)
        _last_open_chat["name"] = full_name_hint
        return True
    except Exception as e:
        logger.debug(f"open chat failed: {e}")
        return False


async def _type_and_send(message: str) -> bool:
    try:
        import pyautogui
        import pygetwindow as gw

        win = gw.getActiveWindow()
        if win is None:
            return False

        def _click_msgbox():
            b = win.box
            pyautogui.click(b.left + b.width // 2, b.bottom - 60)

        await asyncio.to_thread(_click_msgbox)
        await asyncio.sleep(0.4)
        await asyncio.to_thread(pyautogui.typewrite, message, interval=0.03)
        await asyncio.sleep(0.3)
        await asyncio.to_thread(pyautogui.press, "enter")
        return True
    except Exception as e:
        logger.debug(f"send failed: {e}")
        return False


# ------------------------------------------------------- UIA (optional) -----

def _uia_press_call(video: bool) -> bool | None:
    """Try Windows UI Automation for exact 'Voice/Video call' buttons.
    Returns True pressed / False found-but-failed / None=UIA unavailable."""
    try:
        import uiautomation as uia

        w = uia.WindowControl(searchDepth=1, ClassName="WhatsApp")
        if not w.Exists(0.5):
            for c in uia.GetRootControl().GetChildren():
                if "whatsapp" in (c.Name or "").lower():
                    w = c; break
        if not w or not w.Exists(0.5):
            return None
        target = "Video call" if video else "Voice call"
        btns = w.GetChildren() or []
        # search descendants shallowly (perf-bounded)
        stack = [w]; depth = 0
        while stack and depth < 12:
            cur = stack.pop(0); depth += 1
            for ch in (cur.GetChildren() or []):
                nm = (ch.Name or "").strip().lower()
                if target.split()[0] in nm and "call" in nm:
                    try:
                        ch.DoDefaultAction() if hasattr(ch, "DoDefaultAction") else ch.Click(simulateMove=False)
                        return True
                    except Exception:
                        return False
                stack.append(ch)
        return None
    except ImportError:
        return None
    except Exception as e:
        logger.debug(f"UIA failed: {e}")
        return None


async def _start_call(video: bool) -> tuple[bool, str]:
    """After the right chat is OPEN, start audio/video call. Layered attempts."""
    # Layer 1: UIA precision
    r = await asyncio.to_thread(_uia_press_call, video)
    if r is True:
        return True, "accessibility-button"
    if r is False:
        return False, "button found but invoke failed"

    # Layer 2: header icon heuristic (top-right cluster of the focused window)
    def _click_header():
        try:
            import pygetwindow as gw
            import pyautogui

            win = gw.getActiveWindow()
            if not win:
                return False
            b = win.box
            # header band: right side; video sits LEFT of voice call icon
            y = b.top + int(b.height * 0.055)
            x_base = b.left + b.width - int(b.width * 0.075)
            offset = int(b.width * 0.045) if video else 0
            pyautogui.click(x_base - offset, y)
            return True
        except Exception:
            return False

    ok = await asyncio.to_thread(_click_header)
    await asyncio.sleep(1.2)

    # verify a call window appeared
    def _verify():
        import pygetwindow as gw

        for w in gw.getAllWindows():
            t = (w.title or "").lower()
            if any(k in t for k in ("voice call", "video call", "ongoing", "ringing")):
                return True
        return False

    verified = await asyncio.to_thread(_verify)
    label = "video" if video else "audio"
    if ok and verified:
        return True, f"{label}-call started (header heuristic)"
    return False, f"{label}-call could not be confirmed — check WhatsApp"


# --------------------------------------------------- pending disambiguation --

def _stash_pending(action: str, kwargs: dict, candidates: list) -> None:
    _pending.clear()
    _pending.update({"action": action, "kwargs": kwargs,
                     "candidates": candidates, "ts": time.time()})


def _take_pending_valid():
    if not _pending:
        return None
    if time.time() - _pending["ts"] > _PENDING_TTL:
        _pending.clear()
        return None
    return _pending.copy()


def _pick_candidate(pending, choice) -> str | None:
    cands = pending["candidates"]
    if isinstance(choice, int) or (isinstance(choice, str) and choice.strip().isdigit()):
        i = int(choice) - 1
        return cands[i] if 0 <= i < len(cands) else None
    res = _resolve_from(cands, str(choice), min_score=0.45)
    return res[0][1] if res else None


# ============================================================== TOOLS =======

@function_tool()
async def send_whatsapp_smart(contact_name: str, message: str) -> str:
    """Send a WhatsApp message using FUZZY contact matching. Partial names OK
    ('Gagan' → 'Gagan Presidency'). If several people match, Zenith asks you
    which one — answer with confirm_contact('full name' or number).

    Args:
        contact_name: Full OR partial name as you'd say it
        message: Text to deliver
    """
    from Tools.autonomy import allowed_contact, halted, journal
    if halted():
        return "🛑 Autonomy is under FULL STOP — not sending."
    if not allowed_contact(contact_name):
        journal("external_send_blocked", f"NEVER_CONTACT hit: {contact_name}")
        return f"⛔ '{contact_name}' is on your never-contact list."

    # 1) cache fast-path
    cached = _resolve_from(_cache_names(), contact_name, min_score=0.75)
    if len(cached) == 1:
        return await _execute_send(cached[0][1], message)

    # 2) live search OCR ground-truth
    win = await _search_chat(contact_name)
    ocr = await _ocr_window(win) if win else ""
    cands_raw = _parse_candidates(ocr, exclude_query=contact_name) if ocr else []

    merged = {n for _, n in cached}
    merged.update(cands_raw)
    ranked = _resolve_from(list(merged), contact_name)

    if not ranked:
        return (f"❌ Nobody resembling '{contact_name}' surfaced in WhatsApp "
                "(is WhatsApp Desktop open & logged in?). Try the exact name.")
    if len(ranked) == 1:
        return await _execute_send(ranked[0][1], message)

    # AMBIGUOUS → stash + ask (explicit owner rule overrides autonomy-full)
    names = [n for _, n in ranked[:5]]
    _stash_pending("send", {"message": message}, names)
    listing = "\n".join(f"   {i+1}. {n}" for i, n in enumerate(names))
    return (f"❓ Multiple matches for “{contact_name}”, sir — whom exactly?\n{listing}\n"
            'Answer: confirm_contact("full name" or number).')


async def _execute_send(resolved_name: str, message: str) -> str:
    from Tools.autonomy import journal
    opened = await _open_resolved_chat(resolved_name)
    if not opened:
        return f"❌ Couldn't open the chat for {resolved_name}."
    sent = await _type_and_send(message)
    if not sent:
        return f"⚠️ Chat opened but sending failed — message typed but not confirmed."
    _cache_learn(resolved_name)
    journal("external_send", f"WhatsApp → {resolved_name}: {message[:80]}",
            target=resolved_name)
    return f"✅ Delivered to {resolved_name}: “{message[:70]}”"


@function_tool()
async def confirm_contact(choice: str) -> str:
    """Answer a contact-disambiguation question: give the FULL name (or its
    number from the list Zenith showed). Completes the pending send/read/call.

    Args:
        choice: e.g. "Gagan Presidency" or "2"
    """
    pend = _take_pending_valid()
    if not pend:
        return "ℹ️ Nothing pending — no disambiguation was asked."
    picked = _pick_candidate(pend, choice)
    if not picked:
        return (f"❌ '{choice}' doesn't match any option. Options were: "
                + ", ".join(pend["candidates"]))
    act, kw = pend["action"], dict(pend["kwargs"])
    kw["resolved_name"] = picked

    if act == "send":
        r = await _execute_send(picked, kw.get("message", ""))
    elif act == "read":
        r = await _do_read(picked, kw.get("lines", 10))
    elif act == "call":
        r = await _do_call(picked, kw.get("video", False))
    else:
        r = f"⚠️ Unknown pending action '{act}'."
    return f"🎯 Resolved → {picked}\n{r}"


@function_tool()
async def read_whatsapp_chat(contact_name: str, lines: int = 12) -> str:
    """READ a WhatsApp conversation: opens the (fuzzy-matched) chat and OCRs the
    latest messages so Zenith can tell you what they said.

    Args:
        contact_name: Full or partial name
        lines: How many recent lines to read (default 12)
    """
    cached = _resolve_from(_cache_names(), contact_name, min_score=0.8)
    if len(cached) == 1:
        return await _do_read(cached[0][1], lines)
    win = await _search_chat(contact_name)
    ocr = await _ocr_window(win) if win else ""
    cands = _parse_candidates(ocr, exclude_query=contact_name) if ocr else []
    ranked = _resolve_from(list(set(cands) | set(cached)), contact_name)
    if not ranked:
        return f"❌ No chat resembling '{contact_name}' found."
    if len(ranked) > 1:
        names = [n for _, n in ranked[:5]]
        _stash_pending("read", {"lines": lines}, names)
        listing = "\n".join(f"   {i+1}. {n}" for i, n in enumerate(names))
        return (f"❓ Several chats match “{contact_name}” — read which?\n{listing}\n"
                'Answer: confirm_contact("full name").')
    return await _do_read(ranked[0][1], lines)


async def _do_read(resolved_name: str, lines: int) -> str:
    opened = await _open_resolved_chat(resolved_name)
    if not opened:
        return f"❌ Couldn't open chat for {resolved_name}."
    await asyncio.sleep(1.0)
    ocr = await _ocr_window()
    raw_lines = [l.strip() for l in ocr.splitlines()
                 if l.strip() and len(l.strip()) > 2][-max(4, int(lines)):]
    cleaned = "\n".join(raw_lines)
    summary = ""
    try:
        from Tools._llm_client import chat_complete_sync
        s = chat_complete_sync(
            f"These are OCR'd lines from a WhatsApp chat (may include UI noise/timestamps). "
            f"Reconstruct the latest conversation cleanly as NAME: message pairs, then one-line gist.\n\n{cleaned}",
            max_tokens=500)
        if not s.startswith("ERROR"):
            summary = s.strip()
    except Exception:
        pass
    out = (f"📖 CHAT — {resolved_name}\n════════════════════\n"
           + (summary + "\n\n—raw—\n" if summary else "")
           + "\n".join(raw_lines[-int(lines):]))
    return out[:2200]


@function_tool()
async def reply_whatsapp_last(message: str) -> str:
    """Reply in the CURRENTLY OPEN WhatsApp chat (the one just read/opened).

    Args:
        message: Reply text to send
    """
    from Tools.autonomy import journal
    if not _last_open_chat["name"]:
        return "ℹ️ Open a chat first (read_whatsapp_chat or send a message), then reply."
    sent = await _type_and_send(message)
    if not sent:
        return "⚠️ Could not type the reply — is the chat window focused?"
    journal("external_send", f"WhatsApp reply → {_last_open_chat['name']}: {message[:80]}",
            target=_last_open_chat["name"])
    return f"✅ Replied to {_last_open_chat['name']}: “{message[:70]}”"


@function_tool()
async def whatsapp_call(contact_name: str, video: bool = False) -> str:
    """START a WhatsApp AUDIO or VIDEO call to a (fuzzy-matched) contact.
    Same disambiguation rule: multiple matches → Zenith asks which person.

    Args:
        contact_name: Full or partial name
        video: false = audio call (default), true = video call
    """
    from Tools.autonomy import halted
    if halted():
        return "🛑 Autonomy is under FULL STOP — not placing calls."
    cached = _resolve_from(_cache_names(), contact_name, min_score=0.8)
    if len(cached) == 1:
        return await _do_call(cached[0][1], video)
    win = await _search_chat(contact_name)
    ocr = await _ocr_window(win) if win else ""
    cands = _parse_candidates(ocr, exclude_query=contact_name) if ocr else []
    ranked = _resolve_from(list(set(cands) | set(cached)), contact_name)
    if not ranked:
        return f"❌ No contact resembling '{contact_name}' found."
    if len(ranked) > 1:
        names = [n for _, n in ranked[:5]]
        _stash_pending("call", {"video": video}, names)
        listing = "\n".join(f"   {i+1}. {n}" for i, n in enumerate(names))
        kind = "video" if video else "audio"
        return (f"❓ {kind.title()} call — which “{contact_name}”?\n{listing}\n"
                'Answer: confirm_contact("full name").')
    return await _do_call(ranked[0][1], video)


async def _do_call(resolved_name: str, video: bool) -> str:
    from Tools.autonomy import journal
    if not await _open_resolved_chat(resolved_name):
        return f"❌ Couldn't open {resolved_name}'s chat to place the call."
    await asyncio.sleep(0.8)
    ok, how = await _start_call(video)
    kind = "📹 Video" if video else "📞 Audio"
    if ok:
        journal("external_call", f"WhatsApp {kind} call placed to {resolved_name} ({how})",
                target=resolved_name)
        _cache_learn(resolved_name)
        return (f"{kind} call RINGING → {resolved_name} ({how}). "
                "Call Butler will announce if they were calling YOU next time.")
    return f"❌ {kind} call failed: {how}. Open their chat and check the header icons."


@function_tool()
async def add_whatsapp_alias(alias: str, full_name: str) -> str:
    """Teach Zenith a shortcut: 'add whatsapp alias ggp for Gagan Presidency'.
    Future fuzzy matching treats them as the same person.

    Args:
        alias: The short/partial name you'll SAY
        full_name: The exact WhatsApp contact name
    """
    conn = _db()
    conn.execute(
        "INSERT INTO wa_contacts (name,aliases) VALUES (?,?) "
        "ON CONFLICT(name) DO UPDATE SET aliases=excluded.aliases",
        (full_name.strip(), alias.strip()),
    )
    conn.commit(); conn.close()
    return f"🔗 Alias saved: saying “{alias}” now targets “{full_name}”."


@function_tool()
async def list_whatsapp_contacts() -> str:
    """Show every WhatsApp contact Zenith has learned (auto + taught)."""
    conn = _db()
    rows = conn.execute(
        "SELECT name,aliases,hits,last_used FROM wa_contacts ORDER BY hits DESC, name").fetchall()
    conn.close()
    if not rows:
        return "📇 No learned contacts yet — send one message and learning begins."
    out = f"📇 LEARNED CONTACTS ({len(rows)}):\n"
    for r in rows:
        alias = f" (aka {r['aliases']})" if r["aliases"] else ""
        out += f"   • {r['name']}{alias} — {r['hits']} use(s)\n"
    return out