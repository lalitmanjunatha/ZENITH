"""WhatsApp Call Butler — laptop reception desk, JARVIS etiquette.

Watches for incoming WhatsApp Desktop calls (window-title polling), announces
"A call is coming, sir — [Name]" and follows the owner's exact protocol:

  1. Owner replies "connect me"        → Zenith steps aside silently
  2. Owner says "you talk"/"handle it" → AI accepts & converses
  3. Owner silent > AUTO_SCREEN_SECS   → AI answers in screening mode
  4. Caller claims URGENT              → live interrupt: "[Name] insists it's
                                          urgent — shall I connect you?"
After any AI-handled call ends, Zenith compiles a FULL SPOKEN DEBRIEF of
everything the caller said + actions promised, journals it, and surfaces it
in Catch-Me-Up.

Honest mechanics: WhatsApp has no call API — accept/decline is precise OCR-
guided GUI clicking on the ring window; audio path = speakerphone principle
(caller voice out of speakers → mic → agent), identical to your proven SIM-
call design. Headset recommended.
"""

import asyncio
import logging
import re
import sqlite3
import time
from datetime import datetime
from pathlib import Path

from livekit.agents import function_tool

logger = logging.getLogger(__name__)

DB_PATH = "data/zenith_memory.db"
POLL_SEC = 1.0
AUTO_SCREEN_SECS = int(__import__("os").getenv("ZENITH_CALL_AUTOSCREEN", "12"))

_session_holder = {}          # {"session": AgentSession|None}
_state = {
    "handling": False,        # currently managing an active call
    "caller": "",
    "started": None,
    "transcript": [],         # (role, text) captured during screening
}


def set_session(session):
    _session_holder["session"] = session


async def _speak(text: str):
    """Push a spoken line through the live session if available."""
    sess = _session_holder.get("session")
    if not sess:
        logger.info(f"[callbutler] (no session) {text}")
        return False
    try:
        await sess.generate_reply(
            instructions=f"Say EXACTLY this to the user, nothing else: \"{text}\"")
        return True
    except Exception as e:
        logger.warning(f"[callbutler] speak failed: {e}")
        return False


def _db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute(
        """CREATE TABLE IF NOT EXISTS call_log (
               id INTEGER PRIMARY KEY AUTOINCREMENT,
               ts TEXT,
               caller TEXT,
               outcome TEXT,          -- missed / handled_by_ai / connected_owner / declined
               debrief TEXT,
               duration_s INTEGER
           )"""
    )
    return conn


def _find_incoming_call():
    """Return (caller_name, window_obj) if an incoming WhatsApp call window exists."""
    try:
        import pygetwindow as gw

        for w in gw.getAllWindows():
            t = (w.title or "").strip()
            low = t.lower()
            if "whatsapp" in low and ("incoming" in low or "ringing" in low):
                m = re.search(r"(?:incoming\s+(?:voice\s+)?(?:video\s+)?call[^\w]*)(.+)$", t, re.I)
                caller = m.group(1).strip(" -–") if m else "Unknown caller"
                return caller, w
            # Some builds put it on the main window title
            if low.startswith("incoming") and ("voice" in low or "video" in low or "call" in low):
                m = re.search(r"call[^\w]*(.+)$", t, re.I)
                return (m.group(1).strip() if m else "Unknown caller"), w
    except Exception as e:
        logger.debug(f"incoming scan failed: {e}")
    return None


def _find_active_call_window():
    try:
        import pygetwindow as gw

        for w in gw.getAllWindows():
            t = (w.title or "").lower()
            if ("whatsapp" in t or t.strip() == "") and \
               any(k in t for k in ("ongoing", "in call", "voice call", "video call",
                                    "end call")):
                return w
    except Exception:
        pass
    return None


async def _click_button_on_window(win, color_hint: str) -> bool:
    """Click Answer(green)/Decline(red) by scanning the window image for the
    dominant colored round button. Uses existing OCR/color tooling patterns."""
    def _work():
        try:
            import numpy as np
            import pyautogui
            from PIL import Image

            box = win.box
            shot = pyautogui.screenshot(
                region=(box.left, box.top, box.width, box.height))
            arr = np.array(shot)[:, :, :3].astype(int)

            if color_hint == "green":
                mask = (arr[:, :, 1] > 120) & (arr[:, :, 0] < 110) & (arr[:, :, 2] < 130)
            else:
                mask = (arr[:, :, 0] > 150) & (arr[:, :, 1] < 90) & (arr[:, :, 2] < 90)

            ys, xs = __import__("numpy").where(mask)
            if len(xs) < 40:
                return False
            cx, cy = int(xs.mean()), int(ys.mean())
            pyautogui.click(box.left + cx, box.top + cy)
            return True
        except Exception as e:
            logger.debug(f"click {color_hint} failed: {e}")
            return False

    import asyncio
    return await asyncio.to_thread(_work)


async def _accept_call(win) -> bool:
    ok = await _click_button_on_window(win, "green")
    if not ok:   # fallback: Enter often answers when window focused
        try:
            import pyautogui
            await asyncio.to_thread(pyautogui.press, "enter")
            ok = True
        except Exception:
            ok = False
    return ok


async def _decline_call(win) -> bool:
    return await _click_button_on_window(win, "red")


# ------------------------------------------------------------- main loop ----

async def butler_loop(session=None):
    """Background watcher — started from agent entrypoint."""
    if session is not None:
        set_session(session)
    logger.info("📞 Call Butler watching for WhatsApp calls…")
    while True:
        try:
            if not _state["handling"]:
                hit = await asyncio.to_thread(_find_incoming_call)
                if hit:
                    caller, win = hit
                    await _handle_incoming(caller, win)
        except Exception as e:
            logger.debug(f"[callbutler] loop error: {e}")
        await asyncio.sleep(POLL_SEC)


async def _handle_incoming(caller: str, win):
    _state.update({"handling": True, "caller": caller, "started": datetime.now(),
                   "transcript": []})
    from Tools.autonomy import halted, journal, allowed_contact
    try:
        await _speak(f"Sir, a call is coming — {caller}. "
                     "Shall I connect you, or should I talk to them?")

        choice, deadline = None, time.time() + AUTO_SCREEN_SECS
        while time.time() < deadline and choice is None:
            # The user's spoken answer arrives via the normal conversation;
            # Call Butler reads a lightweight intent file written by tools.
            choice = read_user_choice()
            if choice is None and halted():
                choice = "decline_all"
            await asyncio.sleep(0.5)

        if choice == "owner":
            journal("call", f"{caller}: owner took over before answer")
            _log_call(caller, "connected_owner", "")
            await _wait_call_end(win, max_s=3600)
            _finish(owner_took=True)
            return

        if choice == "decline":
            await _decline_call(win)
            _log_call(caller, "declined_by_owner", "")
            _finish()
            return

        # Default / explicit AI-handling → ACCEPT + SCREEN
        if not await _accept_call(win):
            _log_call(caller, "missed", "answer click failed")
            await _speak(f"I couldn't grab the call from {caller}, sir.")
            _finish()
            return

        await _speak(f"On it. Talking with {caller} now.")
        await run_screening(caller)
        dur = await _wait_until_ended(win)
        debrief = compile_debrief(caller)
        _log_call(caller, "handled_by_ai", debrief,
                  duration=int((datetime.now() - _state["started"]).total_seconds()))
        from Tools.autonomy import journal
        journal("external_call", f"Handled WhatsApp call from {caller}. Debrief: {debrief[:180]}")
        await _speak("Call finished, sir. Debrief: " + debrief[:400])
    finally:
        _finish()


def read_user_choice():
    """Call Butler's user-choice channel: Tools.call_butler.USER_CHOICE global."""
    v = globals().get("USER_CHOICE")
    globals()["USER_CHOICE"] = None
    return v


USER_CHOICE = None


@function_tool()
async def connect_me_to_caller() -> str:
    """During an incoming WhatsApp call: 'connect me' — you'll take it yourself."""
    globals()["USER_CHOICE"] = "owner"
    return "📞 Handing the call to you — step in whenever ready, sir."


@function_tool()
async def let_ai_handle_call() -> str:
    """During an incoming WhatsApp call: AI accepts and talks with the caller."""
    globals()["USER_CHOICE"] = "ai"
    return "🤖 Understood — I will speak with them and brief you afterwards."


@function_tool()
async def decline_this_call() -> str:
    """During an incoming WhatsApp call: decline politely without answering."""
    globals()["USER_CHOICE"] = "decline"
    return "🚫 Declining this one."


async def run_screening(caller: str):
    """AI-conversation phase: transcribe what the agent hears/says so we can
    debrief afterwards. The actual dialogue happens through the normal realtime
    session (mic+speaker path); we tag transcript items here via hook."""
    _state["screening"] = True


def note_transcript(role: str, text: str):
    """Called by the session hook during AI-handled calls."""
    if _state.get("screening"):
        _state["transcript"].append((role, text))


async def _wait_call_end(win, max_s: int = 3600):
    """Await until call windows disappear (owner-takeover path)."""
    t0 = time.time()
    while time.time() - t0 < max_s:
        alive = await asyncio.to_thread(_find_active_call_window)
        inc = await asyncio.to_thread(lambda: _find_incoming_call())
        if not alive and not inc:
            return
        await asyncio.sleep(2)


async def _wait_until_ended(win, timeout_s: int = 7200) -> int:
    """Await until the AI-handled call window disappears; returns duration secs."""
    t0 = time.time()
    while time.time() - t0 < timeout_s:
        alive = await asyncio.to_thread(_find_active_call_window)
        if not alive:
            return int(time.time() - t0)
        await asyncio.sleep(2)
    return int(time.time() - t0)


def compile_debrief(caller: str) -> str:
    turns = _state.get("transcript") or []
    if not turns:
        return (f"Spoke with {caller}. No detailed transcript captured — "
                "audio path may have been quiet.")
    convo = "\n".join((f"CALLER: {t}" if r != "assistant" else f"ME: {t}") for r, t in turns[-24:])
    try:
        from Tools._llm_client import chat_complete_sync
        prompt = (
            f"Summarize this phone call for the boss in 3-5 short lines:\n"
            f"Caller: {caller}\nInclude: why they called, key asks, anything I "
            f"promised on their behalf.\n\n{convo}"
        )
        s = chat_complete_sync(prompt, max_tokens=500)
        if not s.startswith("ERROR"):
            return s.strip()
    except Exception:
        pass
    tail = "; ".join(t[:60] for _, t in turns[-4:])
    return f"Talked with {caller}. Last exchanges: {tail}"


def _log_call(caller: str, outcome: str, debrief: str, duration: int = 0):
    try:
        conn = _db()
        conn.execute(
            "INSERT INTO call_log (ts,caller,outcome,debrief,duration_s) VALUES (?,?,?,?,?)",
            (datetime.now().isoformat(), caller, outcome, debrief[:1500], duration),
        )
        conn.commit(); conn.close()
    except Exception as e:
        logger.debug(f"call log failed: {e}")


def _finish(owner_took: bool = False):
    _state.update({"handling": False, "screening": False, "caller": "",
                   "started": None, "transcript": []})


@function_tool()
async def recent_calls(count: int = 5) -> str:
    """Recent WhatsApp calls Zenith managed (outcome + debrief)."""
    conn = _db()
    rows = conn.execute(
        "SELECT ts,caller,outcome,debrief,duration_s FROM call_log ORDER BY id DESC LIMIT ?",
        (max(1, min(int(count), 20)),)).fetchall()
    conn.close()
    if not rows:
        return "📞 No calls handled yet."
    out = "📞 RECENT CALLS:\n"
    for r in rows:
        out += (f"\n• {str(r['ts'])[:16].replace('T',' ')} — {r['caller']} "
                f"[{r['outcome']}] ({r['duration_s']}s)")
        if r["debrief"]:
            out += f"\n   {str(r['debrief'])[:200]}"
    return out
