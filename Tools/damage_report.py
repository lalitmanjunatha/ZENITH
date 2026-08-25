"""Zenith damage assessment — cinematic debrief built from REAL failure data.

Sources (all actual, nothing invented):
- Tool Doctor issue table (open + recently resolved)
- Windows Event Log application-error count since boot
- Health Oracle snapshot findings
"""

import asyncio
import logging

from livekit.agents import function_tool

logger = logging.getLogger(__name__)


async def _crash_count_today() -> int:
    """Application Error events (Event ID 1000) today via wevtutil."""
    try:
        today = datetime.now().strftime("%Y-%m-%dT00:00:00")

        def _run():
            import subprocess

            out = subprocess.run(
                ["wevtutil", "qe", "Application", "/q",
                 f"*[System[(EventID=1000) and TimeCreated[@SystemTime>='{today}']]]",
                 "/count:50", "/f:text"],
                capture_output=True, text=True, timeout=15,
            )
            txt = out.stdout
            return txt.count("Event ID") if txt else 0

        return await asyncio.to_thread(_run)
    except Exception:
        return 0


from datetime import datetime  # noqa: E402  (kept close to usage)


@function_tool()
async def damage_report() -> str:
    """DAMAGE ASSESSMENT: spoken-style debrief of what actually went wrong on
    this laptop today — tool failures, app crashes, hardware warnings — plus
    repair suggestions when issues exist."""
    try:
        from Tools.tool_doctor import _db as tdb
        from Tools.laptop_health import collect_snapshot, analyze_snapshot

        conn = tdb()
        open_rows = conn.execute(
            "SELECT id,tool_name,description FROM tool_issues WHERE status='open' ORDER BY id DESC LIMIT 5"
        ).fetchall()
        resolved = conn.execute(
            "SELECT COUNT(*) c FROM tool_issues WHERE status='resolved'").fetchone()["c"]
        conn.close()

        crashes = await _crash_count_today()
        snap = collect_snapshot()
        findings = analyze_snapshot(snap)

        problems = []
        for r in open_rows:
            problems.append(f"Tool '{r['tool_name']}' — {str(r['description'])[:70]}")
        if crashes:
            problems.append(f"{crashes} application crash event(s) logged by Windows today")
        for sev, msg in findings:
            if sev in ("🔴 CRITICAL", "🟠 HIGH"):
                problems.append(msg)

        if not problems and crashes == 0:
            return (
                "🩺 Damage assessment, sir: **all clear.** No tool failures on record, "
                "no crash events today, no hardware warnings. The suit held up perfectly."
            )

        out = "🩺 DAMAGE ASSESSMENT, SIR\n════════════════════\n"
        for p in problems[:8]:
            out += f"   • {p}\n"
        if resolved:
            out += f"\n✔️ {resolved} earlier issue(s) already repaired."
        out += '\n➡ Say "suggest repairs" and I will draft the fix plans.'
        return out
    except Exception as e:
        return f"❌ Assessment failed: {e}"
