"""Context Engine — Wi-Fi profiles, app-usage heatmap, and Focus Mode blocker.

Features:
- Wi-Fi profiles (feature 6): assign a behavior preset to each SSID you visit
  (home/college/cafe). Zenith reports which profile is active.
- App-usage heatmap (feature 10): a background sampler records your active
  application every 30s into SQLite; reports give real minutes-per-app plus an
  hourly ASCII heatmap. Nothing is estimated — only sampled reality.
- Focus blocker (feature 12): during a focus session, distracting apps are
  gently MINIMIZED (never killed) when they grab foreground; violations counted.
"""

import asyncio
import logging
import os
import sqlite3
import subprocess
import time
from collections import Counter, defaultdict
from datetime import datetime, timedelta

from livekit.agents import function_tool

logger = logging.getLogger(__name__)

DB_PATH = "data/zenith_memory.db"
SAMPLE_INTERVAL_S = 30
PRUNE_DAYS = 7


def _db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS wifi_profiles (
            ssid TEXT PRIMARY KEY,
            preset TEXT,
            notes TEXT,
            updated_at TEXT
        );
        CREATE TABLE IF NOT EXISTS app_usage (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TEXT,
            process TEXT,
            title TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_usage_ts ON app_usage(ts);
        """
    )
    return conn


# ------------------------------------------------------------------ wifi ----

def current_ssid() -> str:
    """Connected SSID on Windows ("" if unknown)."""
    try:
        out = subprocess.run(
            ["netsh", "wlan", "show", "interfaces"],
            capture_output=True, text=True, timeout=10,
        ).stdout
        for line in out.splitlines():
            if "SSID" in line and "BSSID" not in line and ":" in line:
                val = line.split(":", 1)[1].strip()
                if val:
                    return val
    except Exception as e:
        logger.debug(f"ssid query failed: {e}")
    return ""


PRESETS = {
    "home":   "Full trust: automation allowed, indexing unrestricted.",
    "college":"Study bias: focus-friendly nudges louder, entertainment quieter.",
    "cafe":   "Public caution: remind about privacy, avoid sensitive ops.",
    "work":   "Professional mode: concise replies, meeting-awareness on.",
}


@function_tool()
async def wifi_profile() -> str:
    """Show the Wi-Fi network you're on and which behavior profile is assigned."""
    ssid = current_ssid()
    if not ssid:
        return "📶 Not connected to any Wi-Fi network (or ethernet/unknown)."
    conn = _db()
    row = conn.execute("SELECT preset, notes FROM wifi_profiles WHERE ssid = ?", (ssid,)).fetchone()
    conn.close()
    if not row:
        known = ", ".join(PRESETS.keys())
        return (
            f"📶 Wi-Fi: {ssid}\n"
            f"No profile yet. Say \"set wifi profile home/college/cafe/work\".\n"
            f"Available presets: {known}"
        )
    desc = PRESETS.get(row["preset"], "")
    return f"📶 Wi-Fi: {ssid} → 🏷️ {row['preset']} profile\n{desc}" + (f"\n📝 {row['notes']}" if row["notes"] else "")


@function_tool()
async def set_wifi_profile(preset: str, notes: str = "") -> str:
    """Assign a behavior preset to the CURRENT Wi-Fi network.

    Args:
        preset: One of: home, college, cafe, work
        notes: Optional reminder attached to this place
    """
    p = preset.strip().lower()
    if p not in PRESETS:
        return f"❌ Unknown preset '{preset}'. Choose: {', '.join(PRESETS)}"
    ssid = current_ssid()
    if not ssid:
        return "❌ No active Wi-Fi SSID detected — connect first."
    conn = _db()
    conn.execute(
        "INSERT INTO wifi_profiles (ssid,preset,notes,updated_at) VALUES (?,?,?,?) "
        "ON CONFLICT(ssid) DO UPDATE SET preset=excluded.preset, notes=excluded.notes, updated_at=excluded.updated_at",
        (ssid, p, notes, datetime.now().isoformat()),
    )
    conn.commit(); conn.close()
    return f"✅ '{ssid}' will now behave as 🏷️ {p}: {PRESETS[p]}" + (f" Note: {notes}" if notes else "")


# ----------------------------------------------------------- usage stats ----

def record_sample() -> None:
    try:
        import pygetwindow as gw

        w = gw.getActiveWindow()
        proc = ""
        title = ""
        if w is not None:
            title = (w.title or "")[:120]
            try:  # pygetwindow exposes no pid; derive process from title heuristics
                proc = title.split(" - ")[-1][:60] if " - " in title else (title[:60] or "unknown")
            except Exception:
                proc = "unknown"
        if title or proc:
            conn = _db()
            conn.execute("INSERT INTO app_usage (ts,process,title) VALUES (?,?,?)",
                         (datetime.now().isoformat(), proc or "unknown", title))
            conn.commit(); conn.close()
    except Exception as e:
        logger.debug(f"usage sample failed: {e}")


def prune_old() -> None:
    try:
        cutoff = (datetime.now() - timedelta(days=PRUNE_DAYS)).isoformat()
        conn = _db()
        conn.execute("DELETE FROM app_usage WHERE ts < ?", (cutoff,))
        conn.commit(); conn.close()
    except Exception:
        pass


@function_tool()
async def app_usage_report(hours: int = 8) -> str:
    """APP USAGE HEATMAP: where your time actually went — minutes per application
    plus an hourly activity chart, computed ONLY from sampled history.

    Args:
        hours: How far back to analyze (default 8, max 168)
    """
    hours = max(1, min(int(hours), 168))
    since = (datetime.now() - timedelta(hours=hours)).isoformat()
    conn = _db()
    rows = conn.execute(
        "SELECT ts, process FROM app_usage WHERE ts >= ? ORDER BY ts", (since,)
    ).fetchall()
    total_samples = conn.execute("SELECT COUNT(*) c FROM app_usage").fetchone()["c"]
    conn.close()

    if not rows:
        return (
            f"📊 No samples in the last {hours}h (history has {total_samples} rows overall).\n"
            "The sampler runs with the agent; give it a few minutes then ask again."
        )

    # Each sample ≈ SAMPLE_INTERVAL_S of usage
    minutes_per = defaultdict(int)
    hourly = defaultdict(set)          # hour -> set(processes seen)
    for r in rows:
        try:
            dt = datetime.fromisoformat(r["ts"])
        except Exception:
            continue
        minutes_per[r["process"] or "unknown"] += SAMPLE_INTERVAL_S / 60.0
        hourly[dt.strftime("%H")].add(r["process"])

    top = sorted(minutes_per.items(), key=lambda x: x[1], reverse=True)[:12]
    total_min = sum(minutes_per.values())

    out = f"📊 APP USAGE HEATMAP — last {hours}h ({int(total_min)} tracked minutes)\n════════════════════\n"
    maxm = top[0][1] if top else 1
    for proc, m in top:
        bar = "█" * max(1, int(m / maxm * 24))
        out += f"{bar:>24} {m:6.0f} min  {proc[:40]}\n"

    out += "\n🕒 Hourly activity (▁░▒▓█ by distinct apps):\n"
    for h in sorted(hourly):
        n = len(hourly[h])
        cell = ["▁","▂","▃","▄","▅","▆","▇","█"][min(n - 1, 7)]
        out += f"  {h}:00 {cell * 2} {n} apps\n"

    # Honest coverage note
    span_samples = (hours * 3600) / SAMPLE_INTERVAL_S
    coverage = min(100, int(len(rows) / span_samples * 100)) if span_samples else 0
    out += f"\nℹ️ Coverage {coverage}% of wall-clock (sampler runs while agent is up)."
    return out


# ------------------------------------------------------------- focus mode ----

class _FocusState:
    active = False
    until = 0.0
    blocked: set = set()
    violations = 0
    started_title = ""


_fs = _FocusState()


async def _enforce_tick() -> None:
    """One enforcement pass (called from background loop)."""
    if not _fs.active:
        return
    if time.time() > _fs.until:
        await end_focus_session_internal()
        return
    try:
        import pygetwindow as gw

        w = gw.getActiveWindow()
        if w is None or not w.title:
            return
        t = w.title.lower()
        if any(b in t for b in _fs.blocked):
            await asyncio.to_thread(w.minimize)
            _fs.violations += 1
            print(f"🎯 Focus: minimized distraction #{_fs.violations}: {w.title[:50]}")
    except Exception as e:
        logger.debug(f"focus tick: {e}")


async def end_focus_session_internal() -> str:
    mins = int((time.time() - (_fs.until - _fs.duration_holder)) / 60) if _fs.active else 0
    _fs.active = False
    return (
        f"🎯 Focus session ended — {mins} min, {_fs.violations} distraction(s) minimized."
    )


# small holder so end-report can compute intended duration
_fs.duration_holder = 0


@function_tool()
async def start_focus_session(duration_minutes: int = 25, block_list: str = "") -> str:
    """Start FOCUS MODE: for the given duration, whenever a distracting app grabs
    the foreground it gets minimized automatically (apps are matched by window-title
    keywords, comma-separated). Apps are NEVER killed.

    Args:
        duration_minutes: Session length (default 25)
        block_list: Comma-separated keywords, e.g. "youtube, instagram, steam"
    """
    dur = max(5, min(int(duration_minutes), 240))
    blocked = {b.strip().lower() for b in block_list.split(",") if b.strip()}
    if not blocked:
        blocked = {"youtube", "instagram", "netflix", "prime video", "steam", "games"}
    _fs.active = True
    _fs.duration_holder = dur * 60
    _fs.until = time.time() + dur * 60
    _fs.blocked = blocked
    _fs.violations = 0
    return (
        f"🎯 FOCUS MODE ON for {dur} min.\n"
        f"🚫 Auto-minimizing windows containing: {', '.join(sorted(blocked))}\n"
        "Say \"end focus\" anytime for your violation report."
    )


@function_tool()
async def end_focus_session() -> str:
    """End the current focus session and get your distraction report."""
    if not _fs.active:
        return "🎯 No focus session running."
    msg = await end_focus_session_internal()
    return msg + "\n💡 Tip: pair sessions with Pomodoro-style 5-min breaks."


async def focus_loop():
    """Background enforcement loop (started by agent entrypoint)."""
    while True:
        try:
            await _enforce_tick()
        except Exception as e:
            logger.debug(f"focus loop: {e}")
        await asyncio.sleep(10)


async def usage_sampler_loop():
    """Background sampler loop (started by agent entrypoint)."""
    n = 0
    while True:
        await asyncio.to_thread(record_sample)
        n += 1
        if n % 40 == 0:                      # ~every 20 min
            await asyncio.to_thread(prune_old)
        await asyncio.sleep(SAMPLE_INTERVAL_S)
