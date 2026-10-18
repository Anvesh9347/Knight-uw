"""Configuration from environment variables (optionally a local .env file). No secrets in code."""
import os
from pathlib import Path


def _load_dotenv() -> None:
    path = Path(__file__).resolve().parent.parent / ".env"
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_dotenv()


def get(name: str, default: str = "") -> str:
    return os.environ.get(name, default)

LLM_PROVIDER = lambda: get("LLM_PROVIDER", "openai_compatible").strip().lower()
LLM_MODEL = lambda: get("LLM_MODEL", "")
LLM_TIMEOUT = lambda: int(get("LLM_TIMEOUT_SECONDS", "90"))

DEFAULT_MODELS = {
    "gemini": "gemini-3.8-flash",
    "anthropic": "claude-sonnet-5-5",
    "openai_compatible": "gpt-4o-mini",
    "ollama": "llama3.1:8b",
}
