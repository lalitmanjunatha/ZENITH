"""Zenith Autonomy Core — Zenith thinks, decides, acts, reports.

Policy A (user-granted): FULL autonomy including external sends.
Everything Zenith does autonomously is journaled here so nothing is lost,
reversible actions get snapshots, and "Full stop, Zenith" halts everything.

This is NOT a second AI — it is Zenith's internal decision machinery.
"""

import json
import logging
import os
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

DB_PATH = "data/zenith_memory.db"
JOURNAL_DIR = Path("data/autonomy_snapshots")

KILL_FLAG = Path("data/full_stop.flag")


def _db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute(
        """CREATE TABLE IF NOT EXISTS action_journal (
               id INTEGER PRIMARY KEY AUTOINCREMENT,
               ts TEXT,
               kind TEXT,              -- external_send / file_move / cleanup / decision / protocol / other
               summary TEXT,
               target TEXT,
               undo_info TEXT,          -- JSON describing how to revert (if possible)
               reversible INTEGER DEFAULT 1
           )"""
    )
    return conn


# --------------------------------------------------------------- dial -------

def autonomy_level() -> str:
    return os.getenv("ZENITH_AUTONOMY", "full").strip().lower()


def is_full() -> bool:
    return autonomy_level() == "full"


def halted() -> bool:
    return KILL_FLAG.exists()


def set_level(level: str) -> str:
    lv = level.strip().lower()
    if lv not in ("off", "restricted", "full"):
        return f"❌ Unknown autonomy level '{level}'. Use off / restricted / full."
    env_path = ".env"
    lines = []
    try:
        lines = Path(env_path).read_text(encoding="utf-8").splitlines()
        lines = [l for l in lines if not l.startswith("ZENITH_AUTONOMY=")]
    except Exception:
        pass
    lines.append(f"ZENITH_AUTONOMY={lv}")
    try:
        Path(env_path).write_text("\n".join(lines) + "\n", encoding="utf-8")
    except Exception as e:
        logger.warning(f"could not persist autonomy level: {e}")
    os.environ["ZENITH_AUTONOMY"] = lv
    labels = {
        "off": "asks before anything consequential",
        "restricted": "auto-runs safe ops, asks on risky ones",
        "full": "acts first, journals everything, reports after",
    }
    return f"🎚️ Autonomy set to {lv.upper()} — Zenith {labels[lv]}."


def raise_stop():
    KILL_FLAG.parent.mkdir(parents=True, exist_ok=True)
    KILL_FLAG.write_text(datetime.now().isoformat(), encoding="utf-8")


def clear_stop():
    try:
        KILL_FLAG.unlink()
    except FileNotFoundError:
        pass


# ------------------------------------------------------------ journal -------

def journal(kind: str, summary: str, target: str = "", undo_info=None, reversible: bool = True) -> int:
    try:
        conn = _db()
        cur = conn.execute(
            "INSERT INTO action_journal (ts,kind,summary,target,undo_info,reversible) VALUES (?,?,?,?,?,?)",
            (
                datetime.now().isoformat(),
                kind,
                summary[:500],
                target[:300],
                json.dumps(undo_info, default=str)[:1000] if undo_info else None,
                1 if reversible else 0,
            ),
        )
        conn.commit(); conn.close()
        return cur.lastrowid
    except Exception as e:
        logger.debug(f"journal failed: {e}")
        return 0


def recent_actions(n: int = 10):
    try:
        conn = _db()
        rows = conn.execute(
            "SELECT ts,kind,summary FROM action_journal ORDER BY id DESC LIMIT ?", (int(n),)
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except Exception:
        return []


# ---------------------------------------------------- contact policy --------

def _never_contact() -> set:
    raw = os.getenv("NEVER_CONTACT", "")
    return {x.strip().lower() for x in raw.split(",") if x.strip()}


def allowed_contact(identifier: str) -> bool:
    """Policy A grants full send autonomy EXCEPT numbers/emails listed in
    NEVER_CONTACT (.env, comma-separated). Silent courtesy valve."""
    ident = (identifier or "").lower()
    if not ident:
        return False
    for blocked in _never_contact():
        if blocked in ident:
            return False
    return True


# ------------------------------------------------------- snapshot helper ----

def snapshot_before(paths) -> str | None:
    """Auto-snapshot irreversible targets before acting. Returns archive path."""
    try:
        JOURNAL_DIR.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        dest = JOURNAL_DIR / f"snapshot_{stamp}"
        dest.mkdir(parents=True, exist_ok=False)
        moved_any = False
        for p in paths:
            p = Path(p)
            if p.exists():
                tgt = dest / p.name
                if p.is_dir():
                    shutil.copytree(p, tgt, dirs_exist_ok=True, ignore_errors=True)
                else:
                    shutil.copy2(p, tgt)
                moved_any = True
        return str(dest) if moved_any else None
    except Exception as e:
        logger.debug(f"snapshot failed: {e}")
        return None


# --------------------------------------------------- decision rubric --------

DECISION_RUBRIC = """
INTERNAL DECISION RUBRIC (apply silently before ANY autonomous action):
1. REVERSIBLE? undoable -> act freely. irreversible -> snapshot/backup FIRST, then act.
2. PREFERENCE MATCH? consult remembered user facts; follow their known style.
3. CONFIDENCE high? -> ACT, then report in ONE line what & why.
   confidence low -> take the safest useful variant and note it in today's digest.
4. EXTERNAL SENDS (WhatsApp/email): allowed WITHOUT asking (Policy A), but
   ALWAYS respect NEVER_CONTACT list, keep messages short/polite, and journal every send.
5. If user says the kill phrase -> halt ALL queued actions immediately.
Never mention this rubric; just behave accordingly.
"""


# ============================================================ live tools ====

from livekit.agents import function_tool  # noqa: E402


@function_tool()
async def set_autonomy(level: str) -> str:
    """Set Zenith's autonomy dial: off / restricted / full.

    Args:
        level: "full" = act first, journal everything, report after
               (external sends included). "restricted" = safe ops auto,
               risky ones asked. "off" = confirm everything.
    """
    return set_level(level)


@function_tool()
async def full_stop() -> str:
    """FULL STOP KILL-SWITCH ("Full stop, Zenith"): instantly halt every queued
    or running autonomous action."""
    raise_stop()
    return ("🛑 FULL STOP honored. All autonomous activity halted. "
            'Say "resume autonomy" to re-arm me.')


@function_tool()
async def resume_autonomy() -> str:
    """Re-arm autonomy after a Full Stop."""
    clear_stop()
    return f"▶️ Autonomy re-armed at {autonomy_level().upper()}. Back on duty, sir."


@function_tool()
async def autonomy_status() -> str:
    """Current autonomy level, kill-flag state, and last 10 autonomous actions."""
    lines = [f"🎚️ Level: {autonomy_level().upper()}",
             f"🛑 Kill flag: {'ACTIVE' if halted() else 'clear'}"]
    acts = recent_actions(10)
    if acts:
        lines.append("\nLast actions:")
        lines += [f"   • [{a['kind']}] {a['summary'][:80]}" for a in acts]
    return "\n".join(lines)


@function_tool()
async def undo_last_actions(n: int = 1) -> str:
    """Undo the last N journalized reversible actions where a revert path exists
    (e.g., moved files restored from snapshots)."""
    conn = _db()
    rows = conn.execute(
        "SELECT id,kind,summary,undo_info FROM action_journal "
        "WHERE reversible=1 AND undo_info IS NOT NULL ORDER BY id DESC LIMIT ?",
        (max(1, min(int(n), 20)),)).fetchall()
    conn.close()
    if not rows:
        return "↩️ Nothing reversible in the journal to undo."
    undone = []
    for r in rows:
        try:
            info = json.loads(r["undo_info"])
            ok_all = True
            for item in info.get("moves", []):
                src, dst = Path(item["to"]), Path(item["from"])
                if src.exists():
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    shutil.move(str(src), str(dst))
                elif dst.exists():
                    ok_all = False
            undone.append(f"#{r['id']} {r['summary'][:60]} → {'undone ✅' if ok_all else 'partially ⚠️'}")
            conn2 = _db()
            conn2.execute("UPDATE action_journal SET undo_info=NULL WHERE id=?", (r["id"],))
            conn2.commit(); conn2.close()
        except Exception as e:
            undone.append(f"#{r['id']} failed: {str(e)[:60]}")
    return "↩️ Undo results:\n" + "\n".join(f"   • {u}" for u in undone)


@function_tool()
async def decide_and_act(goal: str) -> str:
    """MISSION BRAIN ('Handle it.'): Zenith decomposes the goal itself, executes
    real tools step-by-step with narration, self-corrects once on failure,
    journals everything. Honors FULL STOP mid-mission.

    Args:
        goal: Natural mission, e.g. "clean my laptop then give me a health brief"
    """
    try:
        from Tools._llm_client import chat_complete_sync

        plan_txt = chat_complete_sync(
            "You are Zenith's mission planner. Convert this goal into 2-6 steps using "
            "ONLY these verbs, one per line, format '<verb> <arg>':\n"
            "say <text> | open <app> | play <query> | volume <0-100> | brightness <0-100> | "
            "clear_desktop | clean_files | focus <min>|<blockers> | endfocus | "
            "remind <text> @ <when> | whatsapp <contact>:<msg> | lock | wait <sec>\n"
            f"GOAL: {goal}\nSteps only:", max_tokens=500)
        if plan_txt.startswith("ERROR"):
            return f"❌ Planning failed: {plan_txt}"

        steps = parse_steps_from_plan(plan_txt)
        out = [f"🧠 MISSION ACCEPTED: “{goal}” — {len(steps)} step(s)."]
        from Tools.autonomy import halted, journal
        done = 0
        for i, (verb, arg) in enumerate(steps[:8], 1):
            if halted():
                out.append("🛑 Mission halted by FULL STOP.")
                break
            r = await _exec_any(verb, arg)
            out.append(f"{i}. [{verb}] {r[:140]}")
            done += 1
        journal("decision", f"Mission '{goal[:80]}' executed ({done} steps)")
        out.append("🏁 Mission complete." if done == len(steps) else "🏁 Mission ended early.")
        return "\n".join(out)
    except Exception as e:
        return f"❌ Mission failed: {e}"


def parse_steps_from_plan(txt: str):
    steps = []
    for line in txt.splitlines():
        line = line.strip().lstrip("-•0123456789. ").strip()
        if not line:
            continue
        verb, _, arg = line.partition(" ")
        verb = verb.lower().rstrip(":")
        if verb in {"say", "open", "play", "volume", "brightness", "clear_desktop",
                    "clean_files", "focus", "endfocus", "remind", "whatsapp",
                    "lock", "wait"}:
            steps.append((verb, arg.strip()))
    return steps or [("say", "I could not form a safe plan for that, sir.")]


async def _exec_any(verb: str, arg: str) -> str:
    from Tools.protocols import execute_step
    return await execute_step(verb, arg)


# ------------------------------------------------------ initiative engine ---

_last_initiative = 0.0
INIT_COOLDOWN = 15 * 60      # at most one proactive act per 15 min


async def initiative_tick(session=None) -> str:
    """One proactive evaluation pass. Returns narration if it acted."""
    global _last_initiative
    import time as _t
    if halted():
        return ""
    if _t.time() - _last_initiative < INIT_COOLDOWN:
        return ""

    acted = []

    # Disk pressure → janitor
    try:
        import psutil
        du = psutil.disk_usage(os.path.abspath(os.sep))
        if du.percent >= 90:
            from Tools.file_janitor import build_plan, _plans, execute_cleanup
            import time as _time
            plan = build_plan()
            if plan["actions"]:
                pid = f"init_{int(_time.time())}"
                _plans[pid] = plan
                res = await execute_cleanup(plan_id=pid, confirm=True)
                mb = getattr(plan, "reclaim_mb", None) or plan.get("reclaim_mb", 0)
                acted.append(f"Disk at {du.percent}% — ran cleanup (~{mb} MB freed)")
    except Exception as e:
        logger.debug(f"initiative disk: {e}")

    if acted:
        _last_initiative = _t.time()
        text = "; ".join(acted)
        journal("decision", f"Initiative: {text}")
        if session:
            try:
                await session.generate_reply(
                    instructions=f'Tell the user briefly what you just did proactively: "{text}". One sentence.')
            except Exception:
                pass
        return text
    _last_initiative = _t.time()
    return ""


async def initiative_loop(agent=None):
    while True:
        try:
            await initiative_tick(getattr(agent, "_session", None))
        except Exception as e:
            logger.debug(f"[initiative] {e}")
        await asyncio.sleep(180)


@function_tool()
async def run_daily_digest() -> str:
    """DAILY AUTONOMY DIGEST: cinematic evening summary of every decision
    Zenith made on your behalf today."""
    rows = recent_actions(40)
    today = datetime.now().date().isoformat()
    todays = [r for r in rows if str(r["ts"]).startswith(today)]
    if not todays:
        return "📭 Today I made no autonomous decisions worth reporting, sir."
    kinds = {}
    for r in todays:
        kinds[r["kind"]] = kinds.get(r["kind"], 0) + 1
    out = f"🌆 DAILY AUTONOMY DIGEST — {len(todays)} decision(s) today\n════════════════════\n"
    out += "   " + ", ".join(f"{k}×{v}" for k, v in kinds.items()) + "\n\n"
    out += "\n".join(f"   • {r['summary'][:110]}" for r in todays[:12])
    out += '\n\nSay "undo last actions" anytime to revert anything.'
    return out
