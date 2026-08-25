"""Audio Intelligence — now-playing detection and voice presentation control.

SONG RECOGNIZER (honest design): true audio fingerprinting needs mic/loopback
recording. Instead we detect what's playing from REAL window/tab titles
(Spotify, YouTube, Edge/Chrome media tabs) which covers most desktop listening.
If nothing detectable, we say so plainly + how to enable full recognition.

PRESENTER: arrow-key control for PowerPoint/PDF slideshows (works whenever the
slideshow window is focused). Includes goto-slide via number keys in PPT.
"""

import logging
import re

import asyncio

from livekit.agents import function_tool

logger = logging.getLogger(__name__)

MEDIA_TITLE_RE = re.compile(
    r"^\s*(.+?)\s*[-–—]\s*(.+?)\s*(?:\((?:Official|Lyric|Audio|Video)[^)]*\))?\s*$"
)


def _spotify_now():
    try:
        import pygetwindow as gw

        for w in gw.getAllWindows():
            t = (w.title or "").strip()
            if not t:
                continue
            low = t.lower()
            if "spotify" in low:
                # Spotify title is usually "Artist - Song" (or "Spotify" idle / ad text)
                if low.strip() == "spotify" or "spotify free" in low or "spotify premium" in low:
                    return None, t
                return ("Spotify", t), None
            # YouTube / browser media tabs often look like "Song - Artist - YouTube"
            for site in (" - youtube", "youtube music", " - gaana", " - jiosaavn", " - soundcloud"):
                if low.endswith(site) or site in low:
                    core = re.sub(re.escape(site.replace(" - ", " - ")), "", t, flags=re.I)
                    core = re.sub(r"\s*-\s*youtube.*$", "", t, flags=re.I)
                    return (site.strip(" -").title(), core), None
    except Exception as e:
        logger.debug(f"window scan failed: {e}")
    return None, None


@function_tool()
async def what_song_now() -> str:
    """WHAT'S PLAYING? Detect the current song from Spotify/browser window titles.
    Honest about limits: no mic fingerprinting — if it can't see a media title,
    it says exactly that."""
    try:
        found, note = _spotify_now()
        if found:
            app, raw = found
            m = MEDIA_TITLE_RE.match(raw)
            if m:
                artist, song = m.group(1).strip(), m.group(2).strip()
                return (
                    f"🎵 NOW PLAYING ({app})\n"
                    f"   🎤 Artist: {artist}\n   🎶 Song: {song}\n"
                    f"(detected from the {app} window title)"
                )
            return f"🎵 Media detected in {app}: “{raw[:80]}”"
        if note:
            return f"🎵 {note} is open but idle/no track info in its title."
        return (
            "🤷 Couldn't spot any playing music in window titles (Spotify/YouTube etc.).\n"
            "I don't do microphone fingerprinting yet — play something in Spotify or a "
            "YouTube tab and ask again."
        )
    except Exception as e:
        return f"❌ Detection failed: {e}"


# ------------------------------------------------------------- presenter -----

def _press(*keys):
    try:
        import pyautogui

        pyautogui.hotkey(*keys)
        return True
    except Exception as e:
        logger.debug(f"key press failed: {e}")
        return False


@function_tool()
async def present_start() -> str:
    """Start a slideshow from the beginning (F5 works in PowerPoint; some PDF
    viewers use Ctrl+L). Targets whatever presentation window has focus."""
    ok = _press("f5")
    return ("🎬 Sent F5 — slideshow should start (PowerPoint focused)." if ok
            else "❌ Keystroke failed.")


@function_tool()
async def present_next() -> str:
    """Advance to the next slide/animation (→ key)."""
    ok = await asyncio.to_thread(_press, "right")
    return "➡️ Next slide." if ok else "❌ Keystroke failed."


@function_tool()
async def present_previous() -> str:
    """Go back one slide/animation (← key)."""
    ok = await asyncio.to_thread(_press, "left")
    return "⬅️ Previous slide." if ok else "❌ Keystroke failed."


@function_tool()
async def present_goto(slide_number: int) -> str:
    """Jump to a specific slide in PowerPoint: types the number then Enter.

    Args:
        slide_number: Slide to jump to (1-999)
    """
    n = max(1, min(int(slide_number), 999))
    try:
        import pyautogui

        await asyncio.to_thread(pyautogui.typewrite, str(n), interval=0.05)
        await asyncio.to_thread(pyautogui.press, "enter")
        return f"🎯 Jumped to slide {n} (PowerPoint focused)."
    except Exception as e:
        return f"❌ Jump failed: {e}"


@function_tool()
async def present_end() -> str:
    """End the slideshow (Esc)."""
    ok = await asyncio.to_thread(_press, "esc")
    return "🏁 Slideshow ended." if ok else "❌ Keystroke failed."


@function_tool()
async def present_black_screen() -> str:
    """Toggle black-screen during a PowerPoint show ('B' key) — classic talk trick."""
    try:
        import pyautogui

        await asyncio.to_thread(pyautogui.press, "b")
        return "⬛ Black screen toggled (press again to restore)."
    except Exception as e:
        return f"❌ Failed: {e}"
