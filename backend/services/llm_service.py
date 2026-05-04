import json
from typing import AsyncGenerator

import httpx

from config import settings


def _get_headers() -> dict:
    return {
        "Authorization": f"Bearer {settings.LLM_API_KEY}",
        "Content-Type": "application/json",
    }


async def chat_completion(
    messages: list[dict],
    model: str | None = None,
    tools: list[dict] | None = None,
) -> dict:
    """Non-streaming chat completion, supports function/tool calling."""
    model = model or settings.LLM_MODEL
    url = f"{settings.LLM_BASE_URL}/chat/completions"
    payload: dict = {
        "model": model,
        "messages": messages,
    }
    if tools:
        payload["tools"] = tools
        payload["tool_choice"] = "auto"

    async with httpx.AsyncClient(timeout=120.0) as client:
        resp = await client.post(url, json=payload, headers=_get_headers())
        resp.raise_for_status()
        return resp.json()


async def stream_chat_completion(
    messages: list[dict], model: str | None = None
) -> AsyncGenerator[str, None]:
    """Streaming chat completion, yields SSE data chunks."""
    model = model or settings.LLM_MODEL
    url = f"{settings.LLM_BASE_URL}/chat/completions"
    payload = {
        "model": model,
        "messages": messages,
        "stream": True,
    }

    async with httpx.AsyncClient(timeout=120.0) as client:
        async with client.stream("POST", url, json=payload, headers=_get_headers()) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if not line.startswith("data: "):
                    continue
                data_str = line[len("data: "):]
                if data_str.strip() == "[DONE]":
                    yield json.dumps({"content": "", "done": True})
                    break
                try:
                    chunk = json.loads(data_str)
                    delta = chunk["choices"][0].get("delta", {})
                    content = delta.get("content", "")
                    if content:
                        yield json.dumps({"content": content, "done": False})
                except (json.JSONDecodeError, KeyError, IndexError):
                    continue


async def get_available_models() -> list[str]:
    url = f"{settings.LLM_BASE_URL}/models"
    headers = {"Authorization": f"Bearer {settings.LLM_API_KEY}"}
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(url, headers=headers)
            resp.raise_for_status()
            data = resp.json()
            return [m["id"] for m in data.get("data", [])]
    except Exception:
        return [settings.LLM_MODEL]
