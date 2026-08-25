import faiss
import numpy as np
import json
import logging
import os
from typing import List, Dict, Any, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


class VectorStore:
    def __init__(self, index_path: str = "data/vector_index.faiss", dimension: int = 384):
        self.index_path = index_path
        self.dimension = dimension
        self.index = None
        self.metadata_store: List[Dict[str, Any]] = []
        Path(self.index_path).parent.mkdir(parents=True, exist_ok=True)

    def _ensure_directory(self):
        Path(self.index_path).parent.mkdir(parents=True, exist_ok=True)

    def initialize(self):
        if self.index is None:
            self.index = faiss.IndexFlatIP(self.dimension)
            logger.info(f"Initialized FAISS index with dimension {self.dimension}")

    def add(
        self,
        embeddings: np.ndarray,
        metadata: List[Dict[str, Any]],
        normalize: bool = True,
    ) -> int:
        if self.index is None:
            self.initialize()

        if normalize:
            faiss.normalize_L2(embeddings)

        start_idx = self.index.ntotal
        self.index.add(embeddings.astype(np.float32))

        for i, meta in enumerate(metadata):
            meta["vector_index"] = start_idx + i
            self.metadata_store.append(meta)

        added_count = len(metadata)
        logger.info(f"Added {added_count} vectors to index")
        return added_count

    def search(
        self, query_embedding: np.ndarray, top_k: int = 5
    ) -> List[Dict[str, Any]]:
        if self.index is None or self.index.ntotal == 0:
            return []

        if query_embedding.ndim == 1:
            query_embedding = query_embedding.reshape(1, -1)

        faiss.normalize_L2(query_embedding)

        scores, indices = self.index.search(query_embedding.astype(np.float32), top_k)

        results = []
        for i, (score, idx) in enumerate(zip(scores[0], indices[0])):
            if idx < 0 or idx >= len(self.metadata_store):
                continue

            meta = self.metadata_store[idx].copy()
            meta["similarity_score"] = float(score)
            meta["rank"] = i + 1
            results.append(meta)

        return results

    def save(self) -> str:
        self._ensure_directory()

        if self.index is not None:
            faiss.write_index(self.index, self.index_path)
            logger.info(f"Saved FAISS index to {self.index_path}")

        meta_path = self.index_path.replace(".faiss", "_metadata.json")
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(self.metadata_store, f, indent=2, default=str)

        return self.index_path

    def load(self) -> bool:
        if not os.path.exists(self.index_path):
            logger.info("No existing FAISS index found")
            return False

        try:
            self.index = faiss.read_index(self.index_path)
            logger.info(f"Loaded FAISS index with {self.index.ntotal} vectors")

            meta_path = self.index_path.replace(".faiss", "_metadata.json")
            if os.path.exists(meta_path):
                with open(meta_path, "r", encoding="utf-8") as f:
                    self.metadata_store = json.load(f)
                logger.info(f"Loaded {len(self.metadata_store)} metadata entries")

            return True
        except Exception as e:
            logger.error(f"Failed to load FAISS index: {e}")
            return False

    def get_stats(self) -> Dict[str, Any]:
        return {
            "total_vectors": self.index.ntotal if self.index is not None else 0,
            "dimension": self.dimension,
            "metadata_entries": len(self.metadata_store),
            "index_path": self.index_path,
        }

    def reset(self):
        self.index = faiss.IndexFlatIP(self.dimension)
        self.metadata_store = []
        logger.info("Vector store reset")