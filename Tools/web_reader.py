"""Zenith Web Reader — URL → clean ad-free article → PDF into your RAG.

F27: fetches the page, strips nav/ads/scripts, keeps the main text, renders a
tidy PDF (fpdf2), and drops it in data/web_articles/ where whole-disk indexing
picks it up for future 'ask my notes' queries.
"""

import logging
import re
from datetime import datetime
from pathlib import Path

from livekit.agents import function_tool

logger = logging.getLogger(__name__)

OUT_DIR = Path("data/web_articles")


def _fetch_html(url: str, timeout: int = 25) -> tuple[str, str]:
    import requests

    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                             "AppleWebKit/537.36 Chrome/124 Safari/537.36"}
    r = requests.get(url, headers=headers, timeout=timeout)
    r.raise_for_status()
    ctype = r.headers.get("Content-Type", "")
    return r.text, ctype


def _clean_html(html: str) -> tuple[str, str]:
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    title = (soup.title.get_text(strip=True) if soup.title else "")[:120]

    for tag in soup(["script", "style", "nav", "header", "footer", "aside",
                     "form", "noscript", "iframe", "svg", "button"]):
        tag.decompose()

    # pick the densest <article> or <main>, else body
    node = soup.find("article") or soup.find("main") or soup.body or soup
    text = node.get_text("\n")
    # tidy lines
    lines = []
    for ln in text.splitlines():
        s = re.sub(r"\s+", " ", ln).strip()
        if len(s) > 2:
            lines.append(s)
    # collapse duplicates & ads-y lines
    cleaned, seen = [], set()
    ad_words = ("subscribe", "sign in", "cookie", "newsletter", "advertisement",
                "related stories", "share this", "read more", "comments")
    for ln in lines:
        k = ln.lower()
        if any(a in k for a in ad_words):
            continue
        key = ln[:40]
        if key in seen:
            continue
        seen.add(key)
        cleaned.append(ln)
    return title, "\n\n".join(cleaned)


def _to_pdf(title: str, body: str, url: str) -> Path:
    from fpdf import FPDF

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    safe = re.sub(r"[^\w -]", "", title)[:50] or "article"
    path = OUT_DIR / f"{datetime.now():%Y%m%d_%H%M%S}_{safe}.pdf"

    pdf = FPDF(format="A4")
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.add_page()

    def _safe(s):  # latin-1 safe for core fonts
        return s.encode("latin-1", "replace").decode("latin-1")

    pdf.set_font("Helvetica", "B", 16)
    pdf.multi_cell(0, 9, _safe(title))
    pdf.set_font("Helvetica", "I", 9)
    pdf.set_text_color(110)
    pdf.multi_cell(0, 6, _safe(f"Source: {url} · saved {datetime.now():%d %b %Y %H:%M} by Zenith"))
    pdf.set_text_color(20)
    pdf.ln(4)

    pdf.set_font("Helvetica", "", 11)
    for para in body.split("\n\n"):
        para = para.strip()
        if not para:
            continue
        if para.isupper() and len(para) < 80:      # section headings
            pdf.set_font("Helvetica", "B", 12)
            pdf.multi_cell(0, 8, _safe(para))
            pdf.set_font("Helvetica", "", 11)
        else:
            pdf.multi_cell(0, 6.5, _safe(para))
        pdf.ln(2)

    pdf.output(str(path))
    return path


@function_tool()
async def save_article_as_pdf(url: str, index_into_knowledge: bool = True) -> str:
    """READER-PDF MAKER: download a web article, strip ads/navigation, and save
    it as a clean PDF. Optionally feeds it into Zenith's knowledge base so you
    can ask questions about it later.

    Args:
        url: Article URL
        index_into_knowledge: Add to RAG so 'ask my notes' finds it (default true)
    """
    try:
        html, ctype = await __import__("asyncio").to_thread(_fetch_html, url)
        if "text/html" not in ctype.lower():
            return f"❌ URL isn't an HTML article ({ctype.split(';')[0]})."
        title, body = await __import__("asyncio").to_thread(_clean_html, html)
        words = len(body.split())
        if words < 80:
            return ("❌ Page too empty after cleaning — likely JS-rendered. "
                    "Try a reader-mode friendly source.")
        path = await __import__("asyncio").to_thread(_to_pdf, title or url, body, url)

        indexed = False
        if index_into_knowledge:
            try:
                from Tools.knowledge_search import index_files
                res = await index_files(directory=str(path.parent))
                indexed = "error" not in str(res).lower()
            except Exception as e:
                logger.debug(f"RAG index failed: {e}")

        from Tools.autonomy import journal
        journal("cleanup", f"Saved article PDF '{title[:60]}' ({words} words)")
        return (f"📄 ARTICLE SAVED → {path}\n"
                f"   📛 {title}\n   ✍️ {words} words, ads stripped\n"
                + ("🧠 Indexed into knowledge base — just ask me about it later."
                   if indexed else "ℹ️ Knowledge indexing skipped/failed."))
    except Exception as e:
        return f"❌ Reader-PDF failed: {e}"