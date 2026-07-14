"""Tests for the v6-vs-v5 repl-bench comparison harness (R55).

Locks the metric logic that will decide "what did the working sandbox buy":
inspection success rate (v5's dead sandbox = 0%), informed inspections, and the
action-source split. Pure functions over transcript-shaped dicts — no I/O.
"""

from __future__ import annotations

from scripts.repl_bench_compare import summarize_game


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
