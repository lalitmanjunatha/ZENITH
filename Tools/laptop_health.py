"""Laptop Health Oracle — predictive hardware monitoring for Zenith.

Tracks battery wear, disk SMART status, storage growth trends, RAM pressure
and thermals. Snapshots are stored daily in the existing Zenith SQLite DB so
trends/predictions come from REAL history, never fabricated numbers.
Anything the OS cannot measure is reported as N/A honestly.
"""

import json
import logging
import sqlite3
import subprocess
import time
from datetime import datetime, timedelta
from pathlib import Path

from livekit.agents import function_tool

logger = logging.getLogger(__name__)

DB_PATH = "data/zenith_memory.db"


def _db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute(
        """CREATE TABLE IF NOT EXISTS laptop_health_snapshots (
               id INTEGER PRIMARY KEY AUTOINCREMENT,
               ts TEXT,
               battery_pct REAL,
               battery_plugged INTEGER,
               ram_pct REAL,
               disks_json TEXT,
               smart_json TEXT,
               temps_json TEXT
           )"""
    )
    return conn


def _smart_status():
    """Disk SMART status via wmic. Returns list of {model, status}."""
    out = []
    try:
        raw = subprocess.run(
            ["wmic", "diskdrive", "get", "model,status"],
            capture_output=True, text=True, timeout=15,
        ).stdout.strip().splitlines()
        for line in raw[1:]:
            parts = line.split()
            if len(parts) >= 2 and parts[-1].upper() in ("OK", "PRED FAIL", "UNKNOWN"):
                status = parts[-1]
                model = " ".join(parts[:-1]).strip()
                if model:
                    out.append({"model": model[:40], "status": status})
    except Exception as e:
        logger.debug(f"SMART query unavailable: {e}")
    return out


def _temps():
    """Best-effort thermal zones. Honest 'unavailable' when unsupported."""
    try:
        import psutil

        t = getattr(psutil, "sensors_temperatures", lambda **k: {})()
        if t:
            flat = []
            for name, entries in t.items():
                for e in entries:
                    if e.current:
                        flat.append({"sensor": f"{name}/{e.label or '?'}", "celsius": round(e.current, 1)})
            return flat
    except Exception:
        pass
    try:
        raw = subprocess.run(
            ["wmic", "/namespace:\\\\root\\wmi", "PATH", "MSAcpi_ThermalZoneTemperature",
             "GET", "CurrentTemperature"],
            capture_output=True, text=True, timeout=10,
        ).stdout.strip().splitlines()
        vals = []
        for line in raw[1:]:
            s = line.strip()
            if s.isdigit():
                c = (int(s) / 10.0) - 273.15  # tenths of Kelvin
                if -20 < c < 150:
                    vals.append({"sensor": "acpi_thermal", "celsius": round(c, 1)})
        return vals
    except Exception:
        return []


def _battery_detail():
    """Battery percent/plug via psutil; wear estimate from WMIC FullCharge vs Design capacity."""
    try:
        import psutil

        b = psutil.sensors_battery()
        base = {"pct": round(b.percent, 1), "plugged": bool(b.power_plugged)} if b else {"pct": None, "plugged": None}
    except Exception:
        base = {"pct": None, "plugged": None}
    try:
        raw = subprocess.run(
            ["wmic", "path", "Win32_Battery", "get",
             "DesignCapacity,FullChargeCapacity,BatteryStatus"],
            capture_output=True, text=True, timeout=10,
        ).stdout.strip().splitlines()
        if len(raw) >= 2:
            cols = raw[0].split()
            vals = raw[1].split()
            d = dict(zip(cols, vals))
            design, full = int(d.get("DesignCapacity", 0)), int(d.get("FullChargeCapacity", 0))
            if design > 0 and full > 0:
                base["wear_pct"] = round(100 * (1 - full / design), 1)
                base["full_capacity_mwh"] = full
    except Exception:
        pass
    return base


def collect_snapshot() -> dict:
    """Gather one full health snapshot (no DB write)."""
    try:
        import psutil

        ram_pct = psutil.virtual_memory().percent
        disks = []
        for p in psutil.disk_partitions(all=False):
            try:
                u = psutil.disk_usage(p.mountpoint)
                disks.append({
                    "mount": p.mountpoint,
                    "total_gb": round(u.total / 2**30, 1),
                    "free_gb": round(u.free / 2**30, 1),
                    "used_pct": round(u.percent, 1),
                })
            except Exception:
                continue
    except Exception as e:
        logger.warning(f"psutil failed: {e}")
        ram_pct, disks = None, []

    snap = {
        "ts": datetime.now().isoformat(),
        "battery": _battery_detail(),
        "ram_pct": ram_pct,
        "disks": disks,
        "smart": _smart_status(),
        "temps": _temps(),
    }
    return snap


def analyze_snapshot(snap: dict) -> list:
    """Rule-based findings from a snapshot. Only real measured values used."""
    findings = []
    for d in snap.get("smart", []):
        if d["status"].upper() == "PRED FAIL":
            findings.append(("🔴 CRITICAL", f"Drive '{d['model']}' reports SMART PREDICTIVE FAILURE — back up NOW."))
    batt = snap.get("battery") or {}
    if batt.get("wear_pct") is not None:
        if batt["wear_pct"] >= 40:
            findings.append(("🟠 HIGH", f"Battery worn {batt['wear_pct']}% — expect noticeably short runtime."))
        elif batt["wear_pct"] >= 25:
            findings.append(("🟡 MEDIUM", f"Battery wear {batt['wear_pct']}% — plan replacement within a year."))
    if batt.get("pct") is not None and not batt.get("plugged") and batt["pct"] <= 20:
        findings.append(("🟡 MEDIUM", f"On battery at {batt['pct']}% — plug in soon."))
    if snap.get("ram_pct") is not None and snap["ram_pct"] >= 90:
        findings.append(("🟠 HIGH", f"RAM at {snap['ram_pct']}% — close heavy apps or expect slowdowns."))
    for d in snap.get("disks", []):
        if d["free_gb"] is not None and d["free_gb"] < 5:
            findings.append(("🔴 CRITICAL", f"Drive {d['mount']} has only {d['free_gb']} GB free — OS updates may fail."))
        elif d.get("used_pct", 0) >= 92:
            findings.append(("🟠 HIGH", f"Drive {d['mount']} {d['used_pct']}% full."))
    for t in snap.get("temps", []):
        if t["celsius"] >= 85:
            findings.append(("🟠 HIGH", f"{t['sensor']} at {t['celsius']}°C — check cooling/vents."))
    return findings


@function_tool()
async def run_health_snapshot() -> str:
    """Take a laptop health snapshot now and store it for trend predictions
    (battery, RAM, disk space, SMART, temperatures)."""
    try:
        snap = collect_snapshot()
        conn = _db()
        conn.execute(
            "INSERT INTO laptop_health_snapshots (ts,battery_pct,battery_plugged,ram_pct,disks_json,smart_json,temps_json) VALUES (?,?,?,?,?,?,?)",
            (
                snap["ts"],
                snap["battery"].get("pct"),
                1 if snap["battery"].get("plugged") else 0,
                snap["ram_pct"],
                json.dumps(snap["disks"]),
                json.dumps(snap["smart"]),
                json.dumps(snap["temps"]),
            ),
        )
        conn.commit()
        n = conn.execute("SELECT COUNT(*) c FROM laptop_health_snapshots").fetchone()["c"]
        conn.close()
        return f"🩺 Snapshot stored ({n} total in history). Say 'laptop health' for the full oracle report."
    except Exception as e:
        return f"❌ Snapshot failed: {e}"


def _storage_trend(mount: str):
    """Compute GB/day free-space burn rate from stored snapshots (needs >=2)."""
    try:
        conn = _db()
        rows = conn.execute(
            "SELECT ts, disks_json FROM laptop_health_snapshots ORDER BY id DESC LIMIT 30"
        ).fetchall()
        conn.close()
        pts = []
        for r in reversed(rows):
            try:
                disks = json.loads(r["disks_json"])
                for d in disks:
                    if d.get("mount") == mount and r["ts"]:
                        pts.append((datetime.fromisoformat(r["ts"]), d["free_gb"]))
            except Exception:
                continue
        if len(pts) < 2:
            return None
        (t0, f0), (t1, f1) = pts[0], pts[-1]
        days = max((t1 - t0).total_seconds() / 86400, 1e-6)
        rate = (f0 - f1) / days  # GB consumed per day (positive = filling up)
        return {"rate_gb_per_day": round(rate, 3), "span_days": round(days, 2), "latest_free_gb": f1}
    except Exception:
        return None


@function_tool()
async def get_laptop_health() -> str:
    """LAPTOP HEALTH ORACLE: full report on battery wear, disk SMART, storage
    growth prediction, RAM pressure and thermals — computed from live sensors
    plus your stored snapshot history."""
    try:
        snap = collect_snapshot()

        # Persist so every manual check also feeds the trend engine
        try:
            conn = _db()
            conn.execute(
                "INSERT INTO laptop_health_snapshots (ts,battery_pct,battery_plugged,ram_pct,disks_json,smart_json,temps_json) VALUES (?,?,?,?,?,?,?)",
                (snap["ts"], snap["battery"].get("pct"),
                 1 if snap["battery"].get("plugged") else 0, snap["ram_pct"],
                 json.dumps(snap["disks"]), json.dumps(snap["smart"]), json.dumps(snap["temps"])),
            )
            conn.commit(); conn.close()
        except Exception:
            pass

        out = "🩺 LAPTOP HEALTH ORACLE\n════════════════════\n"

        b = snap["battery"]
        if b.get("pct") is not None:
            out += f"\n🔋 Battery: {b['pct']}% {'(charging ⚡)' if b.get('plugged') else '(on battery 🔋)'}"
            if b.get("wear_pct") is not None:
                out += f" | wear: {b['wear_pct']}%"
        else:
            out += "\n🔋 Battery: N/A (desktop or sensor unsupported)"

        out += f"\n🧠 RAM usage: {snap['ram_pct'] if snap['ram_pct'] is not None else 'N/A'}%"

        out += "\n💾 Storage:"
        for d in snap["disks"]:
            out += f"\n   • {d['mount']}  {d['free_gb']} GB free of {d['total_gb']} GB ({d['used_pct']}% used)"
            tr = _storage_trend(d["mount"])
            if tr and tr["rate_gb_per_day"] > 0.01 and tr["latest_free_gb"] > 0:
                days_left = int(tr["latest_free_gb"] / tr["rate_gb_per_day"])
                out += (
                    f"\n     📈 Trend: filling ~{tr['rate_gb_per_day']} GB/day "
                    f"(over {tr['span_days']}d history) → FULL in ~{days_left} day(s)"
                    if days_left < 400 else
                    f"\n     📈 Trend: ~{tr['rate_gb_per_day']} GB/day — no concern"
                )

        if snap["smart"]:
            out += "\n🛡️ Disk SMART:"
            for s in snap["smart"]:
                icon = "🟢" if s["status"].upper() == "OK" else "🔴"
                out += f"\n   {icon} {s['status']}  {s['model']}"
        else:
            out += "\n🛡️ Disk SMART: N/A (query unsupported)"

        if snap["temps"]:
            hottest = max(t["celsius"] for t in snap["temps"])
            out += f"\n🌡️ Temps: hottest {hottest}°C (" + ", ".join(f"{t['sensor']}:{t['celsius']}°C" for t in snap["temps"]) + ")"
        else:
            out += "\n🌡️ Temps: N/A (no thermal sensor exposed)"

        findings = analyze_snapshot(snap)
        if findings:
            out += "\n\n⚠️ FINDINGS:\n"
            for sev, msg in findings:
                out += f"   {sev} — {msg}\n"
        else:
            out += "\n\n✅ No issues detected in this snapshot."
        out += "\nℹ️ Predictions derive from YOUR stored snapshots only — never fabricated."
        return out
    except Exception as e:
        return f"❌ Health report failed: {e}"


@function_tool()
async def predict_storage() -> str:
    """Predict when each drive will be full based on your real usage history."""
    try:
        snap = collect_snapshot()
        if not snap["disks"]:
            return "❌ No drives readable."
        out = "📈 STORAGE FORECAST (from your actual history)\n════════════════════\n"
        any_trend = False
        for d in snap["disks"]:
            tr = _storage_trend(d["mount"])
            out += f"\n{d['mount']} free now: {d['free_gb']} GB"
            if not tr:
                out += " | need ≥2 snapshots (say 'run health snapshot' today and tomorrow)"
                continue
            any_trend = True
            if tr["rate_gb_per_day"] <= 0.01:
                out += f" | 🟢 stable (~{tr['rate_gb_per_day']} GB/day)"
            else:
                days = int(tr["latest_free_gb"] / tr["rate_gb_per_day"])
                eta = (datetime.now() + timedelta(days=days)).strftime("%d %b %Y")
                out += f" | 🔥 burning {tr['rate_gb_per_day']} GB/day → full in ~{days} days ({eta})"
        if not any_trend:
            out += "\n\nTip: I auto-snapshot whenever you ask for health reports; give me two different days for forecasts."
        return out
    except Exception as e:
        return f"❌ Forecast failed: {e}"
