"""Zenith Session Handoff — close the lid, lose nothing.

On shutdown: captures open apps, clipboard, last conversations, active
focus/protocol state into data/session_handoff.json.
Next boot: offers "Resume where we left off?" briefing and restores what's
restorable (clipboard, app list shown for one-click relaunch).
"""

import json
import logging
import os
import sqlite3
from datetime import datetime
from pathlib import Path

from livekit.agents import function_tool

logger = logging.getLogger(__name__)

HANDOFF = Path("data/session_handoff.json")


def capture_state() -> dict:
    state = {"ts": datetime.now().isoformat(), "apps": [], "clipboard": "",
             "last_messages": [], "focus": None, "protocol": None}
    try:
        import pygetwindow as gw

        seen = []
        for w in gw.getAllWindows():
            t = (w.title or "").strip()
            if t and " - " in t:
                name = t.split(" - ")[-1].strip()[:40]
                if name and name.lower() not in ("program manager", "settings") and name not in seen:
                    seen.append(name)
        state["apps"] = seen[:10]
    except Exception:
        pass
    try:
        import pyperclip
        cb = pyperclip.paste() or ""
        state["clipboard"] = cb[:300] if len(cb) < 300 else cb[:300]
    except Exception:
        pass
    try:
        conn = sqlite3.connect("data/zenith_memory.db")
        rows = conn.execute(
            "SELECT role,text FROM messages ORDER BY id DESC LIMIT 4").fetchall()
        state["last_messages"] = [
            {"role": r[0], "text": r[1][:120]} for r in reversed(rows)]
        conn.close()
    except Exception:
        pass
    try:
        from Tools.context_engine import _fs
        if _fs.active:
            mins_left = int((_fs.until - __import__("time").time()) / 60)
            state["focus"] = f"{mins_left} min focus left, {_fs.violations} distractions blocked"
    except Exception:
        pass
    return state


def save_handoff():
    try:
        HANDOFF.parent.mkdir(parents=True, exist_ok=True)
        HANDOFF.write_text(json.dumps(capture_state(), indent=2), encoding="utf-8")
        return True
    except Exception as e:
        logger.debug(f"handoff save failed: {e}")
        return False


def load_handoff() -> dict | None:
    try:
        if HANDOFF.exists():
            d = json.loads(HANDOFF.read_text(encoding="utf-8"))
            age_h = (datetime.now() - datetime.fromisoformat(d["ts"])).total_seconds() / 3600
            d["age_hours"] = round(age_h, 1)
            return d if age_h < 168 else None      # a week stale → ignore
    except Exception:
        pass
    return None


@function_tool()
async def save_session_handoff(note: str = "") -> str:
    """Capture EVERYTHING about this moment (open apps, clipboard tail, recent
    chat, focus state + optional note) so next boot can resume seamlessly."""
    st = save_handoff()
    if note:
        try:
            d = json.loads(HANDOFF.read_text(encoding="utf-8"))
            d["note"] = note[:300]
            HANDOFF.write_text(json.dumps(d, indent=2), encoding="utf-8")
        except Exception:
            pass
    if st:
        return ("💾 Handoff saved — open apps, clipboard, recent context"
                + (f" and your note (“{note[:60]}”)") + ". Next boot I'll offer to resume.")
    return "⚠️ Couldn't write handoff file."


@function_tool()
async def resume_session() -> str:
    """RESUME SESSION: read the last handoff and brief you on exactly where we
    left off — apps that were open, your clipboard tail, recent conversation."""
    d = load_handoff()
    if not d:
        return "ℹ️ No recent handoff found (or it's over a week old)."
    out = [f"🔁 RESUME BRIEFING (saved {str(d['ts'])[:16].replace('T',' ')}, "
           f"{d.get('age_hours',0)}h ago)\n════════════════════"]
    if d.get("apps"):
        out.append("🪟 Apps that were open:\n   " + ", ".join(d["apps"][:8]))
    if d.get("note"):
        out.append(f"📌 Your note: “{d['note']}”")
    msgs = d.get("last_messages") or []
    if msgs:
        last_u = next((m["text"] for m in reversed(msgs) if m["role"] == "user"), "")
        if last_u:
            out.append(f"🗣️ Last thing you asked: “{last_u}”")
    if d.get("focus"):
        out.append(f"🎯 Focus session was active: {d['focus']}")
    if d.get("clipboard"):
        out.append(f"📋 Clipboard tail: “{d['clipboard'][:80]}…”")

    out.append("\n➡ Want me to reopen those apps? Say \"relaunch handoff apps\".")

    # stash for the relaunch tool
    try:
        json.dump({"apps": d.get("apps", [])},
                  open(Path("data/handoff_apps.json"), "w"), indent=2)
    except Exception:
        pass

    # archive so we don't nag twice
    try:
        done_dir = Path("data/handoff_archive"); done_dir.mkdir(exist_ok=True)
        shutil.move(str(HANDOFF), str(done_dir / HANDOFF.name))
    except Exception:
        pass
    return "\n".join(out)


import shutil  # noqa: E402


@function_tool()
async def relaunch_handoff_apps() -> str:
    """Reopen the applications captured in the last session handoff."""
    try:
        p = Path("data/handoff_apps.json")
        apps = json.loads(p.read_text())["apps"] if p.exists() else []
        if not apps:
            return "ℹ️ No app list from a previous handoff."
        opened = []
        for name in apps[:8]:
            try:
                from Tools.open_app import open_app
                await open_app(app_name=name.split()[0])
                opened.append(name)
            except Exception:
                continue
        return "🚀 Relaunched: " + ", ".join(opened)
    except Exception as e:
        return f"❌ Relaunch failed: {e}"