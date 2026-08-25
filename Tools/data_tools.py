import logging
from typing import Dict, Any, Optional
from livekit.agents import function_tool
import asyncio
import json

logger = logging.getLogger(__name__)


@function_tool()
async def index_my_files(directory: str = None) -> str:
    try:
        from zenith_brain import ZenithBrain

        brain = ZenithBrain()
        brain.initialize()

        if not brain.rag_pipeline:
            return "❌ RAG pipeline not available"

        scan_dir = directory or str(__import__("pathlib").Path.home() / "Documents")
        result = brain.rag_pipeline.index_directory(scan_dir)

        return json.dumps(result, indent=2, default=str)
    except Exception as e:
        return f"❌ File indexing failed: {str(e)}"


@function_tool()
async def search_my_files(query: str, top_k: int = 5) -> str:
    try:
        from zenith_brain import ZenithBrain

        brain = ZenithBrain()
        brain.initialize()

        if not brain.rag_pipeline:
            return "❌ RAG pipeline not available"

        result = brain.rag_pipeline.query(query, top_k=top_k)

        return json.dumps(result, indent=2, default=str)
    except Exception as e:
        return f"❌ File search failed: {str(e)}"


@function_tool()
async def get_knowledge_stats() -> str:
    try:
        from zenith_brain import ZenithBrain

        brain = ZenithBrain()
        brain.initialize()

        stats = brain.get_status()

        return json.dumps(stats, indent=2, default=str)
    except Exception as e:
        return f"❌ Failed to get knowledge stats: {str(e)}"


@function_tool()
async def analyze_dataset(data_path: str, operation: str = "summary") -> str:
    try:
        from data_processor import DataProcessor

        dp = DataProcessor()
        dp.load_data(data_path)

        if operation == "summary":
            result = dp.get_summary()
        elif operation == "clean":
            dp.clean_data()
            result = {"status": "cleaned", "rows": len(dp.processed_data)}
        elif operation == "features":
            dp.engineer_features()
            result = {
                "status": "features engineered",
                "original_columns": len(dp.data.columns),
                "engineered_columns": len(dp.features.columns) if dp.features is not None else 0,
            }
        else:
            result = {"error": f"Unknown operation: {operation}"}

        return json.dumps(result, indent=2, default=str)
    except Exception as e:
        return f"❌ Data operation failed: {str(e)}"