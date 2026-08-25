"""Whole-laptop indexing for Zenith.

Scans every local fixed drive (pruning system/special folders) and feeds
text content into the RAG knowledge base. Two phases:

  Phase 1 (metadata): build/update the file list across all drives.
  Phase 2 (content):   extract + chunk + embed file contents into the
                       FAISS knowledge index, skipping already-hashed
                       files so it resumes across restarts.

Designed to run from a background thread so the voice agent stays
responsive (commands + conversation) while indexing proceeds.
"""

import json
import logging
import os
import string
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)

# System / special directories never scanned.
DEFAULT_SKIP_DIRS = {
    "Windows", "Program Files", "Program Files (x86)", "ProgramData",
    "AppData", "$Recycle.Bin", "System Volume Information", "$RECYCLE.BIN",
    "Recovery", "Config.Msi", "PerfLogs",
    "node_modules", "venv", ".venv", ".git", "__pycache__",
    ".cache", ".pytest_cache", ".mypy_cache", ".idea", ".vscode",
    "livekit", "livekit-1.0.20.dist-info",
    "livekit_agents-1.3.6.dist-info", "livekit_api-1.0.7.dist-info",
    "livekit_blingfire-1.0.0.dist-info",
    "livekit_plugins_google-1.2.14.dist-info",
    "livekit_plugins_groq-1.3.6.dist-info",
    "livekit_plugins_mistralai-1.3.6.dist-info",
    "livekit_plugins_noise_cancellation-0.2.5.dist-info",
    "livekit_plugins_nvidia-1.3.6.dist-info",
    "livekit_plugins_openai-1.3.6.dist-info",
    "livekit_plugins_sarvam-1.3.6.dist-info",
    "livekit_plugins_silero-1.3.6.dist-info",
    "livekit_plugins_turn_detector-1.3.6.dist-info",
    "livekit_plugins_ultravox-1.3.6.dist-info",
    "livekit_protocol-1.1.1.dist-info",
    "data",
}

DEFAULT_SKIP_EXTENSIONS = {
    ".pyc", ".pyo", ".pyd", ".so", ".dll", ".exe", ".bin", ".dat",
    ".db", ".sqlite", ".sqlite3", ".db3", ".lock", ".tmp", ".swp",
    ".swo", ".DS_Store", ".ico", ".cur", ".ani", ".ini",
}

# Maximum file size we read + embed.
DEFAULT_MAX_FILE_BYTES = 50 * 1024 * 1024

STATE_FILE = Path("data") / "disk_index_state.json"


def _now() -> str:
    return datetime.now().isoformat()


def enumerate_fixed_drives() -> List[str]:
    if os.name != "nt":
        return ["/"]
    drives = []
    for letter in string.ascii_uppercase:
        root = f"{letter}:\\"
        if not os.path.exists(root):
            continue
        try:
            import ctypes

            if ctypes.windll.kernel32.GetDriveTypeW(root) == 3:  # DRIVE_FIXED
                drives.append(root)
        except Exception:
            if os.path.exists(root):
                drives.append(root)
    return drives


class WholeDiskIndexer:
    def __init__(
        self,
        vector_store=None,
        embedder=None,
        content_extractor=None,
        chunker=None,
        skip_dirs: Optional[Set[str]] = None,
        skip_extensions: Optional[Set[str]] = None,
        max_file_bytes: int = DEFAULT_MAX_FILE_BYTES,
    ):
        self.vector_store = vector_store
        self.embedder = embedder
        self.content_extractor = content_extractor
        self.chunker = chunker
        self.skip_dirs = skip_dirs or DEFAULT_SKIP_DIRS
        self.skip_extensions = skip_extensions or DEFAULT_SKIP_EXTENSIONS
        self.max_file_bytes = max_file_bytes
        self.processed: Set[str] = set()
        self.failed: Set[str] = set()
        self.current_stats: Dict[str, Any] = {
            "phase": "idle",
            "drives": 0,
            "candidates": 0,
            "indexed": 0,
            "failed": 0,
            "skipped": 0,
            "last_updated": _now(),
        }
        self._load_state()

    # ------------------------------------------------------------------
    # State (resume support)
    # ------------------------------------------------------------------
    def _load_state(self) -> None:
        try:
            if STATE_FILE.exists():
                data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
                self.processed = set(data.get("processed", []))
                self.failed = set(data.get("failed", []))
        except Exception:
            self.processed, self.failed = set(), set()

    def _mark(self, path: str, status: str) -> None:
        try:
            data = self._read_state()
        except Exception:
            data = {"processed": [], "failed": []}
        bucket = data.get("processed", []) if status == "done" else data.get("failed", [])
        if path not in bucket:
            bucket.append(path)
        key = "processed" if status == "done" else "failed"
        data[key] = bucket
        try:
            STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
            STATE_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
        except Exception:
            pass

    def _read_state(self) -> dict:
        try:
            if STATE_FILE.exists():
                return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
        return {"processed": [], "failed": []}

    def save_state(self) -> None:
        try:
            STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
            STATE_FILE.write_text(
                json.dumps(
                    {
                        "processed": list(self.processed),
                        "failed": list(self.failed),
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )
        except Exception as e:
            logger.warning(f"save state failed: {e}")

    # ------------------------------------------------------------------
    # Phase 1: metadata scan
    # ------------------------------------------------------------------
    def scan_metadata(self, directory: Optional[str] = None) -> Dict[str, Any]:
        roots = [directory] if directory else enumerate_fixed_drives()
        roots = [r for r in roots if os.path.exists(r)]
        all_files: List[Dict[str, Any]] = []
        candidates = 0
        for root in roots:
            candidates += self._walk_metadata(root, all_files)
            logger.info(f"Metadata scan {root}: {candidates} candidates so far")
        self.current_stats.update(
            phase="metadata",
            drives=len(roots),
            candidates=candidates,
            last_updated=_now(),
        )
        return {"files_count": len(all_files), "drives": roots, "files": all_files}

    def _walk_metadata(self, root: str, out: List[Dict[str, Any]]) -> int:
        count = 0
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [
                d for d in dirnames
                if d not in self.skip_dirs and not d.startswith(".")
            ]
            try:
                for name in filenames:
                    path = os.path.join(dirpath, name)
                    ext = os.path.splitext(name)[1].lower()
                    if ext in self.skip_extensions:
                        continue
                    try:
                        stat = os.stat(path)
                    except OSError:
                        continue
                    if stat.st_size > self.max_file_bytes:
                        continue
                    out.append(
                        {
                            "path": path,
                            "name": name,
                            "extension": ext,
                            "size_bytes": stat.st_size,
                            "modified_time": stat.st_mtime,
                            "directory": dirpath,
                        }
                    )
                    count += 1
            except OSError:
                pass
        return count

    # ------------------------------------------------------------------
    # Phase 2 — content embedding
    # ------------------------------------------------------------------
    def index_content(self, directory: Optional[str] = None, limit: int = 0) -> Dict[str, Any]:
        if not (self.content_extractor and self.embedder and self.vector_store and self.chunker):
            return {"error": "RAG components not initialized", "indexed": 0}

        self.current_stats["phase"] = "content"
        meta = self.scan_metadata(directory)
        files = meta.get("files", [])
        results = {"indexed": 0, "failed": 0, "skipped": 0}

        for info in files:
            path = info["path"]
            if path in self.processed:
                results["skipped"] += 1
                self.current_stats["skipped"] = results["skipped"]
                continue
            try:
                extraction = self.content_extractor.extract(path)
                if not extraction["metadata"].get("extraction_success"):
                    raise ValueError("extraction failed")
                content = extraction["content"]
                if not content or not content.strip():
                    raise ValueError("no content")
                chunks = self.chunker.chunk(
                    content,
                    metadata={
                        "source_file": path,
                        "file_name": info["name"],
                        "extension": info["extension"],
                        "file_size": info["size_bytes"],
                    },
                )
                texts = [c["text"] for c in chunks]
                embeddings = self.embedder.embed(texts)
                if embeddings is None:
                    raise ValueError("embedding failed")
                self.vector_store.add(embeddings, chunks)
                self.processed.add(path)
                self._mark(path, "done")
                results["indexed"] += 1
            except Exception as e:
                logger.warning(f"Index failed for {path}: {e}")
                self.failed.add(path)
                self._mark(path, "failed")
                results["failed"] += 1

            self.current_stats.update(
                indexed=results["indexed"],
                failed=results["failed"],
                skipped=results["skipped"],
                last_updated=_now(),
            )

            if limit and results["indexed"] >= limit:
                break

        try:
            self.vector_store.save()
        except Exception as e:
            logger.warning(f"save index failed: {e}")
        self.current_stats["phase"] = "done"
        return results

    def stats(self) -> Dict[str, Any]:
        state = self._read_state()
        return {
            "processed": len(state.get("processed", [])),
            "failed": len(state.get("failed", [])),
            "progress": dict(self.current_stats),
            "last_updated": _now(),
        }

    def reset_progress(self) -> None:
        try:
            if STATE_FILE.exists():
                STATE_FILE.unlink()
        except Exception:
            pass
        self.processed.clear()
        self.failed.clear()