"""Cross-session state so the clock shows a sane aggregate.

The indicator app displays a single global picture, but you may run several
Claude Code sessions at once. We persist each session's last-known status and
usage to a small JSON file, then derive one aggregate to display.

Status priority (most attention-worthy wins): waiting > working > done > idle.
"""

from __future__ import annotations

import json
import os
import tempfile
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

STATE_PATH = (
    Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local" / "state"))
    / "claude-lametric"
    / "sessions.json"
)

_PRIORITY = {"waiting": 3, "working": 2, "done": 1, "idle": 0}


@dataclass
class Session:
    status: str = "idle"
    project: str = ""
    context_tokens: int = 0
    output_tokens: int = 0
    context_limit: int = 200_000
    updated: float = 0.0


@dataclass
class Aggregate:
    status: str
    active: int                 # sessions not idle/done
    project: str
    context_tokens: int
    output_tokens: int
    context_limit: int


def _load(path: Path) -> dict[str, Session]:
    if not path.is_file():
        return {}
    try:
        raw = json.loads(path.read_text("utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    out = {}
    for sid, val in raw.items():
        if isinstance(val, dict):
            out[sid] = Session(**{k: v for k, v in val.items() if k in Session.__dataclass_fields__})
    return out


def _save(path: Path, sessions: dict[str, Session]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {sid: asdict(s) for sid, s in sessions.items()}
    # atomic write so concurrent hooks never read a half-written file
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(payload, fh)
        os.replace(tmp, path)
    except OSError:
        try:
            os.unlink(tmp)
        except OSError:
            pass


def update_session(
    session_id: str,
    *,
    status: str,
    project: str,
    context_tokens: int,
    output_tokens: int,
    context_limit: int,
    idle_after_minutes: int,
    now: float | None = None,
    path: Path = STATE_PATH,
) -> Aggregate:
    """Record this session's state, prune stale ones, return the display aggregate."""
    now = time.time() if now is None else now
    sessions = _load(path)
    sessions[session_id] = Session(
        status=status,
        project=project,
        context_tokens=context_tokens,
        output_tokens=output_tokens,
        context_limit=context_limit,
        updated=now,
    )

    # prune sessions we haven't heard from in a while
    cutoff = now - idle_after_minutes * 60
    sessions = {sid: s for sid, s in sessions.items() if s.updated >= cutoff}
    _save(path, sessions)

    return aggregate(sessions, now)


def aggregate(sessions: dict[str, Session], now: float) -> Aggregate:
    if not sessions:
        return Aggregate("idle", 0, "", 0, 0, 200_000)

    # Status = highest-priority status among live sessions.
    top = max(sessions.values(), key=lambda s: (_PRIORITY.get(s.status, 0), s.updated))
    active = sum(1 for s in sessions.values() if s.status in ("working", "waiting"))
    # Usage = the most recently updated session (the one you're watching).
    latest = max(sessions.values(), key=lambda s: s.updated)
    return Aggregate(
        status=top.status,
        active=active,
        project=latest.project,
        context_tokens=latest.context_tokens,
        output_tokens=latest.output_tokens,
        context_limit=latest.context_limit,
    )
