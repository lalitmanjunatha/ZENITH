"""Provider-agnostic LLM client for Zenith's code-editing and memory tools.

Pick a provider with the ZENITH_LLM_PROVIDER env var:
  groq (default), openai, google, mistral, nvidia

Each provider's API key is read from its standard env var
(GROQ_API_KEY / OPENAI_API_KEY / GOOGLE_API_KEY / MISTRAL_API_KEY /
NVIDIA_API_KEY). dotenv is loaded here so the module works standalone.
"""

import asyncio
import aiohttp
import logging
import os

try:
    from dotenv import load_dotenv

    load_dotenv()
except Exception:
    pass

logger = logging.getLogger(__name__)

PROVIDERS = {
    "groq": {
        "key": "GROQ_API_KEY",
        "base": "https://api.groq.com/openai/v1/chat/completions",
        "model": os.getenv("GROQ_MODEL", "openai/gpt-oss-120b"),
    },
    "openai": {
        "key": "OPENAI_API_KEY",
        "base": "https://api.openai.com/v1/chat/completions",
        "model": "gpt-4o-mini",
    },
    "google": {
        "key": "GOOGLE_API_KEY",
        "base": "https://generativelanguage.googleapis.com/v1beta",
        "model": "gemini-2.0-flash",
    },
    "mistral": {
        "key": "MISTRAL_API_KEY",
        "base": "https://api.mistral.ai/v1/chat/completions",
        "model": "mistral-large-latest",
    },
    "nvidia": {
        "key": "NVIDIA_API_KEY",
        "base": "https://integrate.api.nvidia.com/v1/chat/completions",
        "model": "meta/llama-3.1-8b-instruct",
    },
}

DEFAULT_PROVIDER = "groq"


def current_provider() -> str:
    return os.getenv("ZENITH_LLM_PROVIDER", DEFAULT_PROVIDER).strip().lower()


def resolve_provider(name: str = None) -> dict:
    name = (name or current_provider()).lower()
    if name not in PROVIDERS:
        logger.warning(f"Unknown provider {name!r}; falling back to {DEFAULT_PROVIDER}")
        name = DEFAULT_PROVIDER
    return PROVIDERS[name]


def _api_key(cfg: dict) -> str:
    return os.getenv(cfg["key"], "").strip()


def _build_messages(prompt: str, system: str) -> list:
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    return messages


def _google_payload(cfg: dict, prompt: str, system: str, temperature: float, max_tokens: int) -> tuple:
    """Google uses a different request shape (generateContent)."""
    contents = []
    if system:
        contents.append({"role": "user", "parts": [{"text": system}]})
    contents.append({"role": "user", "parts": [{"text": prompt}]})
    url = f'{cfg["base"]}/models/{cfg["model"]}:generateContent'
    body = {
        "contents": contents,
        "generationConfig": {
            "temperature": temperature,
            "maxOutputTokens": max_tokens,
        },
    }
    return url, {"x-goog-api-key": _api_key(cfg)}, body


def _extract_text(data: dict, cfg: dict) -> str:
    try:
        if "candidates" in data:
            return data["candidates"][0]["content"]["parts"][0]["text"].strip()
        return (
            data.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
        )
    except Exception:
        return ""


async def chat_complete(
    prompt: str,
    system: str = "",
    provider: str = None,
    model: str = None,
    temperature: float = 0.2,
    max_tokens: int = 6000,
) -> str:
    """Async completion over any supported provider. Returns text or 'ERROR: ...'."""
    pname = (provider or current_provider()).lower()
    cfg = dict(resolve_provider(pname))
    if model:
        cfg["model"] = model
    key = _api_key(cfg)
    if not key:
        return f"ERROR: {cfg['key']} not set in environment"

    try:
        async with aiohttp.ClientSession() as session:
            if pname == "google":
                url, headers, body = _google_payload(cfg, prompt, system, temperature, max_tokens)
            else:
                url = cfg["base"]
                headers = {
                    "Authorization": f"Bearer {key}",
                    "Content-Type": "application/json",
                }
                body = {
                    "model": cfg["model"],
                    "messages": _build_messages(prompt, system),
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                }
            async with session.post(url, headers=headers, json=body, timeout=120) as res:
                data = await res.json()
                if res.status != 200:
                    return f"ERROR: {cfg['model']} API {res.status}: {data}"
                text = _extract_text(data, cfg)
                return text if text else "ERROR: empty response"
    except Exception as e:
        return f"ERROR: {e}"


def chat_complete_sync(
    prompt: str,
    system: str = "",
    provider: str = None,
    model: str = None,
    temperature: float = 0.2,
    max_tokens: int = 2000,
) -> str:
    """Synchronous completion (requests) — safe to call from a background thread."""
    import requests

    pname = (provider or current_provider()).lower()
    cfg = dict(resolve_provider(pname))
    if model:
        cfg["model"] = model
    key = _api_key(cfg)

    if not key:
        return f"ERROR: {cfg['key']} not set in environment"

    try:
        if pname == "google":
            url, headers, body = _google_payload(cfg, prompt, system, temperature, max_tokens)
        else:
            url = cfg["base"]
            headers = {
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
            }
            body = {
                "model": cfg["model"],
                "messages": _build_messages(prompt, system),
                "temperature": temperature,
                "max_tokens": max_tokens,
            }
        res = requests.post(url, headers=headers, json=body, timeout=90)
        if res.status_code != 200:
            return f"ERROR: {cfg['model']} API {res.status_code}: {res.text}"
        text = _extract_text(res.json(), cfg)
        return text if text else "ERROR: empty response"
    except Exception as e:
        return f"ERROR: {e}"


# Backwards-compatible alias.
async def groq_chat(prompt, system="", model=None, temperature=0.2, max_tokens=6000):
    return await chat_complete(
        prompt, system=system, provider="groq", model=model,
        temperature=temperature, max_tokens=max_tokens,
    )