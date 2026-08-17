#!/usr/bin/env python3
"""Shared Claude client for the Field Stack apps. stdlib only (pip is broken here).

Loads ANTHROPIC_API_KEY from the environment or the repo-root .env.local (which
is gitignored and never committed), and calls the Claude Messages API over HTTP.

Cost control (paid service):
  Default model claude-opus-4-8: $5 / million input tokens, $25 / million output.
  We hard-cap output at MAX_OUTPUT_TOKENS and default to a small cap per call.
  Worst case per call ~= (input ~800 tok * $5/M) + (output 512 tok * $25/M)
    ~= $0.004 + $0.0128 ~= $0.017 per message.
  At a 1500-message/month classroom cap that is about $26/month. Set CLAUDE_MODEL
  to claude-sonnet-4-6 to cut that roughly 5x for chat-heavy use.
  Every entry point passes max_tokens; nothing here can self-trigger a loop.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from pathlib import Path

API_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"
DEFAULT_MODEL = os.environ.get("CLAUDE_MODEL", "claude-opus-4-8")
MAX_OUTPUT_TOKENS = 1024   # absolute ceiling regardless of caller request
_TIMEOUT = 30

_KEY_CACHE: dict = {}


class ClaudeError(RuntimeError):
    pass


def _load_env_local() -> None:
    """Parse the repo-root .env.local into os.environ if not already set."""
    here = Path(__file__).resolve()
    for parent in [here.parent, *here.parents]:
        env = parent / ".env.local"
        if env.exists():
            for line in env.read_text().splitlines():
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                k, v = k.strip(), v.strip().strip('"').strip("'")
                os.environ.setdefault(k, v)
            return


def get_api_key() -> str | None:
    if "key" in _KEY_CACHE:
        return _KEY_CACHE["key"]
    if not os.environ.get("ANTHROPIC_API_KEY"):
        _load_env_local()
    key = os.environ.get("ANTHROPIC_API_KEY") or None
    _KEY_CACHE["key"] = key
    return key


def available() -> bool:
    return bool(get_api_key())


def ask(messages: list[dict], system: str | None = None, max_tokens: int = 512,
        model: str | None = None, effort: str = "medium") -> str:
    """Call Claude and return the text. messages: [{role, content}, ...].

    Raises ClaudeError on any failure so callers can fall back gracefully.
    """
    key = get_api_key()
    if not key:
        raise ClaudeError("no ANTHROPIC_API_KEY available")

    payload = {
        "model": model or DEFAULT_MODEL,
        "max_tokens": max(1, min(int(max_tokens), MAX_OUTPUT_TOKENS)),
        "messages": messages,
        # Opus 4.7+ rejects temperature/top_p/top_k. Use effort, not sampling.
        "output_config": {"effort": effort},
    }
    if system:
        payload["system"] = system

    req = urllib.request.Request(
        API_URL, data=json.dumps(payload).encode(),
        headers={"x-api-key": key, "anthropic-version": ANTHROPIC_VERSION,
                 "content-type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:  # noqa: S310
            data = json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode()[:300] if hasattr(exc, "read") else str(exc)
        raise ClaudeError(f"HTTP {exc.code}: {detail}") from None
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise ClaudeError(f"network: {exc}") from None

    parts = [b.get("text", "") for b in data.get("content", []) if b.get("type") == "text"]
    text = "".join(parts).strip()
    if not text:
        raise ClaudeError("empty response")
    return text


if __name__ == "__main__":
    import sys
    if not available():
        print("no key found (set ANTHROPIC_API_KEY or add .env.local)")
        raise SystemExit(1)
    q = " ".join(sys.argv[1:]) or "Say 'field stack online' and nothing else."
    try:
        print(ask([{"role": "user", "content": q}], max_tokens=64))
    except ClaudeError as e:
        print(f"error: {e}")
        raise SystemExit(1)
