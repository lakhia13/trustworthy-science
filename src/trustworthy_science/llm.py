"""Shared LLM factory — builds a ChatOpenAI-compatible client for api.k2think.ai.

Reads credentials from the .env file at the repository root.
All agents should call ``get_llm()`` rather than constructing LLM clients directly.
"""

from __future__ import annotations

import logging
import os
import re
from pathlib import Path
from functools import lru_cache

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Think-token stripping
# ---------------------------------------------------------------------------

# Patterns for common chain-of-thought delimiters emitted by reasoning models.
# K2-Think-v2 uses <think>...</think>; other models may use <reasoning>...</reasoning>
# or ```thinking ... ``` fenced blocks.
_THINK_PATTERNS: list[re.Pattern] = [
    re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE),
    re.compile(r"<thinking>.*?</thinking>", re.DOTALL | re.IGNORECASE),
    re.compile(r"<reasoning>.*?</reasoning>", re.DOTALL | re.IGNORECASE),
    re.compile(r"```thinking\s.*?```", re.DOTALL),
]


def strip_think_tokens(raw: str) -> str:
    """Remove chain-of-thought / thinking blocks from an LLM response.

    Handles ``<think>...</think>``, ``<thinking>...</thinking>``,
    ``<reasoning>...</reasoning>``, and fenced triple-backtick ``thinking`` blocks.
    Returns the remaining text stripped of leading/trailing whitespace.
    If no known delimiter is found the original string is returned unchanged.

    Examples
    --------
    >>> strip_think_tokens("<think>Let me reason...</think>\\nFinal answer.")
    'Final answer.'
    """
    result = raw
    had_match = False
    for pattern in _THINK_PATTERNS:
        stripped = pattern.sub("", result)
        if stripped != result:
            had_match = True
            result = stripped

    if not had_match and ("<think>" in raw or "<thinking>" in raw or "<reasoning>" in raw):
        logger.warning(
            "strip_think_tokens: detected thinking delimiter but could not strip it. "
            "Returning raw content to avoid data loss."
        )

    return result.strip()

# Repository root (.env lives here)
_REPO_ROOT = Path(__file__).parent.parent.parent

_K2_BASE_URL = "https://api.k2think.ai/v1"
_K2_MODEL = "MBZUAI-IFM/K2-Think-v2"
_ENV_KEY_NAME = "K2_API_KEY"


def _load_dotenv() -> None:
    """Load .env from the repo root into os.environ (no-op if already set)."""
    env_path = _REPO_ROOT / ".env"
    if not env_path.exists():
        return
    with env_path.open() as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value


def get_llm(max_tokens: int = 1024, temperature: float = 0, config: dict | None = None):
    """Return a LangChain ChatOpenAI instance pointed at api.k2think.ai.

    Parameters
    ----------
    max_tokens:
        Maximum tokens in the model response.
    temperature:
        Sampling temperature (0 = deterministic).
    config:
        Optional parsed scoring.yaml dict; ``llm`` section overrides defaults.
    """
    _load_dotenv()

    cfg = (config or {}).get("llm", {})

    # Allow the YAML to override base_url / model, but default to K2
    base_url = cfg.get("base_url", _K2_BASE_URL)
    model = cfg.get("model", _K2_MODEL)
    temp = float(cfg.get("temperature", temperature))
    max_tok = int(cfg.get("max_tokens", max_tokens))

    api_key = os.environ.get(_ENV_KEY_NAME, "")
    if not api_key or api_key == "your-api-key-here":
        logger.warning(
            "K2_API_KEY is not set in .env — LLM calls will fail. "
            "Set K2_API_KEY in .env to enable narrative generation."
        )

    from langchain_openai import ChatOpenAI

    return ChatOpenAI(
        model=model,
        temperature=temp,
        max_tokens=max_tok,
        base_url=base_url,
        api_key=api_key or "missing",  # LangChain requires a non-empty string
    )
