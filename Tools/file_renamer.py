"""Content-Aware File Renamer — gives files names that match what's INSIDE them.

Finds badly-named files (download junk like "document(3).pdf", "Untitled 1.docx")
and proposes meaningful names derived from actual content (title lines, first
paragraph, document metadata). NEVER renames without explicit confirmation.
"""

import logging
import os
import re
import time
from pathlib import Path

from livekit.agents import function_tool

logger = logging.getLogger(__name__)

BAD_NAME_PATTERNS = [
    r"^document\d*[\s(]", r"^untitled", r"^new\s?doc", r"^download",
    r"^\(?\d+\)?\s*\.", r"^file\d*", r"^[a-z]{6,12}\d{2,}$",   # random strings
]
READABLE_EXTS = {".txt", ".md", ".pdf", ".docx", ".csv", ".json", ".html", ".py", ".js"}
MAX_BYTES = 8 * 1024 * 1024


def _is_bad_name(stem: str) -> bool:
    s = stem.strip().lower()
    return any(re.match(p, s) for p in BAD_NAME_PATTERNS)


def _extract_text(path: Path) -> str:
    """Reuse the project's ContentExtractor (PDF/DOCX/HTML/txt all supported)."""
    try:
        from content_extractor import ContentExtractor
        res = ContentExtractor().extract(str(path))
        if res.get("metadata", {}).get("extraction_success"):
            return res.get("content", "")
    except Exception as e:
        logger.debug(f"extractor failed for {path}: {e}")
    return ""


def _slugify(text: str, max_words: int = 7) -> str:
    text = re.sub(r"[^\w\s-]", " ", text).strip().lower()
    words = [w for w in text.split() if len(w) > 2][:max_words]
    slug = "_".join(words)
    slug = re.sub(r"_+", "_", slug)[:60].strip("_")
    return slug or "renamed_file"


def propose_name(path: Path) -> str:
    """Derive a human-sensible filename from real file content."""
    ext = path.suffix.lower()
    text = _extract_text(path) if ext in READABLE_EXTS else ""
    candidate = ""
    if text:
        # Prefer markdown/expl title markers, then first meaty line
        for line in text.splitlines()[:40]:
            l = line.strip()
            if not l:
                continue
            if l.startswith("#"):
                candidate = l.lstrip("#").strip(); break
        if not candidate:
            for para in " ".join(text.split()) .split(". "):
                p = para.strip()
                if 25 <= len(p) <= 120 and not p.lower().startswith(("http", "www")):
                    candidate = p; break
    # Office metadata fallback
    if not candidate and ext == ".docx":
        try:
            from docx import Document
            core = Document(str(path)).core_properties
            candidate = core.title or core.subject or ""
        except Exception:
            pass
    if not candidate and ext == ".pdf":
        try:
            from PyPDF2 import PdfReader
            meta = PdfReader(str(path)).metadata or {}
            candidate = str(meta.get("/Title") or "").strip()
        except Exception:
            pass
    name = _slugify(candidate) if candidate else ""
    return f"{name}{ext}" if name else ""


@function_tool()
async def suggest_rename(file_path: str) -> str:
    """Suggest a better filename based on the file's ACTUAL content.

    Args:
        file_path: Full path to the file
    """
    try:
        p = Path(os.path.expanduser(file_path))
        if not p.exists():
            return f"❌ File not found: {p}"
        new_name = propose_name(p)
        if not new_name:
            return (f"🤔 Couldn't derive a meaningful name from '{p.name}' "
                    "(unsupported type or no readable content). Current name stays.")
        if new_name == p.name:
            return f"✨ '{p.name}' already has a good name."
        return (
            f"📝 RENAME SUGGESTION\n"
            f"   Now:  {p.name}\n"
            f"   New:  {new_name}\n"
            f'Confirm with: apply_rename("{p}", "{new_name}")'
        )
    except Exception as e:
        return f"❌ Suggestion failed: {e}"


@function_tool()
async def apply_rename(file_path: str, new_name: str, confirm: bool = False) -> str:
    """Apply a rename after confirmation. Collision-safe (never overwrites).

    Args:
        file_path: Full current path
        new_name: Proposed new filename (with extension)
        confirm: MUST be True to actually rename
    """
    try:
        if not confirm:
            return "⛔ Confirmation required — I never rename without your explicit yes."
        p = Path(os.path.expanduser(file_path))
        if not p.exists():
            return f"❌ File not found: {p}"
        safe = Path(new_name).name                      # strip any path parts
        if not safe or safe == p.name:
            return "⚠️ Nothing to change."
        dest = p.with_name(safe)
        i = 1
        while dest.exists():                            # collision-safe
            dest = p.with_name(f"{Path(safe).stem}_{i}{p.suffix}")
            i += 1
        p.rename(dest)
        return f"✅ Renamed:\n   {p.name} → {dest.name}"
    except Exception as e:
        return f"❌ Rename failed: {e}"


@function_tool()
async def scan_rename_candidates(folder: str = "") -> str:
    """Scan Downloads/Desktop (or a folder) for badly-named files whose CONTENT
    suggests a better name. Proposes up to 10; nothing changes until you approve.

    Args:
        folder: Optional folder to scan instead of the defaults
    """
    try:
        home = Path.home()
        bases = [Path(folder)] if folder else [home / "Downloads", home / "Desktop"]
        candidates = []
        cap_files, scanned = 250, 0
        for base in bases:
            if not base.exists():
                continue
            for root, _, files in os.walk(base):
                for f in files:
                    fp = Path(root) / f
                    scanned += 1
                    if scanned > cap_files or len(candidates) >= 10:
                        break
                    if fp.suffix.lower() not in READABLE_EXTS:
                        continue
                    try:
                        if fp.stat().st_size > MAX_BYTES:
                            continue
                    except OSError:
                        continue
                    if _is_bad_name(fp.stem):
                        better = propose_name(fp)
                        if better and better != fp.name:
                            candidates.append((str(fp), better))
                if scanned > cap_files or len(candidates) >= 10:
                    break
        if not candidates:
            return (f"✨ Scanned {scanned} files — no badly-named readable files found. "
                    "Names look fine!")
        out = f"📝 RENAME CANDIDATES ({len(candidates)} of {scanned} scanned):\n\n"
        for i, (fp, better) in enumerate(candidates, 1):
            out += f"{i}. {Path(fp).name}  →  {better}\n"
        out += ('\nApprove one-by-one with apply_rename("<path>", "<new>", confirm=True), '
                'or say "rename candidate 3" style commands.')
        return out
    except Exception as e:
        return f"❌ Scan failed: {e}"
