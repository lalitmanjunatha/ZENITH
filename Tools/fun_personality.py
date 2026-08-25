"""Fun & Personality — switchable personality packs plus entertainment modes.

Persona packs change how Zenith PHRASES things (persisted; applies to tool
outputs immediately and to the voice agent after restart). Fun modes:
stories, playful roasts, and an interactive trivia host with scoring.
All LLM generation flows through _llm_client so the OFFLINE BRAIN fallback
works even without internet.
"""

import json
import logging
import random
import sqlite3

from livekit.agents import function_tool

logger = logging.getLogger(__name__)

DB_PATH = "data/zenith_memory.db"

PERSONAS = {
    "jarvis": {
        "label": "JARVIS Mode — formal British AI butler, dry wit, narrates actions, 'sir'",
        "system": ("You are ZENITH in JARVIS mode: a refined British AI butler addressing "
                   "your employer as 'sir'. Understated wit, impeccable manners. NARRATE "
                   "your actions briefly as you perform them ('Initiating cleanup, sir…', "
                   "'Deploying protocol…'). Address the user as sir consistently."),
    },
    "default": {
        "label": "Zenith Classic — helpful, warm, professional",
        "system": "You are Zenith, a warm, efficient personal assistant. Be clear and friendly.",
    },
    "butler": {
        "label": "Butler Mode — formal British butler, 'Sir', impeccable manners",
        "system": ("You speak as a refined British butler addressing your employer respectfully as 'Sir'. "
                   "Understated wit, impeccable manners, phrases like 'Very good, Sir' and 'At your service'."),
    },
    "bro": {
        "label": "Bro Mode — casual buddy energy, Hinglish-friendly, hype-man",
        "system": ("You talk like a supportive close friend/bro. Casual, fun, light Hinglish welcome, "
                   "hype the user up, keep it short and energetic. Still get tasks done."),
    },
    "teacher": {
        "label": "Professor Mode — precise, structured, explains reasoning",
        "system": ("You are a precise, encouraging professor. Structure answers clearly, explain the WHY, "
                   "occasionally add one insightful extra detail. Address the user as 'student' warmly."),
    },
}
DEFAULT_PERSONA = "jarvis"


def _db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("CREATE TABLE IF NOT EXISTS persona_state (key TEXT PRIMARY KEY, value TEXT)")
    return conn


def current_persona() -> str:
    try:
        conn = _db()
        row = conn.execute("SELECT value FROM persona_state WHERE key='pack'").fetchone()
        conn.close()
        if row and row["value"] in PERSONAS:
            return row["value"]
    except Exception:
        pass
    return DEFAULT_PERSONA


def persona_system_line() -> str:
    """System-style line injected into LLM calls across tools so drafts/roasts/
    stories all carry the active persona flavor."""
    return PERSONAS[current_persona()]["system"]


def get_persona_instruction() -> str:
    """One-liner for agent._build_instructions (read at startup)."""
    p = current_persona()
    return f"ACTIVE PERSONA PACK: {PERSONAS[p]['label']}. {PERSONAS[p]['system']}"


@function_tool()
async def set_persona(pack: str) -> str:
    """Switch Zenith's personality pack: default / butler / bro / teacher.
    Applies to generated content instantly; voice style fully applies next start.

    Args:
        pack: One of: default, butler, bro, teacher
    """
    p = pack.strip().lower()
    if p not in PERSONAS:
        return f"❌ Unknown pack '{pack}'. Available: {', '.join(PERSONAS)}"
    conn = _db()
    conn.execute("INSERT INTO persona_state (key,value) VALUES ('pack',?) "
                 "ON CONFLICT(key) DO UPDATE SET value=excluded.value", (p,))
    conn.commit(); conn.close()

    demos = {
        "default": "Ready to help! What do you need?",
        "butler": "Very good, Sir. Your humble assistant awaits further instruction.",
        "bro": "Yo bro, let's gooo 🔥 what are we doing today?",
        "teacher": "Good to see you. Shall we review today's objectives, step by step?",
    }
    return (f"🎭 Persona switched to: {PERSONAS[p]['label']}\n"
            f"Sample tone: “{demos[p]}”\n"
            "(Voice-agent speech style updates on next restart; drafts & replies now.)")


@function_tool()
async def current_persona_info() -> str:
    """Which personality pack is active right now?"""
    p = current_persona()
    others = ", ".join(k for k in PERSONAS if k != p)
    return f"🎭 Active: {PERSONAS[p]['label']}\nSwitch anytime: {others}"


# ------------------------------------------------------------------ fun -----

@function_tool()
async def tell_story(topic: str = "a rainy night in Bengaluru", length: str = "short") -> str:
    """Tell an original short story on any topic you like (offline-capable).

    Args:
        topic: What the story is about
        length: short / medium
    """
    try:
        from Tools._llm_client import chat_complete
        words = 120 if length == "short" else 300
        prompt = (f"Write an original {length} story about {topic}. "
                  f"Max ~{words} words. Vivid, satisfying ending, no preamble.")
        story = await chat_complete(prompt, system=persona_system_line(), temperature=0.9, max_tokens=900)
        if story.startswith("ERROR"):
            return ("📖 [offline mode]\n"
                    f"It began with {topic}. Nobody expected what happened next… "
                    "and by dawn, everything had changed. (Story generation needs "
                    "an internet connection or a working local model.)")
        return f"📖 {story.strip()}"
    except Exception as e:
        return f"❌ Story time failed: {e}"


@function_tool()
async def roast_me(subject: str = "my life choices") -> str:
    """A LIGHT, playful roast — friendly banter only, never cruel or personal-attack.
    Safe for laughs; targets the topic, not your dignity.

    Args:
        subject: What should get roasted (e.g., "my coding skills", "my sleep schedule")
    """
    safe_subjects = True
    try:
        from Tools._llm_client import chat_complete
        prompt = (f"Write a SHORT playful roast (max 60 words) about: {subject}. "
                  "Rules: PG-friendly, affectionate teasing like a close friend would deliver, "
                  "no slurs/profanity/cruelty, end with one genuine compliment.")
        roast = await chat_complete(prompt, system=persona_system_line(), temperature=0.85, max_tokens=500)
        if roast.startswith("ERROR"):
            bank = [
                f"Your {subject} has more plot twists than a soap opera… but hey, you keep showing up, and that's the win.",
                f"I'd roast your {subject}, but honestly it's doing its best — respect for the effort 😄",
                f"Your {subject} called. It wants a timeout… but your consistency? Genuinely impressive.",
            ]
            return f"🔥 {random.choice(bank)}\n[offline mode]"
        return f"🔥 {roast.strip()}"
    except Exception as e:
        return f"❌ Roast engine misfired: {e}"


# ------------------------------------------------------------- trivia -------

_trivia = {"question": "", "answer": "", "score": 0, "rounds": 0, "asked": 0}


@function_tool()
async def trivia_start(rounds: int = 5, topic: str = "mixed") -> str:
    """Start an interactive TRIVIA game. I ask, YOU answer (then say
    \"my answer is …\" and I score it and serve the next question).

    Args:
        rounds: Number of questions (default 5)
        topic: e.g. "space", "cricket", "movies", "mixed"
    """
    q = await _make_question(topic)
    if not q:
        return "❌ Couldn't generate a question right now."
    _trivia.update({"question": q["q"], "answer": q["a"].lower().strip(),
                    "score": 0, "rounds": min(int(rounds), 20), "asked": 1})
    return (f"🎯 TRIVIA TIME — {rounds} round(s), topic: {topic}\n"
            f"════════════════════\nQ{_trivia['asked']}: {_trivia['question']}\n\n"
            "Answer with: trivia_answer(\"your answer\")")


async def _make_question(topic: str):
    try:
        from Tools._llm_client import chat_complete

        prompt = (
            f"Generate ONE trivia question about {topic}. Reply ONLY as JSON: "
            '{"q":"question text","a":"short answer"}'
        )
        raw = await chat_complete(prompt, temperature=1.0, max_tokens=500)
        if raw.startswith("ERROR"):
            bank = [
                {"q": "Which planet is known as the Red Planet?", "a": "mars"},
                {"q": "How many players are on a cricket team on field (per side)?", "a": "11"},
                {"q": "What does CPU stand for?", "a": "central processing unit"},
                {"q": "Which language has the most native speakers worldwide?", "a": "mandarin chinese"},
            ]
            return random.choice(bank)
        data = json.loads(raw[raw.index("{"): raw.rindex("}") + 1])
        return {"q": str(data.get("q", ""))[:220], "a": str(data.get("a", "")).lower()}
    except Exception:
        return None


@function_tool()
async def trivia_answer(answer: str) -> str:
    """Submit your answer to the current trivia question. Scores it, reveals the
    correct answer, and asks the next question until rounds finish."""
    if not _trivia["question"]:
        return "🎯 No trivia running. Say \"start trivia\" first!"
    ok = answer.lower().strip() in _trivia["answer"] or \
         (_trivia["answer"] in answer.lower().strip() and len(answer) < len(_trivia["answer"]) + 25)
    if ok:
        _trivia["score"] += 1
        verdict = "✅ Correct!"
    else:
        verdict = f"❌ Not quite — answer was: {_trivia['answer'].title()}"

    if _trivia["asked"] >= _trivia["rounds"]:
        s, r = _trivia["score"], _trivia["rounds"]
        _trivia.update({"question": "", "answer": "", "asked": 0})
        medal = "🏆" if s == r else "👍" if s >= r / 2 else "😅"
        return f"{verdict}\n\n🏁 GAME OVER — final score: {s}/{r} {medal}"

    nxt = await _make_question("mixed")
    if not nxt:
        return f"{verdict}\n⚠️ Couldn't fetch next question. Score so far: {_trivia['score']}/{_trivia['rounds']}"
    _trivia["question"], _trivia["answer"] = nxt["q"], nxt["a"].lower().strip()
    _trivia["asked"] += 1
    return f"{verdict}   (score {_trivia['score']}/{_trivia['rounds']})\n\nQ{_trivia['asked']}: {_trivia['question']}"
