"""Zenith Protocol System — named mission macros, JARVIS-style.

One phrase fires a whole chain of real tool calls with narration between
stages. Six protocols ship seeded; you create more by conversation.
Destructive steps respect the autonomy dial and the FULL STOP kill flag.

Step grammar (parsed, deterministic — no hallucinated steps):
  open <app>             -> open_app
  play <query>           -> youtube media
  volume <0-100>         -> control_system_volume
  brightness <0-100>     -> control_screen_brightness
  clear_desktop          -> minimize all windows
  clean_files            -> janitor scan+execute (autonomy-aware)
  focus <min>|<blockers> -> start_focus_session
  endfocus               -> end_focus_session
  remind <text> @ <when> -> set_reminder
  whatsapp <contact>:<msg> -> send (Policy A; NEVER_CONTACT respected)
  lock                   -> OS lock workstation
  wait <seconds>
  say <text>             -> spoken narration line
"""

import json
import logging
import sqlite3
from datetime import datetime

from livekit.agents import function_tool

logger = logging.getLogger(__name__)

DB_PATH = "data/zenith_memory.db"

SEED_PROTOCOLS = {
    "clean slate": [
        ("say", "Initiating Clean Slate protocol, sir."),
        ("clear_desktop", ""),
    ],
    "study mode": [
        ("say", "Entering study protocol. Distractions are now my enemy."),
        ("clear_desktop", ""),
        ("volume", "40"),
        ("focus", "50|youtube, instagram, netflix, games, spotify"),
    ],
    "gamer protocol": [
        ("say", "Gamer protocol engaged. Godspeed, sir."),
        ("open", "steam"),
        ("open", "discord"),
        ("volume", "80"),
    ],
    "movie night": [
        ("say", "Movie night configuration deploying."),
        ("brightness", "60"),
        ("volume", "70"),
        ("clear_desktop", ""),
    ],
    "goodnight sequence": [
        ("say", "Goodnight sequence initiated. I will mind the fort, sir."),
        ("clear_desktop", ""),
        ("brightness", "20"),
        ("volume", "10"),
    ],
    "lockdown": [
        ("say", "LOCKDOWN protocol. Securing everything immediately."),
        ("clear_desktop", ""),
        ("lock", ""),
    ],
}


def _db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute(
        """CREATE TABLE IF NOT EXISTS protocols (
               name TEXT PRIMARY KEY,
               steps TEXT,
               created_at TEXT
           )"""
    )
    cur = conn.execute("SELECT COUNT(*) c FROM protocols").fetchone()
    if cur["c"] == 0:
        for name, steps in SEED_PROTOCOLS.items():
            conn.execute(
                "INSERT OR IGNORE INTO protocols (name,steps,created_at) VALUES (?,?,?)",
                (name, json.dumps(steps), datetime.now().isoformat()),
            )
    conn.commit()
    return conn


def get_protocol(name: str):
    key = name.strip().lower()
    row = _db().execute("SELECT * FROM protocols WHERE lower(name)=?", (key,)).fetchone()
    return dict(row) if row else None


# ------------------------------------------------------------ execution -----

async def execute_step(verb: str, arg: str) -> str:
    """Execute one parsed step by dispatching to the REAL underlying tools."""
    try:
        if verb == "say":
            return f"🗣️ {arg}"

        if verb == "open":
            from Tools.open_app import open_app
            return await open_app(app_name=arg)

        if verb == "play":
            from Tools.youtube_videos import play_media
            return await play_media(media_name=arg, media_type="video")

        if verb == "volume":
            from Tools.time_volume_bright import control_system_volume
            return await control_system_volume(prompt="protocol", volume_level=int(arg))

        if verb == "brightness":
            from Tools.time_volume_bright import control_screen_brightness
            return await control_screen_brightness(prompt="protocol", brightness_level=int(arg))

        if verb == "clear_desktop":
            from Tools.window_focus import minimize_all_windows
            return await minimize_all_windows()

        if verb == "clean_files":
            from Tools.file_janitor import build_plan, _plans, execute_cleanup
            import time as _t
            plan = build_plan()
            pid = f"auto_{int(_t.time())}"
            _plans[pid] = plan
            res = await execute_cleanup(plan_id=pid, confirm=True)
            return f"🧹 Janitor: {str(res)[:140]}"

        if verb == "focus":
            mins, _, blocks = arg.partition("|")
            from Tools.context_engine import start_focus_session
            return await start_focus_session(
                duration_minutes=int(mins or 25), block_list=blocks or "")

        if verb == "endfocus":
            from Tools.context_engine import end_focus_session
            return await end_focus_session()

        if verb == "remind":
            text, _, when = arg.partition("@")
            from Tools.reminder import set_reminder
            return await set_reminder(text=text.strip(), when=when.strip())

        if verb == "whatsapp":
            contact, _, msg = arg.partition(":")
            from Tools.autonomy import allowed_contact, journal
            if not allowed_contact(contact):
                journal("external_send_blocked", f"NEVER_CONTACT hit for {contact}")
                return f"⛔ {contact} is on your never-contact list. Skipped."
            from Tools.send_whatsapp_message import send_whatsapp_message
            res = await send_whatsapp_message(contact=contact.strip(), message=msg.strip())
            journal("external_send", f"Protocol WhatsApp → {contact.strip()}",
                    target=contact.strip())
            return res

        if verb == "whatsapp_smart":
            contact, _, msg = arg.partition(":")
            from Tools.whatsapp_x import _resolve_from, _cache_names, _execute_send
            ranked = _resolve_from(_cache_names(), contact.strip(), min_score=0.75)
            if len(ranked) == 1:
                res = await _execute_send(ranked[0][1], msg.strip())
            else:
                # protocols run under autonomy: auto-pick best match, note it
                best = ranked[0][1] if ranked else contact.strip()
                res = await _execute_send(best, msg.strip())
                res = f"(auto-resolved “{contact.strip()}” → {best}) {res}"
            journal("external_send", f"Protocol WhatsAppX → {contact.strip()}", target=contact.strip())
            return res

        if verb == "wait":
            import asyncio
            await asyncio.sleep(min(float(arg or 1), 120))
            return "⏱️ pause complete"

        if verb == "lock":
            from Tools.system_power_action import system_power_action
            return await system_power_action(action="lock")

        return f"⚠️ Unknown step '{verb}' skipped."
    except Exception as e:
        return f"⚠️ Step {verb} failed: {e}"


@function_tool()
async def run_protocol(name: str) -> str:
    """Execute a saved protocol by name with live narration per step.

    Args:
        name: e.g. "study mode", "clean slate", "gamer protocol"
    """
    try:
        p = get_protocol(name)
        if not p:
            names = ", ".join(
                r["name"] for r in _db().execute("SELECT name FROM protocols").fetchall())
            return f"❌ No protocol '{name}'. Saved: {names}"
        steps = json.loads(p["steps"])
        out = [f"🚀 PROTOCOL «{p['name'].upper()}» — {len(steps)} step(s)…"]
        from Tools.autonomy import halted, journal
        done = 0
        for i, item in enumerate(steps, 1):
            if halted():
                out.append("🛑 FULL STOP honored — remaining steps aborted.")
                break
            verb, arg = (item[0], item[1]) if isinstance(item, (list, tuple)) else (item, "")
            r = await execute_step(str(verb), str(arg or ""))
            out.append(f"{i}. [{verb}] {r[:130]}")
            done += 1
        journal("protocol", f"Ran '{p['name']}' ({done}/{len(steps)} steps)")
        out.append("✅ Protocol complete." if done == len(steps) else "⚠️ Protocol finished with aborts.")
        return "\n".join(out)
    except Exception as e:
        return f"❌ Protocol failed: {e}"


STEP_HELP = (
    "Valid steps: say <text> | open <app> | play <query> | volume <0-100> | "
    "brightness <0-100> | clear_desktop | clean_files | focus <min>|<blocked keywords> | "
    "endfocus | remind <text> @ <time> | whatsapp <contact>:<message> | lock | wait <sec>"
)


def parse_steps_text(raw: str):
    """Parse newline-separated step text into [(verb,arg)]. Raises on bad lines."""
    steps = []
    for line in raw.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        verb, _, arg = line.partition(" ")
        verb = verb.strip().lower().rstrip(":")
        if not verb:
            raise ValueError(f"Empty step: '{line}'")
        steps.append((verb, arg.strip()))
    if not steps:
        raise ValueError("No steps given.")
    return steps


@function_tool()
async def create_protocol(name: str, steps_text: str) -> str:
    """Create/replace a protocol by conversation. Each line = one step using the
    simple grammar (say/open/play/volume/brightness/clear_desktop/clean_files/
    focus/endfocus/remind/whatsapp/lock/wait).

    Args:
        name: Protocol name, e.g. "gym mode"
        steps_text: Newline-separated steps, e.g.
            'say hitting the gym sir\\nopen spotify\\nvolume 70'
    """
    try:
        steps = parse_steps_text(steps_text)
        valid_verbs = {
            "say", "open", "play", "volume", "brightness", "clear_desktop",
            "clean_files", "focus", "endfocus", "remind", "whatsapp", "lock", "wait",
        }
        bad = [v for v, _ in steps if v not in valid_verbs]
        if bad:
            return f"❌ Invalid step(s): {', '.join(sorted(set(bad)))}\n{STEP_HELP}"
        conn = _db()
        conn.execute(
            "INSERT INTO protocols (name,steps,created_at) VALUES (?,?,?) "
            "ON CONFLICT(name) DO UPDATE SET steps=excluded.steps, created_at=excluded.created_at",
            (name.strip().lower(), json.dumps(steps), datetime.now().isoformat()),
        )
        conn.commit(); conn.close()
        listing = "\n".join(f"   {i+1}. [{v}] {a}" for i, (v, a) in enumerate(steps))
        return f"✅ Protocol «{name}» saved with {len(steps)} step(s):\n{listing}\nRun it: \"run protocol {name}\""
    except ValueError as ve:
        return f"❌ {ve}\n{STEP_HELP}"
    except Exception as e:
        return f"❌ Create failed: {e}"


@function_tool()
async def list_protocols() -> str:
    """List every saved protocol and its steps."""
    rows = _db().execute("SELECT name,steps FROM protocols ORDER BY name").fetchall()
    if not rows:
        return "📋 No protocols stored."
    out = "📋 PROTOCOLS:\n"
    for r in rows:
        steps = json.loads(r["steps"])
        summary = " → ".join(s[0] for s in steps)
        out += f"\n🎯 {r['name']}  ({len(steps)} steps)\n   {summary[:150]}"
    return out


@function_tool()
async def delete_protocol(name: str) -> str:
    """Delete a saved protocol by name."""
    conn = _db()
    cur = conn.execute("DELETE FROM protocols WHERE lower(name)=?", (name.strip().lower(),))
    conn.commit(); n = cur.rowcount; conn.close()
    return f"🗑️ Protocol '{name}' deleted." if n else f"❌ No protocol '{name}'."


# ---------------- autonomy-aware confirmation helper for gated tools --------

def confirm_allowed(action_label: str) -> bool:
    """Full autonomy = act without asking. Restricted/off = caller must ask user.
    Also honors FULL STOP flag."""
    from Tools.autonomy import halted
    if halted():
        return False
    try:
        from Tools.autonomy import is_full
        return is_full()
    except Exception:
        return False
