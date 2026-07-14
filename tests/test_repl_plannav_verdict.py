"""Tests for the decoupled PLANxNAV 2x2 verdict (R55).

Purpose: prove scripts/repl_plannav_verdict aggregates {game}_{cell}_r{rep}
diagnostics by cell and applies the Codex promotion gates — a cell promotes only
with a reproduced new clear on a zero game, positive median RHAE on >=2/3 games,
>=6/9 paired wins, and no uncompensated throughput loss — with lexicographic
winner selection.

Expected feedback: a pass means the tool correctly promotes/rejects a 2x2 cell,
so its verdict can gate the full25 winner run. A failure means the gate logic is
wrong and could promote a null cell.
"""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from repl_plannav_verdict import evaluate, load_runs  # noqa: E402

# real games so faithful_rhae finds a baseline; L1 clear at these actions scores >0
GAMES = ["ls20", "g50t", "tu93"]


def _write(root, game, cell, rep, levels, actions, level_up_at=None):
    for sub in ("diagnostics", "events"):
        os.makedirs(os.path.join(root, sub), exist_ok=True)
    with open(os.path.join(root, "diagnostics", f"{game}_{cell}_r{rep}.json"), "w") as fh:
        json.dump({"game_id": game, "levels": levels, "actions": actions}, fh)
    evs, seq = [], 0
    for i in range(actions):
        evs.append({"seq": seq, "type": "action_executed", "action_id": i})
        seq += 1
        if level_up_at is not None and i + 1 == level_up_at:
            evs.append({"seq": seq, "type": "level_up"})
            seq += 1
    with open(os.path.join(root, "events", f"{game}_{cell}_r{rep}.events.jsonl"), "w") as fh:
        for e in evs:
            fh.write(json.dumps(e) + "\n")


def _build(root, nav_clears=True):
    for g in GAMES:
        for rep in range(3):
            # base: never clears (zero game), 100 actions
            _write(root, g, "base", rep, 0, 100)
            # nav: clears L1 efficiently (all 3 reps) -> new clear + high RHAE
            _write(root, g, "nav", rep, 1 if nav_clears else 0, 40,
                   level_up_at=20 if nav_clears else None)
            # plan: no clear, same as base
            _write(root, g, "plan", rep, 0, 100)
            # combined: clears too but uses more actions
            _write(root, g, "combined", rep, 1, 60, level_up_at=40)


def test_nav_cell_promotes(tmp_path):
    """A NAV cell that reproduces a new clear on all zero games with better RHAE
    must be PROMOTABLE and selected as winner."""
    root = str(tmp_path)
    _build(root)
    res = evaluate(root)
    nav = res["cell_verdict"]["nav"]
    assert nav["gate1_new_clear"] is True
    assert set(nav["new_clear_games"]) == set(GAMES)
    assert nav["gate2_median_rhae_pos"] is True
    assert nav["gate3_beats_base"] is True
    assert nav["promotable"] is True


def test_winner_prefers_simpler_cell_on_clears_tie(tmp_path):
    """nav and combined both clear all games; nav wins on efficiency/simplicity
    (fewer actions -> higher RHAE, and simpler)."""
    root = str(tmp_path)
    _build(root)
    res = evaluate(root)
    # both nav and combined clear 3 games; nav is more efficient (40 vs 60 actions)
    assert res["winner"] == "nav"


def test_no_new_clear_blocks_promotion(tmp_path):
    """If no treatment cell clears a zero game, none promote -> winner None."""
    root = str(tmp_path)
    _build(root, nav_clears=False)
    # make combined also not clear
    for g in GAMES:
        for rep in range(3):
            _write(root, g, "combined", rep, 0, 100)
    res = evaluate(root)
    assert res["cell_verdict"]["nav"]["promotable"] is False
    assert res["winner"] is None


def test_load_runs_parses_cell_tags(tmp_path):
    root = str(tmp_path)
    _build(root)
    runs = load_runs(root)
    assert len(runs) == 3 * 3 * 4  # games x reps x cells
    assert {r["cell"] for r in runs} == {"base", "nav", "plan", "combined"}
