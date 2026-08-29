"""The general searcher must never promote itself to the harness's PRIMARY OWNER.

Purpose: pin the one relationship that `graph`'s bid and the harness's ownership threshold have to
each other, across two files. `UnifiedAgent` marks a tool `_primary_owns` when its `detect` reaches
`_PRIMARY_CONF`, and an owner is NEVER retired on a stall for the rest of the level. `graph` is the
general searcher that inherits every board no specialist claims, and its top bid fires on
"a small localized region changed" — i.e. "there is an avatar" — which is not evidence that it has a
plan for the board it just inherited.

MEASURED (`scripts/rounds/R101SELECT`, 2026-08-30): at 0.8 it won the handover on bp35 and lf52,
latched ownership, and held those levels for 486 and 366 actions without clearing anything.

Expected feedback: pass ⇒ a stalled `graph` can still be swapped out. Fail ⇒ either the tool's bid
rose or the harness's threshold fell, and the general searcher can once again seize a board for a
whole level — the exact failure this pair of constants exists to prevent. This is a DURABLE
contract test, not feedback-gated: it guards a cross-file invariant that has no other home, which is
how a constant with two homes silently overrode the one that was measured.
"""

from __future__ import annotations

from admorphiq.harness.loop import _PRIMARY_CONF
from admorphiq.tools.graph_search import _LOCALIZED_CONF


def test_graph_top_bid_is_below_the_ownership_threshold():
    assert _LOCALIZED_CONF < _PRIMARY_CONF, (
        f"graph's localized bid {_LOCALIZED_CONF} is at or above the harness ownership "
        f"threshold {_PRIMARY_CONF}: the general searcher would become un-retirable on any "
        f"board where it merely observed an avatar move."
    )


def test_graph_top_bid_still_outranks_its_own_no_evidence_band():
    """The fix must deny OWNERSHIP without demoting graph in the ranking — the two are separate
    changes and only one of them was measured."""
    assert _LOCALIZED_CONF > 0.45
