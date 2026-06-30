"""Build LaMetric frame payloads from Claude state."""

from __future__ import annotations

from .config import Icons
from .state import Aggregate

# Human label + icon attribute name for each status.
_STATUS_LABEL = {
    "working": ("Working", "working"),
    "waiting": ("Needs you", "waiting"),
    "done": ("Done", "done"),
    "idle": ("Idle", "idle"),
    "error": ("Error", "error"),
}


def _icon(icons: Icons, name: str) -> str:
    return getattr(icons, name, "") or ""


def _fmt_tokens(n: int) -> str:
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}k"
    return str(n)


def status_text_frame(agg: Aggregate, icons: Icons) -> dict:
    label, icon_name = _STATUS_LABEL.get(agg.status, _STATUS_LABEL["idle"])
    if agg.active > 1:
        label = f"{label} x{agg.active}"
    elif agg.project and agg.status in ("working", "waiting"):
        label = f"{label}: {agg.project}"
    return {"text": label, "icon": _icon(icons, icon_name)}


def context_goal_frame(agg: Aggregate, icons: Icons) -> dict | None:
    if agg.context_tokens <= 0:
        return None
    end = max(agg.context_limit, agg.context_tokens)
    return {
        "icon": _icon(icons, "tokens"),
        "goalData": {"start": 0, "current": agg.context_tokens, "end": end, "unit": "tok"},
    }


def output_text_frame(agg: Aggregate, icons: Icons) -> dict | None:
    if agg.output_tokens <= 0:
        return None
    return {"text": f"{_fmt_tokens(agg.output_tokens)} out", "icon": _icon(icons, "tokens")}


def status_frames(agg: Aggregate, icons: Icons) -> list[dict]:
    """Full set of frames for the persistent indicator app."""
    frames: list[dict] = [status_text_frame(agg, icons)]
    ctx = context_goal_frame(agg, icons)
    if ctx:
        frames.append(ctx)
    out = output_text_frame(agg, icons)
    if out:
        frames.append(out)
    return frames


def alert_frames(text: str, icon: str) -> list[dict]:
    """Single-frame transient popup for the local device."""
    frame: dict = {"text": text}
    if icon:
        frame["icon"] = icon
    return [frame]
