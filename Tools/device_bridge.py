"""Zenith Device Bridge — REST + WebSocket server on the laptop.

Runs alongside the main agent (started automatically). Exposes every tool,
system stats, and live events over HTTP so the Flutter mobile app (or any
device on the same LAN) can control and monitor the laptop.

Endpoints:
  GET  /api/ping          → {"ok":true,"ts":...}  (heartbeat for phone)
  GET  /api/status        → full laptop dashboard data
  GET  /api/tools         → list of registered tool names
  POST /api/command       → {"tool":"name","args":{...}} executes & returns
  WS   /ws                → real-time event stream (status pushes)

Security: LAN-only by default; bind address configurable via ZENITH_BRIDGE_HOST.
"""

import asyncio
import json
import logging
import os
import socket
import time
from datetime import datetime
from typing import Any, Dict, Optional

from aiohttp import web, WSMsgType

logger = logging.getLogger(__name__)

PORT = int(os.getenv("ZENITH_BRIDGE_PORT", "8990"))
HOST = os.getenv("ZENITH_BRIDGE_HOST", "0.0.0.0")
_started_at = time.time()
_clients = set()          # active WebSocket connections
_agent_ref = {"session": None, "agent": None}


def set_bridge_context(agent=None, session=None):
    _agent_ref["agent"] = agent
    _agent_ref["session"] = session


# ------------------------------------------------------------- helpers ------

def _ip_address() -> str:
    """LAN IP (not loopback)."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def system_stats() -> Dict[str, Any]:
    import psutil
    vm = psutil.virtual_memory()
    du = psutil.disk_usage(os.path.abspath(os.sep))
    b = psutil.sensors_battery()
    return {
        "hostname": socket.gethostname(),
        "ip": _ip_address(),
        "uptime_s": int(time.time() - _started_at),
        "cpu_pct": psutil.cpu_percent(interval=0.5),
        "ram_pct": vm.percent,
        "ram_used_gb": round(vm.used / 2**30, 1),
        "ram_total_gb": round(vm.total / 2**30, 1),
        "disk_pct": du.percent,
        "disk_free_gb": round(du.free / 2**30, 1),
        "battery_pct": round(b.percent, 1) if b else None,
        "charging": b.power_plugged if b else None,
        "ts": datetime.now().isoformat(),
    }


async def broadcast(event: dict):
    """Push an event to all connected WebSocket clients (phone)."""
    dead = set()
    payload = json.dumps(event, default=str)
    for ws in _clients:
        try:
            await ws.send_str(payload)
        except Exception:
            dead.add(ws)
    _clients -= dead


# ------------------------------------------------------------ handlers -------

async def handle_ping(request: web.Request) -> web.Response:
    return web.json_response({"ok": True, "ts": time.time()})


async def handle_status(request: web.Request) -> web.Response:
    return web.json_response(system_stats())


async def handle_tools(request: web.Request) -> web.Response:
    """List all registered tool names."""
    src = Path(os.path.dirname(__file__)).parent / "agent.py"
    try:
        text = src.read_text(encoding="utf-8", errors="replace")
        import re
        m = re.search(r"tools = \[(.*?)\n\s*\]", text, re.S)
        names = []
        if m:
            for ln in m.group(1).splitlines():
                n = ln.strip().rstrip(",")
                if n and not n.startswith("#") and not n.startswith("//"):
                    names.append(n)
        return web.json_response({"tools": names, "count": len(names)})
    except Exception as e:
        return web.json_response({"tools": [], "error": str(e)})


async def handle_command(request: web.Request) -> web.Response:
    """Execute any Zenith tool by name with arguments.
    Body: {"tool":"get_laptop_health","args":{}}
    """
    try:
        body = await request.json()
        tool_name = body.get("tool", "").strip()
        args = body.get("args", {}) or {}

        if not tool_name:
            return web.json_response({"error": "tool name required"}, status=400)

        # Import agent module to access tools
        import sys
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
        import agent as _agent_mod

        # Find the tool function
        tool_fn = None
        for item in _agent_mod.UltimateAdvancedZenith.__init__.__code__.co_consts:
            pass  # skip — use direct lookup below

        # Direct approach: search module namespace
        found = getattr(_agent_mod, tool_name, None)
        if found is None:
            # Try Tools package
            import Tools
            found = getattr(Tools, tool_name, None)
        if found is None:
            # Search sub-modules
            import importlib, pkgutil
            import Tools as T
            for imp in pkgutil.iter_modules(T.__path__):
                try:
                    mod = importlib.import_module(f"Tools.{imp.name}")
                    fn = getattr(mod, tool_name, None)
                    if fn is not None:
                        found = fn
                        break
                except Exception:
                    continue

        if found is None:
            return web.json_response(
                {"error": f"Tool '{tool_name}' not found"}, status=404)

        # Call it
        if asyncio.iscoroutinefunction(found.__wrapped__ if hasattr(found, '__wrapped__') else found):
            result = await found(**args)
        else:
            result = await asyncio.to_thread(found, **args) if not asyncio.iscoroutine(found) else await found(**args)

        return web.json_response({
            "ok": True,
            "tool": tool_name,
            "result": str(result)[:3000],
        })
    except Exception as e:
        return web.json_response({"error": str(e)[:500]}, status=500)


async def handle_ws(request: web.Request) -> web.WebSocketResponse:
    """WebSocket for real-time pushes AND bidirectional phone commands."""
    ws = web.WebSocketResponse()
    await ws.prepare(request)
    _clients.add(ws)
    try:
        # Send initial status
        await ws.send_str(json.dumps({"event": "connected", **system_stats()}))
        async for msg in ws:
            if msg.type == WSMsgType.TEXT:
                data = json.loads(msg.data)
                if data.get("type") == "ping":
                    await ws.send_str(json.dumps({"event": "pong", "ts": time.time()}))
                elif data.get("type") == "phone_tool_result":
                    # Phone sent back a result from a tool we requested
                    _phone_results[data.get("request_id", "")] = data.get("result", "")
                elif data.get("type") == "phone_status":
                    # Phone reports its own status (battery, etc.)
                    _phone_status.update(data.get("data", {}))
            elif msg.type == WSMsgType.ERROR:
                break
    finally:
        _clients.discard(ws)
    return ws


_phone_results: Dict[str, str] = {}
_phone_status: Dict[str, Any] = {}


async def send_to_phone(tool: str, args: dict = None, timeout: float = 10.0) -> str:
    """Send a command TO the connected phone via WebSocket and wait for result."""
    if not _clients:
        return "❌ No phone connected via bridge."
    request_id = f"req_{int(time.time()*1000)}"
    payload = {"type": "phone_tool", "tool": tool, "args": args or {}, "request_id": request_id}
    await broadcast(payload)

    # Wait for result
    deadline = time.time() + timeout
    while time.time() < deadline:
        if request_id in _phone_results:
            result = _phone_results.pop(request_id)
            return result
        await asyncio.sleep(0.5)
    return "⏱️ Phone didn't respond in time."


async def periodic_broadcast():
    """Every 30s, push system stats to all connected phones."""
    while True:
        if _clients:
            await broadcast({"event": "stats", **system_stats()})
        await asyncio.sleep(30)


# ------------------------------------------------------------ app factory ----

def create_app() -> web.Application:
    app = web.Application()
    app.router.add_get("/api/ping", handle_ping)
    app.router.add_get("/api/status", handle_status)
    app.router.add_get("/api/tools", handle_tools)
    app.router.add_post("/api/command", handle_command)
    app.router.add_get("/ws", handle_ws)
    return app


async def start_bridge_server(agent=None, session=None):
    """Start the bridge server + periodic broadcaster."""
    set_bridge_context(agent, session)
    app = create_app()
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, HOST, PORT)
    try:
        await site.start()
        ip = _ip_address()
        print(f"🌐 DEVICE BRIDGE: http://{ip}:{PORT} (phone connects here)")
        print(f"   Status: http://{ip}:{PORT}/api/status")
        print(f"   Ping:   http://{ip}:{PORT}/api/ping")
        asyncio.create_task(periodic_broadcast())
    except OSError as e:
        if e.errno == 10048:
            print(f"⚠️ Port {PORT} already in use — bridge may already be running.")
        else:
            print(f"⚠️ Bridge server failed: {e}")


from pathlib import Path  # noqa: E402