"""SIH Project Manager - Manages SIH projects, ideas, research, and tracking.

Provides project-level isolation with persistent memory storage using SQLite.
Each project's data is completely isolated from other projects.
"""

import json
import logging
import sqlite3
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from livekit.agents import function_tool

logger = logging.getLogger(__name__)


class SIHProjectManager:
    """Manages SIH projects with complete isolation between projects."""
    
    def __init__(self, db_path: str = "data/zenith_memory.db"):
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        try:
            self._conn.execute("PRAGMA foreign_keys = ON")
        except Exception:
            pass
        self._init_tables()
    
    def _init_tables(self) -> None:
        """Initialize all SIH project tables."""
        cur = self._conn.cursor()
        cur.executescript("""
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
        """)
        self._conn.commit()
        self._migrate_columns()
        logger.info("SIH Project tables initialized")

    def _migrate_columns(self) -> None:
        """Add created_at column to legacy SIH tables that lack it."""
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
                    logger.warning(f"Migration failed for {table}: {e}")
    
    # ============ PROJECT MANAGEMENT ============
    
    def create_project(self, project_name: str, problem_statement: str, 
                       description: str = "", category: str = "") -> int:
        """Create a new SIH project. Returns the project ID."""
        cur = self._conn.cursor()
        now = datetime.now().isoformat()
        cur.execute(
            "INSERT INTO sih_projects (project_name, problem_statement, description, category, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
            (project_name, problem_statement, description, category, now, now)
        )
        project_id = cur.lastrowid
        self._conn.commit()
        logger.info(f"Created SIH project '{project_name}' with ID {project_id}")
        return project_id
    
    def list_projects(self) -> List[Dict[str, Any]]:
        """List all SIH projects."""
        cur = self._conn.cursor()
        cur.execute("SELECT id, project_name, created_at, updated_at FROM sih_projects")
        projects = []
        for row in cur.fetchall():
            projects.append({
                'id': row['id'],
                'name': row['project_name'],
                'created_at': row['created_at'],
                'updated_at': row['updated_at']
            })
        return projects
    
    def select_project(self, project_id: int) -> Optional[Dict[str, Any]]:
        """Select and get all data for a specific project."""
        cur = self._conn.cursor()
        cur.execute("SELECT * FROM sih_projects WHERE id = ?", (project_id,))
        row = cur.fetchone()
        if row is None:
            return None
        
        project = dict(row)
        
        # Load related data
        cur.execute("SELECT * FROM sih_team_members WHERE project_id = ?", (project_id,))
        project['team_members'] = [dict(r) for r in cur.fetchall()]
        
        cur.execute("SELECT * FROM sih_ideas WHERE project_id = ?", (project_id,))
        project['ideas'] = [dict(r) for r in cur.fetchall()]
        
        cur.execute("SELECT * FROM sih_research WHERE project_id = ?", (project_id,))
        project['research'] = [dict(r) for r in cur.fetchall()]
        
        cur.execute("SELECT * FROM sih_architecture WHERE project_id = ?", (project_id,))
        project['architecture'] = [dict(r) for r in cur.fetchall()]
        
        cur.execute("SELECT * FROM sih_features WHERE project_id = ?", (project_id,))
        project['features'] = [dict(r) for r in cur.fetchall()]
        
        cur.execute("SELECT * FROM sih_risks WHERE project_id = ?", (project_id,))
        project['risks'] = [dict(r) for r in cur.fetchall()]
        
        cur.execute("SELECT * FROM sih_evidence WHERE project_id = ?", (project_id,))
        project['evidence'] = [dict(r) for r in cur.fetchall()]
        
        cur.execute("SELECT * FROM sih_decisions WHERE project_id = ?", (project_id,))
        project['decisions'] = [dict(r) for r in cur.fetchall()]
        
        return project
    
    # ============ TEAM MEMBERS ============
    
    def add_team_member(self, project_id: int, name: str, role: str) -> int:
        """Add a team member to a project."""
        cur = self._conn.cursor()
        cur.execute(
            "INSERT INTO sih_team_members (project_id, name, role) VALUES (?, ?, ?)",
            (project_id, name, role)
        )
        member_id = cur.lastrowid
        self._conn.commit()
        return member_id
    
    # ============ IDEAS ============
    
    def add_idea(self, project_id: int, title: str, description: str,
                 status: str = "pending", feasibility: str = "unknown") -> int:
        """Add an idea to a project."""
        cur = self._conn.cursor()
        now = datetime.now().isoformat()
        cur.execute(
            "INSERT INTO sih_ideas (project_id, title, description, status, feasibility, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (project_id, title, description, status, feasibility, now)
        )
        idea_id = cur.lastrowid
        self._conn.commit()
        return idea_id
    
    def list_ideas(self, project_id: int) -> List[Dict[str, Any]]:
        """List all ideas for a project."""
        cur = self._conn.cursor()
        cur.execute("SELECT * FROM sih_ideas WHERE project_id = ? ORDER BY created_at DESC", (project_id,))
        return [dict(r) for r in cur.fetchall()]
    
    def update_idea_status(self, idea_id: int, status: str, feasibility: str = None) -> bool:
        """Update an idea's status and feasibility."""
        cur = self._conn.cursor()
        if feasibility:
            cur.execute(
                "UPDATE sih_ideas SET status = ?, feasibility = ? WHERE id = ?",
                (status, feasibility, idea_id)
            )
        else:
            cur.execute(
                "UPDATE sih_ideas SET status = ? WHERE id = ?",
                (status, idea_id)
            )
        self._conn.commit()
        return cur.rowcount > 0
    
    # ============ RESEARCH ============
    
    def add_research(self, project_id: int, title: str, source_type: str,
                     source_url: str, description: str, relevance: str) -> int:
        """Add research finding to a project."""
        cur = self._conn.cursor()
        now = datetime.now().isoformat()
        cur.execute(
            "INSERT INTO sih_research (project_id, title, source_type, source_url, description, relevance, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (project_id, title, source_type, source_url, description, relevance, now)
        )
        research_id = cur.lastrowid
        self._conn.commit()
        return research_id
    
    def list_research(self, project_id: int) -> List[Dict[str, Any]]:
        """List all research for a project."""
        cur = self._conn.cursor()
        cur.execute("SELECT * FROM sih_research WHERE project_id = ? ORDER BY created_at DESC", (project_id,))
        return [dict(r) for r in cur.fetchall()]
    
    # ============ ARCHITECTURE ============
    
    def add_architecture(self, project_id: int, name: str, description: str,
                       components: str = "") -> int:
        """Add architecture description to a project."""
        cur = self._conn.cursor()
        now = datetime.now().isoformat()
        cur.execute(
            "INSERT INTO sih_architecture (project_id, name, description, components, created_at) VALUES (?, ?, ?, ?, ?)",
            (project_id, name, description, components, now)
        )
        arch_id = cur.lastrowid
        self._conn.commit()
        return arch_id
    
    def get_architecture(self, project_id: int) -> Optional[Dict[str, Any]]:
        """Get architecture for a project."""
        cur = self._conn.cursor()
        cur.execute("SELECT * FROM sih_architecture WHERE project_id = ?", (project_id,))
        row = cur.fetchone()
        if row:
            return dict(row)
        return None
    
    # ============ FEATURES ============
    
    def add_feature(self, project_id: int, title: str, priority: str,
                    status: str = "pending", estimated_effort: str = "",
                    dependencies: str = "") -> int:
        """Add a feature to a project."""
        cur = self._conn.cursor()
        now = datetime.now().isoformat()
        cur.execute(
            "INSERT INTO sih_features (project_id, title, priority, status, estimated_effort, dependencies, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (project_id, title, priority, status, estimated_effort, dependencies, now)
        )
        feature_id = cur.lastrowid
        self._conn.commit()
        return feature_id
    
    def list_features(self, project_id: int, priority: str = None) -> List[Dict[str, Any]]:
        """List features for a project, optionally filtered by priority."""
        cur = self._conn.cursor()
        if priority:
            cur.execute("SELECT * FROM sih_features WHERE project_id = ? AND priority = ? ORDER BY created_at DESC", (project_id, priority))
        else:
            cur.execute("SELECT * FROM sih_features WHERE project_id = ? ORDER BY created_at DESC", (project_id,))
        return [dict(r) for r in cur.fetchall()]
    
    # ============ RISKS ============
    
    def add_risk(self, project_id: int, category: str, probability: str,
                 severity: str, description: str, mitigation: str,
                 owner: str = "") -> int:
        """Add a risk to a project."""
        cur = self._conn.cursor()
        now = datetime.now().isoformat()
        cur.execute(
            "INSERT INTO sih_risks (project_id, category, probability, severity, description, mitigation, owner, status, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (project_id, category, probability, severity, description, mitigation, owner, "active", now)
        )
        risk_id = cur.lastrowid
        self._conn.commit()
        return risk_id
    
    def list_risks(self, project_id: int, status: str = None) -> List[Dict[str, Any]]:
        """List risks for a project, optionally filtered by status."""
        cur = self._conn.cursor()
        if status:
            cur.execute("SELECT * FROM sih_risks WHERE project_id = ? AND status = ?", (project_id, status))
        else:
            cur.execute("SELECT * FROM sih_risks WHERE project_id = ?", (project_id,))
        return [dict(r) for r in cur.fetchall()]
    
    def update_risk_status(self, risk_id: int, status: str) -> bool:
        """Update a risk's status."""
        cur = self._conn.cursor()
        cur.execute("UPDATE sih_risks SET status = ? WHERE id = ?", (status, risk_id))
        self._conn.commit()
        return cur.rowcount > 0
    
    # ============ EVIDENCE ============
    
    def add_evidence(self, project_id: int, title: str, e_type: str,
                     path: str, description) -> int:
        """Add evidence to a project."""
        cur = self._conn.cursor()
        now = datetime.now().isoformat()
        if not isinstance(description, str):
            try:
                description = json.dumps(description, indent=2, default=str)
            except Exception:
                description = str(description)
        cur.execute(
            "INSERT INTO sih_evidence (project_id, title, type, path, description, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (project_id, title, e_type, path, description, now)
        )
        evidence_id = cur.lastrowid
        self._conn.commit()
        return evidence_id
    
    def list_evidence(self, project_id: int) -> List[Dict[str, Any]]:
        """List evidence for a project."""
        cur = self._conn.cursor()
        cur.execute("SELECT * FROM sih_evidence WHERE project_id = ? ORDER BY created_at DESC", (project_id,))
        return [dict(r) for r in cur.fetchall()]
    
    # ============ DECISIONS ============
    
    def add_decision(self, project_id: int, decision: str, alternatives, reason: str, evidence: str = "") -> int:
        """Add a decision record to a project."""
        cur = self._conn.cursor()
        now = datetime.now().isoformat()
        if not isinstance(alternatives, str):
            alternatives = json.dumps(list(alternatives), default=str) if isinstance(alternatives, (list, tuple, set)) else str(alternatives)
        cur.execute(
            "INSERT INTO sih_decisions (project_id, decision, alternatives, reason, evidence, date) VALUES (?, ?, ?, ?, ?, ?)",
            (project_id, decision, alternatives, reason, evidence, now)
        )
        decision_id = cur.lastrowid
        self._conn.commit()
        return decision_id
    
    def list_decisions(self, project_id: int) -> List[Dict[str, Any]]:
        """List decisions for a project."""
        cur = self._conn.cursor()
        cur.execute("SELECT * FROM sih_decisions WHERE project_id = ? ORDER BY date DESC", (project_id,))
        return [dict(r) for r in cur.fetchall()]
    
    # ============ PROJECT STATS ============
    
    def get_project_stats(self, project_id: int) -> Dict[str, Any]:
        """Get statistics for a project."""
        cur = self._conn.cursor()

        # Validate project exists
        cur.execute("SELECT id FROM sih_projects WHERE id = ?", (project_id,))
        if cur.fetchone() is None:
            return {"error": f"Project ID {project_id} not found"}

        # Count items
        cur.execute("SELECT COUNT(*) as cnt FROM sih_ideas WHERE project_id = ?", (project_id,))
        ideas_count = cur.fetchone()['cnt']
        
        cur.execute("SELECT COUNT(*) as cnt FROM sih_features WHERE project_id = ?", (project_id,))
        features_count = cur.fetchone()['cnt']
        
        cur.execute("SELECT COUNT(*) as cnt FROM sih_risks WHERE project_id = ?", (project_id,))
        risks_count = cur.fetchone()['cnt']
        
        cur.execute("SELECT COUNT(*) as cnt FROM sih_evidence WHERE project_id = ?", (project_id,))
        evidence_count = cur.fetchone()['cnt']
        
        cur.execute("SELECT COUNT(*) as cnt FROM sih_decisions WHERE project_id = ?", (project_id,))
        decisions_count = cur.fetchone()['cnt']
        
        cur.execute("SELECT COUNT(*) as cnt FROM sih_team_members WHERE project_id = ?", (project_id,))
        team_count = cur.fetchone()['cnt']
        
        cur.execute("SELECT COUNT(*) as cnt FROM sih_research WHERE project_id = ?", (project_id,))
        research_count = cur.fetchone()['cnt']
        
        return {
            'project_id': project_id,
            'ideas': ideas_count,
            'features': features_count,
            'risks': risks_count,
            'evidence': evidence_count,
            'decisions': decisions_count,
            'team_members': team_count,
            'research_items': research_count
        }
    
    def close(self) -> None:
        """Close the database connection."""
        if self._conn:
            self._conn.close()


def _get_manager() -> SIHProjectManager:
    """Get a shared SIHProjectManager instance."""
    return SIHProjectManager()


@function_tool()
async def create_project(project_name: str, problem_statement: str, description: str = "", category: str = "") -> str:
    """Create a new SIH project. Each project is fully isolated from others.
    
    Args:
        project_name: Unique name of the SIH project
        problem_statement: The official problem statement text
        description: Optional short description
        category: Optional theme/category (e.g., "Smart Education", "Agriculture")
    
    Returns:
        Confirmation with the new project ID
    """
    try:
        mgr = _get_manager()
        existing = [p["name"].lower() for p in mgr.list_projects()]
        if project_name.lower() in existing:
            mgr.close()
            return f"❌ Project '{project_name}' already exists. Use list_projects to see IDs."
        pid = mgr.create_project(project_name, problem_statement, description, category)
        mgr.close()
        return (
            f"✅ SIH Project created.\n"
            f"🆔 Project ID: {pid}\n"
            f"📛 Name: {project_name}\n"
            f"📌 This is now your active project context. Next: run 'analyze problem statement' or 'generate ideas'."
        )
    except Exception as e:
        return f"❌ Failed to create project: {e}"


@function_tool()
async def list_projects() -> str:
    """List all SIH projects with their IDs and item counts."""
    try:
        mgr = _get_manager()
        projects = mgr.list_projects()
        if not projects:
            mgr.close()
            return "📋 No SIH projects yet. Create one with create_project."
        out = "📋 SIH Projects:\n\n"
        for p in projects:
            stats = mgr.get_project_stats(p["id"])
            out += (
                f"🆔 {p['id']} — {p['name']}\n"
                f"   ideas:{stats['ideas']} features:{stats['features']} risks:{stats['risks']} "
                f"research:{stats['research_items']} evidence:{stats['evidence']}\n"
                f"   updated: {p['updated_at'][:19] if p['updated_at'] else 'n/a'}\n\n"
            )
        mgr.close()
        return out
    except Exception as e:
        return f"❌ Failed to list projects: {e}"


@function_tool()
async def select_project(project_id: int) -> str:
    """Load full details of one SIH project (isolated view).
    
    Args:
        project_id: The project ID from list_projects
    """
    try:
        mgr = _get_manager()
        proj = mgr.select_project(project_id)
        if not proj:
            mgr.close()
            return f"❌ Project ID {project_id} not found."
        
        out = f"🗂️ Project {project_id}: {proj['project_name']}\n"
        out += f"📌 Problem: {(proj.get('problem_statement') or 'Not set')[:200]}\n"
        out += f"👥 Team: {len(proj.get('team_members', []))} | 💡 Ideas: {len(proj.get('ideas', []))} | "
        out += f"🔬 Research: {len(proj.get('research', []))} | ⚠️ Risks: {len(proj.get('risks', []))} | "
        out += f"✅ Evidence: {len(proj.get('evidence', []))} | 🧭 Decisions: {len(proj.get('decisions', []))}\n"
        mgr.close()
        return out
    except Exception as e:
        return f"❌ Failed to select project: {e}"


@function_tool()
async def get_project_details(project_id: int) -> str:
    """Get complete details of an SIH project including all sub-items.
    
    Args:
        project_id: The project ID
    """
    try:
        mgr = _get_manager()
        proj = mgr.select_project(project_id)
        if not proj:
            mgr.close()
            return f"❌ Project ID {project_id} not found."
        
        import json as _json
        # Return structured but bounded output
        out = _json.dumps({
            "id": proj["id"],
            "name": proj["project_name"],
            "problem_statement": (proj.get("problem_statement") or "")[:500],
            "description": proj.get("description", ""),
            "category": proj.get("category", ""),
            "team_members": proj.get("team_members", []),
            "ideas": [{"id": i["id"], "title": i["title"], "status": i["status"], "feasibility": i["feasibility"]} for i in proj.get("ideas", [])],
            "features": [{"title": f["title"], "priority": f["priority"], "status": f["status"]} for f in proj.get("features", [])],
            "risks": [{"category": r["category"], "severity": r["severity"], "description": r["description"], "status": r["status"]} for r in proj.get("risks", [])],
            "decisions": [{"decision": d["decision"], "reason": d["reason"]} for d in proj.get("decisions", [])],
        }, indent=2, default=str)
        mgr.close()
        return out
    except Exception as e:
        return f"❌ Failed to get details: {e}"


@function_tool()
async def get_project_stats(project_id: int) -> str:
    """Get statistics for an SIH project (counts of all tracked items).
    
    Args:
        project_id: The project ID
    """
    try:
        mgr = _get_manager()
        stats = mgr.get_project_stats(project_id)
        mgr.close()
        import json as _json
        return _json.dumps(stats, indent=2)
    except Exception as e:
        return f"❌ Failed to get stats: {e}"


def _require_project(mgr: SIHProjectManager, project_id: int):
    proj = mgr.select_project(project_id)
    return proj


@function_tool()
async def add_team_member(project_id: int, name: str, role: str) -> str:
    """Add a team member to an SIH project.
    
    Args:
        project_id: The project ID
        name: Member's name
        role: Role (frontend/backend/ai_ml/hardware/research/ui_ux/testing/docs/presentation/management)
    """
    try:
        mgr = _get_manager()
        if not _require_project(mgr, project_id):
            mgr.close()
            return f"❌ Project ID {project_id} not found."
        mid = mgr.add_team_member(project_id, name, role)
        mgr.close()
        return f"✅ Added '{name}' ({role}) to project {project_id} (member #{mid})."
    except Exception as e:
        return f"❌ Failed: {e}"


@function_tool()
async def add_idea(project_id: int, title: str, description: str, status: str = "proposed", feasibility: str = "unknown") -> str:
    """Add a solution idea to an SIH project.
    
    Args:
        project_id: The project ID
        title: Idea name
        description: Full idea description
        status: proposed / selected / rejected / killed
        feasibility: high / good / moderate / challenging / research_level
    """
    try:
        mgr = _get_manager()
        if not _require_project(mgr, project_id):
            mgr.close()
            return f"❌ Project ID {project_id} not found."
        iid = mgr.add_idea(project_id, title, description, status, feasibility)
        mgr.close()
        return f"💡 Idea #{iid} saved to project {project_id}: '{title}' [{status}, feasibility={feasibility}]"
    except Exception as e:
        return f"❌ Failed: {e}"


@function_tool()
async def add_research(project_id: int, title: str, source_type: str, source_url: str, description: str, relevance: str) -> str:
    """Save a research finding WITH its source URL. Never fabricate sources — only save real ones.
    
    Args:
        project_id: The project ID
        title: Research finding title
        source_type: web / paper / github / government / product / dataset / api
        source_url: The actual URL (must be real; say UNVERIFIED if unknown)
        description: Key findings
        relevance: high / medium / low
    """
    try:
        mgr = _get_manager()
        if not _require_project(mgr, project_id):
            mgr.close()
            return f"❌ Project ID {project_id} not found."
        rid = mgr.add_research(project_id, title, source_type, source_url, description, relevance)
        mgr.close()
        return f"🔬 Research #{rid} saved: '{title}' [{source_type}] → {source_url}"
    except Exception as e:
        return f"❌ Failed: {e}"


@function_tool()
async def add_architecture(project_id: int, name: str, description: str, components: str = "") -> str:
    """Record architecture documentation for an SIH project.
    
    Args:
        project_id: The project ID
        name: Architecture name/version
        description: Architecture description
        components: Comma-separated components (frontend, backend, db, ai, ...)
    """
    try:
        mgr = _get_manager()
        if not _require_project(mgr, project_id):
            mgr.close()
            return f"❌ Project ID {project_id} not found."
        aid = mgr.add_architecture(project_id, name, description, components)
        mgr.close()
        return f"🏗️ Architecture '#{aid}' recorded for project {project_id}: {name}"
    except Exception as e:
        return f"❌ Failed: {e}"


@function_tool()
async def add_feature(project_id: int, title: str, priority: str, status: str = "pending",
                      estimated_effort: str = "", dependencies: str = "") -> str:
    """Add a feature to an SIH project's MVP plan.
    
    Args:
        project_id: The project ID
        title: Feature name
        priority: must_have / should_have / nice_to_have / demo_impact / future_scope
        status: pending / in_progress / complete / blocked
        estimated_effort: e.g. "2 weeks"
        dependencies: Comma-separated dependencies
    """
    try:
        mgr = _get_manager()
        if not _require_project(mgr, project_id):
            mgr.close()
            return f"❌ Project ID {project_id} not found."
        fid = mgr.add_feature(project_id, title, priority, status, estimated_effort, dependencies)
        mgr.close()
        return f"⚙️ Feature #{fid} added: '{title}' [{priority}, {status}]"
    except Exception as e:
        return f"❌ Failed: {e}"


@function_tool()
async def add_risk(project_id: int, category: str, probability: str, severity: str,
                   description: str, mitigation: str, owner: str = "") -> str:
    """Add a risk to an SIH project's risk register.
    
    Args:
        project_id: The project ID
        category: technical / ai_ml / hardware / security / privacy / deployment / cost / team / time / demo
        probability: low / medium / high
        severity: low / medium / high / critical
        description: What could go wrong
        mitigation: How to prevent/handle it
        owner: Person responsible
    """
    try:
        mgr = _get_manager()
        if not _require_project(mgr, project_id):
            mgr.close()
            return f"❌ Project ID {project_id} not found."
        rid = mgr.add_risk(project_id, category, probability, severity, description, mitigation, owner)
        mgr.close()
        return f"⚠️ Risk #{rid} logged: [{severity}/{probability}] {description[:100]}"
    except Exception as e:
        return f"❌ Failed: {e}"


@function_tool()
async def add_evidence(project_id: int, title: str, evidence_type: str, path: str, description: str) -> str:
    """Add evidence (test results, screenshots, benchmarks, metrics) to the Evidence Locker.
    Only record evidence that actually exists — never fabricate test results or metrics.
    
    Args:
        project_id: The project ID
        title: Evidence title
        evidence_type: screenshot / video / test_result / benchmark / metric / document / demo_recording
        path: File path if stored locally, else empty
        description: What this evidence proves
    """
    try:
        mgr = _get_manager()
        if not _require_project(mgr, project_id):
            mgr.close()
            return f"❌ Project ID {project_id} not found."
        eid = mgr.add_evidence(project_id, title, evidence_type, path, description)
        mgr.close()
        return f"📎 Evidence #{eid} locked: '{title}' [{evidence_type}]"
    except Exception as e:
        return f"❌ Failed: {e}"


@function_tool()
async def add_decision(project_id: int, decision: str, alternatives: str, reason: str, evidence: str = "") -> str:
    """Log a technology/architecture decision with its rationale for future reference.
    
    Args:
        project_id: The project ID
        decision: What was decided (e.g., "Use PostgreSQL over MongoDB")
        alternatives: Comma-separated alternatives considered
        reason: Why this was chosen
        evidence: Supporting evidence reference
    """
    try:
        mgr = _get_manager()
        if not _require_project(mgr, project_id):
            mgr.close()
            return f"❌ Project ID {project_id} not found."
        did = mgr.add_decision(project_id, decision, alternatives, reason, evidence)
        mgr.close()
        return f"🧭 Decision #{did} logged: {decision[:100]}"
    except Exception as e:
        return f"❌ Failed: {e}"


@function_tool()
async def sih_command_center(project_id: int = 0) -> str:
    """SIH COMMAND CENTER dashboard. Shows readiness scores, health, blockers,
    next best action — all computed from actual stored project data.
    
    Args:
        project_id: Specific project ID (0 = overview of all projects)
    
    Returns:
        Formatted command center dashboard
    """
    try:
        mgr = _get_manager()

        if not project_id:
            projects = mgr.list_projects()
            if not projects:
                mgr.close()
                return (
                    "🎯 SIH COMMAND CENTER\n"
                    "════════════════════\n"
                    "📭 No projects yet.\n"
                    "➡ Next best action: create your first project with create_project."
                )
            out = "🎯 SIH COMMAND CENTER — OVERVIEW\n════════════════════\n"
            for p in projects:
                s = mgr.get_project_stats(p["id"])
                # Simple readiness heuristic from REAL counts
                factors = [
                    min(s["ideas"] / 3, 1.0),
                    min(s["features"] / 5, 1.0),
                    min(s["research_items"] / 3, 1.0),
                    min(s["evidence"] / 5, 1.0),
                    min(s["decisions"] / 3, 1.0),
                ]
                readiness = round(sum(factors) / len(factors) * 100)
                bar = "█" * (readiness // 10) + "░" * (10 - readiness // 10)
                out += f"\n🆔 {p['id']} {p['name']}\n   Readiness: {bar} {readiness}%\n"
                out += f"   💡{s['ideas']} ⚙️{s['features']} 🔬{s['research_items']} ⚠️{s['risks']} 📎{s['evidence']}\n"
            out += "\n➡ Use select_project(id) then ask for analysis, scoring, or judge mode."
            mgr.close()
            return out

        proj = mgr.select_project(project_id)
        if not proj:
            mgr.close()
            return f"❌ Project ID {project_id} not found."

        s = mgr.get_project_stats(project_id)
        risks = mgr.list_risks(project_id)
        features = mgr.list_features(project_id)

        # Readiness from real data
        factors = {
            "problem_defined": 1.0 if (proj.get("problem_statement") or "").strip() else 0.0,
            "ideas_generated": min(s["ideas"] / 3, 1.0),
            "features_planned": min(s["features"] / 5, 1.0),
            "research_done": min(s["research_items"] / 3, 1.0),
            "evidence_collected": min(s["evidence"] / 5, 1.0),
            "risks_managed": ((len([r for r in risks if r.get("status") == "resolved"]) / len(risks)) if risks else 0.5),
            "decisions_logged": min(s["decisions"] / 3, 1.0),
        }
        readiness = round(sum(factors.values()) / len(factors) * 100)

        # Blockers & critical items from real data
        open_risks = [r for r in risks if r.get("status") != "resolved"]
        critical = [r for r in open_risks if r.get("severity") == "critical"]
        pending_must_have = [f for f in features if "must have" in (f.get("priority") or "").lower()
                             and (f.get("status") or "").lower() in ("pending", "in_progress")]

        # Next best action from ACTUAL state
        if not (proj.get("problem_statement") or "").strip():
            next_action = "Add the official problem statement (analyze_problem_statement)."
        elif s["research_items"] == 0:
            next_action = "Research existing solutions before building (uniqueness is unverified)."
        elif pending_must_have:
            next_action = f"Complete MUST HAVE feature: '{pending_must_have[0].get('title')}'."
        elif critical:
            next_action = f"Resolve CRITICAL risk: {critical[0].get('description', '')[:80]}."
        elif s["evidence"] < 3:
            next_action = "Collect demo evidence: tests, screenshots, benchmarks."
        else:
            next_action = "Run Judge Mode practice and Final Audit."

        bar = "█" * (readiness // 10) + "░" * max(0, 10 - readiness // 10)
        out = (
            f"🎯 SIH COMMAND CENTER\n════════════════════\n"
            f"📛 Project: {proj['project_name']} (ID {project_id})\n"
            f"📊 Overall Readiness: {bar} {readiness}%\n\n"
            f"📈 Factors:\n"
        )
        for k, v in factors.items():
            pct = round(v * 100)
            out += f"   {'🟢' if pct >= 80 else '🟡' if pct >= 40 else '🔴'} {k.replace('_', ' ').title()}: {pct}%\n"

        out += (
            f"\n⚠️ Open Risks: {len(open_risks)} (critical: {len(critical)})\n"
            f"🚧 Pending MUST HAVE: {len(pending_must_have)}\n"
            f"🧭 Team: {s['team_members']} | Ideas: {s['ideas']} | Features: {s['features']}\n"
            f"🔬 Research: {s['research_items']} | Evidence: {s['evidence']} | Decisions: {s['decisions']}\n"
            f"\n⚡ NEXT BEST ACTION:\n   → {next_action}\n"
        )
        mgr.close()
        return out
    except Exception as e:
        return f"❌ Command Center error: {e}"