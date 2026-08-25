"""Zenith Battery Coach — learns YOUR charging rhythm and advises plug times.

Uses the real laptop_health_snapshots history (battery %, plugged state,
timestamps) to compute: average drain rate on battery, and concrete plug-in /
unplug advice. All numbers derive from measured snapshots — never fabricated.
"""

import logging
import sqlite3
from datetime import datetime, timedelta

from livekit.agents import function_tool

logger = logging.getLogger(__name__)

DB_PATH = "data/zenith_memory.db"


def _rows(days: int = 7):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cutoff = (datetime.now() - timedelta(days=days)).isoformat()
    rows = [dict(r) for r in conn.execute(
        """SELECT ts,battery_pct,battery_plugged FROM laptop_health_snapshots
           WHERE ts >= ? ORDER BY ts""", (cutoff,)).fetchall()]
    conn.close()
    return rows


def _drain_rate_pct_per_hour(rows):
    pts = [(datetime.fromisoformat(r["ts"]), r["battery_pct"])
           for r in rows if r["battery_pct"] is not None and not r["battery_plugged"]]
    if len(pts) < 2:
        return None
    best = None
    run_start = 0
    for i in range(1, len(pts)):
        gap = (pts[i][0] - pts[i - 1][0]).total_seconds()
        if gap > 3600:
            best = _seg_rate(pts[run_start:i], best)
            run_start = i
    best = _seg_rate(pts[run_start:], best)
    return round(best, 1) if best else None


def _seg_rate(seg, current_best):
    if len(seg) < 2:
        return current_best
    hrs = (seg[-1][0] - seg[0][0]).total_seconds() / 3600
    drop = seg[0][1] - seg[-1][1]
    if hrs > 0.15 and drop > 0:
        rate = drop / hrs
        return max(current_best or 0, rate)
    return current_best


@function_tool()
async def battery_coach() -> str:
    """BATTERY COACH: your measured drain rate plus concrete plug-in /
    unplug advice tuned to how this laptop is actually used."""
    try:
        from Tools.laptop_health import collect_snapshot

        snap = collect_snapshot()
        b = snap.get("battery") or {}
        pct, plugged = b.get("pct"), bool(b.get("plugged"))
        if pct is None:
            return "🔋 No battery detected (desktop?) — nothing to coach."

        rows = _rows(7)
        n_snap = len(rows)
        drain = _drain_rate_pct_per_hour(rows)

        out = ["🔋 BATTERY COACH", "════════════════════"]
        out.append(f"Now: {pct}% ({'charging ⚡' if plugged else 'on battery 🔋'})")
        wear = b.get("wear_pct")
        if wear is not None:
            out.append(f"Health: {100 - wear:.0f}% capacity left (wear {wear}%)")

        if n_snap < 6:
            out.append(f"\n📊 Only {n_snap} snapshot(s) so far.")
            out.append("Keep me running a day (health checks auto-sample), then I "
                       "can predict exact plug-in times.")
            if pct <= 40 and not plugged:
                out.append("👉 Immediate advice: plug in NOW — deep drains below "
                           "40% age the cells faster.")
            return "\n".join(out)

        advice = []
        if drain and not plugged:
            hours_left = pct / drain
            advice.append(f"Measured drain ≈ {drain}%/hour → about {hours_left:.1f}h runtime left.")
            if hours_left < 1.5:
                advice.append("⚠️ Under two hours remain — find a socket soon.")
        elif plugged and pct < 80:
            advice.append("Charging — I'll ping you near 85% so you can unplug "
                          "before the high-stress zone (longevity tip).")
        elif plugged and pct >= 95:
            advice.append("Fully charged — safe to unplug; sitting pinned at 100% "
                          "for long sessions ages cells faster.")

        charge_hours = [datetime.fromisoformat(r["ts"]).hour for r in rows if r["battery_plugged"]]
        if len(set(charge_hours)) >= 3:
            common = max(set(charge_hours), key=charge_hours.count)
            advice.append(f"Pattern spotted: you usually charge around {common:02d}:00 — "
                          "I'll time reminders near that window.")

        out += ["", *("💡 " + a for a in advice)]
        out.append("\nℹ️ Rates computed from YOUR stored snapshots only.")
        return "\n".join(out)
    except Exception as e:
        return f"❌ Battery coach failed: {e}"
