"""Configuration loading.

Config is read from (first match wins):
  1. $CLAUDE_LAMETRIC_CONFIG
  2. ~/.config/claude-lametric/config.toml

Any value can be overridden by an environment variable (handy for hooks and CI):
  LAMETRIC_LOCAL_IP, LAMETRIC_LOCAL_API_KEY, LAMETRIC_LOCAL_ENABLED
  LAMETRIC_INDICATOR_PUSH_URL, LAMETRIC_INDICATOR_ACCESS_TOKEN, LAMETRIC_INDICATOR_ENABLED
"""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_CONFIG_PATH = Path.home() / ".config" / "claude-lametric" / "config.toml"


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass
class LocalConfig:
    """LaMetric device on the local network (instant notification popups)."""

    ip: str = ""
    api_key: str = ""
    enabled: bool = True

    @property
    def configured(self) -> bool:
        return self.enabled and bool(self.ip and self.api_key)


@dataclass
class IndicatorConfig:
    """LaMetric 'Local Push' indicator app (persistent status frames, pushed over LAN)."""

    push_url: str = ""
    access_token: str = ""
    enabled: bool = True

    @property
    def configured(self) -> bool:
        return self.enabled and bool(self.push_url and self.access_token)


@dataclass
class Behavior:
    notify_on_stop: bool = True          # popup when Claude finishes a turn
    notify_on_permission: bool = True    # popup when Claude needs attention/permission
    context_limit: int = 200_000         # token budget used for the context goal frame
    idle_after_minutes: int = 30         # sessions stale beyond this are treated as gone


@dataclass
class Icons:
    """LaMetric icon IDs. Browse / pick yours at https://developer.lametric.com/icons
    Use the numeric id as a string. Prefix 'a' for animations, 'i' for static (or omit)."""

    working: str = "a2740"   # animated spinner-ish
    waiting: str = "a4849"   # attention / bell
    idle: str = "i120"       # check / ok
    done: str = "a1054"      # green check animation
    tokens: str = "i555"     # chart / data
    error: str = "a9335"     # red alert


@dataclass
class Config:
    local: LocalConfig = field(default_factory=LocalConfig)
    indicator: IndicatorConfig = field(default_factory=IndicatorConfig)
    behavior: Behavior = field(default_factory=Behavior)
    icons: Icons = field(default_factory=Icons)
    source_path: Path | None = None

    @property
    def any_configured(self) -> bool:
        return self.local.configured or self.indicator.configured


def _load_file(path: Path) -> dict:
    if not path.is_file():
        return {}
    with path.open("rb") as fh:
        return tomllib.load(fh)


def load_config(path: Path | None = None) -> Config:
    if path is None:
        env_path = os.environ.get("CLAUDE_LAMETRIC_CONFIG")
        path = Path(env_path) if env_path else DEFAULT_CONFIG_PATH

    data = _load_file(path)
    local_raw = data.get("local", {})
    indicator_raw = data.get("indicator", {})
    behavior_raw = data.get("behavior", {})
    icons_raw = data.get("icons", {})

    local = LocalConfig(
        ip=os.environ.get("LAMETRIC_LOCAL_IP", local_raw.get("ip", "")),
        api_key=os.environ.get("LAMETRIC_LOCAL_API_KEY", local_raw.get("api_key", "")),
        enabled=_env_bool("LAMETRIC_LOCAL_ENABLED", local_raw.get("enabled", True)),
    )
    indicator = IndicatorConfig(
        push_url=os.environ.get(
            "LAMETRIC_INDICATOR_PUSH_URL", indicator_raw.get("push_url", "")
        ),
        access_token=os.environ.get(
            "LAMETRIC_INDICATOR_ACCESS_TOKEN", indicator_raw.get("access_token", "")
        ),
        enabled=_env_bool("LAMETRIC_INDICATOR_ENABLED", indicator_raw.get("enabled", True)),
    )
    behavior = Behavior(
        notify_on_stop=behavior_raw.get("notify_on_stop", True),
        notify_on_permission=behavior_raw.get("notify_on_permission", True),
        context_limit=behavior_raw.get("context_limit", 200_000),
        idle_after_minutes=behavior_raw.get("idle_after_minutes", 30),
    )
    icons = Icons(**{k: str(v) for k, v in icons_raw.items() if k in Icons.__dataclass_fields__})

    return Config(
        local=local,
        indicator=indicator,
        behavior=behavior,
        icons=icons,
        source_path=path if path.is_file() else None,
    )
