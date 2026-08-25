"""Zenith Text Tools — grammar fixing and clipboard text transformations.

F7 Grammar fixer: takes your SELECTED/COPIED text, fixes grammar+spelling via
LLM), and puts the corrected version back on
your clipboard ready to paste.
"""

import logging

from livekit.agents import function_tool

logger = logging.getLogger(__name__)


def _get_clipboard() -> str:
    try:
        import pyperclip
        return (pyperclip.paste() or "").strip()
    except Exception:
        return ""


def _set_clipboard(text: str) -> bool:
    try:
        import pyperclip
        pyperclip.copy(text)
        return True
    except Exception:
        return False


@function_tool()
async def fix_grammar(use_clipboard: bool = True, text: str = "") -> str:
    """GRAMMAR FIXER: corrects grammar/spelling/punctuation of the given text —
    or of whatever is currently on your CLIPBOARD if no text is passed. The
    corrected result is copied back to the clipboard automatically.

    Args:
        use_clipboard: Read source text from clipboard when 'text' is empty
        text: Direct text to fix (overrides clipboard)
    """
    try:
        src = text.strip() or (_get_clipboard() if use_clipboard else "")
        if not src:
            return ("📋 Clipboard is empty. Copy some text first, or pass "
                    "text directly: fix_grammar(text=\"...\").")
        if len(src) > 8000:
            return f"❌ Text too long ({len(src)} chars) — split it under 8000."

        from Tools._llm_client import chat_complete_sync
        out = chat_complete_sync(
            "Fix ONLY grammar, spelling and punctuation. Keep meaning, language, "
            "tone and formatting identical. Return ONLY the corrected text.\n\n" + src,
            max_tokens=2000)
        if out.startswith("ERROR"):
            return (f"❌ Brain unavailable ({out[:80]}…). "
                    "Offline fallback isn't reliable for editing yet — retry online.")
        fixed = out.strip().strip('"')
        copied = _set_clipboard(fixed)
        diff_note = "✅ corrections made" if fixed != src else "✨ already clean"
        msg = (f"📝 GRAMMAR FIX {diff_note} ({len(src)}→{len(fixed)} chars)\n"
               f"──────────\n{fixed[:600]}{'…' if len(fixed)>600 else ''}\n──────────\n"
               + ("📋 Copied to clipboard — just paste." if copied
                  else "(clipboard write blocked; copy manually from above)"))
        return msg
    except Exception as e:
        return f"❌ Grammar fix failed: {e}"


@function_tool()
async def rewrite_tone(style: str = "formal", text: str = "") -> str:
    """TONE DIAL: rewrite clipboard/given text in another style.
    styles: formal / casual / short / polite / friendly-professional.

    Args:
        style: Target tone
        text: Text to rewrite (empty = use clipboard)
    """
    try:
        src = text.strip() or _get_clipboard()
        if not src:
            return "📋 Nothing to rewrite — clipboard empty."
        presets = {
            "formal": "professional, courteous, no slang",
            "casual": "relaxed, friendly, contractions welcome",
            "short": "as brief as possible without losing meaning",
            "polite": "extra polite and soft, respectful requests",
            "friendly": "warm professional — approachable but competent",
        }
        rule = presets.get(style.lower(), f"rewrite in this style: {style}")
        from Tools._llm_client import chat_complete_sync
        out = chat_complete_sync(
            f"Rewrite the text below. Style: {rule}. Preserve ALL key facts. "
            f"Return only the rewritten text.\n\n{src}", max_tokens=1800)
        if out.startswith("ERROR"):
            return f"❌ Rewrite unavailable: {out[:80]}"
        fixed = out.strip()
        copied = _set_clipboard(fixed)
        return (f"🎭 TONE → {style.upper()}\n──────────\n{fixed[:600]}"
                f"{'…' if len(fixed)>600 else ''}\n──────────\n"
                + ("📋 On clipboard." if copied else ""))
    except Exception as e:
        return f"❌ Rewrite failed: {e}"