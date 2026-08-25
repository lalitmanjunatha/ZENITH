"""Zenith Missions — situational-awareness tools from the movie pack.

- catch_me_up:    everything that happened while you were away (real logs only)
- daily_threat_board: combined risk briefing (deadlines/risks/health/tools)
- cue_music:      instant hype-track launcher
- power_check:    honest capability report of what Zenith can do RIGHT NOW
"""

import logging
import sqlite3
from datetime import datetime, timedelta

from livekit.agents import function_tool

logger = logging.getLogger(__name__)

DB_PATH = "data/zenith_memory.db"


def _q(sql, args=()):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = [dict(r) for r in conn.execute(sql, args).fetchall()]
    conn.close()
    return rows


def _table_exists(name: str) -> bool:
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (name,)
    ).fetchone()
    conn.close()
    return bool(row)


@function_tool()
async def catch_me_up() -> str:
    """CATCH ME UP: returns after being away — autonomous actions taken,
    handled/missed calls, scheduled sends, unlocked capsules, dream learnings
    and recent usage. Real records only; silence means a quiet day."""
    try:
        from Tools.autonomy import _db as _ensure_autonomy_tables
        _ensure_autonomy_tables()
    except Exception:
        pass
    sections = []

    acts = _q(
        "SELECT ts,kind,summary FROM action_journal "
        "WHERE ts >= datetime('now','-12 hours') ORDER BY id DESC LIMIT 8"
    )
    if acts:
        s = "🤖 My autonomous moves:\n" + "\n".join(
            f"   • [{a['kind']}] {a['summary'][:90]}" for a in acts)
        sections.append(s)

    if _table_exists("call_log"):
        calls = _q(
            "SELECT caller,outcome,debrief FROM call_log "
            "WHERE ts >= datetime('now','-24 hours') ORDER BY id DESC LIMIT 5"
        )
        if calls:
            lines = []
            for c in calls:
                line = f"   • {c.get('caller') or '?'} — {c.get('outcome') or '?'}"
                if c.get("debrief"):
                    line += f": {str(c['debrief'])[:90]}"
                lines.append(line)
            sections.append("📞 Calls:\n" + "\n".join(lines))

    sent = _q(
        "SELECT recipient,message,status FROM scheduled_messages "
        "WHERE status IN ('sent','failed') AND send_at >= datetime('now','-24 hours') LIMIT 6"
    )
    if sent:
        s = "📨 Scheduled messages executed:\n" + "\n".join(
            f"   • {m['status'].upper()} → {m['recipient']}: {m['message'][:50]}"
            for m in sent)
        sections.append(s)

    try:
        from Tools.dream_mode import latest_dream_brief_line
        line = latest_dream_brief_line()
        if line:
            sections.append("🌙 " + line)
    except Exception:
        pass

    try:
        from Tools.time_capsule import newly_unlocked_brief_line
        line = newly_unlocked_brief_line()
        if line:
            sections.append(line)
    except Exception:
        pass

    try:
        rows = _q(
            "SELECT process, COUNT(*) c FROM app_usage "
            "WHERE ts >= datetime('now','-4 hours') GROUP BY process ORDER BY c DESC LIMIT 3"
        )
        if rows:
            top = ", ".join(f"{r['process']} ({r['c']})" for r in rows)
            sections.append(f"📊 Your last hours, mostly: {top}")
    except Exception:
        pass

    if not sections:
        return ("📭 All quiet while you were away, sir — no calls, no sends, "
                "no unlocks, no anomalies. A rare luxury.")
    return "📋 CATCH-UP BRIEFING\n════════════════════\n" + "\n\n".join(sections)


@function_tool()
async def daily_threat_board() -> str:
    """DAILY THREAT BOARD: the 60-second combined brief — upcoming reminders,
    open project risks, hardware warnings and unresolved tool issues.
    Built strictly from real stored data."""
    out = "🎯 THREAT BOARD\n════════════════════\n"
    items = []

    now_iso = datetime.now().isoformat()
    soon = (datetime.now() + timedelta(hours=24)).isoformat()

    # Reminders table exists only if scheduler created it — guard anyway
    if _table_exists("reminders"):
        try:
            rem = _q(
                "SELECT text, remind_at FROM reminders "
                "WHERE remind_at BETWEEN ? AND ? ORDER BY remind_at LIMIT 5",
                (now_iso, soon))
            for r in rem:
                items.append(f"⏰ Reminder at {str(r['remind_at'])[11:16]} — {str(r['text'])[:60]}")
        except Exception:
            pass

    # Open high/critical risks from SIH projects
    if _table_exists("sih_risks"):
        try:
            risks = _q(
                "SELECT severity,description FROM sih_risks "
                "WHERE status != 'resolved' AND severity IN ('high','critical') LIMIT 5"
            )
            for r in risks:
                icon = "🔴" if r["severity"] == "critical" else "🟠"
                items.append(f"{icon} Project risk: {str(r['description'])[:70]}")
        except Exception:
            pass

    # Hardware warnings
    try:
        from Tools.laptop_health import collect_snapshot, analyze_snapshot
        for sev, msg in analyze_snapshot(collect_snapshot()):
            if sev in ("🔴 CRITICAL", "🟠 HIGH"):
                items.append(f"{sev} {msg}")
    except Exception:
        pass

    # Unresolved tool issues
    if _table_exists("tool_issues"):
        try:
            issues = _q(
                "SELECT tool_name FROM tool_issues WHERE status='open' LIMIT 5")
            if issues:
                names = ", ".join(i["tool_name"] for i in issues)
                items.append(f"🐞 Tools misbehaving: {names}")
        except Exception:
            pass

    if not items:
        return out + "✅ Zero threats on the board, sir. Clear skies."
    return out + "\n".join(f"   {i}" for i in items)


@function_tool()
async def cue_music(vibe: str = "hype") -> str:
    """CUE MUSIC: instant mood launcher — 'Zenith, my entrance' energy.
    Plays a vibe-matched track via the existing YouTube media pipeline.

    Args:
        vibe: hype / focus / chill / epic (default hype)
    """
    queries = {
        "hype": "Back In Black AC DC",
        "epic": "epic orchestral battle music",
        "focus": "deep focus electronic music playlist",
        "chill": "lofi chill beats playlist",
    }
    q = queries.get(vibe.lower(), queries["hype"])
    try:
        from Tools.youtube_videos import play_media
        res = await play_media(media_name=q, media_type="video")
        return f"🎵 Cued ({vibe}). {res}"
    except Exception as e:
        return f"❌ Music cue failed: {e}"


@function_tool()
async def power_check() -> str:
    """POWER CHECK — 'what can you actually do right now?': honest capability
    summary including active autonomy level, restrictions, and anything disabled."""
    try:
        from Tools.autonomy import autonomy_level, halted, is_full
        from Tools.fun_personality import current_persona

        caps = []
        lvl = autonomy_level()
        if halted():
            caps.append("⛔ AUTONOMY HALTED by kill phrase — say 'resume autonomy' to re-arm")
        caps.append(f"Autonomy: {lvl.upper()} " + (
            "(act-first, journal-everything)" if is_full() else ""))
        caps.append(f"Persona pack: {current_persona()}")

        # Feature probes (import presence = available)
        probes = [
            ("Protocols", "Tools.protocols", None),
            ("Facial recognition + people window", "Tools.face_recognition", None),
            ("WhatsApp call butler", "Tools.call_butler", None),
            ("Wake-word listener", "Tools.wake_word_daemon", None),
            ("Laptop health oracle", "Tools.laptop_health", None),
            ("File janitor", "Tools.file_janitor", None),
            ("Dream mode", "Tools.dream_mode", None),
            ("SIH command center", "Tools.sih_project_manager", None),
        ]
        on, off = [], []
        for label, modpath, _ in probes:
            try:
                __import__(modpath)
                on.append(label)
            except Exception:
                off.append(label)

        out = "⚡ POWER CHECK — current capabilities\n════════════════════\n"
        out += "\n".join(f"   • {c}" for c in caps) + "\n\n🟢 Online:\n"
        out += "\n".join(f"   ✓ {x}" for x in on)
        if off:
            out += "\n\n🔴 Unavailable this session:\n" + "\n".join(f"   ✗ {x}" for x in off)
        return out
    except Exception as e:
        return f"❌ Power check failed: {e}"
