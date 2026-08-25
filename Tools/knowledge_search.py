import logging
from typing import Dict, Any
from livekit.agents import function_tool
import asyncio
import json

logger = logging.getLogger(__name__)


@function_tool()
async def search_knowledge(query: str, top_k: int = 5) -> str:
    try:
        from zenith_brain import ZenithBrain

        brain = ZenithBrain()
        brain.initialize()

        if not brain.rag_pipeline:
            return "❌ RAG pipeline not initialized. Please index your files first."

        result = brain.rag_pipeline.query(query, top_k=top_k)

        answer = result.get("answer", "No answer found.")
        sources = result.get("sources", [])
        confidence = result.get("confidence", 0)

        output = f"🔍 **Query:** {query}\n\n"
        output += f"📝 **Answer:**\n{answer}\n\n"
        output += f"📊 **Confidence:** {confidence:.2%}\n\n"

        if sources:
            output += "📎 **Sources:**\n"
            for src in sources:
                output += f"  • {src.get('file', 'unknown')} (score: {src.get('score', 0):.3f})\n"

        return output
    except Exception as e:
        return f"❌ Knowledge search failed: {str(e)}"


@function_tool()
async def index_files(directory: str = None) -> str:
    try:
        from zenith_brain import ZenithBrain

        brain = ZenithBrain()
        brain.initialize()

        if not brain.rag_pipeline:
            return "❌ RAG pipeline not available"

        scan_dir = directory or str(__import__("pathlib").Path.home() / "Documents")
        result = brain.rag_pipeline.index_directory(scan_dir)

        return (
            f"✅ Indexing complete!\n"
            f"📁 Indexed: {result.get('indexed', 0)} files\n"
            f"❌ Failed: {result.get('failed', 0)} files\n"
            f"⏭️ Skipped: {result.get('skipped', 0)} files"
        )
    except Exception as e:
        return f"❌ File indexing failed: {str(e)}"


@function_tool()
async def ask_about_my_data(question: str) -> str:
    try:
        from zenith_brain import ZenithBrain

        brain = ZenithBrain()
        brain.initialize()

        result = brain.process_query(question)

        return json.dumps(result, indent=2, default=str)
    except Exception as e:
        return f"❌ Query processing failed: {str(e)}"