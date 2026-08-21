"""
Shared Groq client + JSON-response helper used by every agent in utils/agents/.

Kept separate from utils/analyzer.py and utils/chatbot.py so the agent
package has no import-order dependency on the original single-shot
analyzer/chatbot modules, even though it follows the same conventions.
"""
import os
import json
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

DEFAULT_MODEL = "openai/gpt-oss-20b"


def get_client() -> Groq:
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise ValueError(
            "GROQ_API_KEY not set. Add it to your .env file (local) or environment variables (Render)."
        )
    return Groq(api_key=api_key, timeout=30.0)


def _strip_code_fence(raw: str) -> str:
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    return raw.strip()


def call_json(prompt: str, model: str = DEFAULT_MODEL, temperature: float = 0.3,
              max_tokens: int = 3000, system: str = None, reasoning_effort: str = "low") -> dict:
    """
    Calls Groq expecting a raw JSON object back (no markdown fences).
    Raises json.JSONDecodeError if the model didn't comply — callers should
    catch this and decide how to degrade (retry, fallback, surface raw text).

    `openai/gpt-oss-20b` is a reasoning model: it spends hidden "thinking"
    tokens before writing the actual answer, and those tokens count against
    max_tokens. Without reasoning_effort="low" and a generous max_tokens,
    large prompts can burn the whole budget on reasoning and return empty
    content. reasoning_effort is dropped automatically if the installed
    groq SDK/API version doesn't support it yet.
    """
    client = get_client()
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    kwargs = dict(model=model, messages=messages, temperature=temperature, max_tokens=max_tokens)
    try:
        response = client.chat.completions.create(reasoning_effort=reasoning_effort, **kwargs)
    except TypeError:
        response = client.chat.completions.create(**kwargs)

    raw = (response.choices[0].message.content or "").strip()
    if not raw:
        raise ValueError(
            f"Empty response from model (finish_reason={response.choices[0].finish_reason}). "
            f"Likely ran out of max_tokens on reasoning; try raising max_tokens."
        )
    cleaned = _strip_code_fence(raw)
    return json.loads(cleaned)


def call_text(prompt: str, model: str = DEFAULT_MODEL, temperature: float = 0.5,
              max_tokens: int = 1500, system: str = None, reasoning_effort: str = "low") -> str:
    """Calls Groq expecting free-form text back (used for conversational agents)."""
    client = get_client()
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    kwargs = dict(model=model, messages=messages, temperature=temperature, max_tokens=max_tokens)
    try:
        response = client.chat.completions.create(reasoning_effort=reasoning_effort, **kwargs)
    except TypeError:
        response = client.chat.completions.create(**kwargs)

    return (response.choices[0].message.content or "").strip()