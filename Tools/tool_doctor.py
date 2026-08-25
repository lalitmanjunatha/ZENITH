"""Tool Doctor — health monitoring and repair suggestions for Zenith's tools.

What it measures HONESTLY:
- Static syntax health: every Tools/*.py compiled to catch breakage early
- Registry check: registered tool entries in agent.py
- Human-reported issues: you report what misbehaved; I track + suggest repairs
(Per-call runtime error rates are NOT faked — LiveKit doesn't expose that hook,
so the dashboard labels exactly what is and isn't measured.)

Repair flow (107): suggest_repairs() produces a step-by-step plan wired into the
existing self_edit workflow (read_source_file -> modify_source_file -> restart).
"""

import logging
import py_compile
import re
import sqlite3
from datetime import datetime
from pathlib import Path

from livekit.agents import function_tool

logger = logging.getLogger(__name__)

DB_PATH = "data/zenith_memory.db"
TOOLS_DIR = Path("Tools")


def _db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute(
        """CREATE TABLE IF NOT EXISTS tool_issues (
               id INTEGER PRIMARY KEY AUTOINCREMENT,
               tool_name TEXT,
               description TEXT,
               status TEXT DEFAULT 'open',
               created_at TEXT
           )"""
    )
    return conn


def _registered_tool_names():
    """Parse agent.py's tools list for registered names."""
    try:
        src = Path("agent.py").read_text(encoding="utf-8", errors="replace")
        m = re.search(r"tools = \[(.*?)\n\s*\]", src, re.S)
        if not m:
            return []
        return [ln.strip().rstrip(",") for ln in m.group(1).splitlines()
                if ln.strip() and not ln.strip().startswith("#")]
    except Exception:
        return []


def _static_scan():
    """Compile-check every Tools/*.py. Returns (ok_count, problems list)."""
    ok, problems = 0, []
    if not TOOLS_DIR.exists():
        return ok, problems
    for f in sorted(TOOLS_DIR.glob("*.py")):
        try:
            py_compile.compile(str(f), doraise=True)
            ok += 1
        except Exception as e:
            problems.append((f.name, str(e).splitlines()[0][:120]))
    return ok, problems


def _find_file_for_tool(tool_name: str) -> str:
    tname = (tool_name or "").strip().lower()
    if not TOOLS_DIR.exists() or not tname:
        return ""
    for f in sorted(TOOLS_DIR.glob("*.py")):
        try:
            src = f.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        if re.search(rf"(?:def|async def)\s+{re.escape(tname)}\b", src):
            return str(f).replace("\\", "/")
    # fallback: name-similarity of module file
    stem = tname.split("_")[0]
    if not stem:
        return ""
    for f in sorted(TOOLS_DIR.glob("*.py")):
        if stem in f.stem.lower():
            return str(f).replace("\\", "/")
    return ""


@function_tool()
async def tool_health_dashboard() -> str:
    """TOOL HEALTH DASHBOARD: syntax-scans all tool modules, counts registered
    tools, and summarizes open/recent issues. Clearly states which signals are
    real measurements and which are not tracked."""
    out = "🩺 TOOL DOCTOR DASHBOARD\n════════════════════\n"

    ok, problems = _static_scan()
    total = len(list(TOOLS_DIR.glob("*.py"))) if TOOLS_DIR.exists() else 0
    icon = "🟢" if not problems else "🔴"
    out += f"{icon} Syntax health: {ok}/{total} modules compile clean\n"
    for name, err in problems[:6]:
        out += f"   🔴 {name}: {err}\n"

    names = _registered_tool_names()
    out += f"\n🧰 Registered tool entries in agent.py: {len(names)}\n"

    conn = _db()
    open_issues = conn.execute(
        "SELECT * FROM tool_issues WHERE status='open' ORDER BY id DESC LIMIT 10").fetchall()
    fixed = conn.execute("SELECT COUNT(*) c FROM tool_issues WHERE status='resolved'").fetchone()["c"]
    conn.close()

    if open_issues:
        out += f"\n🐞 Open issues ({len(open_issues)}):\n"
        for r in open_issues:
            out += f"   #{r['id']} [{r['tool_name']}] {r['description'][:80]}\n"
        out += '➡ Say "suggest repairs" for a fix plan.\n'
    else:
        out += "\n✅ No open issues on record.\n"
    out += f"✔️ {fixed} issue(s) resolved historically."

    out += ("\n\nℹ️ Measured: module compilation + registry count + reported issues. "
            'NOT tracked (honestly): automatic per-call error counters. Report anything '
            'weird with: report_tool_issue("<name>", "<what happened>").')
    return out


@function_tool()
async def report_tool_issue(tool_name: str, description: str) -> str:
    """Report a misbehaving tool so Tool Doctor can track it and suggest fixes.

    Args:
        tool_name: Function name, e.g. send_whatsapp_message
        description: What went wrong (include exact error text if any)
    """
    conn = _db()
    cur = conn.execute(
        "INSERT INTO tool_issues (tool_name,description,status,created_at) VALUES (?,?,?,?)",
        (tool_name.strip(), description.strip(), "open", datetime.now().isoformat()),
    )
    n = conn.execute("SELECT COUNT(*) c FROM tool_issues WHERE status='open'").fetchone()["c"]
    conn.commit(); conn.close()
    return (f"🐞 Issue #{cur.lastrowid} filed for '{tool_name}'. "
            f"Open issues now: {n}. Ask \"suggest repairs\" anytime.")


@function_tool()
async def resolve_tool_issue(issue_id: int) -> str:
    """Mark an issue as resolved after fixing it."""
    conn = _db()
    cur = conn.execute("UPDATE tool_issues SET status='resolved' WHERE id=?", (int(issue_id),))
    conn.commit(); ok = cur.rowcount; conn.close()
    return f"✅ Issue #{issue_id} marked resolved." if ok else f"❌ No issue #{issue_id}."


@function_tool()
async def suggest_repairs(issue_id: int = 0) -> str:
    """Generate a concrete REPAIR PLAN for a reported issue (or the newest open
    one), wired into Zenith's self-editing workflow: inspect -> patch -> restart.

    Args:
        issue_id: Specific issue id; 0 = newest open issue
    """
    conn = _db()
    if int(issue_id) > 0:
        row = conn.execute("SELECT * FROM tool_issues WHERE id=?", (int(issue_id),)).fetchone()
        if row and row["status"] == "resolved":
            conn.close()
            return f"✅ Issue #{issue_id} [{row['tool_name']}] is already resolved. Nothing to repair."
    else:
        row = conn.execute(
            "SELECT * FROM tool_issues WHERE status='open' ORDER BY id DESC LIMIT 1").fetchone()

    # Also surface any statically-broken modules — those trump everything
    ok, problems = _static_scan()
    conn.close()

    plans = []
    if problems:
        for fname, err in problems[:3]:
            path = f"Tools/{fname}"
            plans.append(
                f"🔴 BROKEN MODULE {path}\n"
                f"   Error: {err}\n"
                f"   Plan:\n"
                f"   1. read_source_file(\"{path}\") to inspect\n"
                f"   2. modify_source_file(\"{path}\", \"fix syntax error: {err[:80]}\")\n"
                f"   3. Restart Zenith, then run tool_health_dashboard to confirm 🟢"
            )

    if row:
        target = _find_file_for_tool(row["tool_name"])
        loc = target or "Tools/ (couldn't auto-locate — search by function name)"
        desc = (row["description"] or "")[:200]
        err_hint = ""
        dl = desc.lower()
        if "timeout" in dl or "timed out" in dl:
            err_hint = ("Likely cause: blocking call inside async tool. Wrap slow ops in "
                        "await asyncio.to_thread(...) or add timeouts.")
        elif "not found" in dl or "no module" in dl:
            err_hint = "Likely cause: import error or missing dependency — check requirements.txt."
        elif "permission" in dl or "denied" in dl:
            err_hint = "Likely cause: needs admin rights / file locked by another process."
        elif "ocr" in dl or "tesseract" in dl:
            err_hint = "Likely cause: Tesseract binary missing or window not visible on screen."
        plans.append(
            f"🛠️ REPAIR PLAN for issue #{row['id']} [{row['tool_name']}]\n"
            f"   Reported: {desc}\n"
            f"   Target file: {loc}\n"
            f"{err_hint + chr(10) if err_hint else ''}"
            f"   Steps (use my self-edit powers):\n"
            f"   1. read_source_file(\"{loc}\") — inspect the implementation\n"
            f"   2. modify_source_file(\"{loc}\", \"<describe the fix from the report above>\")\n"
            f"   3. I'll tell you honestly what changed; restart Zenith to load it\n"
            f"   4. Test the tool, then resolve_tool_issue({row['id']})"
        )

    if not plans:
        return "✅ Nothing to repair — no broken modules and no open issues."
    return "\n\n────────────\n".join(plans)
