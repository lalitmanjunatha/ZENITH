"""Dream Mode — Zenith improves itself while you are away.

When the laptop is idle (no mouse/keyboard for N minutes), a background cycle:
  1. 🧠 consolidates recent conversations into durable facts (LLM-distilled)
  2. 📁 advances the knowledge index by one bounded pass (20 files)
  3. 📊 records vector-store stats
Everything is logged to data/zenith_memory.db → dream_log, surfaced as a
MORNING DIGEST ("While you were away…") and queryable on demand.

Safety: cycles are throttled (min gap), fully logged, and can be disabled
with ZENITH_DREAM_MODE=off in .env.
"""

import asyncio
import ctypes
import json
import logging
import os
import sqlite3
import time
from datetime import datetime
from pathlib import Path

from livekit.agents import function_tool

logger = logging.getLogger(__name__)

DB_PATH = "data/zenith_memory.db"
_COOLDOWN_S = 30 * 60          # at most one dream per 30 min


def _db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute(
        """CREATE TABLE IF NOT EXISTS dream_log (
               id INTEGER PRIMARY KEY AUTOINCREMENT,
               started_at TEXT,
               finished_at TEXT,
               facts_distilled INTEGER,
               files_indexed INTEGER,
               vectors_total INTEGER,
               summary TEXT
           )"""
    )
    return conn


def enabled() -> bool:
    return os.getenv("ZENITH_DREAM_MODE", "on").lower() in ("on", "1", "true", "yes")


def idle_threshold_s() -> int:
    try:
        return max(5, int(os.getenv("ZENITH_DREAM_IDLE_MIN", "15"))) * 60
    except ValueError:
        return 900


def system_idle_seconds() -> float:
    """Seconds since last user input (Windows)."""
    class LASTINPUTINFO(ctypes.Structure):
        _fields_ = [("cbSize", ctypes.c_uint), ("dwTime", ctypes.c_uint)]

    try:
        lii = LASTINPUTINFO()
        lii.cbSize = ctypes.sizeof(LASTINPUTINFO)
        if ctypes.windll.user32.GetLastInputInfo(ctypes.byref(lii)):
            millis = ctypes.windll.kernel32.GetTickCount() - lii.dwTime
            return max(millis / 1000.0, 0.0)
    except Exception:
        pass
    # Non-Windows fallback: file-system proxy
    try:
        home = Path.home()
        newest = max(
            (p.stat().st_mtime for p in (home / "AppData" / "Local" / "Temp").glob("*") ),
            default=time.time(),
        )
        return max(time.time() - newest, 0.0)
    except Exception:
        return 0.0


# ---------------------------------------------------------------- cycle ----

def run_dream_cycle(agent=None) -> dict:
    """One self-improvement pass. Blocking — call from a background thread."""
    started = datetime.now().isoformat()
    result = {
        "started_at": started, "facts_distilled": 0, "files_indexed": 0,
        "vectors_total": None, "summary": "", "errors": [],
    }

    # --- Step 1: memory consolidation -------------------------------
    memory = getattr(agent, "memory", None)
    if memory is not None:
        try:
            llm = None
            try:
                from Tools._llm_client import chat_complete_sync

                class ProviderAdapter:
                    def generate(self, prompt: str) -> str:
                        reply = chat_complete_sync(prompt, max_tokens=2500)
                        return reply if not reply.startswith("ERROR:") else "[]"

                llm = ProviderAdapter()
            except Exception as e:
                result["errors"].append(f"llm-adapter:{e}")

            cons = memory.consolidate(llm)
            result["facts_distilled"] = int(cons.get("distilled_facts", 0) or 0)
        except Exception as e:
            result["errors"].append(f"consolidate:{e}")

    # --- Step 2: bounded knowledge-index advance ---------------------
    brain = getattr(agent, "brain", None)
    rag = getattr(brain, "rag_pipeline", None) if brain else None
    if rag is not None:
        try:
            from whole_disk_indexer import WholeDiskIndexer

            indexer = WholeDiskIndexer(
                vector_store=rag.vector_store,
                embedder=rag.embedder,
                content_extractor=rag.content_extractor,
                chunker=rag.chunker,
            )
            idx = indexer.index_content(limit=20)
            result["files_indexed"] = int(idx.get("indexed", 0))
        except Exception as e:
            result["errors"].append(f"index:{e}")

        try:
            vs = rag.vector_store
            if vs is not None and vs.index is not None:
                result["vectors_total"] = int(vs.index.ntotal)
        except Exception:
            pass

    # --- Step 3: persist + human summary ------------------------------
    parts = []
    if result["facts_distilled"]:
        parts.append(f"{result['facts_distilled']} new long-term facts distilled")
    if result["files_indexed"]:
        parts.append(f"{result['files_indexed']} new files indexed")
    if result["vectors_total"] is not None:
        parts.append(f"knowledge base now {result['vectors_total']} vectors")
    result["summary"] = "; ".join(parts) + (" ⚠️ " + "; ".join(result["errors"]) if result["errors"] else "")

    try:
        conn = _db()
        conn.execute(
            "INSERT INTO dream_log (started_at, finished_at, facts_distilled, files_indexed, vectors_total, summary) VALUES (?,?,?,?,?,?)",
            (result["started_at"], datetime.now().isoformat(), result["facts_distilled"],
             result["files_indexed"], result["vectors_total"], result["summary"]),
        )
        conn.commit()
        conn.close()
    except Exception as e:
        logger.warning(f"dream log failed: {e}")

    print(f"🌙 Dream cycle complete: {result['summary']}")
    return result


_last_dream_ts = 0.0
_dream_lock = asyncio.Lock()


async def maybe_dream(agent) -> None:
    """Called periodically; triggers a cycle only when truly idle + cooled down."""
    global _last_dream_ts
    if not enabled():
        return
    if time.time() - _last_dream_ts < _COOLDOWN_S:
        return
    idle = await asyncio.to_thread(system_idle_seconds)
    if idle < idle_threshold_s():
        return
    async with _dream_lock:
        if time.time() - _last_dream_ts < _COOLDOWN_S:
            return
        print(f"🌙 Idle {int(idle)}s ≥ threshold — entering Dream Mode…")
        try:
            await asyncio.to_thread(run_dream_cycle, agent)
        finally:
            _last_dream_ts = time.time()


# ------------------------------------------------------------- tools -------

@function_tool()
async def dream_now() -> str:
    """Force an immediate DREAM MODE self-improvement cycle right now:
    distill conversation memory into permanent facts and index 20 more files."""
    global _last_dream_ts
    async with _dream_lock:
        r = await asyncio.to_thread(run_dream_cycle, None)
        _last_dream_ts = time.time()
    icon = "✅" if not r["errors"] else "⚠️"
    return (
        f"🌙 {icon} Dream cycle finished.\n"
        f"🧠 Facts distilled: {r['facts_distilled']}\n"
        f"📁 Files indexed: {r['files_indexed']}\n"
        f"📊 Knowledge vectors: {r['vectors_total'] if r['vectors_total'] is not None else 'n/a'}\n"
        + (f"⚠️ Issues: {'; '.join(r['errors'])}" if r["errors"] else "")
    )


@function_tool()
async def dream_status() -> str:
    """Show Dream Mode settings, idle time, and how many dream cycles have run."""
    try:
        idle = system_idle_seconds()
        thr = idle_threshold_s()
        conn = _db()
        n = conn.execute("SELECT COUNT(*) c FROM dream_log").fetchone()["c"]
        conn.close()
        state = "🟢 will trigger when idle" if enabled() else "🔴 disabled (ZENITH_DREAM_MODE=off)"
        ready = "YES ✨ (threshold met)" if idle >= thr else f"not yet ({int(idle)}/{thr}s idle)"
        return (
            f"🌙 DREAM MODE STATUS\n════════════════════\n"
            f"State: {state}\n"
            f"Idle now: {int(idle)}s | Trigger needs {thr}s idle → {ready}\n"
            f"Cycles completed so far: {n}\n"
            f"Tune via .env: ZENITH_DREAM_IDLE_MIN (minutes)"
        )
    except Exception as e:
        return f"❌ Status failed: {e}"


@function_tool()
async def last_dream_summary() -> str:
    """Read the MORNING DIGEST: what Zenith learned during its most recent
    Dream Mode cycle (facts distilled, files indexed)."""
    try:
        conn = _db()
        rows = conn.execute("SELECT * FROM dream_log ORDER BY id DESC LIMIT 1").fetchall()
        total_facts = conn.execute(
            "SELECT COALESCE(SUM(facts_distilled),0) s FROM dream_log").fetchone()["s"]
        total_files = conn.execute(
            "SELECT COALESCE(SUM(files_indexed),0) s FROM dream_log").fetchone()["s"]
        conn.close()
        if not rows or not rows[0]["summary"]:
            return (
                "🌙 No dream cycles recorded yet. I dream automatically when you're "
                "away 15+ minutes, or say 'dream now' to run one immediately."
            )
        r = dict(rows[0])
        return (
            f"🌅 MORNING DIGEST — while you were away\n════════════════════\n"
            f"🕒 {str(r['started_at'])[:16]} → {str(r['finished_at'])[:11] + str(r['finished_at'])[11:16]}\n"
            f"• {r['summary']}\n\n"
            f"Lifetime dreaming: {total_facts} facts distilled across {n_or(r)} cycles, "
            f"{total_files} files indexed."
        )
    except Exception as e:
        return f"❌ Digest failed: {e}"


def n_or(r) -> int:
    try:
        conn = _db()
        n = conn.execute("SELECT COUNT(*) c FROM dream_log").fetchone()["c"]
        conn.close()
        return n
    except Exception:
        return 0


def latest_dream_brief_line() -> str:
    """One-line digest for integration into the morning brief."""
    try:
        conn = _db()
        row = conn.execute(
            "SELECT summary FROM dream_log WHERE summary != '' ORDER BY id DESC LIMIT 1"
        ).fetchone()
        conn.close()
        if row and row["summary"]:
            return f"While you were away, I dreamed: {row['summary']}"
    except Exception:
        pass
    return ""
