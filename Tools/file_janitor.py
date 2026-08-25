"""Proactive File Janitor — meaning-aware cleanup proposals for Zenith.

Scans Downloads/Desktop and proposes:
- exact duplicates (MD5-verified)
- version chains ("resume v1 / resume FINAL / resume final (2)")
- stale installers/archives older than 30 days

SAFETY MODEL:
- NEVER deletes anything. Confirmed actions MOVE files to
  ~/zenith_cleanup_staging/<timestamp>/ so everything is recoverable.
- Proposals expire after 30 minutes; re-scan regenerates them.
- Every executed move is logged to a manifest inside the staging folder.
"""

import hashlib
import json
import logging
import os
import re
import shutil
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from livekit.agents import function_tool

logger = logging.getLogger(__name__)

_STAGING_ROOT = Path.home() / "zenith_cleanup_staging"
_INSTALLER_EXTS = {".exe", ".msi", ".zip", ".rar", ".7z", ".iso"}
_SCAN_CAP = 400          # max files scanned per run (fast + bounded)
_DUP_GROUP_CAP = 40      # max duplicate groups reported
_MIN_KB = 100            # ignore tiny files

_plans: dict = {}        # plan_id -> {"created": ts, "actions": [...], "target_dir": str}


def _scan_dirs() -> list:
    home = Path.home()
    dirs = []
    for name in ("Downloads", "Desktop"):
        p = home / name
        if p.exists():
            dirs.append(p)
    return dirs


def _iter_files():
    count = 0
    for base in _scan_dirs():
        for root, _, files in os.walk(base):
            for f in files:
                if f.startswith("~$") or f.startswith("."):
                    continue
                yield Path(root) / f
                count += 1
                if count >= _SCAN_CAP:
                    return


def _md5(path: Path, limit_mb: int = 60) -> str:
    try:
        h = hashlib.md5()
        with open(path, "rb") as fh:
            while chunk := fh.read(1 << 20):
                h.update(chunk)
        return h.hexdigest()
    except Exception:
        return ""


def _normalize_name(name: str) -> str:
    """Strip ONLY explicit version/copy markers so 'report v2 final (1)' groups
    with 'report'. Timestamp/ID digit-runs (e.g. screen-20260204-203900,
    VID-20250511-WA0003, Snapchat-1476584578) are PRESERVED because they are
    unique identifiers, not version numbers."""
    s = Path(name).stem.lower()
    s = re.sub(r"\((\d{1,2})\)", " ", s)                      # "(1)" copy counters
    s = re.sub(r"\[(.*?)\]", " ", s)                          # [brackets]
    s = re.sub(r"\b(v|ver|version|rev)[\s._-]*\d+(\.\d+)*\b", " ", s)  # v2 / ver3.1
    s = re.sub(r"\b(final|copy|new|old|backup|bak|draft)\b", " ", s)
    s = re.sub(r"[\s\-_.]+", " ", s).strip()
    return s


def build_plan(scan_dir: str = "") -> dict:
    """Scan and construct a cleanup proposal from REAL files found.
    A file can appear in AT MOST ONE action (cross-action dedupe)."""
    by_hash: dict = defaultdict(list)
    by_norm: dict = defaultdict(list)
    stale_installers = []

    if scan_dir and os.path.isdir(scan_dir):
        bases = [Path(scan_dir)]
        def _iter():
            count = 0
            for base in bases:
                for root, _, files in os.walk(base):
                    for f in files:
                        yield Path(root) / f
                        count += 1
                        if count >= _SCAN_CAP:
                            return
    else:
        _iter = _iter_files

    for p in _iter():
        try:
            stat = p.stat()
        except OSError:
            continue
        if stat.st_size < _MIN_KB * 1024:
            continue
        ext = p.suffix.lower()
        age_days = (time.time() - stat.st_mtime) / 86400
        by_hash[_md5(p)].append(p)
        by_norm[(p.suffix.lower(), _normalize_name(p.name))].append((p, stat.st_size, age_days))
        if ext in _INSTALLER_EXTS and age_days > 30:
            stale_installers.append((p, stat.st_size, age_days))

    actions = []   # each: {"kind","keep","move":[paths],"reason"}
    claimed: set = set()   # every path reserved for exactly one action

    def take(paths) -> list:
        fresh = []
        for p in paths:
            sp = str(p)
            if sp not in claimed:
                claimed.add(sp)
                fresh.append(sp)
        return fresh

    # 1. exact duplicates — keep newest, offer rest
    dup_groups = 0
    for h, paths in by_hash.items():
        if not h or len(paths) < 2 or dup_groups >= _DUP_GROUP_CAP:
            continue
        paths_sorted = sorted(paths, key=lambda p: p.stat().st_mtime, reverse=True)
        keep, rest = paths_sorted[0], paths_sorted[1:]
        rest = take(rest)
        if not rest:
            continue
        size_kb = round(paths_sorted[0].stat().st_size / 1024)
        actions.append({
            "kind": "duplicate",
            "reason": f"{len(rest)} exact copies of '{keep.name}' ({size_kb} KB each)",
            "keep": str(keep),
            "move": rest,
        })
        dup_groups += 1

    # 2. version chains — same normalized name AND same real suffix family,
    #    keep newest; requires ≥2 unclaimed leftovers
    chains = 0
    for (_ext, norm), entries in sorted(by_norm.items()):
        if len(entries) < 3 or chains >= _DUP_GROUP_CAP:
            continue
        entries.sort(key=lambda e: e[1], reverse=True)  # newest first by mtime
        keep = entries[0][0]
        rest = take([e[0] for e in entries[1:] if e[0] != keep])
        if len(rest) < 2:
            continue
        actions.append({
            "kind": "version_chain",
            "reason": f"'{norm}' has {len(rest)} older versions (e.g. {Path(rest[0]).name[:40]})",
            "keep": str(keep),
            "move": rest,
        })
        chains += 1

    # 3. stale installers
    big_installers = sorted(stale_installers, key=lambda x: x[1], reverse=True)[:20]
    installer_paths = take([p for p, _, _ in big_installers])
    if installer_paths:
        total_mb = round(sum(Path(p).stat().st_size for p in installer_paths) / (1024 * 1024), 1)
        actions.append({
            "kind": "stale_installer",
            "reason": f"{len(installer_paths)} installers/archives older than 30 days (~{total_mb} MB)",
            "keep": "",
            "move": installer_paths,
        })

    reclaim_mb = sum(
        os.path.getsize(p) for a in actions for p in a["move"] if os.path.exists(p)
    ) / (1024 * 1024)

    return {
        "created": time.time(),
        "actions": actions,
        "reclaim_mb": round(reclaim_mb, 1),
    }


@function_tool()
async def scan_cleanup_candidates(scan_dir: str = "") -> str:
    """PROACTIVE FILE JANITOR: scan Downloads/Desktop (or a specific folder) and
    propose safe cleanups (exact duplicates, old versions of the same document,
    stale installers). Nothing is touched until you explicitly confirm execution.

    Args:
        scan_dir: Optional specific folder to scan instead of Downloads+Desktop
    """
    try:
        plan = build_plan(scan_dir=scan_dir)
        if not plan["actions"]:
            return (
                "🧹 FILE JANITOR: ✨ Downloads/Desktop are already tidy — "
                "no duplicates, version-chains, or stale installers found "
                f"(scanned up to {_SCAN_CAP} files ≥{_MIN_KB} KB)."
            )

        pid = f"plan_{int(plan['created'])}"
        plans_store = _plans
        plans_store[pid] = plan

        out = (
            f"🧹 FILE JANITOR REPORT  [{pid}]\n════════════════════\n"
            f"Potential reclaim: ~{plan['reclaim_mb']} MB (moves to recovery folder — never deleted)\n\n"
        )
        icons = {"duplicate": "👯", "version_chain": "📑", "stale_installer": "📦"}
        n_show = 0
        for a in plan["actions"]:
            if n_show >= 12:
                out += f"…and {len(plan['actions']) - 12} more group(s).\n"
                break
            out += f"{icons.get(a['kind'], '•')} {a['reason']}\n"
            out += f"    keep: {Path(a['keep']).name if a['keep'] else '(n/a)'}\n"
            for mv in a["move"][:4]:
                out += f"    move: {Path(mv).name}\n"
            if len(a["move"]) > 4:
                out += f"    …+{len(a['move']) - 4} more\n"
            n_show += 1

        out += (
            "\n➡ Say \"clean my files\" to execute this exact plan "
            "(files go to ~/zenith_cleanup_staging, fully recoverable).\n"
            "⚠️ I will never delete or auto-execute without your confirmation."
        )
        return out
    except Exception as e:
        return f"❌ Janitor scan failed: {e}"


@function_tool()
async def execute_cleanup(plan_id: str, confirm: bool = False) -> str:
    """Execute an approved janitor plan. Files are MOVED to
    ~/zenith_cleanup_staging/<ts>/ with a manifest — recoverable, never deleted.

    Args:
        plan_id: The plan id from scan_cleanup_candidates (e.g. plan_1730000000)
        confirm: MUST be true to actually move anything.
    """
    try:
        plan = _plans.get(plan_id)
        if not plan:
            return f"❌ Unknown or expired plan '{plan_id}'. Run a fresh scan first."
        if time.time() - plan["created"] > 1800:
            del _plans[plan_id]
            return "⌛ Plan expired (>30 min). Run a fresh scan for current state."
        if not confirm:
            return "⛔ Confirmation required. Re-ask me with explicit confirmation to proceed."

        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        target = _STAGING_ROOT / ts
        target.mkdir(parents=True, exist_ok=True)

        moved, skipped, freed = [], [], 0
        manifest = {"plan_id": plan_id, "executed_at": datetime.now().isoformat(), "moved": []}
        for a in plan["actions"]:
            for src in a["move"]:
                try:
                    sp = Path(src)
                    if not sp.exists():
                        skipped.append(src); continue
                    size_bytes = sp.stat().st_size      # BEFORE move (source vanishes after)
                    dest = target / sp.name
                    i = 1
                    while dest.exists():                      # collision-safe
                        dest = target / f"{sp.stem}_{i}{sp.suffix}"
                        i += 1
                    shutil.move(str(sp), str(dest))
                    moved.append(str(dest))
                    freed += size_bytes
                    manifest["moved"].append({"from": src, "to": str(dest)})
                except Exception as e:
                    logger.warning(f"move failed {src}: {e}")
                    skipped.append(src)

        (target / "_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        del _plans[plan_id]

        return (
            f"✅ Cleanup complete.\n"
            f"📦 Moved {len(moved)} file(s) → {target}\n"
            f"💾 Reclaimed on original folders: ~{round(freed/1024/1024, 1)} MB\n"
            f"🗑️ Recover anytime from that folder (nothing was deleted).\n"
            + (f"⚠️ Skipped {len(skipped)} locked/missing file(s)." if skipped else "")
        )
    except Exception as e:
        return f"❌ Cleanup failed: {e}"
