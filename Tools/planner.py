"""Autonomous multi-step goal executor for Zenith.

Given a user goal, this tool loops: an LLM decides the next concrete
step (a tool call), we execute it, feed the result back, and repeat until
the LLM says the goal is done (capped at max_steps). Only a safe toolset
is callable by default; extend with ZENITH_AUTONOMOUS_ALLOW in .env.
"""

import asyncio
import json
import logging
import os

from livekit.agents import function_tool

from ._llm_client import chat_complete

logger = logging.getLogger(__name__)


def _tool_registry() -> dict:
    reg: dict = {}

    def load(module_path, *names):
        try:
            mod = __import__(module_path, fromlist=list(names))
        except Exception as e:
            logger.warning(f"planner import {module_path}: {e}")
            return
        for n in names:
            if hasattr(mod, n):
                reg[n] = getattr(mod, n)

    load("Tools.memory_tools", "recall_memory", "what_do_you_remember",
         "get_memory_stats", "train_from_conversations", "store_memory", "memory_status")
    load("Tools.knowledge_search", "search_knowledge", "ask_about_my_data", "index_files")
    load("Tools.data_tools", "get_knowledge_stats", "search_my_files", "analyze_dataset")
    load("Tools.news_provider", "get_top_news")
    load("Tools.search_web", "search_web")
    load("Tools.self_edit", "read_source_file")
    load("Tools.time_volume_bright", "get_time_info")

    extra = [n.strip() for n in os.getenv("ZENITH_AUTONOMOUS_ALLOW", "").split(",") if n.strip()]
    for name in extra:
        if name not in reg:
            # Try a last-resort import from any Tools module by name.
            try:
                top = __import__(name)
                reg[name] = getattr(top, name)
            except Exception:
                logger.warning(f"Could not auto-register extra tool: {name}")
    return reg


def _parse_json(reply: str) -> dict:
    reply = reply.strip()
    if reply.startswith("```"):
        reply = "\n".join(reply.split("\n")[1:]).replace("```", "")
    s, e = reply.find("{"), reply.rfind("}")
    if s == -1 or e == -1:
        return {"done": True, "tool": None, "params": {}}
    try:
        return json.loads(reply[s:e + 1])
    except Exception:
        return {"done": True, "tool": None, "params": {}}


async def _run_step(reg: dict, step: dict) -> str:
    name = step.get("tool")
    params = step.get("params") or {}
    if not name or name not in reg:
        return "No executable tool for that step; pick a different step."
    fn = reg[name]
    try:
        if asyncio.iscoroutinefunction(fn):
            result = await fn(**params)
        else:
            result = fn(**params)
        return str(result)[:2000]
    except TypeError as e:
        return f"Bad params for {name}: {e}"
    except Exception as e:
        return f"Tool {name} failed: {e}"


def _record(mem, goal: str, i: int, step: dict, result: str) -> None:
    try:
        mem.record_fact(
            f"Goal: {goal} | step {i}: {step.get('tool')} -> {result[:200]}",
            category="goal", source="goal",
        )
    except Exception:
        pass


@function_tool()
async def execute_goal(goal: str, max_steps: int = 8) -> str:
    """Work autonomously toward a multi-step goal.

    Args:
        goal: What the user wants Zenith to accomplish.
        max_steps: Maximum steps before the plan ends.
    """
    reg = _tool_registry()
    try:
        from memory_manager import MemoryManager
        mem = MemoryManager()
    except Exception:
        mem = None

    system = (
        "You are Zenith's autonomous planner. Given a user goal, decide ONE next "
        "concrete tool step and reply with STRICT JSON only: "
        '{"tool":"<name>","params":{...},"done":false}. When the goal is complete, '
        'reply {"done":true,"tool":null,"params":{}}. Never return prose.'
    )
    tools_desc = (
        "Choose from: search_web(query), search_knowledge(query), "
        "ask_about_my_data(question), get_knowledge_stats(), search_my_files(query), "
        "get_top_news(), get_memory_stats(), recall_memory(query), "
        "what_do_you_remember(), get_time(), read_source_file(file_path).\n"
    )

    history: list = []
    summary: list = []
    reached_done = False

    for i in range(1, max_steps + 1):
        hist = ("\n".join(history[-10:])) or "(no steps yet)"
        prompt = (
            f"GOAL: {goal}\n\n"
            f"{tools_desc}"
            f"STEP HISTORY:\n{hist}\n\n"
            "Next step as JSON:"
        )
        reply = await chat_complete(prompt, system=system, temperature=0.7, max_tokens=500)
        step = _parse_json(reply)
        if step.get("done"):
            reached_done = True
            summary.append("✅ Goal achieved.")
            break
        result = await _run_step(reg, step)
        history.append(f"Step {i}: {step.get('tool')} -> {result[:400]}")
        if mem:
            _record(mem, goal, i, step, result)
        summary.append(f"Step {i}: {step.get('tool')} -> {result[:150]}")

    if not reached_done:
        summary.append(f"⏹️ Stopped after {max_steps} steps (say continue to keep going).")

    if mem:
        try:
            mem.flush_vectors()
        except Exception:
            pass
    return "🗂️ Report:\n" + "\n".join(summary[-15:])