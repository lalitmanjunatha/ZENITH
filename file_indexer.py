import os
import hashlib
import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional, Set
from datetime import datetime

logger = logging.getLogger(__name__)

DEFAULT_EXCLUDE_DIRS = {
    "__pycache__",
    ".git",
    ".venv",
    "venv",
    "node_modules",
    ".next",
    ".nuxt",
    "dist",
    "build",
    ".cache",
    ".pytest_cache",
    ".mypy_cache",
    ".idea",
    ".vscode",
    ".opencode",
    "livekit",
    "livekit-1.0.20.dist-info",
    "livekit_agents-1.3.6.dist-info",
    "livekit_api-1.0.7.dist-info",
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
    "__pycache__",
    ".git",
}

DEFAULT_EXCLUDE_EXTENSIONS = {
    ".pyc",
    ".pyo",
    ".pyd",
    ".so",
    ".dll",
    ".exe",
    ".bin",
    ".dat",
    ".db",
    ".sqlite",
    ".db3",
    ".lock",
    ".tmp",
    ".swp",
    ".swo",
    ".DS_Store",
    ".Thumbs.db",
    ".ico",
    ".cur",
    ".ani",
}

DEFAULT_INDEX_DIRS = [
    str(Path.home() / "Documents"),
    str(Path.home() / "Desktop"),
    str(Path.home() / "Downloads"),
    str(Path.home() / "Pictures"),
    str(Path.home() / "Videos"),
]


class FileIndexer:
    def __init__(
        self,
        index_dir: str = None,
        exclude_dirs: Set[str] = None,
        exclude_extensions: Set[str] = None,
        index_dirs: List[str] = None,
        db_path: str = "data/file_index.db",
    ):
        self.index_dir = index_dir or str(Path.home())
        self.exclude_dirs = exclude_dirs or DEFAULT_EXCLUDE_DIRS
        self.exclude_extensions = exclude_extensions or DEFAULT_EXCLUDE_EXTENSIONS
        self.index_dirs = index_dirs or DEFAULT_INDEX_DIRS
        self.db_path = db_path
        self.file_index = {}
        self.changes = {"added": [], "modified": [], "deleted": []}

        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

    def _file_hash(self, file_path: str) -> str:
        try:
            hasher = hashlib.md5()
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(8192), b""):
                    hasher.update(chunk)
            return hasher.hexdigest()
        except Exception:
            return ""

    def _should_index(self, path: Path) -> bool:
        if path.is_dir():
            return path.name not in self.exclude_dirs
        if path.suffix.lower() in self.exclude_extensions:
            return False
        if path.stat().st_size > 50 * 1024 * 1024:
            return False
        return True

    def scan_directory(self, directory: str = None) -> List[Dict[str, Any]]:
        directory = directory or self.index_dir
        indexed_files = []

        for root, dirs, files in os.walk(directory):
            dirs[:] = [d for d in dirs if d not in self.exclude_dirs]

            for filename in files:
                file_path = Path(root) / filename

                if not self._should_index(file_path):
                    continue

                try:
                    stat = file_path.stat()
                    file_hash = self._file_hash(str(file_path))

                    indexed_files.append(
                        {
                            "path": str(file_path),
                            "name": filename,
                            "extension": file_path.suffix.lower(),
                            "size_bytes": stat.st_size,
                            "modified_time": stat.st_mtime,
                            "hash": file_hash,
                            "directory": root,
                        }
                    )
                except Exception as e:
                    logger.warning(f"Could not index {file_path}: {e}")

        return indexed_files

    def scan_all(self) -> List[Dict[str, Any]]:
        all_files = []
        for dir_path in self.index_dirs:
            if os.path.exists(dir_path):
                files = self.scan_directory(dir_path)
                all_files.extend(files)
                logger.info(f"Indexed {len(files)} files from {dir_path}")

        return all_files

    def load_index(self) -> Dict[str, Dict[str, Any]]:
        if not os.path.exists(self.db_path):
            return {}

        try:
            with open(self.db_path, "r", encoding="utf-8") as f:
                self.file_index = json.load(f)
            logger.info(f"Loaded {len(self.file_index)} files from index")
        except Exception as e:
            logger.error(f"Failed to load index: {e}")
            self.file_index = {}

        return self.file_index

    def save_index(self) -> str:
        with open(self.db_path, "w", encoding="utf-8") as f:
            json.dump(self.file_index, f, indent=2)
        return self.db_path

    def update_index(self) -> Dict[str, List]:
        current_files = {}
        new_files = self.scan_all()

        for f in new_files:
            path = f["path"]
            if path in current_files:
                existing = current_files[path]
                if f["modified_time"] > existing["modified_time"]:
                    current_files[path] = f
            else:
                current_files[path] = f

        old_index = self.load_index()

        added = []
        modified = []
        deleted = []

        for path, info in current_files.items():
            if path not in old_index:
                added.append(info)
            elif old_index[path].get("hash") != info["hash"]:
                modified.append(info)

        for path in old_index:
            if path not in current_files:
                deleted.append(old_index[path])

        self.file_index = current_files
        self.changes = {"added": added, "modified": modified, "deleted": deleted}

        self.save_index()

        return {
            "added": len(added),
            "modified": len(modified),
            "deleted": len(deleted),
            "total_indexed": len(current_files),
        }

    def get_file_by_path(self, file_path: str) -> Optional[Dict[str, Any]]:
        return self.file_index.get(file_path)

    def search_by_extension(self, ext: str) -> List[Dict[str, Any]]:
        ext = ext.lower() if not ext.startswith(".") else ext.lower()
        return [
            info
            for info in self.file_index.values()
            if info.get("extension", "").lower() == ext
        ]

    def search_by_name(self, name: str) -> List[Dict[str, Any]]:
        name_lower = name.lower()
        return [
            info
            for info in self.file_index.values()
            if name_lower in info.get("name", "").lower()
        ]

    def get_stats(self) -> Dict[str, Any]:
        total_size = sum(f.get("size_bytes", 0) for f in self.file_index.values())
        ext_counts = {}
        for f in self.file_index.values():
            ext = f.get("extension", "unknown")
            ext_counts[ext] = ext_counts.get(ext, 0) + 1

        return {
            "total_files": len(self.file_index),
            "total_size_bytes": total_size,
            "total_size_mb": round(total_size / (1024 * 1024), 2),
            "extension_counts": ext_counts,
            "last_updated": datetime.now().isoformat(),
        }