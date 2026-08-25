import logging
import numpy as np
from typing import List, Dict, Any, Optional
from pathlib import Path

logger = logging.getLogger(__name__)

try:
    from sentence_transformers import SentenceTransformer
    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    SENTENCE_TRANSFORMERS_AVAILABLE = False

try:
    import faiss
    FAISS_AVAILABLE = True
except ImportError:
    FAISS_AVAILABLE = False


class Embedder:
    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        self.model_name = model_name
        self.model = None
        self._initialize_model()

    def _initialize_model(self):
        if not SENTENCE_TRANSFORMERS_AVAILABLE:
            logger.warning(
                "sentence-transformers not installed. "
                "Install with: pip install sentence-transformers"
            )
            return

        try:
            self.model = SentenceTransformer(self.model_name)
            logger.info(f"Loaded embedding model: {self.model_name}")
        except Exception as e:
            logger.error(f"Failed to load embedding model: {e}")
            self.model = None

    def embed(self, texts: List[str]) -> Optional[np.ndarray]:
        if not self.model:
            logger.error("Embedding model not loaded")
            return None

        if not texts:
            return np.array([])

        try:
            embeddings = self.model.encode(texts, show_progress_bar=False)
            return np.array(embeddings)
        except Exception as e:
            logger.error(f"Embedding failed: {e}")
            return None

    def embed_single(self, text: str) -> Optional[np.ndarray]:
        if not self.model:
            return None

        try:
            embedding = self.model.encode([text], show_progress_bar=False)
            return np.array(embedding[0])
        except Exception as e:
            logger.error(f"Single embedding failed: {e}")
            return None

    def get_dimension(self) -> int:
        if self.model:
            return self.model.get_sentence_embedding_dimension()
        return 384

    def is_available(self) -> bool:
        return self.model is not None