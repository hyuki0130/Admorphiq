"""Tests for the matched12 OFF/ON continuation-gate evaluator (R55).

Purpose: prove that ``scripts/repl_matched_verdict.evaluate`` aggregates
per-run diagnostics by arm and adjudicates the three Codex-v8 gate conditions
(replicate clears, revision-precedes-clear causality, +2 coverage without an
efficiency regression) exactly as specified.

Expected feedback: a pass means the verdict tool will correctly PASS/FAIL the
gate when the real matched12 package lands, so its output can be trusted to
decide whether the REPL audit arm advances to full-25. A failure means the
adjudication logic is wrong and must not be used to gate the round.
"""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from repl_matched_verdict import (  # noqa: E402
    _split_tag,
    evaluate,
    faithful_rhae,
    load_baselines,
    load_runs,
    per_level_actions,
)


def _write_run(root, tag, *, levels, actions, audits=0, terminal="budget",
               level_up_seq=None, audit_at=None):
    """Materialize one matched run's diagnostics (+ optional events/transcript)."""
    title, arm, rep = _split_tag(tag)
    for sub in ("diagnostics", "events", "transcripts"):
        os.makedirs(os.path.join(root, sub), exist_ok=True)
    with open(os.path.join(root, "diagnostics", f"{tag}.json"), "w") as fh:
        json.dump({"game_id": title, "arm": arm, "rep": rep, "levels": levels,
                   "actions": actions, "audits_triggered": audits,
                   "terminal_reason": terminal}, fh)
    # event stream: one action per step, an optional level_up at level_up_seq.
    evs = []
    seq = 0
    for i in range(actions):
        evs.append({"seq": seq, "type": "action_executed", "action_id": i})
        seq += 1
        if level_up_seq is not None and i + 1 == level_up_seq:
            evs.append({"seq": seq, "type": "level_up"})
            seq += 1
    with open(os.path.join(root, "events", f"{tag}.events.jsonl"), "w") as fh:
        for e in evs:
            fh.write(json.dumps(e) + "\n")
    # transcript: one record; an audit that fired at audit_at (turn_in_level).
    rec = {"raw_output": "", "audit": None}
    if audit_at is not None:
        rec = {"raw_output": "", "audit": {"threshold": 12, "action_count": audit_at,
                                           "fields": {"hypothesis": "x"}}}
    with open(os.path.join(root, "transcripts", f"{tag}.jsonl"), "w") as fh:
        fh.write(json.dumps(rec) + "\n")


def test_split_tag():
    """Tag parsing must recover (title, arm, rep) and reject malformed tags."""
    assert _split_tag("su15_on_r2") == ("su15", "on", 2)
    assert _split_tag("ls20_off_r0") == ("ls20", "off", 0)
    assert _split_tag("su15_on") is None
    assert _split_tag("su15_maybe_r0") is None


def test_gate_pass(tmp_path):
    """A run where ON clears su15 3/3 with an audit before every clear and gains
    +2 games over OFF must PASS all three conditions."""
    root = str(tmp_path)
    # replicate su15: ON clears 3/3 (audit precedes level_up), OFF clears 0/3.
    for rep in range(3):
        _write_run(root, f"su15_on_r{rep}", levels=1, actions=25, audits=1,
                   terminal="win", level_up_seq=19, audit_at=12)
        _write_run(root, f"su15_off_r{rep}", levels=0, actions=25)
    # two more games ON clears, OFF does not -> coverage gain +2.
    for g in ("ls20", "bp35"):
        _write_run(root, f"{g}_on_r0", levels=1, actions=30, audits=1,
                   terminal="win", level_up_seq=20, audit_at=12)
        _write_run(root, f"{g}_off_r0", levels=0, actions=30)

    res = evaluate(root, "su15")
    assert res["C1_replicate"]["pass"] is True
    assert res["C2_revision_precedes_clear"]["pass"] is True
    assert res["C3_coverage"]["pass"] is True
    assert res["GATE_PASS"] is True


def test_gate_fail_no_revision(tmp_path):
    """If an ON clear has no audit before the level-up, C2 (causality) must FAIL
    even when the replicate and coverage conditions hold."""
    root = str(tmp_path)
    for rep in range(3):
        # su15 ON clears but WITHOUT an audit -> revision does not precede clear.
        _write_run(root, f"su15_on_r{rep}", levels=1, actions=25,
                   terminal="win", level_up_seq=19, audit_at=None)
        _write_run(root, f"su15_off_r{rep}", levels=0, actions=25)
    for g in ("ls20", "bp35"):
        _write_run(root, f"{g}_on_r0", levels=1, actions=30,
                   terminal="win", level_up_seq=20, audit_at=None)
        _write_run(root, f"{g}_off_r0", levels=0, actions=30)

    res = evaluate(root, "su15")
    assert res["C1_replicate"]["pass"] is True
    assert res["C2_revision_precedes_clear"]["pass"] is False
    assert res["GATE_PASS"] is False


def test_gate_fail_replicate_flaky(tmp_path):
    """If ON clears the replicate only 1/3, C1 must FAIL (>=2/3 required)."""
    root = str(tmp_path)
    _write_run(root, "su15_on_r0", levels=1, actions=25, audits=1,
               terminal="win", level_up_seq=19, audit_at=12)
    _write_run(root, "su15_on_r1", levels=0, actions=25)
    _write_run(root, "su15_on_r2", levels=0, actions=25)
    for rep in range(3):
        _write_run(root, f"su15_off_r{rep}", levels=0, actions=25)

    res = evaluate(root, "su15")
    assert res["C1_replicate"]["pass"] is False
    assert res["GATE_PASS"] is False


def test_per_level_actions_segments_by_level_up(tmp_path):
    """Per-level action counts must segment the event stream at level_up
    boundaries and exclude the trailing in-progress level."""
    root = str(tmp_path)
    # 6 actions (the 6th triggers level_up), then 4 (4th triggers), 2 trailing.
    _write_run(root, "su15_on_r0", levels=2, actions=12, terminal="budget")
    # overwrite events with a controlled two-level stream
    os.makedirs(os.path.join(root, "events"), exist_ok=True)
    evs, seq = [], 0
    for i, boundary in enumerate([False] * 5 + [True] + [False] * 3 + [True] + [False] * 2):
        evs.append({"seq": seq, "type": "action_executed", "action_id": i})
        seq += 1
        if boundary:
            evs.append({"seq": seq, "type": "level_up"})
            seq += 1
    with open(os.path.join(root, "events", "su15_on_r0.events.jsonl"), "w") as fh:
        for e in evs:
            fh.write(json.dumps(e) + "\n")
    # trailing 2 actions after the last level_up are excluded (in-progress level).
    assert per_level_actions(root, "su15_on_r0") == [6, 4]


def test_faithful_rhae_matches_metadata_baseline(tmp_path):
    """faithful_rhae must square the min(baseline/agent,1) ratio using the real
    metadata baseline — su15 L1 baseline is 22, so a 19-action clear caps at 1.0
    for L1 and yields 1/45 after the 9-level weighting."""
    baselines = load_baselines()
    assert baselines.get("su15", [None])[0] == 22  # sanity: metadata present
    root = str(tmp_path)
    _write_run(root, "su15_on_r0", levels=1, actions=25,
               terminal="win", level_up_seq=19)
    val = faithful_rhae(root, "su15_on_r0", "su15", baselines)
    # L1: min(22/19,1)**2 = 1.0; game_score([1.0], win_levels=9) = 1/45.
    assert val is not None and abs(val - (1.0 / 45.0)) < 1e-9


def test_faithful_rhae_none_without_baseline(tmp_path):
    """A game with no local baseline returns None (drops out of RHAE), never 0
    that would silently drag the aggregate down."""
    root = str(tmp_path)
    _write_run(root, "zz99_on_r0", levels=1, actions=25,
               terminal="win", level_up_seq=19)
    assert faithful_rhae(root, "zz99_on_r0", "zz99", {}) is None


def test_load_runs_reparses_tag_without_arm_keys(tmp_path):
    """Arm/rep must be recovered from the tag when diagnostics omit those keys
    (defensive: older kernels wrote only game_id)."""
    root = str(tmp_path)
    os.makedirs(os.path.join(root, "diagnostics"))
    with open(os.path.join(root, "diagnostics", "su15_on_r1.json"), "w") as fh:
        json.dump({"game_id": "su15", "levels": 1, "actions": 20}, fh)
    runs = load_runs(root)
    assert len(runs) == 1
    assert runs[0]["arm"] == "on" and runs[0]["rep"] == 1 and runs[0]["title"] == "su15"
