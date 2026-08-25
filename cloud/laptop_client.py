"""Zenith Laptop Client Daemon.

Connects OUT to the Zenith Cloud Brain (render.com) over WebSocket - no port
forwarding needed. Executes laptop-class Zenith tools when the brain commands
it, using the same proven tool-resolution strategy as Tools/device_bridge.py.

Env vars:
  ZENITH_CLOUD_URL   e.g. wss://zenith-cloud-brain.onrender.com/ws
  BRIDGE_PIN         must match the Render env var

Run:  python cloud/laptop_client.py
"""

import asyncio
import json
import os
import sys
import time
from pathlib import Path

import websockets

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

CLOUD_URL = os.environ.get("ZENITH_CLOUD_URL", "ws://127.0.0.1:8123/ws")
PIN = os.environ.get("BRIDGE_PIN", "")


def resolve_tool(tool_name: str):
    """Same 3-step lookup used by the local LAN bridge (proven working)."""
    import agent as _agent_mod
    found = getattr(_agent_mod, tool_name, None)
    if found is not None:
        return found
    try:
        import Tools
        found = getattr(Tools, tool_name, None)
        if found is not None:
            return found
    except Exception:
        pass
    import importlib
    import pkgutil
    import Tools as T
    for imp in pkgutil.iter_modules(T.__path__):
        try:
            mod = importlib.import_module(f"Tools.{imp.name}")
            fn = getattr(mod, tool_name, None)
            if fn is not None:
                return fn
        except Exception:
            continue
    return None


async def run_tool(tool_name: str, args: dict) -> dict:
    try:
        found = resolve_tool(tool_name)
        if found is None:
            return {
                "ok": False,
                "output": f"Unknown laptop tool '{tool_name}'. Closest: "
                          f"get_laptop_health, battery_coach, daily_threat_board, "
                          f"damage_report.",
            }
        target = getattr(found, "__wrapped__", found)
        if asyncio.iscoroutinefunction(target):
            result = await found(**args)
        else:
            result = await asyncio.to_thread(found, **args)
        return {"ok": True, "output": str(result)[:3000]}
    except Exception as e:
        return {"ok": False, "output": f"{type(e).__name__}: {e}"[:500]}


async def handle(ws):
    while True:
        raw = await ws.recv()
        data = json.loads(raw)
        mtype = data.get("type")
        if mtype == "tool_exec":
            req_id = data.get("req_id", "")
            result = await run_tool(data.get("tool", ""), data.get("args") or {})
            await ws.send(json.dumps({
                "type": "result",
                "req_id": req_id,
                "ok": result["ok"],
                "output": result["output"],
            }))
        elif mtype == "ping":
            await ws.send(json.dumps({"type": "pong"}))


async def heartbeat(ws):
    while True:
        await asyncio.sleep(20)
        await ws.send(json.dumps({"type": "heartbeat"}))


async def session():
    from urllib.parse import quote
    sep = "&" if "?" in CLOUD_URL else "?"
    url = f"{CLOUD_URL}{sep}role=laptop&pin={quote(PIN)}"
    async with websockets.connect(url, open_timeout=90) as ws:
        hello = json.loads(await ws.recv())
        print(f"[laptop-client] connected as {hello.get('role')} "
              f"to {CLOUD_URL}", flush=True)
        hb = asyncio.create_task(heartbeat(ws))
        try:
            await handle(ws)
        finally:
            hb.cancel()


async def main():
    delay = 2.0
    while True:
        try:
            await session()
            delay = 2.0
        except asyncio.CancelledError:
            raise
        except Exception as e:
            print(f"[laptop-client] {type(e).__name__}: {e} "
                  f"- retrying in {delay:.0f}s", flush=True)
            await asyncio.sleep(delay)
            delay = min(delay * 1.6, 30.0)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("[laptop-client] stopped")
