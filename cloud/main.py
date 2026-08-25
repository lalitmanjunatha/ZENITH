"""Zenith Cloud Brain - FastAPI service for render.com.

Hub between the phone app (wake word + STT + native phone tools) and the
laptop client daemon (executes Zenith's laptop tools). Routes every command
through Groq, tracks which devices are online, and runs the
"Laptop based tool -> status -> ask to run" confirmation flow.
"""

import asyncio
import json
import os
import time
import uuid
from typing import Dict, Optional

import httpx
from fastapi import FastAPI, Header, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from registry import PHONE_TOOLS, prompt_block, tool_class

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
BRIDGE_PIN = os.environ.get("BRIDGE_PIN", "")
MODEL_PRIMARY = os.environ.get("ZENITH_MODEL", "openai/gpt-oss-120b")
MODEL_FALLBACK = "openai/gpt-oss-20b"
CONFIRM_TTL = 60.0

app = FastAPI(title="Zenith Cloud Brain")


class Hub:
    def __init__(self):
        self.phone: Optional[WebSocket] = None
        self.laptop: Optional[WebSocket] = None
        self.laptop_last_seen: float = 0.0
        self.phone_last_seen: float = 0.0

    def laptop_status(self) -> dict:
        online = self.laptop is not None
        info = {"online": online}
        if self.laptop_last_seen:
            info["last_seen_sec_ago"] = int(time.time() - self.laptop_last_seen)
        return info


HUB = Hub()
RESULTS: Dict[str, dict] = {}
PENDING: Dict[str, dict] = {}


def pin_ok(pin: str) -> bool:
    return (not BRIDGE_PIN) or (pin == BRIDGE_PIN)


async def wait_result(req_id: str, timeout: float = 30.0) -> Optional[dict]:
    end = time.time() + timeout
    while time.time() < end:
        if req_id in RESULTS:
            return RESULTS.pop(req_id)
        await asyncio.sleep(0.15)
    return None


async def dispatch(role: str, tool: str, args: dict, timeout: float = 30.0) -> dict:
    ws = getattr(HUB, role)
    if ws is None:
        raise RuntimeError(f"{role}_offline")
    req_id = f"req_{uuid.uuid4().hex[:10]}"
    payload = {"type": "tool_exec", "req_id": req_id, "tool": tool, "args": args or {}}
    await ws.send_text(json.dumps(payload))
    result = await wait_result(req_id, timeout)
    if result is None:
        return {"ok": False, "output": f"⏱️ {role} did not respond in time."}
    return result


async def groq_chat(messages, model: str) -> str:
    async with httpx.AsyncClient(timeout=40) as client:
        resp = await client.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
            json={
                "model": model,
                "messages": messages,
                "temperature": 0.3,
                "max_tokens": 500,
            },
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]


SYSTEM_PROMPT = """You are ZENITH, the user's personal JARVIS-style AI running in the cloud.
Decide what the user's command needs. Respond with STRICT JSON only, no markdown:

{"reply": "<short spoken-style answer>", "tool": "<tool name or null>", "args": {}, "device": "phone|laptop|none|status"}

Rules:
- device=status means the user asks about laptop/phone connectivity; set tool=null and put a brief line in reply. The system appends live status.
- device=none for general chat/questions needing no tool.
- For any LAPTOP-class intent, pick the closest real Zenith laptop tool name if you know it, else use tool=null and say it is laptop based.
"""
SYSTEM_PROMPT += prompt_block()


def parse_decision(raw: str) -> dict:
    txt = raw.strip()
    if "```" in txt:
        parts = txt.split("```")
        for p in parts:
            p2 = p.removeprefix("json").strip()
            if p2.startswith("{"):
                txt = p2
                break
    start, end = txt.find("{"), txt.rfind("}")
    if start == -1 or end <= start:
        return {"reply": raw.strip()[:400], "tool": None, "args": {}, "device": "none"}
    try:
        d = json.loads(txt[start : end + 1])
    except json.JSONDecodeError:
        return {"reply": raw.strip()[:400], "tool": None, "args": {}, "device": "none"}
    d.setdefault("reply", "")
    d.setdefault("tool", None)
    d.setdefault("args", {})
    d.setdefault("device", "none")
    return d


class CommandIn(BaseModel):
    command: str
    pin: str = ""
    history: list = []


@app.get("/")
async def root():
    return {"service": "zenith-cloud-brain", "status": "alive"}


@app.get("/api/ping")
async def ping():
    return {"ok": True}


@app.get("/api/status")
async def status(pin: str = ""):
    if not pin_ok(pin):
        raise HTTPException(401, "bad PIN")
    return {
        "laptop": HUB.laptop_status(),
        "phone_connected": HUB.phone is not None,
        "pending_confirmations": len(PENDING),
        "phone_tools": len(PHONE_TOOLS),
    }


@app.get("/api/tools")
async def tools():
    return {"phone_tools": sorted(PHONE_TOOLS.keys())}


@app.post("/api/command")
async def command(cmd: CommandIn):
    if not pin_ok(cmd.pin):
        raise HTTPException(401, "bad PIN")
    if not GROQ_API_KEY:
        return {"type": "text", "reply": "⚠️ GROQ_API_KEY not set on the server yet."}

    messages = [{"role": "system", "content": SYSTEM_PROMPT}] + cmd.history[-8:]
    messages.append({"role": "user", "content": cmd.command})

    decision = None
    for model in (MODEL_PRIMARY, MODEL_FALLBACK):
        try:
            raw = await groq_chat(messages, model)
            decision = parse_decision(raw)
            break
        except Exception:
            continue
    if decision is None:
        return {"type": "text", "reply": "🧠 Brain hiccup — couldn't reach Groq. Try again."}

    tool = decision.get("tool")
    args = decision.get("args") or {}
    device = decision.get("device") or tool_class(tool)

    if not tool:
        extra = ""
        if decision.get("device") == "status":
            ls = HUB.laptop_status()
            extra = (
                f"\n📊 Laptop: {'ONLINE ✅' if ls['online'] else 'OFFLINE ❌'}"
                + (f" (last seen {ls['last_seen_sec_ago']}s ago)" if not ls['online'] and 'last_seen_sec_ago' in ls else "")
                + f" | Phone: {'connected ✅' if HUB.phone is not None else 'not connected ❌'}"
            )
        return {"type": "text", "reply": decision["reply"] + extra}

    klass = tool_class(tool)

    if klass == "phone":
        if HUB.phone is None:
            return {"type": "text", "reply": "📱 Phone isn't connected to me right now. Open the Zenith app."}
        result = await dispatch("phone", tool, args)
        prefix = "" if result.get("ok") else "⚠️ "
        return {"type": "text", "reply": prefix + result.get("output", "done")}

    ls = HUB.laptop_status()
    if not ls["online"]:
        ago = ls.get("last_seen_sec_ago")
        seen = f" Last seen {ago // 60} min ago." if ago and ago >= 60 else ""
        return {
            "type": "text",
            "reply": f"Laptop based tool. ❌ Laptop is offline right now.{seen} Wake it up and I'll retry.",
        }

    session = uuid.uuid4().hex[:12]
    PENDING[session] = {"tool": tool, "args": args, "ts": time.time()}
    return {
        "type": "confirm",
        "session": session,
        "reply": (
            f"Laptop based tool. 📊 Laptop is ONLINE. "
            f"Should I perform '{tool}' on the laptop?"
        ),
    }


class RespondIn(BaseModel):
    session: str
    text: str
    pin: str = ""


@app.post("/api/respond")
async def respond(r: RespondIn):
    if not pin_ok(r.pin):
        raise HTTPException(401, "bad PIN")
    pend = PENDING.pop(r.session, None)
    if pend is None:
        return {"type": "text", "reply": "That confirmation expired. Say the command again."}

    yes = any(w in r.text.lower() for w in ("yes", "yeah", "do it", "go ahead", "sure", "confirm", "run"))
    if not yes:
        return {"type": "text", "reply": "Cancelled. 👍"}

    if HUB.laptop is None:
        return {"type": "text", "reply": "❌ Laptop dropped offline before I could run it."}
    result = await dispatch("laptop", pend["tool"], pend["args"], timeout=60)
    prefix = "" if result.get("ok") else "⚠️ "
    return {"type": "text", "reply": prefix + result.get("output", "done")}


@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket, role: str = "phone", pin: str = ""):
    if not pin_ok(pin):
        await ws.close(code=4001)
        return
    await ws.accept()
    if role == "laptop":
        HUB.laptop = ws
        HUB.laptop_last_seen = time.time()
    else:
        HUB.phone = ws
        HUB.phone_last_seen = time.time()
    await ws.send_text(json.dumps({"type": "hello", "role": role}))
    try:
        while True:
            msg = await ws.receive_text()
            data = json.loads(msg)
            mtype = data.get("type")
            if role == "laptop":
                HUB.laptop_last_seen = time.time()
            else:
                HUB.phone_last_seen = time.time()
            if mtype == "result":
                RESULTS[data.get("req_id", "")] = {
                    "ok": data.get("ok", False),
                    "output": data.get("output", ""),
                }
            elif mtype == "heartbeat":
                await ws.send_text(json.dumps({"type": "pong"}))
    except WebSocketDisconnect:
        pass
    finally:
        if getattr(HUB, role) is ws:
            setattr(HUB, role, None)


@app.on_event("startup")
async def cleanup_loop():
    async def sweeper():
        while True:
            now = time.time()
            expired = [s for s, p in PENDING.items() if now - p["ts"] > CONFIRM_TTL]
            for s in expired:
                PENDING.pop(s, None)
            await asyncio.sleep(5)

    asyncio.create_task(sweeper())
