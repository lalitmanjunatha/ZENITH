"""Zenith Life Memory — never lose physical things again.

F31 WHERE-IS-IT: a location brain for your stuff. "Keys are on the study table"
→ later "where are my keys?" → instant spoken answer.
F32 ROOM INVENTORY: log what you own + which bag/box it lives in, and generate
packing checklists ("going home for Diwali — what do I need?").
"""

import logging
import re
import sqlite3
from datetime import datetime
from pathlib import Path

from livekit.agents import function_tool

logger = logging.getLogger(__name__)

DB_PATH = "data/zenith_memory.db"


def _db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS item_locations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item TEXT,
            location TEXT,
            container TEXT DEFAULT '',
            updated_at TEXT,
            UNIQUE(item)
        );
        CREATE TABLE IF NOT EXISTS inventory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item TEXT UNIQUE,
            category TEXT DEFAULT 'general',
            stored_in TEXT DEFAULT '',
            essential INTEGER DEFAULT 0,
            added_at TEXT
        );
        """
    )
    return conn


# ---------------------------------------------------------- where-is-it -----

@function_tool()
async def remember_item_location(item: str, location: str, container: str = "") -> str:
    """Tell Zenith where something is. Later just ask 'where is my X?'.
    Re-stating an item UPDATES its place (latest wins).

    Args:
        item: e.g. "locker key", "college ID", "spare charger"
        location: e.g. "study table", "hostel drawer 2", "black backpack"
        container: Optional specific box/pouch inside that location
    """
    try:
        conn = _db()
        conn.execute(
            """INSERT INTO item_locations (item,location,container,updated_at)
               VALUES (?,?,?,?)
               ON CONFLICT(item) DO UPDATE SET
                 location=excluded.location,
                 container=excluded.container,
                 updated_at=excluded.updated_at""",
            (item.strip().lower(), location.strip(), container.strip(),
             datetime.now().isoformat()),
        )
        conn.commit(); conn.close()
        extra = f" (inside {container})" if container else ""
        return f"📍 Noted: {item} → {location}{extra}. Ask me anytime."
    except Exception as e:
        return f"❌ Failed to note: {e}"


@function_tool()
async def find_item(item: str) -> str:
    """WHERE IS MY…? Recall the last known place of any item you've told
    Zenith about. Matches partial words too ('keys' finds 'locker key')."""
    try:
        conn = _db()
        rows = [dict(r) for r in conn.execute(
            "SELECT * FROM item_locations ORDER BY updated_at DESC").fetchall()]
        n = len(rows)
        conn.close()
        if not rows:
            return ("🤷 I don't track any items yet. Tell me once like: "
                    "\"my locker key is on the study table\".")

        q_tokens = set(re.findall(r"\w+", item.strip().lower())) - {"my", "the", "a"}
        def _sing(t):
            return t[:-1] if len(t) > 3 and t.endswith("s") else t
        q_norm = {_sing(t) for t in q_tokens}

        def relevance(r):
            it = r["item"].lower()
            i_tokens = {_sing(t) for t in re.findall(r"\w+", it)}
            score = 0
            if q_norm & i_tokens:
                score = 3                                    # shared word(s)
            if item.lower() in it or it in item.lower():
                score = max(score, 4)                        # substring either way
            return score

        ranked = sorted(((relevance(r), r) for r in rows),
                        key=lambda x: -x[0])
        if not ranked or ranked[0][0] == 0:
            return (f"🤷 Nothing about “{item}” in my location brain "
                    f"({n} item(s) tracked). Tell me where it is and I'll remember.")
        r = ranked[0][1]
        when = str(r["updated_at"])[:16].replace("T", " ")
        extra = f" (inside {r['container']})" if r["container"] else ""
        return (f"📍 {r['item'].title()} → **{r['location']}**{extra}\n"
                f"   Last updated {when}.")
    except Exception as e:
        return f"❌ Lookup failed: {e}"


@function_tool()
async def list_tracked_items() -> str:
    """Show every item whose location Zenith remembers."""
    conn = _db()
    rows = conn.execute("SELECT item,location,container,updated_at FROM item_locations "
                        "ORDER BY updated_at DESC").fetchall()
    conn.close()
    if not rows:
        return "📍 Location brain empty. Start noting things!"
    out = f"📍 TRACKED ITEMS ({len(rows)}):\n"
    for r in rows:
        extra = f" ({r['container']})" if r["container"] else ""
        out += f"   • {r['item'].title()} → {r['location']}{extra} · {str(r['updated_at'])[:10]}\n"
    return out


# --------------------------------------------------------- room inventory ---

@function_tool()
async def add_inventory_item(item: str, category: str = "general",
                             stored_in: str = "", essential: bool = False) -> str:
    """Log something you OWN into room inventory (charger, adapter, notes…).
    Mark essentials=true for things you can't travel without.

    Args:
        item: Item name
        category: electronics / documents / clothing / daily / other
        stored_in: Which bag/box/drawer it lives in
        essential: Must-carry when travelling?
    """
    try:
        conn = _db()
        conn.execute(
            """INSERT INTO inventory (item,category,stored_in,essential,added_at)
               VALUES (?,?,?,?,?)
               ON CONFLICT(item) DO UPDATE SET category=excluded.category,
                 stored_in=excluded.stored_in, essential=excluded.essential""",
            (item.strip(), category.strip() or "general", stored_in.strip(),
             1 if essential else 0, datetime.now().isoformat()),
        )
        n = conn.execute("SELECT COUNT(*) c FROM inventory").fetchone()["c"]
        conn.commit(); conn.close()
        star = " ⭐(essential)" if essential else ""
        return f"📦 Logged: {item}{star} [{category}] — inventory now has {n} item(s)."
    except Exception as e:
        return f"❌ Inventory failed: {e}"


@function_tool()
async def packing_checklist(trip: str = "home visit") -> str:
    """PACKING CHECKLIST: builds a smart checklist from your essential inventory
    plus common trip needs. Returns it grouped so nothing gets forgotten.

    Args:
        trip: Purpose label, e.g. "home visit", "college trip"
    """
    conn = _db()
    ess = [dict(r) for r in conn.execute(
        "SELECT item,stored_in FROM inventory WHERE essential=1 ORDER BY item").fetchall()]
    conn.close()

    base = ["Phone + charger", "Wallet / ID cards", "House keys"]
    groups = {"🎒 From your essentials": [], "🧠 Standard basics": base}

    for r in ess:
        line = f"{r['item']}" + (f" — packed from {r['stored_in']}" if r["stored_in"] else "")
        groups["🎒 From your essentials"].append(line)

    out = [f"✅ PACKING CHECKLIST — {trip}\n════════════════════"]
    total = 0
    for g, items in groups.items():
        if not items:
            continue
        out.append(f"\n{g}")
        for i in items:
            out.append(f"   ☐ {i}")
            total += 1
    if len(ess) < 3:
        out.append("\n💡 Tip: log more items with add_inventory_item(... essential=True) "
                   "so future checklists get smarter.")
    out.append(f"\n{total} thing(s) to pack. Safe travels!")
    return "\n".join(out)


@function_tool()
async def list_inventory(category: str = "") -> str:
    """List your logged belongings (optionally one category)."""
    conn = _db()
    if category.strip():
        rows = conn.execute("SELECT * FROM inventory WHERE category=? ORDER BY item",
                            (category.strip().lower(),)).fetchall()
    else:
        rows = conn.execute("SELECT * FROM inventory ORDER BY essential DESC, item").fetchall()
    conn.close()
    if not rows:
        return "📦 Inventory empty. Log things with add_inventory_item."
    out = f"📦 INVENTORY ({len(rows)}):\n"
    for r in rows:
        star = " ⭐" if r["essential"] else ""
        loc = f" @ {r['stored_in']}" if r["stored_in"] else ""
        out += f"   • {r['item']}{star} [{r['category']}]{loc}\n"
    return out