"""Self-editing capability: Zenith can read and modify its own source code.

Flow for "fix this tool in your code":
  1. Read the target file.
  2. Ask Groq (code model) to produce corrected content given the request.
  3. Validate the result with ast.parse BEFORE writing.
  4. Back up the original to data/code_backups/.
  5. Write the new content atomically.
  6. Re-import / smoke-test the module; auto-rollback on failure.
  7. Log the edit into permanent memory.

Guardrails:
  - Only *.py files under the workspace are editable.
  - Never .env, data/, livekit/, or non-python files.
  - No arbitrary shell execution; only fixed validation commands.
  - Changes apply on next launch (we do NOT hot-reload the running worker).
"""

import ast
import asyncio
import json
import logging
import shutil
import traceback
from datetime import datetime
from pathlib import Path

from livekit.agents import function_tool

from ._llm_client import chat_complete

logger = logging.getLogger(__name__)

# Workspace root = F:\\Nova 5.0 (parent of the Tools dir).
WORKSPACE = Path(__file__).resolve().parent.parent

# Sub-paths that must never be edited even though they sit inside the workspace.
BLOCKED = {"livekit", "data", "zenith_remote", "zenith_knowledge"}

BACKUP_DIR = Path("data") / "code_backups"


def _resolve(path: str) -> Path:
    """Resolve a path and ensure it is an editable .py within the workspace."""
    p = Path(path).resolve()
    if WORKSPACE not in p.parents:
        raise PermissionError(f"Outside workspace: {path}")
    for block in BLOCKED:
        if p.is_relative_to(WORKSPACE / block):
            raise PermissionError(f"Blocked path: {path}")
    if p.suffix.lower() != ".py":
        raise PermissionError(f"Only .py files are editable (got {p.name})")
    return p


def _validate_syntax(code: str) -> str:
    """Return '' if valid, else a human-readable syntax error message."""
    try:
        ast.parse(code)
        return ""
    except SyntaxError as e:
        return f"line {e.lineno}: {e.msg}"


def _read_current(p: Path) -> str:
    return p.read_text(encoding="utf-8", errors="replace")


def _backup(p: Path) -> Path:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dest = BACKUP_DIR / f"{p.stem}_{stamp}.bak"
    shutil.copy2(p, dest)
    return dest


def _write_atomic(p: Path, content: str) -> None:
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(content, encoding="utf-8")
    tmp.replace(p)


def _log_edit(p: Path, description: str, ok: bool, detail: str) -> None:
    try:
        from memory_manager import MemoryManager

        mem = MemoryManager()
        mem.record_fact(
            f"Self-edit {'SUCCESS' if ok else 'FAILED'} on {p.name}: {description}",
            category="self_edit",
            source="self_edit",
        )
        mem.flush_vectors()
    except Exception as e:
        logger.warning(f"log edit failed: {e}")


def _extract_python(reply: str) -> str:
    """Strip code fences from a Groq reply if present."""
    reply = reply.strip()
    if reply.startswith("```"):
        lines = reply.split("\n")
        reply = "\n".join(lines[1:-1])
        if reply.endswith("```"):
            reply = reply[:-3]
    return reply.strip() + "\n"


@function_tool()
async def read_source_file(file_path: str) -> str:
    """Read the source of a workspace .py file so you can inspect it.

    Args:
        file_path: Absolute path to a .py file inside the workspace.
    """
    try:
        p = _resolve(file_path)
        content = _read_current(p)
        return f"--- {p.name} ({len(content.splitlines())} lines) ---\n{content[:16000]}"
    except Exception as e:
        return f"Error reading file: {e}"


@function_tool()
async def modify_source_file(file_path: str, description: str) -> str:
    """Fix/change one of Zenith's own source files based on a description.

    Args:
        file_path: Absolute path of the workspace .py file to modify.
        description: What should change / what bug to fix, in the user's words.
    """
    try:
        p = _resolve(file_path)
    except Exception as e:
        return f"❌ {e}"

    current = _read_current(p)
    system = (
        "You are a meticulous Python engineer. You will be given a file and a "
        "requested change. Return the COMPLETE updated file content as plain "
        "Python — no markdown fences, no explanations, no `text` — preserving "
        "working behavior while implementing the requested fix. Keep imports, "
        "class names, and function signatures stable unless the request says "
        "otherwise."
    )
    prompt = (
        f"FILE: {p.name}\n\n"
        f"REQUEST: {description}\n\n"
        f"CURRENT CONTENT:\n```python\n{current[-48000:]}\n```\n\n"
        "Return ONLY the complete new file content."
    )

    reply = await chat_complete(prompt, system=system, max_tokens=6000)
    if reply.startswith("ERROR:"):
        return f"❌ Operating model call failed: {reply}"

    new_code = _extract_python(reply)
    if not new_code.strip():
        return "❌ The model returned an empty result."

    err = _validate_syntax(new_code)
    if err:
        return f"❌ Proposed change is invalid Python ({err}); nothing was written."

    backup = _backup(p)
    _write_atomic(p, new_code)

    # Verify it still imports (smoke test). Roll back on failure.
    try:
        module_name = p.stem
        # Remove loaded sys.modules copy so we re-verify from disk.
        import sys, importlib

        if module_name in sys.modules:
            del sys.modules[module_name]
        importlib.import_module(module_name)
        ok = True
        detail = f"Imported OK. Backup saved: {backup.name}"
        _log_edit(p, description, True, detail)
        return (
            f"✅ Changed {p.name} per your request.\n"
            f"   Syntax verified and module imported successfully.\n"
            f"   Backup: {backup}\n"
            f"   Note: restart Zenith to load the change."
        )
    except Exception as e:
        # Rollback
        shutil.copy2(backup, p)
        _log_edit(p, description, False, f"{e}")
        return (
            f"❌ Change broke the module ({e}). "
            f"Reverted to the backup automatically. Nothing was kept."
        )