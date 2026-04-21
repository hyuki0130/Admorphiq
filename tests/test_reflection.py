"""Unit tests for the R4 reflection script's pure helpers.

Exercises `_summarize_trace`, `_parse_proposal`, `_validate_schema`. The
LLM call itself is NOT tested here — that belongs in a live-env bench
(R6). This file only validates the glue around the LLM.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest


# The script lives under `scripts/` which isn't a package, so load it by file.
_SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "reflect_wiki_agent.py"
_SPEC = importlib.util.spec_from_file_location("reflect_wiki_agent", _SCRIPT_PATH)
assert _SPEC is not None and _SPEC.loader is not None
_MOD = importlib.util.module_from_spec(_SPEC)
sys.modules["reflect_wiki_agent"] = _MOD
_SPEC.loader.exec_module(_MOD)


# ---------------------------------------------------------------------------
# _summarize_trace
# ---------------------------------------------------------------------------


def _make_env_record(game_id="AR25", best_levels=2, strategy="bfs_state_space"):
    return {
        "game_id": game_id,
        "game_title": game_id,
        "discovery": {
            "available_actions": [1, 2, 3, 4, 6],
            "dir_map": {1: "N", 2: "S"},
            "player_color": 5,
            "movable_region_count": 1,
            "change_topology": "sprite_move",
            "probe_diffs": {1: 4, 2: 4, 6: 0, -6: 0},
            "dominant_colors": [(5, 100)],
            "click_responsive_cells": [],
            "color_histogram": {0: 0.9, 5: 0.1},
            "symmetry_score": 0.85,
        },
        "hypothesis": {
            "game_type": "movement",
            "primary_strategy": strategy,
            "fallback_stack": ["raster"],
            "rationale": "directional diffs + player color",
            "confidence": 0.7,
            "features_missing": [],
        },
        "executions": [
            {"strategy": strategy, "status": "ok", "levels": best_levels, "actions": 1200}
        ],
        "best_levels": best_levels,
        "status": "ok",
    }


def test_summarize_trace_aggregates_totals():
    trace = {
        "timestamp": "2026-04-21T12:00:00",
        "candidate": "qwen_3_8b_q4",
        "results": [
            _make_env_record("A", best_levels=2),
            _make_env_record("B", best_levels=0),
            _make_env_record("C", best_levels=5),
        ],
    }
    out = _MOD._summarize_trace(trace)
    assert out["total_envs"] == 3
    assert out["envs_cleared"] == 2  # A and C
    assert out["total_levels"] == 7
    assert out["candidate"] == "qwen_3_8b_q4"
    assert len(out["per_env"]) == 3


def test_summarize_trace_keeps_classification_inputs():
    trace = {"results": [_make_env_record()]}
    out = _MOD._summarize_trace(trace)
    entry = out["per_env"][0]
    # Features the reflection LLM must see
    assert entry["dir_map"] == {1: "N", 2: "S"}
    assert entry["player_color"] == 5
    assert entry["change_topology"] == "sprite_move"
    assert entry["predicted_type"] == "movement"
    assert entry["confidence"] == 0.7


def test_summarize_trace_drops_verbose_detail():
    """dominant_colors + click_responsive_cells + color_histogram are NOT
    forwarded — they bloat the prompt without signal for reflection."""
    trace = {"results": [_make_env_record()]}
    out = _MOD._summarize_trace(trace)
    entry = out["per_env"][0]
    assert "dominant_colors" not in entry
    assert "click_responsive_cells" not in entry
    assert "color_histogram" not in entry


def test_summarize_trace_handles_missing_best_levels():
    rec = _make_env_record()
    rec["best_levels"] = None
    trace = {"results": [rec]}
    out = _MOD._summarize_trace(trace)
    assert out["total_levels"] == 0
    assert out["envs_cleared"] == 0


# ---------------------------------------------------------------------------
# _parse_proposal
# ---------------------------------------------------------------------------


def test_parse_proposal_plain_json():
    raw = '{"summary": "ok", "failure_patterns": [], "wiki_edits": [], "new_features": [], "new_strategies": []}'
    out = _MOD._parse_proposal(raw)
    assert out["summary"] == "ok"
    assert out["failure_patterns"] == []


def test_parse_proposal_fenced_json():
    raw = "Here is the proposal:\n```json\n{\"summary\": \"fenced\", \"failure_patterns\": []}\n```\nThat's all."
    out = _MOD._parse_proposal(raw)
    assert out["summary"] == "fenced"


def test_parse_proposal_with_leading_prose():
    raw = (
        "The run looks OK.\n\n"
        '{"summary": "leading prose", "failure_patterns": [], '
        '"wiki_edits": [], "new_features": [], "new_strategies": []}'
    )
    out = _MOD._parse_proposal(raw)
    assert out["summary"] == "leading prose"


def test_parse_proposal_empty_response():
    out = _MOD._parse_proposal("")
    assert "error" in out


def test_parse_proposal_no_json():
    out = _MOD._parse_proposal("no braces here at all")
    assert "error" in out


def test_parse_proposal_invalid_json():
    out = _MOD._parse_proposal("{summary: missing quotes}")
    assert "error" in out
    assert "raw_head" in out


def test_parse_proposal_prefers_summary_bearing_object():
    """LLM often echoes trace entries. Parser must pick the proposal that has
    the `summary` key, not the first `{...}` span it encounters."""
    raw = (
        '{"game_id": "X1", "probe_diffs": {"1": 0}}\n'
        'Then my analysis:\n'
        '{"summary": "the right one", "failure_patterns": [], '
        '"wiki_edits": [], "new_features": [], "new_strategies": []}'
    )
    out = _MOD._parse_proposal(raw)
    assert out.get("summary") == "the right one"


def test_parse_proposal_picks_longest_summary_match():
    """If multiple summary-bearing spans exist (e.g., example + real answer),
    the longest one wins — the real answer is typically richer than the
    in-prompt example the LLM may parrot."""
    short = '{"summary": "short", "failure_patterns": []}'
    longer = ('{"summary": "longer with more detail in every section",'
              ' "failure_patterns": [{"pattern": "X", "envs": ["A", "B"],'
              ' "root_cause_hypothesis": "Y"}]}')
    out = _MOD._parse_proposal(f"before {short} then {longer}")
    assert "longer with more detail" in out["summary"]


# ---------------------------------------------------------------------------
# _validate_schema
# ---------------------------------------------------------------------------


def _complete_proposal():
    return {
        "summary": "s",
        "failure_patterns": [],
        "wiki_edits": [],
        "new_features": [],
        "new_strategies": [],
    }


def test_validate_schema_complete_is_ok():
    assert _MOD._validate_schema(_complete_proposal()) == []


def test_validate_schema_flags_missing_field():
    p = _complete_proposal()
    del p["summary"]
    issues = _MOD._validate_schema(p)
    assert any("summary" in i for i in issues)


def test_validate_schema_flags_wrong_type():
    p = _complete_proposal()
    p["failure_patterns"] = "not a list"
    issues = _MOD._validate_schema(p)
    assert any("failure_patterns" in i for i in issues)


def test_validate_schema_short_circuits_on_error_key():
    issues = _MOD._validate_schema({"error": "parse failed"})
    assert len(issues) == 1
    assert "parse failed" in issues[0]
