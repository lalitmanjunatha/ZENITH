"""Zenith File Radar — surfaces long-untouched files and proposes archiving.

F25: scans chosen roots (default Downloads/Desktop/Documents), ranks files by
age × size (real 'cold storage' candidates), proposes moving them into
~/ZenithArchive/<year>/ — with the same safety model as File Janitor:
propose → explicit confirm → MOVE (never delete), journaled for undo.
"""

import json
import logging
import os
import shutil
import time
from datetime import datetime
from pathlib import Path

from livekit.agents import function_tool

logger = logging.getLogger(__name__)

ARCHIVE_ROOT = Path.home() / "ZenithArchive"
_SCAN_CAP = 600
_pending = {}


def _iter_candidates(min_days: int, min_mb: float, folder: str = ""):
    if folder and os.path.isdir(folder):
        roots = [Path(folder)]
    else:
        home = Path.home()
        roots = [home / "Downloads", home / "Desktop", home / "Documents"]
    now = time.time()
    count = 0
    for base in roots:
        if not base.exists():
            continue
        for root, dirs, files in os.walk(base):
            dirs[:] = [d for d in dirs if not d.startswith((".", "_", "zenith"))]
            for f in files:
                p = Path(root) / f
                try:
                    st = p.stat()
                except OSError:
                    continue
                age_days = (now - st.st_mtime) / 86400
                size_mb = st.st_size / (1024 * 1024)
                if age_days >= min_days and size_mb >= min_mb:
                    yield {
                        "path": str(p),
                        "name": f,
                        "age_days": int(age_days),
                        "size_mb": round(size_mb, 2),
                        "score": round(age_days * max(size_mb, 0.1)),
                    }
                count += 1
                if count >= _SCAN_CAP:
                    return


@function_tool()
async def scan_old_files(min_days: int = 180, min_size_mb: float = 10.0,
                         folder: str = "") -> str:
    """OLD FILE RADAR: find files untouched for months that still eat space.
    Proposes an archive move plan — nothing changes until you approve.

    Args:
        min_days: Untouched longer than this many days (default 180)
        min_size_mb: And larger than this many MB (default 10)
        folder: Optional specific folder to sweep instead of the defaults
    """
    try:
        cands = sorted(_iter_candidates(int(min_days), float(min_size_mb), folder),
                       key=lambda c: -c["score"])[:15]
        total_mb = sum(c["size_mb"] for c in cands)
        if not cands:
            return (f"📡 Radar sweep done — no files older than {min_days} days "
                    f"and larger than {min_size_mb} MB in Downloads/Desktop/Documents.")

        pid = f"radar_{int(time.time())}"
        _pending.clear()
        _pending.update({"id": pid, "files": [c["path"] for c in cands],
                         "ts": time.time()})

        out = (f"📡 OLD-FILE RADAR — top {len(cands)} cold candidates "
               f"(~{total_mb:.0f} MB reclaimable)\n════════════════════\n")
        for i, c in enumerate(cands, 1):
            out += (f"{i}. {Path(c['path']).name[:45]}\n"
                    f"     {c['size_mb']} MB · untouched {c['age_days']} days · "
                    f"{Path(c['path']).parent.name}/\n")
        out += ("\n➡ Say \"archive old files\" to move ALL of these into "
                "~/ZenithArchive (recoverable, never deleted).")
        return out
    except Exception as e:
        return f"❌ Radar failed: {e}"


@function_tool()
async def archive_old_files(confirm: bool = False) -> str:
    """Execute the radar's proposed archive move. Files are MOVED into
    ~/ZenithArchive/<year>/ preserving structure — recoverable forever.

    Args:
        confirm: MUST be True to actually move anything.
    """
    try:
        pend = _pending.get("files")
        if not pend:
            return "ℹ️ Run a radar scan first."
        if not confirm:
            return "⛔ Confirmation required before I touch any file."

        year = str(datetime.now().year)
        moved = skipped = 0
        manifest = []
        for src in pend:
            try:
                sp = Path(src)
                if not sp.exists():
                    skipped += 1; continue
                dest_dir = ARCHIVE_ROOT / year / (sp.drive.strip(":") or "C") / sp.parent.name
                dest_dir.mkdir(parents=True, exist_ok=True)
                dst = dest_dir / sp.name
                i = 1
                while dst.exists():
                    dst = dest_dir / f"{sp.stem}_{i}{sp.suffix}"
                    i += 1
                shutil.move(str(sp), str(dst))
                manifest.append({"from": src, "to": str(dst)})
                moved += 1
            except Exception as e:
                logger.debug(f"archive skip {src}: {e}")
                skipped += 1

        (ARCHIVE_ROOT / "_manifest.json").open("a", encoding="utf-8").write(
            json.dumps({"ts": datetime.now().isoformat(), "moved": manifest}, indent=2) + "\n")

        from Tools.autonomy import journal
        journal("cleanup", f"Archived {moved} old file(s) → {ARCHIVE_ROOT}")

        _pending.clear()
        return (f"📦 ARCHIVED {moved} file(s) → {ARCHIVE_ROOT}\\{year}\\"
                + (f"  (skipped {skipped})" if skipped else "")
                + "\n🗂️ Manifest appended. Nothing was ever deleted.")
    except Exception as e:
        return f"❌ Archive failed: {e}"
