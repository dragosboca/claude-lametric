# claude-lametric

Show **Claude Code** status, notifications, and token usage on a **LaMetric Time** clock.

Claude Code hooks fire on real events in your sessions and push to the clock two ways:

- **Cloud DIY app** (persistent) — a "My Data DIY" indicator app cycles frames showing the
  current status, a context-window goal bar, and output tokens. Works from anywhere.
- **Local device** (instant) — a popup notification on your LAN when Claude needs your
  attention (permission / input) or finishes a turn.

```
┌─────────────────┐   ┌─────────────────┐   ┌─────────────────┐
│ ⏳ Working: app │ → │ ▓▓▓▓░░ 45k tok  │ → │ 📊 12.3k out    │
└─────────────────┘   └─────────────────┘   └─────────────────┘
   status frame          context goal           output tokens
```

Zero runtime dependencies (stdlib `urllib` + `tomllib`) so the hook never breaks a session.

## Install

```bash
uv tool install .          # puts `claude-lametric` on your PATH
# or run in-place: `uv run claude-lametric ...`
```

## Configure

1. Copy the example config and fill in your values:

   ```bash
   mkdir -p ~/.config/claude-lametric
   cp config.example.toml ~/.config/claude-lametric/config.toml
   ```

2. **Local device** (instant popups):
   - `ip` — LaMetric app → Settings → Wi-Fi → IP Address
   - `api_key` — [developer.lametric.com](https://developer.lametric.com) → your account → **Devices** → API key

3. **Cloud DIY app** (persistent status):
   - At [developer.lametric.com](https://developer.lametric.com), create a **"My Data DIY"**
     indicator app (push / "predefined JSON" mode). Add it to your clock.
   - Copy its **push URL** (`…/api/v1/dev/widget/update/com.lametric.<APP_ID>/1`) and
     **access token** into `[cloud]`.

Either section is optional — configure one or both. Check what's resolved:

```bash
claude-lametric doctor
claude-lametric test     # pushes a sample status + popup to your clock
```

> Every value can also be set via env var: `LAMETRIC_LOCAL_IP`, `LAMETRIC_LOCAL_API_KEY`,
> `LAMETRIC_CLOUD_PUSH_URL`, `LAMETRIC_CLOUD_ACCESS_TOKEN`, etc. — useful for secrets.

## Wire up the hooks

Merge the `hooks` block from [`hooks.example.json`](hooks.example.json) into your
`~/.claude/settings.json` (global) or a project's `.claude/settings.json`:

```json
{
  "hooks": {
    "SessionStart":     [{ "hooks": [{ "type": "command", "command": "claude-lametric hook" }] }],
    "UserPromptSubmit": [{ "hooks": [{ "type": "command", "command": "claude-lametric hook" }] }],
    "Notification":     [{ "hooks": [{ "type": "command", "command": "claude-lametric hook" }] }],
    "Stop":             [{ "hooks": [{ "type": "command", "command": "claude-lametric hook" }] }],
    "SessionEnd":       [{ "hooks": [{ "type": "command", "command": "claude-lametric hook" }] }]
  }
}
```

Each hook pipes a JSON payload on stdin; `claude-lametric hook` reads it, maps the event to a
status, parses the transcript for token usage, and updates the clock.

| Hook event        | Status shown | Local popup                          |
| ----------------- | ------------ | ------------------------------------ |
| `SessionStart`    | Idle         | —                                    |
| `UserPromptSubmit`| Working      | —                                    |
| `Notification`    | Needs you    | ✅ the permission/attention message  |
| `Stop`            | Done         | ✅ "Done: \<project>"                 |
| `SessionEnd`      | Idle         | —                                    |

Multiple concurrent sessions are aggregated: status = the most attention-worthy one
(`waiting` > `working` > `done` > `idle`), with `x2`/`x3` when several are active. Sessions
silent longer than `idle_after_minutes` are forgotten.

## Manual commands

```bash
claude-lametric status working --project myapp --context 45000 --output 12300
claude-lametric notify "Deploy finished" --priority warning --sound notification
claude-lametric test
claude-lametric doctor
```

## How usage is computed

The transcript (`.jsonl`) records `message.usage` per assistant turn. We show:

- **context_tokens** — current context size = last turn's `input + cache_creation + cache_read`
  (what fills the window), rendered as a goal bar toward `context_limit` (auto-bumped to 1M for
  `[1m]` models).
- **output_tokens** — cumulative output across the session (work done).

## Develop

```bash
uv run pytest      # offline tests, no device needed
```

## Layout

```
src/claude_lametric/
  config.py   load TOML + env overrides
  client.py   HTTP transport (local notifications + cloud frames)
  usage.py    parse transcript .jsonl for token usage
  state.py    per-session state + cross-session aggregate
  frames.py   build LaMetric frame payloads
  hook.py     map a hook event -> clock update
  cli.py      `claude-lametric` entrypoint
```

## Notes & limits

- Pushes are best-effort: network errors are swallowed and the hook always exits 0, so an
  offline clock never blocks Claude Code.
- Icon IDs are configurable in `[icons]` — browse them at
  [developer.lametric.com/icons](https://developer.lametric.com/icons) (`a…` animation, `i…` static).
- The local API requires your machine and the clock to be on the same network.
