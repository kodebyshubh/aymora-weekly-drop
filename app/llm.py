"""Optional language model layer (Groq, OpenAI compatible). Off unless AYMORA_LLM=1 and GROQ_API_KEY is set.

The model never invents facts. It only (1) pulls interest tags out of free text, restricted to our
vocabulary, and (2) rewords reasons that the engine already produced. Any failure falls back to the
deterministic text, so the demo never depends on the network.
"""
from __future__ import annotations

import json
import os

import httpx

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
DEFAULT_MODEL = "openai/gpt-oss-20b"


def enabled() -> bool:
    return os.getenv("AYMORA_LLM", "0") == "1" and bool(os.getenv("GROQ_API_KEY"))


def _chat(messages: list[dict], max_tokens: int = 400, timeout: float = 6.0) -> str | None:
    if not enabled():
        return None
    try:
        r = httpx.post(
            GROQ_URL,
            headers={"Authorization": f"Bearer {os.environ['GROQ_API_KEY']}"},
            json={"model": os.getenv("GROQ_MODEL", DEFAULT_MODEL), "messages": messages,
                  "temperature": 0.2, "max_completion_tokens": max_tokens, "reasoning_effort": "low"},
            timeout=timeout,
        )
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]
    except Exception:
        return None


def extract_interests(text: str, vocabulary: list[str]) -> list[str] | None:
    """Return interest tags found in `text`, restricted to `vocabulary`; None means 'use the fallback'."""
    if not text.strip():
        return []
    out = _chat([
        {"role": "system", "content": "Extract interests from the user's text. Reply with a JSON array of strings "
                                      "chosen only from this list, nothing else: " + json.dumps(vocabulary)},
        {"role": "user", "content": text[:600]},
    ], max_tokens=200)
    if out is None:
        return None
    try:
        start, end = out.index("["), out.rindex("]") + 1
        tags = json.loads(out[start:end])
    except (ValueError, json.JSONDecodeError):
        return None
    return [t for t in tags if isinstance(t, str) and t in vocabulary]


def reword(reasons: list[str]) -> list[str] | None:
    """Make the engine's reasons sound warmer without adding or removing any fact."""
    if not reasons:
        return None
    out = _chat([
        {"role": "system", "content": "Rewrite each line in a warm, playful, plain voice. Keep the exact same facts. "
                                      "Do not add anything. One short sentence each. Reply with a JSON array of "
                                      "strings, the same length and order as the input."},
        {"role": "user", "content": json.dumps(reasons)},
    ], max_tokens=300)
    if out is None:
        return None
    try:
        start, end = out.index("["), out.rindex("]") + 1
        lines = json.loads(out[start:end])
    except (ValueError, json.JSONDecodeError):
        return None
    if (not isinstance(lines, list) or len(lines) != len(reasons)
            or not all(isinstance(x, str) and 0 < len(x) <= 180 for x in lines)):
        return None
    return lines
