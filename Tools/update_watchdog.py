"""Zenith Update Watchdog — monthly driver/OS/app update advisories.

Checks what's actually updatable using winget (Windows Package Manager) and
flags Windows Update status via USO/registry heuristics. Never auto-installs
anything without an explicit confirm — updates can restart your machine.
"""

import asyncio
import logging
import re
import subprocess

from livekit.agents import function_tool

logger = logging.getLogger(__name__)


def _run(cmd: list, timeout: int = 60):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.returncode, r.stdout or "", r.stderr or ""
    except FileNotFoundError:
        return 127, "", "not installed"
    except Exception as e:
        return 1, "", str(e)


@function_tool()
async def check_updates() -> str:
    """UPDATE WATCHDOG: scan for outdated apps (via winget), pending Windows
    updates, and GPU-driver advisories. Read-only report — nothing installs."""
    sections = []

    # --- winget app upgrades -------------------------------------------
    code, out, err = await asyncio.to_thread(_run, ["winget", "upgrade"], timeout=90)
    if code == 0 or "upgrades available" in out.lower():
        lines = [l for l in out.splitlines() if l.strip()]
        # header rows usually contain Id/Version columns
        pkgs = []
        for l in lines:
            m = re.match(r"\S+\s{2,}(.+?)\s{2,}(\S+)\s{2,}(\S+)\s{2,}", l)
            if not m:
                # fallback parse: first token id, then name
                parts = l.split()
                if len(parts) >= 3 and not l.lower().startswith(("the ", "winget", "-", "name")):
                    pkgs.append((parts[0][:28], parts[-2] if len(parts) >= 4 else "?"))
            else:
                pkgs.append((m.group(1)[:28], m.group(2)))
        if pkgs:
            body = "\n".join(f"   • {n:<30} {v} → {v}" if False else f"   • {n:<32} current {v}"
                             for n, v in pkgs[:10])
            sections.append(f"📦 APP UPDATES AVAILABLE ({len(pkgs)}):\n{body}")
        else:
            sections.append("📦 Apps: all up to date ✅")
    elif code == 127:
        sections.append("📦 winget not found — install 'App Installer' from MS Store "
                        "for full app-update scanning.")
    else:
        sections.append(f"📦 winget error: {err.strip()[:80]}")

    # --- Windows Update pending? ---------------------------------------
    code, out, err = await asyncio.to_thread(_run,
        ["powershell", "-NoProfile", "-Command",
         "(New-Object -ComObject Microsoft.Update.Session)."
         "CreateUpdateSearcher().Search('IsInstalled=0').Updates.Count"],
        timeout=120)
    if code == 0 and out.strip().isdigit():
        n = int(out.strip())
        sections.append(
            f"🪟 WINDOWS UPDATES PENDING: {n}" + ("  ⚠️ schedule a restart window." if n else " ✅"))
    else:
        sections.append("🪟 Windows Update count unavailable (service busy?) — "
                        "check Settings → Windows Update manually.")

    # --- GPU driver hint ------------------------------------------------
    code, out, _ = await asyncio.to_thread(_run,
        ["powershell", "-NoProfile", "-Command",
         "Get-CimInstance Win32_VideoController | Select-Object -ExpandProperty DriverDate"],
        timeout=45)
    date_hint = ""
    if out.strip():
        try:
            from datetime import datetime
            raw = out.strip().splitlines()[0].strip()
            d = datetime.strptime(raw[:10], "%Y-%m-%d") if "-" in raw else None
            if d:
                age_days = (datetime.now() - d).days
                date_hint = f"(driver dated {d:%b %Y}, {age_days//30} months old)"
                if age_days > 365:
                    date_hint += " — consider checking NVIDIA/AMD/Intel for newer."
        except Exception:
            pass
    sections.append("🎮 GPU DRIVERS: " + (date_hint or "date unavailable"))

    out = "🛰️ UPDATE WATCHDOG\n════════════════════\n" + "\n\n".join(sections)
    out += ("\n\nℹ️ Nothing was installed. Say \"install app updates\" if you want me "
            "to run winget upgrades (apps only; I'll never force a restart).")
    return out


@function_tool()
async def install_app_updates(confirm: bool = False) -> str:
    """Install available APPLICATION updates via winget (skips OS restarts).
    Requires confirm=True.

    Args:
        confirm: Must be True to begin installing.
    """
    if not confirm:
        return "⛔ Confirmation required — app updates can take several minutes."
    code, out, err = await asyncio.to_thread(_run, ["winget", "upgrade", "--all", "--silent"],
                                             timeout=1800)
    if code in (0, 0x8B15E015):   # success / partial-success codes
        return ("📦 App update sweep finished.\n"
                + (out[-600:] if out else "(no output)")
                + "\nReboot only when convenient — I never force one.")
    return f"❌ winget failed ({code}): {err.strip()[:150]}"


@function_tool()
async def enable_update_monthly_watch() -> str:
    """Add 'check updates' into the Daily Threat Board rotation so Zenith
    reminds you roughly once a month."""
    conn_path = "data/zenith_memory.db"
    import sqlite3
    conn = sqlite3.connect(conn_path)
    conn.execute("""CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT)""")
    conn.execute(
        "INSERT INTO meta (key,value) VALUES ('update_watch','monthly') "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value")
    conn.commit(); conn.close()
    return ("🛰️ Monthly update-watch enabled — it will surface on your Threat Board "
            "when ~30 days pass since the last check.")
