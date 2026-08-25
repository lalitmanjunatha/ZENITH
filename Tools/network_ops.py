"""Zenith Network Ops — Wi-Fi password recall + one-tap network reset.

F21  wifi_passwords      : read saved network keys (needs admin cmd window)
F22  network_reset       : flush DNS → release/renew IP → restart adapter, narrated
plus quick diagnostics helpers.
"""

import asyncio
import logging
import re
import subprocess

from livekit.agents import function_tool

logger = logging.getLogger(__name__)


def _run(cmd: list, timeout=20):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.returncode, (r.stdout or ""), (r.stderr or "")
    except Exception as e:
        return 1, "", str(e)


@function_tool()
async def list_wifi_profiles() -> str:
    """List every Wi-Fi network this laptop has saved (names only)."""
    code, out, err = await asyncio.to_thread(
        _run, ["netsh", "wlan", "show", "profiles"])
    if code != 0:
        return f"❌ netsh failed: {err.strip()[:100]}"
    names = [m.group(1).strip() for m in
             re.finditer(r"All User Profile\s*:\s*(.+)", out)]
    if not names:
        return "📶 No saved Wi-Fi profiles."
    return f"📶 {len(names)} saved network(s):\n" + "\n".join(f"   • {n}" for n in names)


def _extract_key(profile: str) -> tuple[str, str]:
    code, out, _ = _run(["netsh", "wlan", "show", "profile", f"name={profile}", "key=clear"])
    if code != 0:
        return profile, ""
    m = re.search(r"Key Content\s*:\s*(.+)", out)
    key = m.group(1).strip() if m else ""
    auth = ""
    ma = re.search(r"Authentication\s*:\s*(.+)", out)
    if ma:
        auth = ma.group(1).strip()
    return key, auth


@function_tool()
async def wifi_passwords(profile_name: str = "") -> str:
    """Recall saved Wi-Fi passwords. Say a specific network name for just that
    one, or none for ALL saved networks. Requires admin rights on Windows —
    if access is denied, I will tell you exactly how to grant it.

    Args:
        profile_name: Optional single network; empty = all saved networks
    """
    def _work():
        if profile_name.strip():
            key, auth = _extract_key(profile_name.strip())
            return [(profile_name.strip(), key, auth)]
        _, out, _ = _run(["netsh", "wlan", "show", "profiles"])
        names = [m.group(1).strip() for m in re.finditer(r"All User Profile\s*:\s*(.+)", out)]
        rows = []
        for n in names[:15]:
            key, auth = _extract_key(n)
            rows.append((n, key, auth))
        return rows

    rows = await asyncio.to_thread(_work)
    if rows is None:
        return "❌ Could not query WLAN service."

    lines = ["🔑 SAVED WI-FI KEYS\n════════════════════"]
    denied = False
    any_open = False
    for name, key, auth in rows:
        if key:
            lines.append(f"   • {name} → {key}" + (f"   [{auth}]" if auth else ""))
        elif auth.lower().startswith("open"):
            any_open = True
            lines.append(f"   • {name} → (open network, no password)")
        else:
            denied = True
            lines.append(f"   • {name} → 🔒 key hidden by Windows")
    if denied:
        lines.append("\n⚠️ Hidden keys mean this shell lacks admin rights.")
        lines.append("Fix: run Terminal as Administrator once, then ask me again — "
                     "or I can print the exact netsh command for you.")
    if any_open and len(lines) == 2:
        pass
    return "\n".join(lines)


@function_tool()
async def internet_diagnostics() -> str:
    """Quick connectivity ladder: adapter → gateway → DNS → internet, so we know
    exactly which link is broken before touching anything."""
    steps = []

    code, out, _ = await asyncio.to_thread(
        _run, ["netsh", "interface", "show", "interface"])
    up = [l for l in out.splitlines() if "Connected" in l or "连接" in l]
    steps.append(("🟢 Adapter connected" if up else "🔴 No adapter connected",
                  bool(up)))

    # default gateway present?
    ip_out = (await asyncio.to_thread(
        _run, ["ipconfig"]))[1]
    gw = re.search(r"Default Gateway[ .:]+([\d.]+)", ip_out)
    steps.append((f"{'🟢' if gw else '🔴'} Gateway: {gw.group(1) if gw else 'none found'}", bool(gw)))

    if gw:
        c, o, e = await asyncio.to_thread(_run, ["ping", "-n", "1", "-w", "1500", gw.group(1)])
        ok = ("TTL=" in o)
        steps.append((f"{'🟢' if ok else '🔴'} Ping gateway {'ok' if ok else 'FAILED'}", ok))

    c, o, e = await asyncio.to_thread(_run, ["ping", "-n", "1", "-w", "2000", "8.8.8.8"])
    dns_ip_ok = "TTL=" in o
    steps.append((f"{'🟢' if dns_ip_ok else '🔴'} Internet (8.8.8.8): "
                  f"{'reachable' if dns_ip_ok else 'unreachable'}", dns_ip_ok))

    c, o, e = await asyncio.to_thread(_run, ["ping", "-n", "1", "-w", "2500", "google.com"])
    dns_name_ok = "TTL=" in o
    steps.append((f"{'🟢' if dns_name_ok else '🔴'} DNS resolution (google.com): "
                  f"{'works' if dns_name_ok else 'BROKEN'}", dns_name_ok))

    verdict = "Internet link healthy end-to-end ✅"
    if up and not gw:
        verdict = "Adapter up but no gateway — router/link issue."
    elif gw and not dns_ip_ok:
        verdict = "Gateway reachable but no internet — modem/ISP issue."
    elif dns_ip_ok and not dns_name_ok:
        verdict = "IPs work but DNS broken → run 'reset network' to fix."

    body = "\n".join(f"   {s}" for s, _ in steps)
    return f"🌐 NETWORK DIAGNOSTICS\n════════════════════\n{body}\n\n🩺 Verdict: {verdict}"


@function_tool()
async def reset_network(scope: str = "dns") -> str:
    """One-tap network repair, escalating levels:
       'dns'     → flush DNS cache          (safe, instant)
       'renew'   → new IP from router       (brief disconnect)
       'adapter' → full adapter restart     (10-15s offline)
    Each level includes the previous ones.

    Args:
        scope: dns / renew / adapter
    """
    s = scope.strip().lower()
    log = []
    log.append("🧹 Flushing DNS cache…")
    await asyncio.to_thread(_run, ["ipconfig", "/flushdns"])

    if s in ("renew", "adapter"):
        log.append("📡 Releasing current IP…")
        await asyncio.to_thread(_run, ["ipconfig", "/release"], timeout=25)
        log.append("📡 Requesting fresh IP from router…")
        rc, o, e = await asyncio.to_thread(_run, ["ipconfig", "/renew"], timeout=40)

    if s == "adapter":
        # find primary interface alias
        _, out, _ = await asyncio.to_thread(_run, ["netsh", "interface", "show", "interface"])
        alias = None
        for line in out.splitlines():
            if "Connected" in line or "已连接" in line:
                parts = line.split()
                alias = parts[-1] if parts else None
                break
        if alias:
            log.append(f"🔁 Restarting adapter '{alias}' (~10s offline)…")
            await asyncio.to_thread(_run, ["netsh", "interface", "set", "interface",
                                           f"name={alias}", "admin=disable"], timeout=20)
            await asyncio.sleep(3)
            await asyncio.to_thread(_run, ["netsh", "interface", "set", "interface",
                                           f"name={alias}", "admin=enable"], timeout=20)
        else:
            log.append("⚠️ Could not identify active adapter — skipped restart.")

    # verify
    diag = await internet_diagnostics()
    ok_line = [l for l in diag.splitlines() if "8.8.8.8" in l]
    fixed = "reachable" in "".join(ok_line)
    log.append("✅ Internet restored!" if fixed
               else "⚠️ Still down after reset — deeper issue (router/ISP/driver).")

    return ("🔧 NETWORK RESET (" + s.upper() + ")\n════════════════════\n"
            + "\n".join(f"   {l}" for l in log))