"""Offline tests — no network, no real LaMetric. Run with: uv run pytest"""

import json

from claude_lametric import frames as F
from claude_lametric.config import Config, Icons
from claude_lametric.state import Aggregate, aggregate, Session, update_session
from claude_lametric.usage import context_limit_for, parse_transcript


def _agg(**kw):
    base = dict(status="working", active=1, project="proj",
                context_tokens=45000, output_tokens=12300, context_limit=200000)
    base.update(kw)
    return Aggregate(**base)


def test_status_frames_full():
    frames = F.status_frames(_agg(), Icons())
    assert frames[0]["text"] == "Working: proj"
    goal = next(f for f in frames if "goalData" in f)
    assert goal["goalData"]["current"] == 45000
    assert goal["goalData"]["end"] == 200000
    assert any("out" in f.get("text", "") for f in frames)


def test_status_frames_multi_session_label():
    frames = F.status_frames(_agg(active=3), Icons())
    assert frames[0]["text"] == "Working x3"


def test_token_formatting():
    assert "12.3k out" == F.output_text_frame(_agg(output_tokens=12300), Icons())["text"]
    assert "1.5M out" == F.output_text_frame(_agg(output_tokens=1_500_000), Icons())["text"]


def test_context_goal_clamps_when_over_limit():
    frame = F.context_goal_frame(_agg(context_tokens=250000, context_limit=200000), Icons())
    assert frame["goalData"]["end"] == 250000  # never let current exceed end


def test_no_usage_frames_when_zero():
    frames = F.status_frames(_agg(context_tokens=0, output_tokens=0), Icons())
    assert len(frames) == 1  # status text only


def test_parse_transcript(tmp_path):
    p = tmp_path / "t.jsonl"
    lines = [
        {"type": "user", "message": {"role": "user"}},
        {"type": "assistant", "message": {"model": "claude-opus-4-8",
            "usage": {"input_tokens": 100, "output_tokens": 50,
                      "cache_read_input_tokens": 1000, "cache_creation_input_tokens": 200}}},
        {"type": "assistant", "message": {"model": "claude-opus-4-8",
            "usage": {"input_tokens": 80, "output_tokens": 70,
                      "cache_read_input_tokens": 5000, "cache_creation_input_tokens": 0}}},
    ]
    p.write_text("\n".join(json.dumps(x) for x in lines))
    u = parse_transcript(p)
    assert u.output_tokens == 120                 # 50 + 70 cumulative
    assert u.context_tokens == 80 + 5000 + 0      # last message only
    assert u.model == "claude-opus-4-8"


def test_parse_transcript_missing_file():
    assert not parse_transcript("/nope/nope.jsonl").found


def test_context_limit_for_1m_model():
    assert context_limit_for("claude-opus-4-8[1m]", 200000) == 1_000_000
    assert context_limit_for("claude-opus-4-8", 200000) == 200000


def test_aggregate_priority_waiting_wins():
    now = 1000.0
    sessions = {
        "a": Session(status="working", updated=now, project="A"),
        "b": Session(status="waiting", updated=now - 5, project="B"),
    }
    agg = aggregate(sessions, now)
    assert agg.status == "waiting"
    assert agg.active == 2


def test_update_session_prunes_stale(tmp_path):
    path = tmp_path / "s.json"
    update_session("old", status="working", project="x", context_tokens=1,
                   output_tokens=1, context_limit=200000, idle_after_minutes=30,
                   now=0.0, path=path)
    agg = update_session("new", status="idle", project="y", context_tokens=2,
                         output_tokens=2, context_limit=200000, idle_after_minutes=30,
                         now=10_000.0, path=path)
    # 'old' (t=0) is >30min before t=10000 -> pruned, only 'new' remains
    assert agg.project == "y"
    assert agg.active == 0


def test_local_not_configured_returns_error():
    from claude_lametric.client import LaMetricClient
    res = LaMetricClient(Config()).notify_local([{"text": "hi"}])
    assert not res.ok and res.error == "not configured"
