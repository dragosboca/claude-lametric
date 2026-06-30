"""Command-line entrypoint: `claude-lametric <command>`.

Commands:
  hook      Read a Claude Code hook payload on stdin and update the clock.
            (This is what you wire into .claude/settings.json.)
  status    Manually set the displayed status: working|waiting|done|idle.
  notify    Fire a one-off local popup: `claude-lametric notify "text"`.
  test      Push a sample status + popup to verify your config end to end.
  doctor    Show what's configured and where the config was loaded from.
"""

from __future__ import annotations

import argparse
import sys

from .client import LaMetricClient
from .config import load_config
from . import frames as F
from .hook import handle, read_stdin_payload
from .state import Aggregate


def _print_results(results) -> int:
    if not results:
        print("nothing pushed (no targets configured)", file=sys.stderr)
        return 1
    failures = 0
    for r in results:
        print(r)
        failures += 0 if r.ok else 1
    return 0 if failures == 0 else 2


def cmd_hook(args, config) -> int:
    payload = read_stdin_payload()
    results = handle(payload, config, event_override=args.event)
    # Hooks must exit 0 even on push failure so the session is never blocked.
    _print_results(results)
    return 0


def cmd_status(args, config) -> int:
    agg = Aggregate(
        status=args.state,
        active=1 if args.state in ("working", "waiting") else 0,
        project=args.project or "",
        context_tokens=args.context or 0,
        output_tokens=args.output or 0,
        context_limit=config.behavior.context_limit,
    )
    client = LaMetricClient(config)
    results = []
    if config.cloud.configured:
        results.append(client.push_cloud(F.status_frames(agg, config.icons)))
    else:
        print("cloud not configured; status frames go to the DIY app", file=sys.stderr)
    return _print_results(results)


def cmd_notify(args, config) -> int:
    client = LaMetricClient(config)
    icon = args.icon or config.icons.waiting
    res = client.notify_local(
        F.alert_frames(args.text, icon),
        priority=args.priority,
        icon_type="info" if args.priority == "info" else "alert",
        sound=args.sound,
    )
    return _print_results([res])


def cmd_test(args, config) -> int:
    print(f"config: {config.source_path or '(defaults / env only)'}")
    agg = Aggregate("working", 1, "claude-notifications", 45_000, 12_300, 200_000)
    client = LaMetricClient(config)
    results = []
    if config.cloud.configured:
        results.append(client.push_cloud(F.status_frames(agg, config.icons)))
    if config.local.configured:
        results.append(
            client.notify_local(
                F.alert_frames("LaMetric + Claude OK", config.icons.done),
                priority="info",
                icon_type="info",
                sound="notification",
            )
        )
    return _print_results(results)


def cmd_doctor(args, config) -> int:
    print(f"config source : {config.source_path or '(none — using defaults/env)'}")
    print(f"local device  : {'configured' if config.local.configured else 'NOT configured'}"
          + (f"  ({config.local.ip})" if config.local.ip else ""))
    print(f"cloud DIY app : {'configured' if config.cloud.configured else 'NOT configured'}")
    print(f"context limit : {config.behavior.context_limit:,} tokens")
    print(f"notify on stop: {config.behavior.notify_on_stop}")
    print(f"notify on perm: {config.behavior.notify_on_permission}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="claude-lametric", description=__doc__)
    p.add_argument("--config", help="path to config.toml (overrides default lookup)")
    sub = p.add_subparsers(dest="command", required=True)

    h = sub.add_parser("hook", help="handle a Claude Code hook (reads stdin)")
    h.add_argument("--event", help="override hook_event_name (e.g. Stop, Notification)")
    h.set_defaults(func=cmd_hook)

    s = sub.add_parser("status", help="manually set displayed status")
    s.add_argument("state", choices=["working", "waiting", "done", "idle", "error"])
    s.add_argument("--project", help="project label")
    s.add_argument("--context", type=int, help="current context tokens")
    s.add_argument("--output", type=int, help="cumulative output tokens")
    s.set_defaults(func=cmd_status)

    n = sub.add_parser("notify", help="fire a one-off local popup")
    n.add_argument("text")
    n.add_argument("--icon")
    n.add_argument("--sound", default="notification")
    n.add_argument("--priority", choices=["info", "warning", "critical"], default="info")
    n.set_defaults(func=cmd_notify)

    t = sub.add_parser("test", help="push a sample status + popup")
    t.set_defaults(func=cmd_test)

    d = sub.add_parser("doctor", help="show resolved configuration")
    d.set_defaults(func=cmd_doctor)
    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    from pathlib import Path

    config = load_config(Path(args.config) if args.config else None)
    return args.func(args, config)


if __name__ == "__main__":
    raise SystemExit(main())
