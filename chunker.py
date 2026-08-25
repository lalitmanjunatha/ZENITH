from typing import List, Dict, Any
import logging

logger = logging.getLogger(__name__)


class Chunker:
    def __init__(self, chunk_size: int = 512, overlap: int = 50):
        self.chunk_size = chunk_size
        self.overlap = overlap

    def chunk_text(self, text: str, metadata: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        if not text or not text.strip():
            return []

        chunks = []
        words = text.split()
        start = 0
        chunk_index = 0

        while start < len(words):
            end = min(start + self.chunk_size, len(words))
            chunk_text = " ".join(words[start:end])

            if len(chunk_text.strip()) < 20:
                break

            chunk_meta = {
                "chunk_index": chunk_index,
                "start_word": start,
                "end_word": end,
                "total_words": len(words),
            }
            if metadata:
                chunk_meta.update(metadata)

            chunks.append({
                "text": chunk_text,
                "metadata": chunk_meta,
            })

            chunk_index += 1
            start = end - self.overlap
            if start < 0:
                start = 0

        return chunks

    def chunk_by_paragraphs(self, text: str, metadata: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        if not text or not text.strip():
            return []

        paragraphs = text.split("\n\n")
        chunks = []
        current_chunk = ""
        chunk_index = 0

        for para in paragraphs:
            para_words = para.split()

            if len(current_chunk.split()) + len(para_words) <= self.chunk_size:
                current_chunk += (" " + para) if current_chunk else para
            else:
                if current_chunk.strip():
                    chunk_meta = {"chunk_index": chunk_index, "method": "paragraph"}
                    if metadata:
                        chunk_meta.update(metadata)
                    chunks.append({"text": current_chunk.strip(), "metadata": chunk_meta})
                    chunk_index += 1

                current_chunk = para

        if current_chunk.strip():
            chunk_meta = {"chunk_index": chunk_index, "method": "paragraph"}
            if metadata:
                chunk_meta.update(metadata)
            chunks.append({"text": current_chunk.strip(), "metadata": chunk_meta})

        return chunks

    def chunk_by_sentences(self, text: str, metadata: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        import re

        if not text or not text.strip():
            return []

        sentences = re.split(r"(?<=[.!?])\s+", text)
        chunks = []
        current_chunk = ""
        chunk_index = 0

        for sentence in sentences:
            sentence_words = sentence.split()

            if len(current_chunk.split()) + len(sentence_words) <= self.chunk_size:
                current_chunk += (" " + sentence) if current_chunk else sentence
            else:
                if current_chunk.strip():
                    chunk_meta = {"chunk_index": chunk_index, "method": "sentence"}
                    if metadata:
                        chunk_meta.update(metadata)
                    chunks.append({"text": current_chunk.strip(), "metadata": chunk_meta})
                    chunk_index += 1

                current_chunk = sentence

        if current_chunk.strip():
            chunk_meta = {"chunk_index": chunk_index, "method": "sentence"}
            if metadata:
                chunk_meta.update(metadata)
            chunks.append({"text": current_chunk.strip(), "metadata": chunk_meta})

        return chunks

    def chunk(
        self, text: str, method: str = "words", metadata: Dict[str, Any] = None
    ) -> List[Dict[str, Any]]:
        if method == "paragraphs":
            return self.chunk_by_paragraphs(text, metadata)
        elif method == "sentences":
            return self.chunk_by_sentences(text, metadata)
        else:
            return self.chunk_text(text, metadata)