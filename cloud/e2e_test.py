"""Local E2E test for the cloud brain: fake laptop + phone WS clients."""
import asyncio
import json
import os
import sys

import httpx
import websockets

BASE = "http://127.0.0.1:8123"
WS = "ws://127.0.0.1:8123/ws"
PIN = "test123"


async def fake_laptop():
    async def _run(ws):
        await ws.send(json.dumps({"type": "heartbeat"}))
        while True:
            data = json.loads(await ws.recv())
            if data.get("type") == "tool_exec":
                tool = data["tool"]
                if "smart" in tool or "disk" in tool:
                    out = "SMART status: all 3 drives OK"
                else:
                    out = f"laptop executed {tool}"
                await ws.send(json.dumps({
                    "type": "result", "req_id": data["req_id"],
                    "ok": True, "output": out,
                }))

    async with websockets.connect(f"{WS}?role=laptop&pin={PIN}") as ws:
        await _run(ws)


async def fake_phone():
    async def _run(ws):
        while True:
            data = json.loads(await ws.recv())
            if data.get("type") == "tool_exec":
                await ws.send(json.dumps({
                    "type": "result", "req_id": data["req_id"],
                    "ok": True, "output": f"phone executed {data['tool']}",
                }))

    async with websockets.connect(f"{WS}?role=phone&pin={PIN}") as ws:
        await _run(ws)


async def cmd(text, session=None, reply=None):
    body = {"command": text, "pin": PIN} if reply is None else {
        "session": session, "text": reply, "pin": PIN}
    url = f"{BASE}/api/command" if reply is None else f"{BASE}/api/respond"
    async with httpx.AsyncClient(timeout=60) as c:
        r = await c.post(url, json=body)
        return r.json()


async def main():
    results = []

    def check(name, cond, extra=""):
        results.append((name, cond))
        print(f"{'PASS' if cond else 'FAIL'} - {name} {extra}")

    lt = None
    if "--real-laptop" not in sys.argv:
        lt = asyncio.create_task(fake_laptop())
    pt = asyncio.create_task(fake_phone())
    await asyncio.sleep(2)

    st = (await httpx.AsyncClient().get(f"{BASE}/api/status?pin={PIN}")).json()
    check("both devices online", st["laptop"]["online"] and st["phone_connected"], str(st))

    r1 = await cmd("what is my laptop disk health")
    print("   R1:", json.dumps(r1)[:160])
    check("laptop tool -> confirm flow", r1.get("type") == "confirm", "")
    check("reply mentions Laptop based", "Laptop based" in r1.get("reply", ""))

    r2 = await cmd(None, session=r1.get("session"), reply="yes do it")
    print("   R2:", json.dumps(r2)[:200])
    check("confirmed -> executed on laptop",
          "SMART" in r2.get("reply", "") or "OK" in r2.get("reply", ""))

    r3 = await cmd("turn on my flashlight")
    print("   R3:", json.dumps(r3)[:160])
    check("phone flashlight executed", "flashlight" in r3.get("reply", "").lower())

    r4 = await cmd("hey who are you")
    print("   R4:", json.dumps(r4)[:120])
    check("general chat works", len(r4.get("reply", "")) > 5)

    if lt:
        lt.cancel()
    pt.cancel()
    fails = [n for n, ok in results if not ok]
    print(f"\n{len(results) - len(fails)}/{len(results)} PASSED")
    sys.exit(1 if fails else 0)


asyncio.run(main())
