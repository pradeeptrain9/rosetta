"""Nebius Token Factory client.

Token Factory exposes an OpenAI-compatible surface, so the official openai SDK
is pointed at it. This module adds the two things the pipeline actually needs:
per-tier token accounting (so the report can show the Ultra -> Nano cost delta)
and retry with jitter.
"""

from __future__ import annotations

import json
import random
import re
import time
from collections import defaultdict
from typing import Any, Iterable

from openai import OpenAI
from openai import APIConnectionError, APIStatusError, RateLimitError

from .config import Settings

RETRYABLE_STATUS = {408, 409, 429, 500, 502, 503, 504}


class TokenLedger:
    """Accumulates prompt/completion tokens per model id."""

    def __init__(self) -> None:
        self._data: dict[str, dict[str, int]] = defaultdict(
            lambda: {"prompt": 0, "completion": 0, "calls": 0}
        )

    def add(self, model: str, prompt: int, completion: int) -> None:
        row = self._data[model]
        row["prompt"] += prompt
        row["completion"] += completion
        row["calls"] += 1

    def merge(self, other: "TokenLedger") -> None:
        for model, row in other.as_dict().items():
            tgt = self._data[model]
            for k in ("prompt", "completion", "calls"):
                tgt[k] += row[k]

    def as_dict(self) -> dict[str, dict[str, int]]:
        return {k: dict(v) for k, v in self._data.items()}

    def total_tokens(self) -> int:
        return sum(r["prompt"] + r["completion"] for r in self._data.values())


class LLMClient:
    def __init__(self, settings: Settings, ledger: TokenLedger | None = None) -> None:
        if not settings.api_key:
            raise RuntimeError(
                "NEBIUS_API_KEY is not set. Copy .env.example to .env and fill it in."
            )
        self.settings = settings
        self.ledger = ledger or TokenLedger()
        self._client = OpenAI(
            api_key=settings.api_key,
            base_url=settings.base_url,
            timeout=600.0,
            max_retries=0,  # retries handled here so the ledger stays accurate
        )

    # ---------- discovery ----------

    def served_models(self) -> list[str]:
        return sorted(m.id for m in self._client.models.list().data)

    # ---------- core call ----------

    def chat(
        self,
        model: str,
        messages: list[dict[str, str]],
        temperature: float = 0.0,
        max_tokens: int = 8192,
        attempts: int = 4,
    ) -> str:
        last_err: Exception | None = None
        for i in range(attempts):
            try:
                resp = self._client.chat.completions.create(
                    model=model,
                    messages=messages,  # type: ignore[arg-type]
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
                usage = resp.usage
                if usage is not None:
                    self.ledger.add(
                        model,
                        usage.prompt_tokens or 0,
                        usage.completion_tokens or 0,
                    )
                content = resp.choices[0].message.content or ""
                return _strip_reasoning(content)
            except (RateLimitError, APIConnectionError) as exc:
                last_err = exc
            except APIStatusError as exc:
                if exc.status_code not in RETRYABLE_STATUS:
                    raise
                last_err = exc
            sleep = min(2 ** i, 8) + random.uniform(0, 0.75)
            time.sleep(sleep)
        raise RuntimeError(f"Nebius call to {model} failed after {attempts} attempts: {last_err}")

    def chat_json(
        self,
        model: str,
        messages: list[dict[str, str]],
        temperature: float = 0.0,
        max_tokens: int = 4096,
    ) -> Any:
        raw = self.chat(model, messages, temperature=temperature, max_tokens=max_tokens)
        return parse_json_loose(raw)


# ---------- output cleaning ----------

_THINK_RX = re.compile(r"<think>.*?</think>\s*", re.S | re.I)
_FENCE_RX = re.compile(r"```[a-zA-Z0-9_+-]*\s*\n(.*?)```", re.S)


def _strip_reasoning(text: str) -> str:
    """Nemotron reasoning tiers may emit a <think> block. Drop it.

    An unterminated block means the response was cut off mid-reasoning; keep
    whatever follows the opening tag so the caller can still fail loudly rather
    than silently parsing reasoning as an answer.
    """
    cleaned = _THINK_RX.sub("", text)
    if "<think>" in cleaned.lower():
        idx = cleaned.lower().rfind("</think>")
        cleaned = cleaned[idx + len("</think>") :] if idx != -1 else cleaned
    return cleaned.strip()


def extract_code(text: str, language_hint: str = "python") -> str:
    """Pull the largest fenced code block, or fall back to the raw text."""
    blocks = _FENCE_RX.findall(text)
    if blocks:
        return max(blocks, key=len).strip() + "\n"
    return text.strip() + "\n"


def parse_json_loose(text: str) -> Any:
    """Parse JSON that may be fenced or surrounded by prose."""
    candidates: Iterable[str] = [*_FENCE_RX.findall(text), text]
    for cand in candidates:
        cand = cand.strip()
        try:
            return json.loads(cand)
        except json.JSONDecodeError:
            pass
        # Last resort: slice the outermost brace/bracket pair.
        for open_c, close_c in (("{", "}"), ("[", "]")):
            start, end = cand.find(open_c), cand.rfind(close_c)
            if start != -1 and end > start:
                try:
                    return json.loads(cand[start : end + 1])
                except json.JSONDecodeError:
                    continue
    raise ValueError(f"Model did not return parseable JSON. Got: {text[:400]!r}")
