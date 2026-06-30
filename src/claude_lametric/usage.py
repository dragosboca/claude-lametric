"""Parse a Claude Code transcript (.jsonl) for token usage.

Each line is one event. Assistant messages carry a `message.usage` object with
input_tokens, output_tokens, and cache_{creation,read}_input_tokens.

We report two numbers:
  - context_tokens: the *current* context size = the last assistant message's
    input + cache_creation + cache_read. This is what fills the context window.
  - output_tokens: cumulative output tokens generated this session (work done).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Usage:
    context_tokens: int = 0
    output_tokens: int = 0
    model: str | None = None

    @property
    def found(self) -> bool:
        return self.context_tokens > 0 or self.output_tokens > 0


def _usage_of(message: dict) -> dict | None:
    usage = message.get("usage")
    return usage if isinstance(usage, dict) else None


def parse_transcript(path: str | Path | None) -> Usage:
    result = Usage()
    if not path:
        return result
    p = Path(path)
    if not p.is_file():
        return result

    last_context = 0
    total_output = 0
    model = None
    try:
        with p.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if event.get("type") != "assistant":
                    continue
                message = event.get("message")
                if not isinstance(message, dict):
                    continue
                usage = _usage_of(message)
                if not usage:
                    continue
                model = message.get("model", model)
                total_output += int(usage.get("output_tokens", 0) or 0)
                last_context = (
                    int(usage.get("input_tokens", 0) or 0)
                    + int(usage.get("cache_creation_input_tokens", 0) or 0)
                    + int(usage.get("cache_read_input_tokens", 0) or 0)
                )
    except OSError:
        return result

    result.context_tokens = last_context
    result.output_tokens = total_output
    result.model = model
    return result


def context_limit_for(model: str | None, default: int) -> int:
    """Best-effort context window for the goal frame."""
    if not model:
        return default
    m = model.lower()
    if "[1m]" in m or "-1m" in m:
        return 1_000_000
    return default
