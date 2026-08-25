import logging
from typing import Dict, Any, Optional
from livekit.agents import function_tool
import asyncio
import json

logger = logging.getLogger(__name__)


@function_tool()
async def analyze_sentiment(text: str) -> str:
    try:
        from nlp_engine import NLPEngine

        nlp = NLPEngine()
        result = nlp.sentiment_analysis(text)

        return json.dumps(result, indent=2, default=str)
    except Exception as e:
        return f"❌ Sentiment analysis failed: {str(e)}"


@function_tool()
async def extract_entities(text: str) -> str:
    try:
        from nlp_engine import NLPEngine

        nlp = NLPEngine()
        entities = nlp.extract_entities(text)

        return json.dumps(
            {"entities": entities, "count": len(entities)},
            indent=2,
            default=str,
        )
    except Exception as e:
        return f"❌ Entity extraction failed: {str(e)}"


@function_tool()
async def summarize_text(text: str, max_length: int = 130) -> str:
    try:
        from nlp_engine import NLPEngine

        nlp = NLPEngine()
        summary = nlp.summarize(text, max_length=max_length)

        return f"📝 Summary:\n\n{summary}"
    except Exception as e:
        return f"❌ Summarization failed: {str(e)}"


@function_tool()
async def detect_language(text: str) -> str:
    try:
        from nlp_engine import NLPEngine

        nlp = NLPEngine()
        lang = nlp.detect_language(text)

        return f"🌐 Detected language: {lang}"
    except Exception as e:
        return f"❌ Language detection failed: {str(e)}"


@function_tool()
async def preprocess_text(text: str) -> str:
    try:
        from nlp_engine import NLPEngine

        nlp = NLPEngine()
        result = nlp.preprocess(text)

        return json.dumps(result, indent=2, default=str)
    except Exception as e:
        return f"❌ Text preprocessing failed: {str(e)}"