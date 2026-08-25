"""Zenith PDF Studio — page surgery + watermarking by voice.

F1 PDF page surgeon : extract / reorder / delete pages, merge extra files
F2 Watermark stamper: text watermark across every page (batch-capable)

Uses pypdf (PyPDF2 compatible API already in the project).
"""

import logging
import os
import re
from datetime import datetime
from pathlib import Path

from livekit.agents import function_tool

try:
    from pypdf import PdfReader, PdfWriter          # modern name
except ImportError:
    from PyPDF2 import PdfReader, PdfWriter         # legacy alias (same API)

logger = logging.getLogger(__name__)


def _out_path(src: str, tag: str) -> Path:
    p = Path(src)
    out_dir = p.parent / "zenith_pdf_studio"
    out_dir.mkdir(exist_ok=True)
    return out_dir / f"{p.stem}_{tag}_{datetime.now().strftime('%H%M%S')}.pdf"


def _reader(src: str):
    r = PdfReader(src)
    if getattr(r, "is_encrypted", False):
        try:
            r.decrypt("")
        except Exception:
            raise ValueError("PDF is password-protected.")
    return r


@function_tool()
async def pdf_page_info(file_path: str) -> str:
    """Inspect a PDF: page count, sizes, encrypted state — before surgery.

    Args:
        file_path: Path to the PDF
    """
    try:
        r = _reader(file_path)
        box = r.pages[0].mediabox
        w_in, h_in = float(box.width) / 72, float(box.height) / 72
        orient = "landscape" if w_in > h_in else "portrait"
        meta = r.metadata or {}
        title = str(getattr(meta, "title", "") or "")
        return (
            f"📄 {Path(file_path).name}\n"
            f"   Pages: {len(r.pages)} | {w_in:.1f}×{h_in:.1f} in ({orient})\n"
            + (f"   Title: {title[:60]}\n" if title else "")
            + "Say e.g.: extract pages 2,5-7 · delete page 1 · reorder 3,1,2"
        )
    except FileNotFoundError:
        return f"❌ File not found: {file_path}"
    except ValueError as ve:
        return f"🔒 {ve}"
    except Exception as e:
        return f"❌ Inspect failed: {e}"


def _parse_pages(spec: str, total: int) -> list:
    """'2,5-7,10' -> [2,5,6,7,10]; negative/-1 allowed for 'to end' style."""
    pages = []
    for part in spec.replace(" ", "").split(","):
        if not part:
            continue
        if "-" in part:
            a, _, b = part.partition("-")
            lo = int(a) if a else 1
            hi = int(b) if b else total
            pages.extend(range(max(1, lo), min(total, hi) + 1))
        else:
            n = int(part)
            if 1 <= n <= total:
                pages.append(n)
    # dedupe preserving order
    seen, out = set(), []
    for p in pages:
        if p not in seen:
            seen.add(p); out.append(p)
    return out


@function_tool()
async def pdf_extract_pages(file_path: str, pages_spec: str, as_separate: bool = False) -> str:
    """Extract pages from a PDF into a new file (or one file per page).

    Args:
        file_path: Source PDF
        pages_spec: e.g. "2,5-7" or "all"
        as_separate: True = each page becomes its own PDF
    """
    try:
        r = _reader(file_path)
        total = len(r.pages)
        spec = pages_spec.strip().lower()
        nums = list(range(1, total + 1)) if spec == "all" else _parse_pages(pages_spec, total)
        if not nums:
            return f"❌ No valid pages in '{pages_spec}' (PDF has {total})."

        outs = []
        if as_separate:
            for n in nums:
                w = PdfWriter()
                w.add_page(r.pages[n - 1])
                op = _out_path(file_path, f"p{n}")
                with open(op, "wb") as fh:
                    w.write(fh)
                outs.append(op.name)
        else:
            w = PdfWriter()
            for n in nums:
                w.add_page(r.pages[n - 1])
            op = _out_path(file_path, f"pages{'_'.join(map(str, nums[:4]))}{'…' if len(nums)>4 else ''}")
            with open(op, "wb") as fh:
                w.write(fh)
            outs.append(op.name)

        from Tools.autonomy import journal
        journal("cleanup", f"PDF extracted pages {nums[:6]} from {Path(file_path).name}",
                target=str(file_path))
        return (f"✂️ Extracted {len(nums)} page(s): {nums[:8]}{'…' if len(nums)>8 else ''}\n"
                f"📁 Saved: {[str(o) for o in outs][:3]}")
    except Exception as e:
        return f"❌ Extract failed: {e}"


@function_tool()
async def pdf_delete_pages(file_path: str, pages_spec: str) -> str:
    """Delete pages from a PDF (original preserved; new file written).

    Args:
        file_path: Source PDF
        pages_spec: Pages to REMOVE, e.g. "1" or "2,10-12"
    """
    try:
        r = _reader(file_path)
        total = len(r.pages)
        kill = set(_parse_pages(pages_spec, total))
        if not kill:
            return f"❌ No valid pages in '{pages_spec}'."
        if len(kill) >= total:
            return "❌ That would delete every page."

        w = PdfWriter()
        kept = []
        for i in range(1, total + 1):
            if i not in kill:
                w.add_page(r.pages[i - 1]); kept.append(i)
        op = _out_path(file_path, "trimmed")
        with open(op, "wb") as fh:
            w.write(fh)
        journal_ok = None
        try:
            from Tools.autonomy import journal
            journal_ok = journal("cleanup", f"PDF removed pages {sorted(kill)} from {Path(file_path).name}",
                                 target=str(file_path))
        except Exception:
            pass
        return (f"🗑️ Removed page(s) {sorted(kill)} | kept {len(kept)}.\n📁 Saved: {op}")
    except Exception as e:
        return f"❌ Delete failed: {e}"


@function_tool()
async def pdf_reorder_pages(file_path: str, new_order_spec: str) -> str:
    """Rewrite a PDF in YOUR custom page order.

    Args:
        file_path: Source PDF
        new_order_spec: Full desired order, e.g. "3,1,2" or "2,1,4,3"
    """
    try:
        r = _reader(file_path)
        total = len(r.pages)
        raw = [int(p) for p in re.sub(r"\s", "", new_order_spec).split(",") if p]
        bad = [p for p in raw if not (1 <= p <= total)]
        if bad:
            return f"❌ Pages out of range: {bad} (PDF has {total})."
        if len(set(raw)) != len(raw):
            dupes = sorted({p for p in raw if raw.count(p) > 1})
            return f"❌ Order repeats page(s): {dupes} — each page exactly once."
        if not raw:
            return "❌ No pages given."
        from Tools.pdf_studio import PdfWriter as _PW  # shim import
        w = PdfWriter()
        for n in raw:
            w.add_page(r.pages[n - 1])
        op = _out_path(file_path, "reordered")
        with open(op, "wb") as fh:
            w.write(fh)
        return f"🔀 Reordered {len(raw)} pages → {op}"
    except Exception as e:
        return f"❌ Reorder failed: {e}"


@function_tool()
async def pdf_merge(files_spec: str) -> str:
    """Merge multiple PDFs into one, in the given order.

    Args:
        files_spec: Comma-separated paths in join order
    """
    try:
        paths = [s.strip() for s in files_spec.split(",") if s.strip()]
        readers = [_reader(p) for p in paths]

        w = PdfWriter()
        total = 0
        for r in readers:
            for pg in r.pages:
                w.add_page(pg); total += 1
        first = Path(paths[0]).parent / "zenith_pdf_studio"
        first.mkdir(exist_ok=True)
        op = first / f"merged_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        with open(op, "wb") as fh:
            w.write(fh)
        return f"🔗 Merged {len(paths)} files ({total} pages) → {op}"
    except Exception as e:
        return f"❌ Merge failed: {e}"


@function_tool()
async def pdf_watermark(file_path: str, text: str = "CONFIDENTIAL",
                        opacity_note: str = "light diagonal", batch_folder: str = "") -> str:
    """Stamp a text watermark diagonally across every page of one PDF — or every
    PDF inside a folder (batch).

    Args:
        file_path: Single PDF to stamp
        text: Watermark text (default CONFIDENTIAL)
        opacity_note: cosmetic label ('light diagonal' typical)
        batch_folder: If set, stamps ALL *.pdf inside this folder instead
    """
    try:
        targets = []
        if batch_folder and os.path.isdir(batch_folder):
            targets = [str(p) for p in Path(batch_folder).glob("*.pdf")]
        elif file_path:
            targets = [file_path]
        if not targets:
            return "❌ Nothing to stamp (file missing / empty folder)."

        done = []
        for t in targets[:20]:
            try:
                r = _reader(t)

                # build overlay once per unique page size

                try:
                    from reportlab.pdfgen import canvas as rl_canvas
                    import io

                    def make_overlay(w, h):
                        buf = io.BytesIO()
                        c = rl_canvas.Canvas(buf, pagesize=(w, h))
                        c.setFont("Helvetica-Bold", max(28, w // 22))
                        c.setFillColorRGB(0.6, 0.6, 0.6, alpha=0.28)
                        c.saveState()
                        c.translate(w / 2, h / 2)
                        c.rotate(35)
                        c.drawCentredString(0, 0, text)
                        c.restoreState()
                        c.save(); buf.seek(0)
                        return buf

                    wtr_pages = {}
                    for pg in r.pages:
                        key = (float(pg.mediabox.width), float(pg.mediabox.height))
                        if key not in wtr_pages:
                            buf = make_overlay(*key)

                            wtr_pages[key] = _R(buf).pages[0]

                    w = PdfWriter()
                    for pg in r.pages:
                        key = (float(pg.mediabox.width), float(pg.mediabox.height))
                        pg.merge_page(wtr_pages[key])
                        w.add_page(pg)
                    op = _out_path(t, "watermarked")
                    with open(op, "wb") as fh:
                        w.write(fh)
                    done.append(f"{Path(t).name} ✅")
                except ImportError:
                    # reportlab absent → fallback: footer-style stamp without rotation
                    return ("❌ 'reportlab' is needed for pretty watermarks. "
                            "Run: pip install reportlab")
            except Exception as e:
                done.append(f"{Path(t).name} ⚠️ {str(e)[:50]}")

        from Tools.autonomy import journal
        journal("cleanup", f"Watermarked {len(done)} PDF(s) with '{text}'")
        return ("💧 WATERMARK COMPLETE\n" + "\n".join(f"   • {d}" for d in done[:10])
                + f"\nText: “{text}” ({opacity_note})")
    except Exception as e:
        return f"❌ Watermark failed: {e}"
