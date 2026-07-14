"""Tests for the code-REPL segmenter + tracker (R55 module 2).

These prove the perception invariants the turn packet relies on: stable object
ids across translation, correct CHANGE events (move / recolor / split / appear /
disappear), translation-invariant shape hashes, hole counting, a verified
interior click, and containment/adjacency relations. Wrong tracking here would
feed the model a false transition ledger — the exact failure mode the design doc
warns makes reflection entrench false theories.
"""

from __future__ import annotations

import numpy as np

from admorphiq.repl_agent.segmentation import (
    SceneTracker,
    shape_hash,
)


def _blank(bg: int = 0) -> np.ndarray:
    return np.full((16, 16), bg, dtype=np.int64)


def test_shape_hash_translation_invariant():
    """Purpose: the same shape at different positions hashes identically.

    Feedback: failure means a moving object would get a new id every frame,
    destroying the transition ledger.
    """
    a = [(2, 2), (2, 3), (3, 2)]
    b = [(9, 5), (9, 6), (10, 5)]  # same L-shape, translated
    assert shape_hash(a) == shape_hash(b)
    assert shape_hash(a) != shape_hash([(0, 0), (0, 1)])


def test_stable_id_across_move():
    """Purpose: a moved object keeps its id and emits a 'moved' event.

    Feedback: failure means action-effect attribution (LEFT moved o3) breaks.
    """
    tracker = SceneTracker(background=0)
    f1 = _blank()
    f1[5, 5] = 2
    f1[5, 6] = 2
    scene1 = tracker.update(f1)
    oid = scene1.objects[0].id

    f2 = _blank()
    f2[5, 3] = 2
    f2[5, 4] = 2  # same 2-cell object, shifted left
    scene2 = tracker.update(f2)
    assert scene2.objects[0].id == oid
    assert any(e["type"] == "moved" and e["id"] == oid for e in scene2.events)


def test_recolor_keeps_id_and_events():
    """Purpose: an object recolored in place keeps its id, emits 'recolored'.

    Feedback: failure means recolor mechanics (paint games) are mis-tracked as
    disappear+appear.
    """
    tracker = SceneTracker(background=0)
    f1 = _blank()
    f1[4:6, 4:6] = 3  # 2x2 green block
    s1 = tracker.update(f1)
    oid = s1.objects[0].id

    f2 = _blank()
    f2[4:6, 4:6] = 7  # same cells, now orange
    s2 = tracker.update(f2)
    assert s2.objects[0].id == oid
    assert any(e["type"] == "recolored" and e["to"] == 7 for e in s2.events)


def test_split_event_and_new_ids():
    """Purpose: one object splitting into two emits a 'split' event with the two
    child ids.

    Feedback: failure means split/merge mechanics feed wrong object counts to the
    model.
    """
    tracker = SceneTracker(background=0)
    f1 = _blank()
    f1[8, 4:9] = 5  # a 1x5 bar
    s1 = tracker.update(f1)
    parent = s1.objects[0].id

    f2 = _blank()
    f2[8, 4:6] = 5   # left piece
    f2[8, 7:9] = 5   # right piece (gap in the middle)
    s2 = tracker.update(f2)
    split = [e for e in s2.events if e["type"] == "split"]
    assert split and split[0]["id"] == parent
    assert len(split[0]["into"]) == 2
    assert len(s2.objects) == 2


def test_appear_and_disappear():
    """Purpose: a brand-new object appears; a removed one disappears.

    Feedback: failure means object lifecycle events (spawns/removals) are lost.
    """
    tracker = SceneTracker(background=0)
    f1 = _blank()
    f1[2, 2] = 2
    tracker.update(f1)

    f2 = _blank()
    f2[2, 2] = 2
    f2[10, 10] = 4  # new object
    s2 = tracker.update(f2)
    assert any(e["type"] == "appeared" for e in s2.events)

    f3 = _blank()
    f3[10, 10] = 4  # the first object is gone
    s3 = tracker.update(f3)
    assert any(e["type"] == "disappeared" for e in s3.events)


def test_holes_and_safe_click():
    """Purpose: a ring object reports 1 hole and a safe_click that is an on-object
    cell (never the hole).

    Feedback: failure means the model could be handed a click coordinate that
    misses the object.
    """
    tracker = SceneTracker(background=0)
    f = _blank()
    f[4:9, 4:9] = 6      # 5x5 filled
    f[6, 6] = 0          # punch a hole in the center
    scene = tracker.update(f)
    obj = scene.objects[0]
    assert obj.holes == 1
    assert obj.safe_click in set(obj.cells)
    assert obj.safe_click != (6, 6)


def test_containment_relation():
    """Purpose: a small object inside a larger ring is contained_by it.

    Feedback: failure means spatial relations (inside/outside) are wrong, which
    the goal reasoning depends on.
    """
    tracker = SceneTracker(background=0)
    f = _blank()
    # hollow 7x7 ring of color 5
    f[2:9, 2] = 5
    f[2:9, 8] = 5
    f[2, 2:9] = 5
    f[8, 2:9] = 5
    f[5, 5] = 3  # a dot inside
    scene = tracker.update(f)
    dot = next(o for o in scene.objects if o.color == 3)
    ring = next(o for o in scene.objects if o.color == 5)
    assert dot.contained_by == ring.id


def test_adjacency_direction():
    """Purpose: two touching objects record each other as adjacent with the
    correct direction.

    Feedback: failure means "o3 adjacent_left_of o8" style relations are wrong.
    """
    tracker = SceneTracker(background=0)
    f = _blank()
    f[5, 5] = 2   # left object
    f[5, 6] = 4   # right object, touching
    scene = tracker.update(f)
    left = next(o for o in scene.objects if o.color == 2)
    adj = {a["id"]: a["direction"] for a in left.adjacent}
    right = next(o for o in scene.objects if o.color == 4)
    assert adj.get(right.id) == "right"
