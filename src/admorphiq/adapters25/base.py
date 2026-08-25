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

    @classmethod
    def detect(cls, latest_frame: Any) -> bool:
        """Does THIS adapter's mechanic appear in the frame? Never overridden.

        Detection runs an adapter's own discovery code against boards it was never
        written for, and that code is entitled to assume its mechanic — MEASURED on the
        first port: ft09's ring discovery raises ``IndexError`` reading a glyph compass
        on a foreign board, because no ring is there to read. An exception means "not my
        mechanic", so the guard belongs here, once, rather than as boilerplate in every
        adapter.
        """
        if not has_frame(latest_frame):
            return False
        try:
            return bool(cls._detect_mechanic(latest_frame))
        except Exception:  # noqa: BLE001 — a foreign board is a NO, never a crash
            return False

    @classmethod
    def detect_probed(cls, before: Any, after: Any) -> bool:
        """Does this adapter's mechanic appear across ONE probe transition? Never overridden.

        Some mechanics are simply not visible in a still frame. MEASURED: m0r0's grounding
        reads the player colour from what MOVED, and a static colour-searching stand-in
        resolves a "maze" on 18 of the 25 public games; one probe takes that to 2, and
        adding the mechanic's own mirror pair takes it to 1. The dispatcher issues a
        SINGLE shared probe and offers the pair to every probe detector, so the cost is
        one action no matter how many adapters are ported this way.

        Same guard as :meth:`detect`, for the same measured reason.
        """
        if not (has_frame(before) and has_frame(after)):
            return False
        try:
            return bool(cls._detect_mechanic_probed(before, after))
        except Exception:  # noqa: BLE001 — a foreign board is a NO, never a crash
            return False

    @classmethod
    def _detect_mechanic_probed(cls, before: Any, after: Any) -> bool:
        """The mechanic's signature ACROSS a probe. Override this, not :meth:`detect_probed`.

        Default ``False``: an adapter that reads statically, or not at all, never asks for
        the probe. Override it only when a still frame genuinely cannot show the mechanic —
        paying an action to recognise a board is only worth it when the recognition is
        otherwise impossible.
        """
        return False

    @classmethod
    def _detect_mechanic(cls, latest_frame: Any) -> bool:
        """The mechanic's OBSERVABLE signature. Override this, not :meth:`detect`.

        The default is ``False``, so an adapter that has not been ported never fires
        under detection dispatch and costs nothing. Write it the way
        `ring_paint.detect_paint_layout` reads a canvas/target/swatch geometry — with no
        game identity anywhere — never by recognising one board's constants.

        ⛔ `GAME_ID` selection stays for script25's own ceiling measurement. Detection is
        what a submission may use, because the 110 private games carry no id we know.
        """
        return False

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
