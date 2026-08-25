"""System Explainer — identify what any running process actually is.

Combines live psutil data (path, command line, resources, parent) with a
built-in dictionary of common Windows processes and honest risk heuristics.
Unknown binaries are labelled UNVERIFIED with concrete next-step checks —
never invented facts about what a file "definitely" does.
"""

import logging
import os

from livekit.agents import function_tool

logger = logging.getLogger(__name__)

# Common Windows processes (name → plain-words purpose)
KNOWN = {
    "explorer.exe": "Windows shell — desktop, taskbar, file explorer UI.",
    "svchost.exe": "Windows service host; legit ones run from System32. Multiple instances normal.",
    "system": "Windows kernel core.",
    "system idle process": "Placeholder showing free CPU, not a real process.",
    "csrss.exe": "Windows client/server runtime — critical system process.",
    "winlogon.exe": "Handles Windows logon sessions.",
    "services.exe": "Windows Service Control Manager.",
    "lsass.exe": "Local Security Authority — handles authentication.",
    "dwm.exe": "Desktop Window Manager — composites your screen visuals.",
    "fontdrvhost.exe": "Windows font driver host.",
    "sihost.exe": "Shell Infrastructure Host — start menu, taskbar bits.",
    "ctfmon.exe": "Text input / language bar support.",
    "searchapp.exe": "Windows Start-menu search UI.",
    "searchindexer.exe": "Builds Windows file-search index.",
    "audiodg.exe": "Windows audio device graph (sound engine).",
    "python.exe": "Python interpreter — likely Zenith itself or your scripts.",
    "pythonw.exe": "Python without console window.",
    "code.exe": "Visual Studio Code editor.",
    "msedgewebview2.exe": "Microsoft Edge WebView — embedded browser inside other apps.",
    "msedge.exe": "Microsoft Edge browser.",
    "chrome.exe": "Google Chrome browser.",
    "firefox.exe": "Mozilla Firefox browser.",
    "whatsapp.exe": "WhatsApp desktop app.",
    "telegram.exe": "Telegram desktop app.",
    "spotify.exe": "Spotify music client.",
    "discord.exe": "Discord chat client.",
    "steam.exe": "Steam game platform.",
    "onedrive.exe": "Microsoft OneDrive sync client.",
    "dropbox.exe": "Dropbox sync client.",
    "securityhealthservice.exe": "Windows Defender status service.",
    "msmpeng.exe": "Windows Defender antivirus engine.",
    "nissrv.exe": "Windows Defender network inspection.",
    "runtimebroker.exe": "Permissions broker for Windows Store apps.",
    "widgetservice.exe": "Windows widgets background service.",
    "phonelink.exe": "Windows Phone Link app.",
    "livekit.exe": "LiveKit agent/worker (Zenith voice stack).",
}


def _find_process(query: str):
    import psutil

    q = query.strip().lower()
    if q.isdigit():
        try:
            return psutil.Process(int(q))
        except Exception:
            return None
    for p in psutil.process_iter(["pid", "name"]):
        try:
            if p.info["name"] and q in p.info["name"].lower():
                return p
        except Exception:
            continue
    return None


@function_tool()
async def explain_process(name_or_pid: str) -> str:
    """WHAT IS THIS EXE? Identify a running program by name or PID:
    its path, resource use, parent, plain-words purpose, and honest risk flags.

    Args:
        name_or_pid: e.g. "chrome.exe" or "4816"
    """
    try:
        p = _find_process(name_or_pid)
        if p is None:
            return f"❌ No running process matches '{name_or_pid}'. Say \"top processes\" to list candidates."
        info = p.as_dict(attrs=["pid", "name", "exe", "cmdline", "cpu_percent",
                                "memory_info", "create_time", "ppid", "username"])
        name = (info.get("name") or "").lower()
        exe = info.get("exe") or "unknown path"
        mem_mb = round((info.get("memory_info").rss if info.get("memory_info") else 0) / 1024**2, 1)

        out = f"🔎 PROCESS REPORT\n════════════════════\n"
        out += f"📛 {info['name']}  (PID {info['pid']})\n"
        out += f"📂 {exe}\n"
        out += f"💾 RAM: {mem_mb} MB\n"
        parent_name = ""
        try:
            parent = p.parent()
            parent_name = parent.info["name"] if parent else ""
            out += f"👪 Parent: {parent_name} (PID {parent.pid})\n" if parent else ""
        except Exception:
            pass

        known_line = KNOWN.get(name)
        if not known_line and name.startswith("svchost"):
            known_line = KNOWN["svchost.exe"]
        out += f"\n📖 Purpose: {known_line}\n" if known_line else \
               "\n📖 Purpose: ⚠️ UNVERIFIED — not in my built-in database of known processes.\n"

        # Risk heuristics (transparent rules, no fabrication)
        flags = []
        lowered_exe = exe.lower()
        if known_line is None and any(k in lowered_exe for k in ("\\temp\\", "\\appdata\\local\\temp", "\\downloads\\")):
            flags.append("Runs from a temp/downloads folder — unusual for trusted software.")
        if name.endswith(".tmp") or ".tmp-" in name:
            flags.append("Temporary-named executable.")
        if known_line is None and "\\" not in exe and exe != "unknown path":
            flags.append("No full path exposed (may be elevated/system).")
        if flags:
            out += "🚩 Risk checks:\n" + "".join(f"   • {f}\n" for f in flags)
            out += "➡ Verify by right-clicking the file → Properties → Digital Signatures, or ask me to search the web for the exact filename."
        elif known_line:
            out += "✅ Matches a well-known Windows/application component."

        try:
            from datetime import datetime
            started = datetime.fromtimestamp(info["create_time"])
            out += f"\n⏱️ Started: {started.strftime('%d %b %H:%M')}"
        except Exception:
            pass
        return out
    except Exception as e:
        return f"❌ Explain failed: {e}"


@function_tool()
async def top_processes(count: int = 10) -> str:
    """List your heaviest running programs right now by memory usage.

    Args:
        count: How many to show (default 10)
    """
    try:
        import psutil

        procs = []
        for p in psutil.process_iter(["pid", "name", "memory_info"]):
            try:
                mi = p.info["memory_info"]
                if mi:
                    procs.append((mi.rss, p.info["pid"], p.info["name"] or "?"))
            except Exception:
                continue
        procs.sort(reverse=True)
        total = psutil.virtual_memory()
        out = (f"⚙️ TOP {min(int(count), len(procs))} BY RAM "
               f"(system total used {total.percent}%)\n════════════════════\n")
        for rss, pid, name in procs[: int(count)]:
            tag = " ✅known" if name.lower() in KNOWN else " ❔"
            out += f"  {rss / 1024**2:7.0f} MB  [{pid}] {name}{tag}\n"
        out += "\nAsk \"explain <name or pid>\" for any row's full report."
        return out
    except Exception as e:
        return f"❌ Listing failed: {e}"
