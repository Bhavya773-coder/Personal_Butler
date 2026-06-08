"""
JARVIS Core — Ollama LLM Client

Async streaming chat with local Ollama API.
Supports token-by-token streaming for real-time UI updates.
"""

import httpx
import json
import os
import logging
from typing import AsyncGenerator

logger = logging.getLogger("jarvis.ollama")

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2")


async def check_ollama_status() -> dict:
    """Check if Ollama is running and the model is available."""
    status = {"running": False, "model_available": False, "error": None}

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            # Check if Ollama is running
            resp = await client.get(f"{OLLAMA_HOST}/api/tags")
            if resp.status_code == 200:
                status["running"] = True
                data = resp.json()
                models = [m["name"] for m in data.get("models", [])]
                # Check for model with or without tag suffix
                model_base = OLLAMA_MODEL.split(":")[0]
                status["model_available"] = any(
                    m == OLLAMA_MODEL or m.startswith(f"{model_base}:") or m == model_base
                    for m in models
                )
                if not status["model_available"]:
                    status["error"] = f"Model '{OLLAMA_MODEL}' not found. Run: ollama pull {OLLAMA_MODEL}"
                    status["available_models"] = models
            else:
                status["error"] = "Ollama returned unexpected status."
    except httpx.ConnectError:
        status["error"] = "Ollama is not running. Start Ollama or run: ollama serve"
    except Exception as e:
        status["error"] = f"Failed to connect to Ollama: {str(e)}"

    return status


async def chat_stream(
    messages: list[dict],
    model: str | None = None,
    temperature: float = 0.7,
) -> AsyncGenerator[str, None]:
    """
    Stream chat completion from Ollama, yielding tokens as they arrive.
    
    Args:
        messages: List of {"role": "...", "content": "..."} message dicts
        model: Override model name (defaults to env OLLAMA_MODEL)
        temperature: Sampling temperature
    
    Yields:
        Individual text tokens as strings
    """
    target_model = model or OLLAMA_MODEL

    payload = {
        "model": target_model,
        "messages": messages,
        "stream": True,
        "options": {
            "temperature": temperature,
        },
    }

    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(300.0, connect=10.0)) as client:
            async with client.stream(
                "POST",
                f"{OLLAMA_HOST}/api/chat",
                json=payload,
            ) as response:
                if response.status_code != 200:
                    error_text = ""
                    async for chunk in response.aiter_text():
                        error_text += chunk
                    logger.error(f"Ollama error {response.status_code}: {error_text}")
                    yield f"[Error: Ollama returned status {response.status_code}]"
                    return

                async for line in response.aiter_lines():
                    if not line.strip():
                        continue
                    try:
                        data = json.loads(line)
                        token = data.get("message", {}).get("content", "")
                        if token:
                            yield token
                        if data.get("done", False):
                            return
                    except json.JSONDecodeError:
                        continue

    except httpx.ConnectError:
        yield "[Error: Cannot connect to Ollama. Run: ollama serve]"
    except Exception as e:
        logger.error(f"Ollama streaming error: {e}")
        yield f"[Error: {str(e)}]"


async def chat_complete(
    messages: list[dict],
    model: str | None = None,
    temperature: float = 0.7,
) -> str:
    """Non-streaming chat completion. Returns full response text."""
    target_model = model or OLLAMA_MODEL

    payload = {
        "model": target_model,
        "messages": messages,
        "stream": False,
        "options": {
            "temperature": temperature,
        },
    }

    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(120.0, connect=10.0)) as client:
            resp = await client.post(f"{OLLAMA_HOST}/api/chat", json=payload)
            if resp.status_code == 200:
                data = resp.json()
                return data.get("message", {}).get("content", "")
            else:
                return f"[Error: Ollama returned status {resp.status_code}]"
    except httpx.ConnectError:
        return "[Error: Cannot connect to Ollama. Run: ollama serve]"
    except Exception as e:
        return f"[Error: {str(e)}]"
