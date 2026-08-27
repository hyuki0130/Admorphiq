"""Registration order now DECIDES boards, so its invariant is pinned rather than assumed.

Purpose: prove that `default_tools()` lists every selective tool before every general searcher.
Ties in both routing paths break by registration order — `_signature_default` takes a strict
argmax over the registry dict, and `_decide` sorts its ranked list by (-fit, registration index)
— so the order encodes "specialist before general searcher". It stopped being a comment the
moment a tie decided a game: cn04's two best fits are both 0.45, and the specialist scores 1.0000
where the searcher scores 0.0000.

Expected feedback: a failure means a newly registered tool sits in the wrong band, and the next
tied board may be routed to a searcher that cannot solve it. Fix the ORDER, not this test.
"""

from __future__ import annotations

import sys

sys.path.insert(0, "src")

from admorphiq.harness.registry import default_tools  # noqa: E402

# The three general searchers, measured 2026-08-27 to bid on ALL 25 sample boards while every
# other tool bids on exactly one. The split is clean — no tool anywhere in between — which is
# why a name list is honest here rather than a threshold that would need re-tuning.
GENERAL_SEARCHERS = {"graph", "world_model", "deadsig"}


def test_every_specialist_precedes_every_general_searcher() -> None:
    """Purpose: pin the ordering invariant the registry's own docstring claims.

    Expected feedback: failing means a specialist was registered after graph/world_model/deadsig,
    so on a tied board the searcher wins and the mechanic tool never gets a turn.
    """
    order = [t.name for t in default_tools()]
    last_specialist = max(
        (i for i, n in enumerate(order) if n not in GENERAL_SEARCHERS), default=-1
    )
    first_general = min(
        (i for i, n in enumerate(order) if n in GENERAL_SEARCHERS), default=len(order)
    )
    misplaced = [n for n in order[first_general:] if n not in GENERAL_SEARCHERS]
    assert not misplaced, (
        f"registered after a general searcher: {misplaced}. "
        f"Ties break by registration order, so these lose boards they could solve. "
        f"(last specialist at {last_specialist}, first searcher at {first_general})"
    )


def test_the_general_searchers_are_all_registered() -> None:
    """Purpose: the fallback path names graph and world_model explicitly when nothing bids.

    Expected feedback: failing means `_signature_default`'s deliberate default is unreachable and
    an unclaimed board would fall to whichever tool happens to be first in the dict — which the
    docstring there calls an accident of ordering rather than a decision.
    """
    names = {t.name for t in default_tools()}
    assert GENERAL_SEARCHERS <= names, f"missing: {sorted(GENERAL_SEARCHERS - names)}"


def test_tool_names_are_unique() -> None:
    """Purpose: names are the routing key — the LLM picks one, and `self.tools` is keyed by it.

    Expected feedback: failing means one tool silently shadows another in the registry dict, so a
    tool that measures well in isolation never runs and its gate reports it inert.
    """
    names = [t.name for t in default_tools()]
    dupes = {n for n in names if names.count(n) > 1}
    assert not dupes, f"duplicate tool names: {sorted(dupes)}"
