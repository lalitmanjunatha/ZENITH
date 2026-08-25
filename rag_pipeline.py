import logging
from typing import List, Dict, Any, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


class RAGPipeline:
    def __init__(
        self,
        vector_store=None,
        embedder=None,
        content_extractor=None,
        chunker=None,
        llm_provider=None,
    ):
        self.vector_store = vector_store
        self.embedder = embedder
        self.content_extractor = content_extractor
        self.chunker = chunker
        self.llm_provider = llm_provider
        self.indexed_files: List[str] = []

    def index_file(self, file_path: str) -> Dict[str, Any]:
        if not self.content_extractor:
            return {"error": "Content extractor not initialized"}

        extraction = self.content_extractor.extract(file_path)
        if not extraction["metadata"].get("extraction_success"):
            return {"error": f"Failed to extract content from {file_path}"}

        content = extraction["content"]
        if not content.strip():
            return {"error": "No content extracted"}

        metadata = {
            "source_file": file_path,
            "file_name": extraction["file_name"],
            "extension": extraction["extension"],
            "file_size": extraction["metadata"].get("size_bytes", 0),
        }

        if not self.chunker:
            return {"error": "Chunker not initialized"}

        chunks = self.chunker.chunk(content, metadata=metadata)

        if not chunks:
            return {"error": "No chunks generated"}

        if not self.embedder:
            return {"error": "Embedder not initialized"}

        texts = [chunk["text"] for chunk in chunks]
        embeddings = self.embedder.embed(texts)

        if embeddings is None:
            return {"error": "Failed to generate embeddings"}

        if not self.vector_store:
            return {"error": "Vector store not initialized"}

        self.vector_store.add(embeddings, chunks)

        self.indexed_files.append(file_path)

        return {
            "file_path": file_path,
            "chunks_created": len(chunks),
            "vectors_added": len(chunks),
            "status": "indexed",
        }

    def index_directory(self, directory: str, recursive: bool = True) -> Dict[str, Any]:
        from content_extractor import ContentExtractor
        from file_indexer import FileIndexer

        # Build an indexer rooted at the requested directory so we actually
        # scan THAT directory (previous code scanned home subfolders instead).
        indexer = FileIndexer(
            index_dir=directory or str(Path.home()),
            index_dirs=[directory] if directory else None,
        )
        files = indexer.scan_directory(directory) if directory else indexer.scan_all()

        results = {"indexed": 0, "failed": 0, "skipped": 0, "files": []}

        for file_info in files:
            file_path = file_info["path"]

            if file_path in self.indexed_files:
                results["skipped"] += 1
                continue

            result = self.index_file(file_path)

            if "error" in result:
                results["failed"] += 1
            else:
                results["indexed"] += 1

            results["files"].append(result)

        return results

    def search(
        self, query: str, top_k: int = 5, min_score: float = 0.3
    ) -> List[Dict[str, Any]]:
        if not self.embedder or not self.vector_store:
            return []

        query_embedding = self.embedder.embed_single(query)
        if query_embedding is None:
            return []

        results = self.vector_store.search(query_embedding, top_k=top_k)

        filtered = [r for r in results if r.get("similarity_score", 0) >= min_score]

        return filtered

    def query(self, question: str, top_k: int = 5) -> Dict[str, Any]:
        search_results = self.search(question, top_k=top_k)

        if not search_results:
            return {
                "question": question,
                "answer": "No relevant information found in indexed files.",
                "sources": [],
                "confidence": 0,
            }

        context = "\n\n".join(
            [r.get("text", r.get("chunk_text", "")) for r in search_results]
        )
        sources = [
            {
                "file": r.get("source_file", r.get("file_name", "unknown")),
                "score": r.get("similarity_score", 0),
                "chunk_index": r.get("chunk_index", 0),
            }
            for r in search_results
        ]

        avg_score = sum(r.get("similarity_score", 0) for r in search_results) / len(
            search_results
        )

        answer = self._generate_answer(question, context, sources)

        return {
            "question": question,
            "answer": answer,
            "sources": sources,
            "confidence": round(avg_score, 4),
            "context_used": len(context),
        }

    def _generate_answer(
        self, question: str, context: str, sources: List[Dict[str, Any]]
    ) -> str:
        if self.llm_provider:
            try:
                prompt = f"""Based on the following retrieved context from your files, answer the question.
If the context doesn't contain enough information, say so.

Context:
{context[:3000]}

Question: {question}

Answer:"""
                return self.llm_provider.generate(prompt)
            except Exception as e:
                logger.warning(f"LLM generation failed: {e}")

        return f"Based on your files, the most relevant information is found in {len(sources)} source(s). Confidence: {sources[0].get('score', 0):.2f}"

    def get_index_stats(self) -> Dict[str, Any]:
        return {
            "indexed_files_count": len(self.indexed_files),
            "indexed_files": self.indexed_files,
            "vector_store_stats": self.vector_store.get_stats() if self.vector_store else {},
        }

    def search_by_content(
        self, keyword: str, top_k: int = 5
    ) -> List[Dict[str, Any]]:
        results = self.search(keyword, top_k=top_k)
        return results

    def find_and_open_file(
        self, query: str, search_by: str = "content"
    ) -> Dict[str, Any]:
        if search_by == "content":
            results = self.search(query, top_k=3)
        else:
            results = []

        if not results:
            return {
                "query": query,
                "found": False,
                "message": "No matching files found in your indexed documents.",
            }

        best_match = results[0]
        file_path = best_match.get("source_file", best_match.get("file_name", "unknown"))

        return {
            "query": query,
            "found": True,
            "file_path": file_path,
            "file_name": best_match.get("file_name", "unknown"),
            "source_file": best_match.get("source_file", "unknown"),
            "score": best_match.get("similarity_score", 0),
            "message": f"Found file: {file_path}",
        }

    def get_file_info(self, file_path: str) -> Dict[str, Any]:
        from file_indexer import FileIndexer

        indexer = FileIndexer()
        indexer.load_index()

        info = indexer.get_file_by_path(file_path)
        if info:
            return {
                "found": True,
                "path": file_path,
                "name": info.get("name", "unknown"),
                "extension": info.get("extension", "unknown"),
                "size_bytes": info.get("size_bytes", 0),
                "modified_time": info.get("modified_time", "unknown"),
            }

        return {"found": False, "path": file_path}

    def search_files_by_name(
        self, name_query: str
    ) -> List[Dict[str, Any]]:
        from file_indexer import FileIndexer

        indexer = FileIndexer()
        indexer.load_index()

        results = indexer.search_by_name(name_query)
        return [
            {
                "path": r["path"],
                "name": r["name"],
                "extension": r["extension"],
                "size_bytes": r["size_bytes"],
                "modified_time": r["modified_time"],
            }
            for r in results
        ]