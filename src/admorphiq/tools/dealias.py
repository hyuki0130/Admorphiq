"""Hidden-state de-aliasing tool — detects and corrects frame-hash aliasing.

Problem (measured in ``graph_frontier_agent.py``, R53): a graph-search agent
keys states by a hash of the VISIBLE frame (``base_hash``). Some games carry
hidden state the frame does not fully expose (an internal counter, a queued
item, a turn parity) so two genuinely different underlying states can hash to
the SAME ``base_hash``. When that happens, the same (state, action) pair is
observed to lead to two DIFFERENT resulting states — a nondeterminism
signature from the search's point of view, even though the game itself is
deterministic. This is the #1 cause of graph-search plateaus: the graph
corrupts (one node's outgoing edge keeps getting silently overwritten) and
search stalls on a state that is actually still expanding.

This tool is a pure AUGMENTATION, not a primary mover:

* :meth:`observe` watches ``(from_hash, action) -> next_hash`` across the
  whole trajectory and flags a ``from_hash`` as ALIASED the moment two visits
  disagree on where the same action leads.
* :meth:`key` is what a graph/search tool should call instead of raw
  ``base_hash`` — for a non-aliased state it IS ``base_hash`` unchanged; for a
  flagged one it appends a short suffix built from the last few action ids
  that reached the frame, splitting the corrupted node into as many keys as
  there are distinguishable recent histories.
* :meth:`propose` always returns ``[]``: de-aliasing does not choose actions,
  it only sharpens the state key other tools consult.

Frame-only and game-agnostic throughout: every signal here is derived from
``base_hash`` of observed frames and the action ids taken between them, never
from game internals, titles, sprite tags, or ids.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import numpy as np

from admorphiq.tools.base import Step, base_hash

__all__ = ["DealiasTool"]

# How many recent action ids the de-aliased key suffix carries. Short enough
# that it does not itself explode the key space, long enough to usually
# separate the handful of hidden-state variants a game exhibits.
_DEFAULT_HISTORY_K = 3

# Fixed confidence reported once ANY aliasing has been measured this level.
# detect() is a coarse "is this primitive relevant at all" signal, not a
# graded score — the graph corrupting even once is enough to warrant
# switching search tools over to de-aliased keys.
_ALIASED_CONFIDENCE = 0.9


class DealiasTool:
    """Detects frame-hash aliasing and hands out de-aliased state keys.

    Call :meth:`observe` after every action, exactly like any other harness
    tool. Call :meth:`key` wherever a graph/search tool would otherwise use
    ``base_hash(frame)`` directly, passing the recent action history that led
    to ``frame`` — the tool uses it only for states it has actually measured
    as ambiguous, so unaffected games see byte-identical keys.
    """

    name = "dealias"

    def __init__(self, history_k: int = _DEFAULT_HISTORY_K) -> None:
        self._history_k = history_k
        # (from_hash, action) -> the most recently observed next_hash. Only
        # ever needs the LAST outcome: a second, differing outcome is what
        # flags the alias, so the table never has to remember every visit.
        self._edges: dict[tuple[str, Step], str] = {}
        self._aliased: set[str] = set()
        # The (from_hash, action) pair whose resulting hash is not yet known
        # — resolved by the NEXT call to observe() (see its docstring).
        self._pending: tuple[str, Step] | None = None

    # ── Tool protocol (src/admorphiq/tools/base.py) ─────────────────────────

    def detect(self, frames: list[Any], obs: Any) -> float:
        """HIGH once any aliasing has been measured this level, ~0 otherwise.

        Frame-only: the confidence is entirely a function of what
        :meth:`observe` has measured from frame-hash transitions, never of
        game internals. ``frames``/``obs`` are accepted for protocol parity
        with every other tool but are not consulted directly — the tool's
        own aliasing trace, built purely from frame hashes, is the signal.
        """
        return _ALIASED_CONFIDENCE if self._aliased else 0.0

    def reset(self) -> None:
        """Drop all per-level aliasing memory (called on a level transition).

        A hidden-state ambiguity discovered in one level says nothing about
        the next level's layout, so the edge table, the aliased-base set, and
        the pending transition all start empty again.
        """
        self._edges.clear()
        self._aliased.clear()
        self._pending = None

    def observe(self, prev: np.ndarray, action: Step, changed: bool) -> None:
        """Fold one more (frame, action) step into the aliasing trace.

        ``prev`` is the frame the agent was looking at when it chose
        ``action`` — which is simultaneously the RESULT of whatever action was
        supplied on the call before. That dual role is what lets a
        one-frame-at-a-time signature reconstruct full transitions: this call
        first resolves the PREVIOUS call's pending ``(from_hash, action)``
        pair against ``base_hash(prev)``, flagging ``from_hash`` as aliased if
        the resolved hash disagrees with what that pair produced last time,
        then opens a new pending pair for the ``action`` just supplied.

        ``changed`` is accepted for protocol parity with every other tool;
        the frame content (not the boolean) is the ground truth used here, so
        it is not read.
        """
        cur_hash = base_hash(prev)
        if self._pending is not None:
            from_hash, from_action = self._pending
            edge_key = (from_hash, from_action)
            prior_next = self._edges.get(edge_key)
            if prior_next is not None and prior_next != cur_hash:
                self._aliased.add(from_hash)
            self._edges[edge_key] = cur_hash
        self._pending = (cur_hash, action)

    def propose(self, frames: list[Any], obs: Any) -> list[Step]:
        """Always empty — de-aliasing augments state keys, it proposes no actions."""
        return []

    # ── de-aliased key ───────────────────────────────────────────────────────

    def key(self, frame: np.ndarray, recent_actions: Sequence[Step]) -> str:
        """The state key search tools should use instead of raw ``base_hash``.

        Returns ``base_hash(frame)`` unchanged unless that hash has been
        flagged aliased by :meth:`observe`, in which case the ids of the last
        ``history_k`` actions in ``recent_actions`` (the history that reached
        ``frame``) are appended so the hidden states that collided on the
        same visible hash separate into distinct keys again.
        """
        h = base_hash(frame)
        if h not in self._aliased:
            return h
        tail = list(recent_actions)[-self._history_k:]
        suffix = ",".join(str(step[0]) for step in tail)
        return f"{h}|{suffix}"

    @property
    def aliased_bases(self) -> frozenset[str]:
        """Read-only snapshot of the base hashes currently flagged as aliased."""
        return frozenset(self._aliased)
