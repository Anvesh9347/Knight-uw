"""Thin, dependency-light LLM client. Real calls only: failures raise LLMError and are shown in the UI.

Providers (LLM_PROVIDER):
    gemini             -> Google Gemini generateContent API (GEMINI_API_KEY)
  anthropic          -> Anthropic Messages API (ANTHROPIC_API_KEY)
  openai_compatible  -> any /chat/completions server (OPENAI_BASE_URL, OPENAI_API_KEY) e.g. OpenAI, Groq, LM Studio
  ollama             -> local model via Ollama (OLLAMA_HOST, default http://localhost:11434)
"""
import json
import re

import requests

from . import config


class LLMError(Exception):
    """Any failure to obtain a usable model response."""


def provider_info() -> dict:
    provider = config.LLM_PROVIDER()
    return {"provider": provider, "model": config.LLM_MODEL() or config.DEFAULT_MODELS.get(provider, "?")}


def complete(system: str, user: str, max_tokens: int = 1500) -> str:
    provider = config.LLM_PROVIDER()
    model = config.LLM_MODEL() or config.DEFAULT_MODELS.get(provider)
    if provider not in config.DEFAULT_MODELS:
        raise LLMError(f"Unknown LLM_PROVIDER '{provider}'.")
    timeout = config.LLM_TIMEOUT()
    try:
        if provider == "gemini":
            key = config.get("GEMINI_API_KEY") or config.get("GOOGLE_API_KEY")
            if not key:
                raise LLMError("GEMINI_API_KEY is not set.")
            base = config.get("GEMINI_BASE_URL", "https://generativelanguage.googleapis.com/v1beta").rstrip("/")
            r = requests.post(
                f"{base}/models/{model}:generateContent",
                params={"key": key}, headers={"content-type": "application/json"}, timeout=timeout,
                json={"systemInstruction": {"parts": [{"text": system}]},
                      "contents": [{"role": "user", "parts": [{"text": user}]}],
                      "generationConfig": {"temperature": 0, "maxOutputTokens": max_tokens}},
            )
            _check(r)
            return "".join(part.get("text", "") for part in
                           r.json()["candidates"][0]["content"].get("parts", []))
        if provider == "anthropic":
            key = config.get("ANTHROPIC_API_KEY")
            if not key:
                raise LLMError("ANTHROPIC_API_KEY is not set.")
            base = config.get("ANTHROPIC_BASE_URL", "https://api.anthropic.com").rstrip("/")
            r = requests.post(
                f"{base}/v1/messages",
                headers={"x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"},
                json={"model": model, "max_tokens": max_tokens, "temperature": 0, "system": system,
                      "messages": [{"role": "user", "content": user}]},
                timeout=timeout,
            )
            _check(r)
            return "".join(b.get("text", "") for b in r.json().get("content", []) if b.get("type") == "text")
        if provider == "openai_compatible":
            base = config.get("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
            headers = {"content-type": "application/json"}
            if config.get("OPENAI_API_KEY"):
                headers["authorization"] = f"Bearer {config.get('OPENAI_API_KEY')}"
            r = requests.post(
                f"{base}/chat/completions", headers=headers, timeout=timeout,
                json={"model": model, "temperature": 0, "max_tokens": max_tokens,
                      "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]},
            )
            _check(r)
            return r.json()["choices"][0]["message"]["content"]
        host = config.get("OLLAMA_HOST", "http://localhost:11434").rstrip("/")
        r = requests.post(
            f"{host}/api/chat", timeout=timeout,
            json={"model": model, "stream": False, "options": {"temperature": 0}, "format": "json",
                  "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]},
        )
        _check(r)
        return r.json()["message"]["content"]
    except LLMError:
        raise
    except requests.RequestException as e:
        raise LLMError(f"Could not reach the model provider: {type(e).__name__}") from e
    except (KeyError, IndexError, ValueError) as e:
        raise LLMError(f"Unexpected response shape from model provider: {type(e).__name__}") from e


def _check(r: requests.Response) -> None:
    if r.status_code >= 400:
        raise LLMError(f"Model provider returned HTTP {r.status_code}: {r.text[:200]}")


def parse_json(text: str) -> dict:
    """Extract the first JSON object from a model reply (tolerates ``` fences / chatter)."""
    t = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip(), flags=re.I)
    start, end = t.find("{"), t.rfind("}")
    if start < 0 or end <= start:
        raise LLMError("Model reply contained no JSON object.")
    try:
        obj = json.loads(t[start:end + 1])
    except json.JSONDecodeError as e:
        raise LLMError(f"Model reply was not valid JSON: {e}") from e
    if not isinstance(obj, dict):
        raise LLMError("Model JSON was not an object.")
    return obj
