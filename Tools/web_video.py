"""Web Video — YouTube summarizer from real transcripts.

Fetches the actual caption track (youtube-transcript-api), then LLM-summarizes
key points. If a video has no captions, says so honestly. Summary generation
flows through _llm_client; the writing step needs internet
writing step (transcript fetch itself needs internet).
"""

import logging
import re

from livekit.agents import function_tool

logger = logging.getLogger(__name__)


def _video_id(url: str) -> str:
    patterns = [
        r"(?:v=|/videos/|embed/|youtu\.be/|/shorts/)([A-Za-z0-9_-]{11})",
        r"^([A-Za-z0-9_-]{11})$",
    ]
    for p in patterns:
        m = re.search(p, url.strip())
        if m:
            return m.group(1)
    return ""


@function_tool()
async def summarize_youtube(url_or_id: str, style: str = "bullets") -> str:
    """Summarize a YouTube video from its REAL captions/transcript.

    Args:
        url_or_id: Full URL (watch/shorts/youtu.be) or 11-char video ID
        style: "bullets", "paragraph", or "tldr"
    """
    vid = _video_id(url_or_id)
    if not vid:
        return "❌ Couldn't extract a video ID. Paste a normal youtube.com/watch, youtu.be or /shorts link."

    try:
        from youtube_transcript_api import YouTubeTranscriptApi

        try:
            tracks = YouTubeTranscriptApi.list_transcripts(vid)
            # Prefer English; else take first available (incl. auto-generated)
            chosen = None
            try:
                chosen = tracks.find_transcript(["en"])
            except Exception:
                for t in tracks:
                    chosen = t
                    break
            if chosen is None:
                return "❌ This video has no caption tracks at all — nothing to summarize honestly."
            data = chosen.fetch()
            lang = chosen.language_code
        except Exception as e:
            msg = str(e).lower()
            if "no transcript" in msg or "not found" in msg or "disabled" in msg:
                return ("❌ No captions available for this video (creator disabled them "
                        "and no auto-captions exist). Can't summarize without text.")
            return f"❌ Transcript fetch failed: {str(e)[:150]}"

        # Join with light punctuation restoration on timestamps
        lines = []
        for seg in data:
            txt = (seg.get("text") or seg.get("snippet") or "").replace("\n", " ").strip()
            if txt and txt != "[Music]":
                lines.append(txt)
        transcript = " ".join(lines)
        if len(transcript.split()) < 40:
            return "❌ Transcript too short/empty to summarize meaningfully."

        # Bound very long ones for the LLM (keep head + tail coverage)
        words = transcript.split()
        if len(words) > 9000:
            transcript = " ".join(words[:4500]) + "\n[...middle skipped...]\n" + " ".join(words[-3500:])
            trimmed = True
        else:
            trimmed = False

        from Tools._llm_client import chat_complete
        style_map = {
            "bullets": "8-12 concise bullet points of the key ideas.",
            "paragraph": "3 short paragraphs telling the core narrative.",
            "tldr": "a single-sentence TL;DR followed by 3 must-know points.",
        }
        prompt = (
            f"Summarize this video transcript as {style_map.get(style, style_map['bullets'])} "
            f"Mention the video's apparent topic first.\n\nTRANSCRIPT:\n{transcript}"
        )
        summary = await chat_complete(prompt, system="You are a precise summarizer.", temperature=0.2, max_tokens=1200)

        dur_min = None
        try:
            last = data[-1]
            start = float(last.get("start", last.get("snippet", {}).get("start", 0)) or 0)
            dur_min = int(start // 60)
        except Exception:
            pass

        head = f"🎬 VIDEO SUMMARY ({lang}, ~{dur_min or '?'} min of captions)\n════════════════════\n"
        if summary.startswith("ERROR"):
            # Offline fallback: give raw gist via first/last lines instead of failing silently
            gist = " ".join(words[:60])
            return (head + f"⚠️ LLM unavailable ({summary[:80]}…).\n"
                    f"Raw opening of transcript: “{gist}…”")
        note = "\n\nℹ️ Very long video — head+tail analyzed." if trimmed else ""
        return head + summary.strip() + note
    except ImportError:
        return ("❌ Missing library. Run: pip install youtube-transcript-api")
    except Exception as e:
        return f"❌ Summarizer failed: {e}"
