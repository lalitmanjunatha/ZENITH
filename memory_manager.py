"""Persistent memory for Zenith.

Stores every conversation exchange in SQLite and maintains a semantic
vector index (data/memory_index.faiss) so past conversations and stored
facts can be recalled by meaning. Designed to never raise on failure so
the voice agent keeps working even if the embedding model is unavailable.
"""

import json
import logging
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def _now() -> str:
    return datetime.now().isoformat()


class MemoryManager:
    def __init__(
        self,
        db_path: str = "data/zenith_memory.db",
        index_path: str = "data/memory_index.faiss",
        dimension: int = 384,
    ):
        self.db_path = db_path
        self.index_path = index_path
        self.dimension = dimension
        self._conn: Optional[sqlite3.Connection] = None
        self._embedder = None
        self._vector_store = None
        self._session_started = False
        self._conv_id: Optional[int] = None
        self._pending_vectors = 0
        self._save_threshold = 25
        self.paused = False

        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._connect()
        self._init_schema()
        self._sih_init_schema()
        self._init_embedding()

    # ------------------------------------------------------------------
    # DB plumbing
    # ------------------------------------------------------------------
    def _connect(self) -> None:
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row

    def _init_schema(self) -> None:
        cur = self._conn.cursor()
        cur.executescript(
            """
            CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT,
                started_at TEXT
            );
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                conv_id INTEGER,
                role TEXT,
                text TEXT,
                created_at TEXT
            );
            CREATE TABLE IF NOT EXISTS facts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                content TEXT,
                category TEXT,
                source TEXT,
                created_at TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_messages_conv ON messages(conv_id);
            CREATE TABLE IF NOT EXISTS meta (
                key TEXT PRIMARY KEY,
                value TEXT
            );
            """
        )
        self._conn.commit()
        self.paused = self._read_meta_bool("paused", False)

    def _init_embedding(self) -> None:
        try:
            from embedder import Embedder
            from vector_store import VectorStore

            self._embedder = Embedder()
            self.dimension = self._embedder.get_dimension()
            self._vector_store = VectorStore(
                index_path=self.index_path, dimension=self.dimension
            )
            self._vector_store.load()
            self._vector_store.initialize()
        except Exception as e:
            logger.warning(f"Memory embedding unavailable: {e}")
            self._embedder = None
            self._vector_store = None

    def _add_vector(self, text: str, meta: Dict[str, Any]) -> None:
        if not self._embedder or not self._vector_store or not text:
            return
        try:
            emb = self._embedder.embed_single(text)
            if emb is None:
                return
            import numpy as np

            self._vector_store.add(np.array([emb], dtype=np.float32), [meta], normalize=True)
            self._pending_vectors += 1
            if self._pending_vectors >= self._save_threshold:
                self.flush_vectors()
        except Exception as e:
            logger.warning(f"add_vector failed: {e}")

    def flush_vectors(self) -> None:
        try:
            if self._vector_store:
                self._vector_store.save()
            self._pending_vectors = 0
        except Exception as e:
            logger.warning(f"flush_vectors failed: {e}")

    # ------------------------------------------------------------------
    # Recording
    # ------------------------------------------------------------------
    def ensure_session(self) -> None:
        if self._session_started:
            return
        cur = self._conn.cursor()
        cur.execute(
            "INSERT INTO conversations (session_id, started_at) VALUES (?, ?)",
            (str(uuid.uuid4()), _now()),
        )
        self._conn.commit()
        self._conv_id = cur.lastrowid
        self._session_started = True

    def record_message(self, role: str, text: str, ephemeral: bool = False) -> None:
        if not text or not str(text).strip():
            return
        if not ephemeral and (self.paused or self._read_meta_bool("paused", False)):
            return
        try:
            self.ensure_session()
            cur = self._conn.cursor()
            cur.execute(
                "INSERT INTO messages (conv_id, role, text, created_at) VALUES (?, ?, ?, ?)",
                (self._conv_id, role, str(text), _now()),
            )
            msg_id = cur.lastrowid
            self._conn.commit()
            if ephemeral:
                # Keep a textual trace but keep it out of the semantic index.
                return
            self._add_vector(
                str(text),
                {
                    "type": "message",
                    "role": role,
                    "content": str(text),
                    "message_id": msg_id,
                    "conv_id": self._conv_id,
                    "created_at": _now(),
                },
            )
        except Exception as e:
            logger.warning(f"record_message failed: {e}")

    def set_paused(self, paused: bool) -> None:
        self.paused = paused
        try:
            cur = self._conn.cursor()
            cur.execute(
                "INSERT INTO meta (key, value) VALUES ('paused', ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                ("1" if paused else "0",),
            )
            self._conn.commit()
        except Exception as e:
            logger.warning(f"persist paused failed: {e}")

    def is_paused(self) -> bool:
        return self.paused

    def _read_meta(self, key: str) -> Optional[str]:
        try:
            cur = self._conn.cursor()
            cur.execute("SELECT value FROM meta WHERE key = ?", (key,))
            row = cur.fetchone()
            return row["value"] if row else None
        except Exception:
            return None

    def _read_meta_bool(self, key: str, default: bool) -> bool:
        v = self._read_meta(key)
        if v is None:
            return default
        return v.lower() in ("1", "true", "yes", "on")

    def forget_last(self) -> Dict[str, Any]:
        """Remove the most recent stored message (used for 'don't remember that')."""
        try:
            cur = self._conn.cursor()
            cur.execute(
                "SELECT id FROM messages ORDER BY id DESC LIMIT 1"
            )
            row = cur.fetchone()
            if row:
                cur.execute("DELETE FROM messages WHERE id = ?", (row["id"],))
                self._conn.commit()
                return {"forgot": True, "message_id": row["id"]}
            return {"forgot": False}
        except Exception as e:
            logger.warning(f"forget_last failed: {e}")
            return {"forgot": False, "error": str(e)}

    def record_fact(self, content: str, category: str = "general", source: str = "user") -> None:
        if not content or not str(content).strip():
            return
        try:
            cur = self._conn.cursor()
            cur.execute(
                "SELECT id FROM facts WHERE content = ? AND category = ?",
                (str(content).strip(), category),
            )
            row = cur.fetchone()
            if row:
                cur.execute(
                    "UPDATE facts SET source = ?, created_at = ? WHERE id = ?",
                    (source, _now(), row["id"]),
                )
            else:
                cur.execute(
                    "INSERT INTO facts (content, category, source, created_at) VALUES (?, ?, ?, ?)",
                    (str(content).strip(), category, source, _now()),
                )
            self._conn.commit()
            self._add_vector(
                str(content).strip(),
                {
                    "type": "fact",
                    "category": category,
                    "content": str(content).strip(),
                    "source": source,
                    "created_at": _now(),
                },
            )
        except Exception as e:
            logger.warning(f"record_fact failed: {e}")

    # ------------------------------------------------------------------
    # Recall
    # ------------------------------------------------------------------
    def recall(self, query: str, top_k: int = 5) -> Dict[str, Any]:
        return {
            "query": query,
            "messages": self._recall_messages(query, top_k),
            "facts": self._recall_facts(top_k),
        }

    def _recall_messages(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        if self._embedder and self._vector_store:
            try:
                emb = self._embedder.embed_single(query)
                if emb is not None:
                    import numpy as np

                    hits = self._vector_store.search(
                        np.array([emb], dtype=np.float32), top_k=top_k
                    )
                    found = [
                        {
                            "content": h.get("content", ""),
                            "role": h.get("role", "user"),
                            "score": round(h.get("similarity_score", 0), 4),
                        }
                        for h in hits
                        if h.get("type") == "message" and h.get("content")
                    ]
                    if found:
                        return found
            except Exception as e:
                logger.warning(f"vector recall failed: {e}")
        return self._recent_messages(top_k)

    def _recall_facts(self, top_k: int) -> List[Dict[str, Any]]:
        try:
            cur = self._conn.cursor()
            cur.execute(
                "SELECT content, category, source, created_at "
                "FROM facts ORDER BY id DESC LIMIT ?",
                (top_k,),
            )
            return [dict(r) for r in cur.fetchall()]
        except Exception as e:
            logger.warning(f"fact recall failed: {e}")
            return []

    def _recent_messages(self, limit: int) -> List[Dict[str, Any]]:
        try:
            cur = self._conn.cursor()
            cur.execute(
                "SELECT text, role FROM messages ORDER BY id DESC LIMIT ?", (limit,)
            )
            return [
                {"content": r["text"], "role": r["role"], "score": 0.0}
                for r in cur.fetchall()
            ]
        except Exception:
            return []

    def recent_context(self, n: int = 8) -> str:
        try:
            cur = self._conn.cursor()
            cur.execute(
                "SELECT role, text FROM messages ORDER BY id DESC LIMIT ?", (n,)
            )
            rows = cur.fetchall()
            return "\n".join(
                f"{'You' if r['role'] == 'assistant' else 'User'}: {r['text']}"
                for r in reversed(rows)
            )
        except Exception:
            return ""

    def recent_text(self, n: int = 24) -> str:
        return self.recent_context(n)

    def all_facts(self) -> List[Dict[str, Any]]:
        try:
            cur = self._conn.cursor()
            cur.execute(
                "SELECT content, category, source, created_at FROM facts ORDER BY id DESC"
            )
            return [dict(r) for r in cur.fetchall()]
        except Exception:
            return []

    # ------------------------------------------------------------------
    # Training / consolidation
    # ------------------------------------------------------------------
    def train_from_conversations(self) -> Dict[str, Any]:
        embedded = 0
        for f in self.all_facts():
            self._add_vector(
                f["content"],
                {
                    "type": "fact",
                    "category": f.get("category", "general"),
                    "content": f["content"],
                    "source": f.get("source", "user"),
                },
            )
            embedded += 1
        self.flush_vectors()
        return {
            "facts_embedded": embedded,
            "facts": len(self.all_facts()),
            "messages": self.count_messages(),
            "vectors": self.vector_count(),
            "status": "trained",
        }

    def consolidate(self, llm) -> Dict[str, Any]:
        recent = self.recent_context(24)
        if not recent or llm is None:
            return self.train_from_conversations()
        try:
            prompt = (
                "From the conversation below, extract concise durable facts the "
                'assistant should remember about the user. Return ONLY a JSON list '
                'of objects: [{"content":"...","category":"..."}]. No prose.\n\n'
                f"Conversation:\n{recent}"
            )
            reply = llm.generate(prompt)
            facts = self._parse_facts(reply)
            for f in facts:
                self.record_fact(
                    f.get("content", ""),
                    f.get("category", "general"),
                    source="consolidation",
                )
            return {"distilled_facts": len(facts), "facts": facts}
        except Exception as e:
            logger.warning(f"consolidate failed: {e}")
            return {"error": str(e), "distilled_facts": 0}

    def _parse_facts(self, reply: str) -> List[Dict[str, str]]:
        reply = reply.strip()
        if reply.startswith("```"):
            lines = reply.split("\n")
            reply = "\n".join(lines[1:-1]) if len(lines) > 2 else reply.replace("```", "")
        try:
            data = json.loads(reply)
            if isinstance(data, list):
                return [d for d in data if isinstance(d, dict)]
        except Exception:
            pass
        return [
            {"content": line.strip(), "category": "general"}
            for line in reply.splitlines()
            if line.strip()
        ]

    # ------------------------------------------------------------------
    # Stats / misc
    # ------------------------------------------------------------------
    def count_messages(self) -> int:
        try:
            cur = self._conn.cursor()
            cur.execute("SELECT COUNT(*) AS c FROM messages")
            return cur.fetchone()["c"]
        except Exception:
            return 0

    def vector_count(self) -> int:
        try:
            if self._vector_store and self._vector_store.index:
                return self._vector_store.index.ntotal
            return 0
        except Exception:
            return 0

    def stats(self) -> Dict[str, Any]:
        try:
            cur = self._conn.cursor()
            cur.execute("SELECT COUNT(*) AS c FROM messages")
            messages = cur.fetchone()["c"]
            cur.execute("SELECT COUNT(*) AS c FROM conversations")
            conversations = cur.fetchone()["c"]
            cur.execute("SELECT COUNT(*) AS c FROM facts")
            facts = cur.fetchone()["c"]
            return {
                "messages": messages,
                "conversations": conversations,
                "facts": facts,
                "vectors": self.vector_count(),
                "db_path": self.db_path,
            }
        except Exception as e:
            return {"error": str(e)}

    def _sih_init_schema(self) -> None:
        """Initialize SIH project tables if they don't exist."""
        cur = self._conn.cursor()
        cur.executescript(
            """
            CREATE TABLE IF NOT EXISTS sih_projects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_name TEXT UNIQUE,
                problem_statement TEXT,
                description TEXT,
                category TEXT,
                created_at TEXT,
                updated_at TEXT
            );
            CREATE TABLE IF NOT EXISTS sih_team_members (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER,
                name TEXT,
                role TEXT,
                FOREIGN KEY (project_id) REFERENCES sih_projects(id)
            );
            CREATE TABLE IF NOT EXISTS sih_ideas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER,
                title TEXT,
                description TEXT,
                status TEXT,
                feasibility TEXT,
                created_at TEXT,
                FOREIGN KEY (project_id) REFERENCES sih_projects(id)
            );
            CREATE TABLE IF NOT EXISTS sih_research (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER,
                title TEXT,
                source_type TEXT,
                source_url TEXT,
                description TEXT,
                relevance TEXT,
                created_at TEXT,
                FOREIGN KEY (project_id) REFERENCES sih_projects(id)
            );
            CREATE TABLE IF NOT EXISTS sih_architecture (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER,
                name TEXT,
                description TEXT,
                components TEXT,
                created_at TEXT,
                FOREIGN KEY (project_id) REFERENCES sih_projects(id)
            );
            CREATE TABLE IF NOT EXISTS sih_features (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER,
                title TEXT,
                priority TEXT,
                status TEXT,
                estimated_effort TEXT,
                dependencies TEXT,
                created_at TEXT,
                FOREIGN KEY (project_id) REFERENCES sih_projects(id)
            );
            CREATE TABLE IF NOT EXISTS sih_risks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER,
                category TEXT,
                probability TEXT,
                severity TEXT,
                description TEXT,
                mitigation TEXT,
                owner TEXT,
                status TEXT,
                created_at TEXT,
                FOREIGN KEY (project_id) REFERENCES sih_projects(id)
            );
            CREATE TABLE IF NOT EXISTS sih_evidence (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER,
                title TEXT,
                type TEXT,
                path TEXT,
                description TEXT,
                created_at TEXT,
                FOREIGN KEY (project_id) REFERENCES sih_projects(id)
            );
            CREATE TABLE IF NOT EXISTS sih_decisions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER,
                decision TEXT,
                alternatives TEXT,
                reason TEXT,
                evidence TEXT,
                date TEXT,
                FOREIGN KEY (project_id) REFERENCES sih_projects(id)
            );
            """
        )
        self._conn.commit()
        self._sih_migrate_columns()

    def _sih_migrate_columns(self) -> None:
        """Add created_at to legacy SIH tables that lack it."""
        cur = self._conn.cursor()
        for table in ("sih_research", "sih_features", "sih_risks", "sih_evidence", "sih_architecture"):
            cur.execute(f"PRAGMA table_info({table})")
            cols = {row[1] for row in cur.fetchall()}
            if cols and "created_at" not in cols:
                try:
                    cur.execute(f"ALTER TABLE {table} ADD COLUMN created_at TEXT")
                    self._conn.commit()
                    logger.info(f"Migrated {table}: added created_at column")
                except Exception as e:
                    logger.warning(f"SIH migration failed for {table}: {e}")

    def close(self) -> None:
        """Flush pending vectors and close the database connection."""
        try:
            self.flush_vectors()
        except Exception:
            pass
        try:
            if self._conn:
                self._conn.close()
        except Exception:
            pass

    def clear(self) -> Dict[str, Any]:
        try:
            cur = self._conn.cursor()
            cur.execute("DELETE FROM messages")
            cur.execute("DELETE FROM conversations")
            cur.execute("DELETE FROM facts")
            cur.execute("DELETE FROM sih_projects")
            cur.execute("DELETE FROM sih_team_members")
            cur.execute("DELETE FROM sih_ideas")
            cur.execute("DELETE FROM sih_research")
            cur.execute("DELETE FROM sih_architecture")
            cur.execute("DELETE FROM sih_features")
            cur.execute("DELETE FROM sih_risks")
            cur.execute("DELETE FROM sih_evidence")
            cur.execute("DELETE FROM sih_decisions")
            self._conn.commit()
            if self._vector_store:
                self._vector_store.reset()
                self.flush_vectors()
            return {"status": "cleared"}
        except Exception:
            return {"status": "failed"}