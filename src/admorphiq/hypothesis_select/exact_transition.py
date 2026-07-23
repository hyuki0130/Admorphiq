"""R97 build prerequisite #1: the EXACT colour-transition verifier.

Codex trap 2 made concrete: the footprint verifier in
:mod:`admorphiq.hypothesis_select.verifier` checks only the modal changed-cell
FOOTPRINT (single-cell vs multi-cell) and so treats ``BinaryFlip`` and
``OrderedCycle`` identically — both are single-cell transitions. That verifier
CANNOT discriminate a 2-state flip from a k-colour ordered cycle, which is
exactly the discrimination R97's tier-2 hole test turns on.

This module verifies a transition model's predicted next-colour EXACTLY, per
source colour, against recorded ``(colour_before, colour_after)`` click edges:

* **OrderedCycle(order)** — every held-out edge must advance one step along the
  declared order (``order[i] -> order[i+1] -> ... -> order[0]``). Any edge whose
  source or target is off the declared order, or whose target is not the declared
  successor, is CONTRADICTED. PASS requires held-out coverage of every source
  colour in the order AND the wrap edge (``order[-1] -> order[0]``); otherwise
  UNKNOWN (min-probe: an unexercised source colour or wrap edge is not confirmed).
* **BinaryFlip** — the held-out edges must form an involution over EXACTLY two
  colours (``x <-> y``). Three or more colours, or a non-involutive edge, is
  CONTRADICTED. PASS requires both directions covered; one direction only is
  UNKNOWN.
* **EmpiricalEffectMatrix / anything else** — UNKNOWN (a footprint claim is out
  of THIS verifier's scope; the footprint verifier owns it).

Episode split (R50b leakage doctrine): verdicts are computed on HELD-OUT edges;
train edges are carried for the synthesis feedback channel only and are never
consulted for a verdict here.

Hole certification (R97 binding correction 1): :func:`certify_hole` returns True
iff, on the SAME evidence, every offered candidate is CONTRADICTED and the
ablated oracle PASSes — the pre-model, oracle-first proof that a vocabulary hole
is real (the ablated entry is genuinely non-expressible by the remaining
vocabulary) rather than a false positive (the remaining vocabulary already
expresses it, as ordered_cycle(k=2) expresses binary_flip).

Scope: exact colour-transition verification only — no compiler, no LLM, no
sandbox.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from admorphiq.hypothesis_select.grounding import GroundingService
from admorphiq.hypothesis_select.parse import _cell_class, _is_wholesale_change
from admorphiq.hypothesis_select.schema import BinaryFlip, OrderedCycle, Verdict
from admorphiq.hypothesis_select.verifier import VTransition, _split_episodes


@dataclass(frozen=True)
class ColourEdge:
    """One recorded same-cell colour transition under a click: the clicked cell
    showed ``before`` and became ``after``. ``episode`` drives the train/held-out
    split. Only colour-CHANGING clicks are recorded (``before != after``)."""

    episode: int
    before: int
    after: int


@dataclass(frozen=True)
class ColourTransitionEvidence:
    """The colour-transition evidence for one game, episode-split. Verdicts are
    computed on ``holdout``; ``train`` is the (leakage-free) synthesis-feedback
    channel and is NOT consulted for a verdict."""

    train: tuple[ColourEdge, ...]
    holdout: tuple[ColourEdge, ...]


@dataclass(frozen=True)
class HoleCertification:
    """The pre-model hole proof: whether the ablated oracle PASSes while every
    offered candidate is CONTRADICTED on the same evidence, with the per-candidate
    verdicts and a one-line reason for the decision."""

    certified: bool
    oracle_verdict: Verdict
    offered_verdicts: tuple[tuple[str, Verdict], ...]
    reason: str


# ── evidence construction ────────────────────────────────────────────────────


def _clicked_cell_edge(trace_t: VTransition) -> Optional[tuple[int, int]]:
    """The ``(before_colour, after_colour)`` of the cell a click landed on, or
    ``None`` when the transition is not a colour-changing single-cell click (a
    non-click action, a wholesale layout replacement, or a click that changed no
    cell colour at its landing site). Uses a fresh grounding parse of the before
    frame to resolve the clicked cell — the same cell-resolution the runtime
    grounding uses, so extraction is family-generic (no game id)."""
    if trace_t.action != 6:
        return None
    if _is_wholesale_change(trace_t.before, trace_t.after):
        return None
    gs = GroundingService()
    gs.feed(trace_t.before)
    rec = gs._cell_at_xy(trace_t.xy)
    if rec is None:
        return None
    before_colour = _cell_class(trace_t.before, rec.bbox)
    after_colour = _cell_class(trace_t.after, rec.bbox)
    if before_colour == after_colour:
        return None
    return before_colour, after_colour


def colour_edges_from_trace(trace: list[VTransition]) -> list[ColourEdge]:
    """Extract every colour-changing single-cell click edge from a recorded trace
    (best-effort; a real trace may be noisy — a decoy-reveal or a mis-resolved
    click can inject an off-cycle edge, which the verifier then correctly reads as
    CONTRADICTED). Returned in trace order, episode-tagged."""
    edges: list[ColourEdge] = []
    for t in trace:
        edge = _clicked_cell_edge(t)
        if edge is not None:
            edges.append(ColourEdge(episode=t.episode, before=edge[0], after=edge[1]))
    return edges


def build_colour_evidence(trace: list[VTransition]) -> ColourTransitionEvidence:
    """Build episode-split colour-transition evidence from a trace, reusing the
    verifier's ``_split_episodes`` (later win-bearing episodes held out, earlier +
    exploration episodes train)."""
    train_eps, holdout_eps = _split_episodes(trace)
    edges = colour_edges_from_trace(trace)
    return evidence_from_edges(edges, holdout_episodes=holdout_eps)


def evidence_from_edges(
    edges: list[ColourEdge], holdout_episodes: set[int]
) -> ColourTransitionEvidence:
    """Partition explicit ``ColourEdge``s into train/held-out by episode. The
    canonical seed-test entry point: the ground-truth decoded mechanic is supplied
    as clean edges (the oracle-first doctrine KNOWS the mechanic), avoiding the
    noise of naive trace scraping."""
    train = tuple(e for e in edges if e.episode not in holdout_episodes)
    holdout = tuple(e for e in edges if e.episode in holdout_episodes)
    return ColourTransitionEvidence(train=train, holdout=holdout)


# ── the exact verifier ───────────────────────────────────────────────────────


def _verify_ordered_cycle(order: tuple[int, ...], holdout: tuple[ColourEdge, ...]) -> Verdict:
    order_set = set(order)
    n = len(order)
    succ = {order[i]: order[(i + 1) % n] for i in range(n)}
    for e in holdout:
        if e.before not in order_set or e.after not in order_set:
            return Verdict.CONTRADICTED  # an off-cycle colour refutes the declared closed cycle
        if succ[e.before] != e.after:
            return Verdict.CONTRADICTED  # a source advancing to the wrong successor
    covered_sources = {e.before for e in holdout}
    if order_set - covered_sources:
        return Verdict.UNKNOWN  # some declared source colour never exercised in held-out
    wrap = (order[-1], order[0])
    if not any((e.before, e.after) == wrap for e in holdout):
        return Verdict.UNKNOWN  # the wrap edge specifically has no held-out coverage
    return Verdict.PASS


def _verify_binary_flip(holdout: tuple[ColourEdge, ...]) -> Verdict:
    colours = {e.before for e in holdout} | {e.after for e in holdout}
    if len(colours) > 2:
        return Verdict.CONTRADICTED  # a flip is 2-state; 3+ colours refute it (the k=3 case)
    if len(colours) < 2:
        return Verdict.UNKNOWN  # cannot confirm a two-state involution from < 2 colours
    x, y = sorted(colours)
    for e in holdout:
        if not ((e.before == x and e.after == y) or (e.before == y and e.after == x)):
            return Verdict.CONTRADICTED  # a non-involutive edge over the two colours
    directions = {(e.before, e.after) for e in holdout}
    if (x, y) in directions and (y, x) in directions:
        return Verdict.PASS
    return Verdict.UNKNOWN  # only one direction of the involution exercised


def verify_exact(transition_model: Any, evidence: ColourTransitionEvidence) -> Verdict:
    """The exact colour-transition verdict for ``transition_model`` on the held-out
    edges. UNKNOWN with no held-out coverage, or for a model whose claim this
    verifier does not judge (``EmpiricalEffectMatrix`` — a footprint claim)."""
    holdout = evidence.holdout
    if not holdout:
        return Verdict.UNKNOWN
    if isinstance(transition_model, OrderedCycle):
        return _verify_ordered_cycle(transition_model.order, holdout)
    if isinstance(transition_model, BinaryFlip):
        return _verify_binary_flip(holdout)
    return Verdict.UNKNOWN


def _label(transition_model: Any) -> str:
    if isinstance(transition_model, OrderedCycle):
        return f"ordered_cycle{transition_model.order}"
    if isinstance(transition_model, BinaryFlip):
        return "binary_flip"
    return type(transition_model).__name__


def certify_hole(
    evidence: ColourTransitionEvidence,
    offered: list[Any],
    oracle: Any,
) -> HoleCertification:
    """Certify that ``evidence`` exhibits a genuine vocabulary HOLE for ``oracle``:
    the ablated ``oracle`` PASSes while EVERY offered candidate is CONTRADICTED on
    the same held-out evidence (R97 binding correction 1). An empty offered set is
    never a certified hole (there is nothing shown non-expressible). A no-hole
    control (an offered candidate that PASSes — e.g. ordered_cycle(k=2) on a
    2-state toggle) returns ``certified=False``: the correct behaviour there is to
    SELECT, not to extend."""
    oracle_verdict = verify_exact(oracle, evidence)
    offered_verdicts = tuple((_label(c), verify_exact(c, evidence)) for c in offered)
    all_offered_contradicted = bool(offered_verdicts) and all(
        v is Verdict.CONTRADICTED for _, v in offered_verdicts
    )
    certified = oracle_verdict is Verdict.PASS and all_offered_contradicted
    if certified:
        reason = "ablated oracle PASS and every offered candidate CONTRADICTED — genuine hole"
    elif oracle_verdict is not Verdict.PASS:
        reason = f"oracle not confirmed on this evidence (verdict {oracle_verdict.value})"
    elif not offered_verdicts:
        reason = "no offered candidates — nothing shown non-expressible"
    else:
        passing = [lbl for lbl, v in offered_verdicts if v is not Verdict.CONTRADICTED]
        reason = f"no hole: offered candidate(s) not contradicted ({', '.join(passing)})"
    return HoleCertification(
        certified=certified,
        oracle_verdict=oracle_verdict,
        offered_verdicts=offered_verdicts,
        reason=reason,
    )


__all__ = [
    "ColourEdge",
    "ColourTransitionEvidence",
    "HoleCertification",
    "colour_edges_from_trace",
    "build_colour_evidence",
    "evidence_from_edges",
    "verify_exact",
    "certify_hole",
]
