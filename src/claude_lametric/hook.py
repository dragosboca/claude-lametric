"""Core hook handler: map a Claude Code hook event to LaMetric updates.

Claude Code invokes a hook by piping a JSON object on stdin, e.g.:
    {"session_id": "...", "transcript_path": "/.../x.jsonl",
     "cwd": "/path/to/project", "hook_event_name": "Stop", ...}

We translate the event into a status, refresh per-session state, push the
aggregate status frames to the cloud DIY app, and fire a transient popup on the
local device for attention-worthy events (Notification, Stop).
"""

from __future__ import annotations

import sys
from pathlib import Path

from .client import LaMetricClient, PushResult
from .config import Config
from . import frames as F
from .state import update_session
from .usage import context_limit_for, parse_transcript

# hook_event_name -> our status
EVENT_STATUS = {
    "SessionStart": "idle",
    "UserPromptSubmit": "working",
    "PreToolUse": "working",
    "PostToolUse": "working",
    "Notification": "waiting",
    "Stop": "done",
    "SubagentStop": "working",
    "SessionEnd": "idle",
}


def _project_name(cwd: str | None) -> str:
    if not cwd:
        return ""
    return Path(cwd).name


def handle(payload: dict, config: Config, *, event_override: str | None = None) -> list[PushResult]:
    event = event_override or payload.get("hook_event_name") or "UserPromptSubmit"
    status = EVENT_STATUS.get(event, "working")
    session_id = str(payload.get("session_id") or "default")
    project = _project_name(payload.get("cwd"))

    usage = parse_transcript(payload.get("transcript_path"))
    limit = context_limit_for(usage.model, config.behavior.context_limit)

    agg = update_session(
        session_id,
        status=status,
        project=project,
        context_tokens=usage.context_tokens,
        output_tokens=usage.output_tokens,
        context_limit=limit,
        idle_after_minutes=config.behavior.idle_after_minutes,
    )

    client = LaMetricClient(config)
    results: list[PushResult] = []

    # Persistent status on the cloud DIY app.
    if config.cloud.configured:
        results.append(client.push_cloud(F.status_frames(agg, config.icons)))

    # Transient popups on the local device for attention-worthy events.
    if config.local.configured:
        popup = _popup_for(event, payload, project, config)
        if popup is not None:
            text, icon, priority, icon_type, sound = popup
            results.append(
                client.notify_local(
                    F.alert_frames(text, icon),
                    priority=priority,
                    icon_type=icon_type,
                    sound=sound,
                )
            )

    return results


def _popup_for(event: str, payload: dict, project: str, config: Config):
    """Return (text, icon, priority, icon_type, sound) or None if no popup."""
    icons = config.icons
    if event == "Notification" and config.behavior.notify_on_permission:
        text = str(payload.get("message") or "Claude needs your attention")
        return (text, icons.waiting, "warning", "alert", "notification")
    if event == "Stop" and config.behavior.notify_on_stop:
        text = f"Done: {project}" if project else "Claude finished"
        return (text, icons.done, "info", "info", "notification")
    return None


def read_stdin_payload() -> dict:
    import json

    raw = sys.stdin.read() if not sys.stdin.isatty() else ""
    if not raw.strip():
        return {}
    try:
        data = json.loads(raw)
        return data if isinstance(data, dict) else {}
    except json.JSONDecodeError:
        return {}
