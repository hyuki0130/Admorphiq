"""Adapter base contract for the script25 quarantine zone (R56).

****************************************************************************
* QUARANTINE — MODEL-NEVER-VISIBLE.                                        *
*                                                                          *
* Everything under ``admorphiq.adapters25`` (this module included) exists  *
* ONLY to prove that ``admorphiq.kernels`` is expressive enough for a      *
* thin, hand-written script to compose a solution to a specific public     *
* game. The runtime LLM/harness agent (``admorphiq.harness``) MUST NEVER   *
* import, reference, or otherwise be exposed to anything in this package.  *
* See docs/r56_codex_toolbase_verdict_20260715.md, "script25: kernel       *
* expressiveness" vs "agent25: LLM competence" — this scoreboard is NEVER  *
* reported as agent capability.                                           *
****************************************************************************

An adapter subclasses :class:`GameAdapter` and exposes the exact harness
contract every other admorphiq agent exposes (``is_done`` /
``choose_action`` over the raw arcengine observation), so
``scripts/score_efficiency.py``'s existing ``run_game`` env-stepping loop
drives it unmodified — see that function's ``adapter_factory`` parameter.

This module is the ONE place inside the quarantine zone allowed to import
``arcengine`` directly (adapters themselves may not — see
``scripts/adapters25_lint.py``'s import whitelist, which excludes this file
from the scan). Everything an adapter needs to build a valid action or read
the observation lives here as a plain function so an adapter module's own
imports never need to reach outside ``admorphiq.kernels`` +
``admorphiq.adapters25.base`` + the standard library.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from arcengine import GameAction

Grid = tuple[tuple[int, ...], ...]


class GameAdapter(ABC):
    """Base class every quarantined per-game script25 adapter subclasses.

    Same harness contract every other admorphiq agent exposes —
    ``is_done(frames, latest_frame)`` / ``choose_action(frames,
    latest_frame)`` over the raw arcengine observation, returning an
    official :class:`arcengine.GameAction` — so
    :func:`scripts.score_efficiency.run_game` can drive an instance of this
    class exactly the way it drives every other named agent.
    """

    #: Lowercase substring matched against ``f"{game_id} {title}"`` to
    #: select which live environments this adapter targets. Set by the
    #: adapter module's ``GAME_ID`` constant (see the package docstring's
    #: discovery contract) and mirrored here for the class's own use.
    GAME_ID: str = ""

    @abstractmethod
    def is_done(self, frames: list[Any], latest_frame: Any) -> bool: ...

    @abstractmethod
    def choose_action(self, frames: list[Any], latest_frame: Any) -> GameAction: ...


# ── observation helpers ───────────────────────────────────────────────────


def state_name(latest_frame: Any) -> str:
    """The observation's state as a plain string (``"WIN"``, ``"PLAYING"``, ...)."""
    state = getattr(latest_frame, "state", None)
    return getattr(state, "name", str(state) if state is not None else "")


def has_frame(latest_frame: Any) -> bool:
    """Whether the observation carries any frame data at all."""
    fr = getattr(latest_frame, "frame", None)
    return fr is not None and len(fr) > 0


def canonical_layer(latest_frame: Any) -> Grid:
    """The observation's first frame layer as a plain ``(row, col)`` grid.

    ``latest_frame.frame`` is arcengine's ``list[list[list[int]]]`` (layer
    count varies per game). The FIRST layer is canonical here, matching the
    convention the measured-working navigation agents use
    (``admorphiq.graph_frontier_agent``, ``admorphiq.random_agent``'s own
    ``_frame_2d``) — not ``admorphiq.adapter.AdmorphiqAdapter``'s LAST-layer
    convention, which is a different (CNN-perception) agent family. Pure
    re-shaping, no game semantics; returns ``()`` when there is no frame.
    """
    fr = getattr(latest_frame, "frame", None)
    if not fr:
        return ()
    layer = fr[0]
    return tuple(tuple(int(v) for v in row) for row in layer)


def available_action_ids(latest_frame: Any) -> tuple[list[int], bool]:
    """``(simple non-coordinate action ids available, whether ACTION6 is available)``.

    "Simple" = a non-coordinate action an adapter can issue directly via
    :func:`simple_action`: ACTION1-5 and ACTION7 (undo/cancel). ACTION6 is the
    only coordinate action, so it is reported as the separate ``action6_ok``
    flag rather than in the id list; RESET (id 0) is excluded because adapters
    drive it explicitly through their own reset paths, not as a chosen move.
    Ids are returned in ``available_actions`` order (callers that need a
    stable order sort themselves). Note: ACTION7 was previously dropped here,
    which silently made undo unreachable for every adapter that filtered on
    this list — see ``tests/test_base_available_actions.py``.
    """
    simple_ids: list[int] = []
    action6_ok = False
    for a in getattr(latest_frame, "available_actions", []) or []:
        aid = a if isinstance(a, int) else getattr(a, "value", getattr(a, "id", None))
        if aid is None:
            continue
        if aid in (1, 2, 3, 4, 5, 7):
            simple_ids.append(aid)
        elif aid == 6:
            action6_ok = True
    return simple_ids, action6_ok


def most_common_color(grid: Grid) -> int:
    """The single most frequent color in ``grid`` — a generic background guess.

    Ties broken toward the smallest color value for determinism. Returns 0
    for an empty grid.
    """
    counts: dict[int, int] = {}
    for row in grid:
        for v in row:
            counts[v] = counts.get(v, 0) + 1
    if not counts:
        return 0
    return max(counts.items(), key=lambda kv: (kv[1], -kv[0]))[0]


# ── action plumbing ───────────────────────────────────────────────────────


def reset_action() -> GameAction:
    return GameAction.RESET


def simple_action(action_id: int) -> GameAction:
    """A non-coordinate action (RESET or ACTION1-5/7) by its official id."""
    return GameAction.from_id(action_id)


def click_action(x: int, y: int) -> GameAction:
    """An ACTION6 click at pixel ``(x, y)``, coordinates already resolved by the caller."""
    action = GameAction.ACTION6
    action.set_data({"x": int(x), "y": int(y)})
    return action
