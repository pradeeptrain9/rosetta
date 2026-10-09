"""Nebius Token Factory client.

Token Factory exposes an OpenAI-compatible surface, so the official openai SDK
is pointed at it. This module adds the two things the pipeline actually needs:
per-tier token accounting (so the report can show the Ultra -> Nano cost delta)
and retry with jitter.
"""

from __future__ import annotations

import ast
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
        # Set on every completed call. "length" means the response was cut off,
        # which for a code request yields an unusable half-file.
        self.last_finish_reason: str | None = None
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
                choice = resp.choices[0]
                self.last_finish_reason = getattr(choice, "finish_reason", None)
                content = _strip_reasoning(choice.message.content or "")
                if not content:
                    # An empty completion is never a usable answer, and silently
                    # returning "" makes every caller downstream interpret a
                    # failed call as a model that had nothing to say. Seen in
                    # practice when a reasoning tier spends its whole budget
                    # before emitting any answer, so surface the finish reason.
                    last_err = RuntimeError(
                        f"empty completion (finish_reason="
                        f"{getattr(choice, 'finish_reason', '?')}, "
                        f"completion_tokens="
                        f"{getattr(resp.usage, 'completion_tokens', '?')}); "
                        f"max_tokens={max_tokens} may be too low"
                    )
                    if i < attempts - 1:
                        time.sleep(min(2 ** i, 8) + random.uniform(0, 0.75))
                        continue
                    raise last_err
                return content
            except (RateLimitError, APIConnectionError) as exc:
                last_err = exc
            except APIStatusError as exc:
                if exc.status_code not in RETRYABLE_STATUS:
                    raise
                last_err = exc
            sleep = min(2 ** i, 8) + random.uniform(0, 0.75)
            time.sleep(sleep)
        raise RuntimeError(f"Nebius call to {model} failed after {attempts} attempts: {last_err}")

    def chat_code(
        self,
        model: str,
        messages: list[dict[str, str]],
        max_tokens: int = 32768,
        attempts: int = 3,
        retry_messages: list[dict[str, str]] | None = None,
        fallback_model: str | None = None,
    ) -> str:
        """Chat and return a parseable Python file.

        A response with no usable code is recoverable: telling the model plainly
        that its last answer was unusable almost always fixes it, and that is far
        cheaper than letting a broken file through and spending three repair
        iterations discovering it fails every vector.
        """
        unusable = (
            "\n\nYour previous response did not contain a parseable Python file. "
            "Return ONLY the complete Python file, in a single ```python fenced "
            "block. Do not restate the COBOL. Do not explain."
        )
        truncated = (
            "\n\nYour previous response was CUT OFF before it finished. Do not "
            "write any analysis, preamble or commentary - that is what exhausted "
            "the budget. Start your reply with ```python on the very first line "
            "and emit only the file. Keep comments to the few lines where a "
            "semantics decision genuinely needs one."
        )
        last: Exception | None = None
        # The reasoning tier occasionally refuses to stop narrating, burning every
        # attempt on analysis and never emitting a file. Observed losing a whole
        # program that way. A different model is the cheapest escape: the tiers
        # already exist, and a translation from the middle tier that passes the
        # differential suite is worth incomparably more than a failed program.
        models = [model] * attempts + ([fallback_model] if fallback_model else [])
        for i, active in enumerate(models):
            # Retries use the compact prompt when the caller supplied one. A
            # long prompt measurably raises the chance of an essay instead of a
            # file, and by the retry the model has already been given the full
            # briefing once - what it needs now is less to read, not more.
            base = (retry_messages or messages) if i else messages
            msgs = list(base)
            if i:
                # Pick the correction that matches how the last attempt failed.
                hint = truncated if self.last_finish_reason == "length" else unusable
                msgs[-1] = {**msgs[-1], "content": msgs[-1]["content"] + hint}
            try:
                text = self.chat(active, msgs, temperature=0.0, max_tokens=max_tokens)
            except RuntimeError as exc:
                last = exc
                continue
            try:
                code = extract_code(text)
            except ValueError as exc:
                last = exc
                continue
            if self.last_finish_reason == "length":
                # Parsed, but the response was still cut off: a truncated file
                # that happens to parse is a trap - it silently omits behaviour.
                last = ValueError(
                    "response hit the token limit; the file is incomplete"
                )
                continue
            return code
        tried = f"{attempts} attempt(s) on {model}"
        if fallback_model:
            tried += f" and a fallback to {fallback_model}"
        raise ValueError(f"no parseable Python after {tried}: {last}")

    def chat_json(
        self,
        model: str,
        messages: list[dict[str, str]],
        temperature: float = 0.0,
        max_tokens: int = 4096,
        attempts: int = 3,
    ) -> Any:
        """Chat and parse JSON, retrying a malformed or truncated response.

        The common failure is truncation: the object starts, the budget runs
        out, and what arrives is unparseable through no fault of the prompt.
        Retrying with an explicit "be terse" instruction costs one call and
        saves the caller from losing its whole unit of work.
        """
        terse = (
            "\n\nYour previous response was not parseable JSON - it was most "
            "likely cut off. Return ONLY the JSON, minified, with short values. "
            "No markdown fence, no commentary."
        )
        last: Exception | None = None
        for i in range(attempts):
            msgs = list(messages)
            if i:
                msgs[-1] = {**msgs[-1], "content": msgs[-1]["content"] + terse}
            try:
                raw = self.chat(
                    model, msgs, temperature=temperature, max_tokens=max_tokens
                )
                return parse_json_loose(raw)
            except (ValueError, RuntimeError) as exc:
                last = exc
        raise ValueError(f"no parseable JSON after {attempts} attempt(s): {last}")


# ---------- output cleaning ----------

_THINK_RX = re.compile(r"<think>.*?</think>\s*", re.S | re.I)
# Captures the language tag as well as the body: picking a block by size alone
# hands back the COBOL whenever the model echoes the source.
_FENCE_RX = re.compile(r"```([a-zA-Z0-9_+-]*)\s*\n(.*?)```", re.S)
_PY_TAGS = {"python", "py", "python3"}
# Truncation usually leaves an opening fence with no closing one.
_OPEN_FENCE_RX = re.compile(r"```([a-zA-Z0-9_+-]*)\s*\n(.*)\Z", re.S)


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


def extract_code(text: str) -> str:
    """Return the largest fenced block that actually parses as Python.

    Two failure modes made a naive "largest block" wrong in practice. The model
    sometimes echoes the COBOL source back in a fence, and that block can be the
    largest one in the response; and a response can be mostly prose with only a
    fragment of code. Requiring the result to parse rejects both: COBOL is not
    valid Python, and neither is half a function.

    Raises ValueError when nothing in the response is parseable Python, which is
    a hard failure worth surfacing rather than writing a broken file to disk and
    burning repair iterations on it.
    """
    blocks = [(lang.lower(), body) for lang, body in _FENCE_RX.findall(text)]

    tagged = [b for lang, b in blocks if lang in _PY_TAGS]
    untagged = [b for lang, b in blocks if not lang]
    other = [b for lang, b in blocks if lang and lang not in _PY_TAGS]

    # Explicitly tagged python first, then untagged, then anything else; within
    # each group prefer the longest, which is the complete file over a snippet.
    candidates = (
        sorted(tagged, key=len, reverse=True)
        + sorted(untagged, key=len, reverse=True)
        + sorted(other, key=len, reverse=True)
    )

    # Recover a truncated response: an opening fence with nothing closing it.
    # It parses only if the cut happened to land on a statement boundary, but
    # when it does the file is usable and the alternative is discarding it.
    if not blocks:
        open_m = _OPEN_FENCE_RX.search(text)
        if open_m:
            candidates.append(open_m.group(2))

    candidates.append(text)

    for cand in candidates:
        cleaned = cand.strip()
        if not cleaned:
            continue
        cleaned += "\n"
        try:
            ast.parse(cleaned)
        except (SyntaxError, ValueError):
            continue
        return cleaned

    raise ValueError(
        f"no parseable Python in the response ({len(blocks)} fenced block(s), "
        f"tags={[lang for lang, _ in blocks]}); first 300 chars: {text[:300]!r}"
    )


def parse_json_loose(text: str) -> Any:
    """Parse JSON that may be fenced or surrounded by prose."""
    candidates: Iterable[str] = [body for _lang, body in _FENCE_RX.findall(text)]
    candidates = [*candidates, text]
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
