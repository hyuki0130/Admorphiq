"""Unit tests for the deterministic trace analyzer (R4 minus LLM)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "analyze_trace.py"
_SPEC = importlib.util.spec_from_file_location("analyze_trace", _SCRIPT)
assert _SPEC is not None and _SPEC.loader is not None
_MOD = importlib.util.module_from_spec(_SPEC)
sys.modules["analyze_trace"] = _MOD
_SPEC.loader.exec_module(_MOD)


def _env(
    *,
    game_id: str = "X",
    title: str = "X",
    dir_map: dict | None = None,
    primary: str = "bfs_state_space",
    fallback_stack: list | None = None,
    best_levels: int = 0,
    executions: list | None = None,
    game_type: str = "movement",
    confidence: float | None = 0.5,
    features_missing: list | None = None,
):
    return {
        "game_id": game_id,
        "game_title": title,
        "discovery": {"dir_map": dir_map or {}},
        "hypothesis": {
            "game_type": game_type,
            "primary_strategy": primary,
            "fallback_stack": fallback_stack or [],
            "confidence": confidence,
            "features_missing": features_missing or [],
        },
        "executions": executions
        or [{"strategy": primary, "status": "ok", "levels": best_levels, "actions": 1}],
        "best_levels": best_levels,
    }


def test_headline_aggregates():
    report = _MOD.analyze(
        {
            "results": [
                _env(game_id="A", best_levels=2),
                _env(game_id="B", best_levels=0),
                _env(game_id="C", best_levels=5),
            ]
        }
    )
    h = report["headline"]
    assert h["total_envs"] == 3
    assert h["envs_cleared"] == 2
    assert h["envs_failed"] == 1
    assert h["total_levels"] == 7


def test_dir_map_but_click_primary_flags_misroutes():
    report = _MOD.analyze(
        {
            "results": [
                _env(game_id="M0R0", dir_map={"1": "N", "2": "S"}, primary="click_rare"),
                _env(game_id="KA59", dir_map={"1": "N"}, primary="click_all_colors"),
                _env(game_id="AR25", dir_map={"1": "N"}, primary="bfs_state_space"),
                _env(game_id="FT09", dir_map={}, primary="click_rare"),
            ]
        }
    )
    patt = report["patterns"]["dir_map_but_click_primary"]
    assert patt["count"] == 2
    flagged = {e["game_id"] for e in patt["envs"]}
    assert flagged == {"M0R0", "KA59"}


def test_movement_type_wrong_primary():
    report = _MOD.analyze(
        {
            "results": [
                _env(game_id="A", game_type="movement", primary="click_rare"),
                _env(game_id="B", game_type="movement", primary="bfs_state_space"),
                _env(game_id="C", game_type="click", primary="click_rare"),
            ]
        }
    )
    patt = report["patterns"]["movement_type_non_movement_primary"]
    assert patt["count"] == 1
    assert patt["envs"][0]["game_id"] == "A"


def test_wasted_budget_caught_when_all_zero():
    execs = [
        {"strategy": "a", "status": "ok", "levels": 0, "actions": 500},
        {"strategy": "b", "status": "ok", "levels": 0, "actions": 1200},
    ]
    report = _MOD.analyze(
        {
            "results": [
                _env(game_id="WASTED", executions=execs, best_levels=0),
                _env(game_id="WON", best_levels=3),
            ]
        }
    )
    patt = report["patterns"]["wasted_budget_zero_levels"]
    assert patt["count"] == 1
    assert patt["envs"][0]["game_id"] == "WASTED"
    assert patt["envs"][0]["total_actions"] == 1700


def test_unknown_strategy_picks_detected():
    execs = [
        {"strategy": "bfs_state_space", "status": "ok", "levels": 0, "actions": 1},
        {"strategy": "imaginary_strategy", "status": "unknown_strategy"},
    ]
    report = _MOD.analyze({"results": [_env(game_id="X", executions=execs)]})
    patt = report["patterns"]["unknown_strategy_picks"]
    assert patt["count"] == 1
    assert patt["envs"][0]["invented_name"] == "imaginary_strategy"


def test_llm_flagged_missing_features_grouped_by_feature():
    report = _MOD.analyze(
        {
            "results": [
                _env(game_id="A", features_missing=["sprite_pixel_count"]),
                _env(game_id="B", features_missing=["sprite_pixel_count", "grid_period"]),
                _env(game_id="C", features_missing=[]),
            ]
        }
    )
    patt = report["patterns"]["llm_flagged_missing_features"]
    assert patt["count"] == 3
    by_feat = patt["by_feature"]
    assert set(by_feat["sprite_pixel_count"]) == {"A", "B"}
    assert set(by_feat["grid_period"]) == {"B"}


def test_primary_success_rates():
    report = _MOD.analyze(
        {
            "results": [
                _env(game_id="A", primary="bfs_state_space", best_levels=2),
                _env(game_id="B", primary="bfs_state_space", best_levels=0),
                _env(game_id="C", primary="click_rare", best_levels=6),
            ]
        }
    )
    rates = report["primary_success_rates"]
    assert rates["bfs_state_space"]["attempts"] == 2
    assert rates["bfs_state_space"]["cleared"] == 1
    assert rates["bfs_state_space"]["cleared_pct"] == 0.5
    assert rates["click_rare"]["cleared"] == 1


def test_mean_confidence_ignores_missing():
    report = _MOD.analyze(
        {
            "results": [
                _env(game_id="A", confidence=0.8),
                _env(game_id="B", confidence=0.2),
                _env(game_id="C", confidence=None),
            ]
        }
    )
    assert report["headline"]["mean_confidence"] == 0.5
