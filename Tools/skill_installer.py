"""Zenith Skill Installer — adopt new .py tool files safely.

Drop any Zenith-style tool file (with @function_tool functions) and this
installs it: syntax-compile check, dangerous-import audit, copy into Tools/,
then a restart loads it automatically. Nothing executes during install.
"""

import ast
import logging
import re
import shutil
from datetime import datetime
from pathlib import Path

from livekit.agents import function_tool

logger = logging.getLogger(__name__)

TOOLS_DIR = Path("Tools")

BLOCKED_PATTERNS = [
    (r"\bos\.system\s*\(", "os.system shell call"),
    (r"\bsubprocess\b", "subprocess use"),
    (r"\beval\s*\(", "eval()"),
    (r"\bexec\s*\(", "exec()"),
    (r"shutil\.rmtree", "recursive delete"),
    (r"os\.remove|os\.unlink", "file delete"),
    (r"\bsocket\.socket", "raw socket"),
    (r"requests\.(post|put|delete)", "state-changing web calls"),
]


def _audit(source: str) -> tuple[list, list]:
    """Returns (errors, warnings)."""
    errors, warns = [], []
    try:
        tree = ast.parse(source)
    except SyntaxError as e:
        return [f"syntax error line {e.lineno}: {e.msg}"], warns

    has_tool = "@function_tool" in source or "function_tool(" in source
    if not has_tool:
        warns.append("no @function_tool found — file will load but expose no voice tools")

    for pat, label in BLOCKED_PATTERNS:
        if re.search(pat, source):
            warns.append(f"contains {label} — allowed, but flagged for your awareness")
    # crude secret scan
    if re.search(r"(api[_-]?key|secret|password)\s*=\s*['\"][^'\"]{8,}", source, re.I):
        warns.append("possible hardcoded secret detected — move it to .env!")
    return errors, warns


@function_tool()
async def install_skill(py_file_path: str, force: bool = False) -> str:
    """SKILL INSTALLER: safely adopt a .py tool file. Checks syntax + audits
    risky patterns, then copies into Tools/ so the next restart activates it.
    Nothing is executed during install.

    Args:
        py_file_path: Path to the .py skill file
        force: Install even when audit raises warnings
    """
    try:
        src = Path(py_file_path)
        if not src.exists():
            return f"❌ File not found: {src}"
        if src.suffix != ".py":
            return "❌ Only .py files can be installed as skills."
        code = src.read_text(encoding="utf-8", errors="replace")
        if len(code) > 400_000:
            return "❌ File too large to be a sane skill (>400KB)."

        errors, warns = _audit(code)
        if errors:
            return ("❌ INSTALL REFUSED — broken code:\n   " + "\n   ".join(errors)
                    + "\nFix these first; I never install syntactically broken tools.")

        if warns and not force:
            return ("⚠️ Audit flags:\n   • " + "\n   • ".join(warns[:6])
                    + "\n\nIf you accept these, say: install_skill(path, force=True)")

        dest = TOOLS_DIR / src.name
        if dest.exists() and not force:
            return (f"⚠️ Tools/{src.name} already exists. Re-run with force=True "
                    "to overwrite.")
        shutil.copy2(src, dest)

        from Tools.autonomy import journal
        journal("cleanup", f"Installed skill '{src.name}' ({len(warns)} warning(s))",
                target=str(dest))
        return (f"🧩 SKILL INSTALLED → Tools/{src.name}"
                + (f"\n⚠️ Notes:\n   • " + "\n   • ".join(warns[:5]) if warns else "")
                + "\n🔁 Restart Zenith and its tools go live automatically."
                + '\nTest after restart: just ask for what the tool does.')
    except Exception as e:
        return f"❌ Install failed: {e}"


@function_tool()
async def list_installed_skills() -> str:
    """List non-core custom skills in Tools/ (files added via installer naming)."""
    rows = []
    if TOOLS_DIR.exists():
        for f in sorted(TOOLS_DIR.glob("*.py")):
            try:
                mtime = datetime.fromtimestamp(f.stat().st_mtime)
                rows.append((f.name, mtime))
            except Exception:
                continue
    core = {"__init__.py", "_llm_client.py"}
    customs = [(n, t) for n, t in rows if n not in core]
    out = f"🧩 TOOL MODULES ({len(customs)}):\n"
    for n, t in sorted(customs, key=lambda x: -x[1].timestamp())[:20]:
        out += f"   • {n}  (modified {t:%d %b %H:%M})\n"
    return out