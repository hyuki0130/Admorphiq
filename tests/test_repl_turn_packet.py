"""Tests for the code-REPL turn-packet builder (R55 module 3).

These lock the prompt contract: the YAML packet has the six required sections,
CHANGE reflects tracked events, the packet is snapshot-stable (deterministic) and
respects the token budget, the three-tier history compacts correctly, and — most
importantly — the falsifiable-hypothesis memory DOWNGRADES a theory on
contradiction (contradiction recovery) instead of entrenching it.
"""

from __future__ import annotations

import numpy as np
import yaml

from admorphiq.repl_agent.segmentation import SceneTracker
from admorphiq.repl_agent.turn_packet import (
    EnvironmentMemory,
    HistoryTiers,
    Hypothesis,
    TurnPacketBuilder,
    estimate_tokens,
)


def _scene_pair():
    """A move transition: a 2-cell object shifts left one column."""
    tracker = SceneTracker(background=0)
    f1 = np.zeros((16, 16), dtype=np.int64)
    f1[5, 5:7] = 2
    s1 = tracker.update(f1)
    f2 = np.zeros((16, 16), dtype=np.int64)
    f2[5, 4:6] = 2
    s2 = tracker.update(f2)
    return s1, s2, f1, f2


def _game_ctx():
    return {"game_id": "hidden_042", "level": 1, "turn_in_level": 3,
            "total_actions": 3, "legal_actions": ["LEFT", "RIGHT", "MOUSE"]}


def test_packet_has_six_sections():
    """Purpose: the packet exposes GAME/LAST_ACTION/CHANGE/SCENE/RECENT_EVENTS/
    MEMORY as the design doc requires.

    Feedback: failure means the model prompt is missing a structural section.
    """
    s1, s2, f1, f2 = _scene_pair()
    b = TurnPacketBuilder()
    packet = b.build(game=_game_ctx(), last_action={"action": "LEFT"},
                     scene=s2, prev_scene=s1, frame=f2, prev_frame=f1,
                     history=HistoryTiers(), memory=EnvironmentMemory())
    for key in ("GAME", "LAST_ACTION", "CHANGE", "SCENE", "RECENT_EVENTS", "MEMORY"):
        assert key in packet


def test_change_section_reports_move():
    """Purpose: CHANGE reflects the tracked 'moved' event + a nonzero diff bbox.

    Feedback: failure means the transition ledger handed to the model is wrong.
    """
    s1, s2, f1, f2 = _scene_pair()
    b = TurnPacketBuilder()
    packet = b.build(game=_game_ctx(), last_action={"action": "LEFT"},
                     scene=s2, prev_scene=s1, frame=f2, prev_frame=f1,
                     history=HistoryTiers(), memory=EnvironmentMemory())
    change = packet["CHANGE"]
    assert change["moved"] and change["moved"][0]["id"] == s2.objects[0].id
    assert change["changed_bbox"] is not None
    assert change["cells_changed"] > 0


def test_yaml_snapshot_stable():
    """Purpose: identical inputs produce byte-identical YAML (deterministic).

    Feedback: failure means prompt-cache reasoning and replay diffing are
    unreliable.
    """
    s1, s2, f1, f2 = _scene_pair()
    b = TurnPacketBuilder()
    kwargs = dict(game=_game_ctx(), last_action={"action": "LEFT"},
                  scene=s2, prev_scene=s1, frame=f2, prev_frame=f1)
    y1 = b.to_yaml(b.build(**kwargs, history=HistoryTiers(), memory=EnvironmentMemory()))
    y2 = b.to_yaml(b.build(**kwargs, history=HistoryTiers(), memory=EnvironmentMemory()))
    assert y1 == y2
    parsed = yaml.safe_load(y1)  # valid YAML
    assert "SCENE" in parsed


def test_objects_use_rc_coordinate_names():
    """Purpose: object coordinate fields carry the _rc suffix (Codex defect #6:
    unlabeled arrays caused row/col swaps).

    Feedback: failure means the model cannot tell (row,col) from (x,y).
    """
    s1, s2, f1, f2 = _scene_pair()
    b = TurnPacketBuilder()
    packet = b.build(game=_game_ctx(), last_action=None, scene=s2,
                     history=HistoryTiers(), memory=EnvironmentMemory())
    obj = packet["SCENE"]["objects"][0]
    assert "safe_click_rc" in obj and "bbox_rc" in obj and "centroid_rc" in obj
    assert "safe_click" not in obj and "bbox" not in obj


def test_changed_objects_retained_first_on_trim():
    """Purpose: when trimming for the token budget, CHANGED objects are kept and
    large UNCHANGED ones are dropped first (Codex defect #7: events referenced
    trimmed ids), with a visible objects_shown marker.

    Feedback: failure means CHANGE names an object absent from SCENE.objects.
    """
    tracker = SceneTracker(background=0)
    f1 = np.zeros((16, 16), dtype=np.int64)
    f1[0:4, 0:4] = 5          # a big unchanged block
    f1[10, 10] = 2            # a small object that will move
    tracker.update(f1)
    f2 = np.zeros((16, 16), dtype=np.int64)
    f2[0:4, 0:4] = 5          # big block unchanged
    f2[10, 12] = 2            # the small object moved -> a CHANGE event
    scene = tracker.update(f2)
    moved_ids = {e["id"] for e in scene.events if e["type"] == "moved"}
    b = TurnPacketBuilder(token_budget=90, max_objects=20)  # tight -> must trim
    packet = b.build(game=_game_ctx(), last_action=None, scene=scene,
                     history=HistoryTiers(), memory=EnvironmentMemory())
    shown_ids = {o["id"] for o in packet["SCENE"]["objects"]}
    assert moved_ids and moved_ids <= shown_ids   # changed object survived the trim
    assert "objects_shown" in packet["SCENE"]     # visible marker


def test_token_budget_trims_objects():
    """Purpose: a tiny token budget forces SCENE.objects truncation and sets the
    truncated meta flag.

    Feedback: failure means packets can blow the context window on busy scenes.
    """
    tracker = SceneTracker(background=0)
    f = np.zeros((16, 16), dtype=np.int64)
    for i in range(6):  # six separate objects
        f[2 * i, 0] = i + 1
    scene = tracker.update(f)
    b = TurnPacketBuilder(token_budget=60)  # very tight
    packet = b.build(game=_game_ctx(), last_action=None, scene=scene,
                     history=HistoryTiers(), memory=EnvironmentMemory())
    assert packet["_meta"].get("truncated") is True
    assert len(packet["SCENE"]["objects"]) < 6


def test_history_tiers_compaction():
    """Purpose: the ledger keeps only its last N events; recent_events returns the
    tail.

    Feedback: failure means unbounded history growth or wrong recent-event slice.
    """
    h = HistoryTiers(recent=4, ledger=5)
    for i in range(10):
        h.push({"t": i}, [f"e{i}"])
    assert len(h.ledger) == 5
    assert len(h.recent) == 4
    assert h.recent_events(3) == ["e7", "e8", "e9"]


def test_hypothesis_contradiction_recovery():
    """Purpose: a confirmed hypothesis is downgraded on contradicting evidence and
    rejected on sustained contradiction (falsifiability).

    Feedback: failure means the memory entrenches false theories — the exact
    reflection failure the design doc warns against.
    """
    h = Hypothesis("goal is X", confidence=0.85)
    h.support("t1: predicted change happened")  # -> 0.95, confirmed
    assert h.status == "confirmed"
    h.contradict("t2: predicted change did NOT happen")
    assert h.status == "active" and h.confidence < 0.95
    h.contradict("t3: contradicted again")
    assert h.status == "rejected"


def test_memory_hides_rejected_hypotheses():
    """Purpose: rejected hypotheses drop out of the memory dict surfaced to the
    model; active ones remain, most-confident first.

    Feedback: failure means dead theories keep polluting the prompt.
    """
    mem = EnvironmentMemory()
    good = Hypothesis("keep me", confidence=0.7)
    bad = Hypothesis("reject me", confidence=0.3)
    bad.contradict("x")
    bad.contradict("y")  # -> rejected
    mem.add_hypothesis(good)
    mem.add_hypothesis(bad)
    d = mem.to_dict()
    texts = [x["hypothesis"] for x in d["goal_hypotheses"]]
    assert "keep me" in texts and "reject me" not in texts


def test_estimate_tokens_monotone():
    """Purpose: the token estimate grows with text length (budget math sanity).

    Feedback: failure means the budget cap can't be trusted.
    """
    assert estimate_tokens("") == 0
    assert estimate_tokens("a" * 40) == 10
    assert estimate_tokens("a" * 41) > estimate_tokens("a" * 40)
