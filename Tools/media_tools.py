"""Zenith Media Micro-tools — local file conversions.

F36 video_to_mp3   : extract audio track from a LOCAL video (ffmpeg; graceful
                      guidance if ffmpeg is missing — never touches YouTube)
F38 compress_images: batch-shrink images to a target KB size for forms/uploads
"""

import asyncio
import logging
import shutil
from pathlib import Path

from livekit.agents import function_tool

logger = logging.getLogger(__name__)


def _has_ffmpeg() -> bool:
    return shutil.which("ffmpeg") is not None


@function_tool()
async def video_to_mp3(video_path: str, quality: str = "192k") -> str:
    """Extract the audio track from a LOCAL video file into MP3.

    Args:
        video_path: Path to your .mp4/.mkv/.mov etc.
        quality: bitrate like 128k / 192k / 320k
    """
    try:
        src = Path(video_path)
        if not src.exists():
            return f"❌ Video not found: {src}"
        if not _has_ffmpeg():
            return ("❌ ffmpeg isn't installed. One-time fix:\n"
                    "   winget install Gyan.FFmpeg\n"
                    "…then ask me again. (I never touch YouTube downloads.)")

        out = src.with_suffix(".mp3")
        i = 1
        while out.exists():
            out = src.with_name(f"{src.stem}_{i}.mp3"); i += 1
        q = quality if re.match(r"^\d+k$", quality or "") else "192k"

        def _run():
            import subprocess
            r = subprocess.run(
                ["ffmpeg", "-y", "-i", str(src), "-vn", "-b:a", q, str(out)],
                capture_output=True, text=True, timeout=1800)
            return r.returncode, (r.stderr or "")
        rc, err = await asyncio.to_thread(_run)
        if rc != 0:
            m = [l for l in err.splitlines() if "error" in l.lower()]
            return f"❌ ffmpeg error: {(m[-1] if m else err.strip())[:150]}"
        mb = out.stat().st_size / (1024 * 1024)
        return f"🎵 Extracted → {out}\n   {mb:.1f} MB @ {q}"
    except Exception as e:
        return f"❌ Conversion failed: {e}"


import re  # noqa: E402


@function_tool()
async def compress_images(folder_or_file: str = "", target_kb: int = 200,
                         max_side_px: int = 1600) -> str:
    """COMPRESS IMAGES to hit a target file size (forms/uploads love this).
    Processes one image or every image in a folder; originals preserved as
    <name>_original.<ext> beside them.

    Args:
        folder_or_file: Image path OR folder of images (empty = pick common dirs)
        target_kb: Aim for roughly this many KB per image (default 200)
        max_side_px: Downscale longest side to at most this many pixels first
    """
    try:
        from PIL import Image

        p = Path(folder_or_file) if folder_or_file else None
        files = []
        if p and p.is_file():
            files = [p]
        elif p and p.is_dir():
            files = [f for f in sorted(p.iterdir())
                     if f.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp")]
        else:
            home = Path.home()
            for base in (home / "Pictures" / "Screenshots", home / "Downloads"):
                if base.exists():
                    files = [f for f in sorted(base.iterdir())
                             if f.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp")]
                    break
        files = files[:20]
        if not files:
            return "🖼️ No images found to compress."

        results = []
        for f in files:
            try:
                orig_kb = f.stat().st_size / 1024
                backup = f.with_name(f.stem + "_original" + f.suffix)
                if not backup.exists():
                    shutil.copy2(f, backup)

                img = Image.open(f).convert("RGB")
                w, h = img.size
                scale = min(1.0, max_side_px / max(w, h))
                if scale < 1.0:
                    img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)

                # iterative quality search toward target
                lo, hi, best_q = 30, 92, 85
                target_bytes = int(target_kb) * 1024
                best_buf = None
                import io
                for _ in range(7):
                    q = (lo + hi) // 2
                    buf = io.BytesIO()
                    img.save(buf, "JPEG", quality=q, optimize=True)
                    if buf.tell() <= target_bytes:
                        best_q, best_buf = q, buf.getvalue()
                        lo = q + 1
                    else:
                        hi = q - 1
                    if lo > hi:
                        break
                if best_buf is None:
                    best_q = max(30, hi)
                    buf = io.BytesIO()
                    img.save(buf, "JPEG", quality=best_q, optimize=True)
                    best_buf = buf.getvalue()

                outp = f.with_suffix(".jpg")
                outp.write_bytes(best_buf)
                new_kb = len(best_buf) / 1024
                results.append(f"✅ {f.name}: {orig_kb:.0f}KB → {new_kb:.0f}KB (q{best_q})")
            except Exception as e:
                results.append(f"⚠️ {f.name}: {str(e)[:50]}")

        from Tools.autonomy import journal
        journal("cleanup", f"Compressed {len(results)} image(s) to ~{target_kb}KB")
        return ("🖼️ COMPRESSION DONE\n" + "\n".join(f"   {r}" for r in results[:12])
                + "\n(Originals kept as *_original.*)")
    except Exception as e:
        return f"❌ Compression failed: {e}"