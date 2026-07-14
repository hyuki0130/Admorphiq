"""Tests for the v6-vs-v5 repl-bench comparison harness (R55).

Locks the metric logic that will decide "what did the working sandbox buy":
inspection success rate (v5's dead sandbox = 0%), informed inspections, and the
action-source split. Pure functions over transcript-shaped dicts — no I/O.
"""

from __future__ import annotations

import json

from scripts.repl_bench_compare import action_phases, summarize_game


def test_summarize_game_metrics():
    """Purpose: inspection success + informed inspections + source split are
    computed correctly from transcript records.

    Feedback: failure means the v6/v5 delta analysis reports wrong numbers.
    """
    recs = [
        # inspection that ERRORED (v5 P0 case): code, no action(), sandbox_error.
        {"raw_output": "```python\nobjects(-1)\n```", "sandbox_error": "boom",
         "sandbox_stdout": "", "parsed_tool_calls": [{"tool": "code"}],
         "prompt_text": "LAST_ACTION: source: fallback"},
        # inspection that SUCCEEDED: code, no action(), real stdout, no error.
        {"raw_output": "```python\nprint(objects(-1))\n```", "sandbox_error": "",
         "sandbox_stdout": "COUNT 3", "parsed_tool_calls": [{"tool": "code"}],
         "prompt_text": "LAST_ACTION: source: llm"},
        # a direct action turn.
        {"raw_output": '{"action":"LEFT"}', "sandbox_error": "", "sandbox_stdout": "",
         "parsed_tool_calls": [{"tool": "action"}],
         "prompt_text": "LAST_ACTION: source: llm"},
    ]
    m = summarize_game(recs, events=None, diag={"actions": 2, "levels": 1})
    assert m["code_turns"] == 2
    assert m["sandbox_error_turns"] == 1
    assert m["inspection_success_rate"] == 0.5      # 1 of 2 code turns clean
    assert m["informed_inspections"] == 1           # the one with real stdout
    assert m["src_llm_pct"] == round(100 * 2 / 3, 1)
    assert m["src_fallback_pct"] == round(100 * 1 / 3, 1)
    assert m["env_actions"] == 2 and m["levels"] == 1


def test_action_phases_separates_l1_from_post_clear(tmp_path):
    """Purpose: actions-to-first-level-up counts only pre-clear actions, not the
    bench's post-L1 continuation (Codex v7: '107 actions' was really 19 to L1 +
    86 after).

    Feedback: failure means RHAE/efficiency is computed on the wrong action count.
    """
    (tmp_path / "transcripts").mkdir()
    (tmp_path / "events").mkdir()
    # 5 executed actions, level_up after the 3rd; one audit at action_count 2.
    events = []
    seq = 0
    for i in range(5):
        events.append({"seq": seq, "type": "action_executed", "action_id": i})
        seq += 1
        events.append({"seq": seq, "type": "transition", "action_id": i})
        seq += 1
        if i == 2:
            events.append({"seq": seq, "type": "level_up", "level": 1})
            seq += 1
    (tmp_path / "events" / "g.events.jsonl").write_text(
        "\n".join(json.dumps(e) for e in events) + "\n")
    recs = [{"audit": {"threshold": 12, "action_count": 2, "fields": {}}}]
    (tmp_path / "transcripts" / "g.jsonl").write_text(
        "\n".join(json.dumps(r) for r in recs) + "\n")
    ph = action_phases(str(tmp_path), "g")
    assert ph["cleared"] is True
    assert ph["actions_to_first_level_up"] == 3      # not 5 (2 were post-clear)
    assert ph["actions_after_level_up"] == 2
    assert ph["revision_to_level_up"] == 1           # audit@2 -> level_up@3


def test_summarize_game_empty_dead_sandbox():
    """Purpose: the v5-shaped case (all inspections errored) reports 0 success / 0
    informed — the signal the P0 fix must flip.

    Feedback: failure means we can't detect the dead-sandbox regression.
    """
    recs = [{"raw_output": "```python\nobjects(-1)\n```", "sandbox_error": "modErr",
             "sandbox_stdout": "", "parsed_tool_calls": [], "prompt_text": ""}
            for _ in range(5)]
    m = summarize_game(recs, events=None, diag=None)
    assert m["inspection_success_rate"] == 0.0
    assert m["informed_inspections"] == 0
    assert m["parse_fail_pct"] == 100.0
