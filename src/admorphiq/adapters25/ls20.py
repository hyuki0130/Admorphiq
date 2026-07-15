"""script25 quarantined adapter: LS20 (shape/color/rotation-matching maze).

*** QUARANTINE — MODEL-NEVER-VISIBLE. See admorphiq.adapters25's package
docstring. ***

``.wiki/wiki/games/LS20.md`` (read for reference, not imported) recorded
LS20 as "pure maze navigation" (a 2026-07-13 correction that OVER-corrected
an even-earlier "shape/rotation matching" note). **Both the pure-maze read
and the original shape-matching read were half-right; direct source +
live measurement below shows the true mechanic is a COMBINATION:**

**Mechanic model (measured — offline source read of the game class for
UNDERSTANDING only, never imported; then verified live).** The avatar is a
compound sprite carrying a "token" with three attributes — SHAPE, COLOR,
ROTATION. The maze contains three kinds of *changer* cells that each cycle
one attribute of the carried token when stepped on, plus WALL cells and one
or more GOAL cells. A goal cell is:

- BLOCKING while the carried token does NOT match that goal's required
  (shape, color, rotation) — you cannot even step onto it; and
- level-completing the moment the avatar stands on it WITH a fully matching
  token.

So a level is solved by routing through the right changer cells to transform
the token into each goal's required appearance, then standing on the goal —
a joint (position × token-appearance) planning problem, NOT a plain xy maze.
Level 1's start token already matches the goal in shape and color but is one
ROTATION step off, so L1 reduces to "pass one rotation-changer, then reach
the goal" — which is why a blind navigator ever cleared it and mis-labelled
the whole game as pure navigation.

Additional live-measured environment facts (L1):
  - ``available_actions`` is ``[1, 2, 3, 4]`` (four grid moves; no
    interact/click). ACTION1=up, ACTION2=down, ACTION3=left, ACTION4=right.
  - A per-level STEP COUNTER (rendered as a shrinking colour-11 bar on the
    bottom two rows) decrements every action; on exhaustion the avatar
    loses one of 3 lives, a full-frame overlay flashes, and the avatar
    repositions to the level start (the maze itself is unchanged). Losing
    all 3 lives is a GAME_OVER (the harness resets and this adapter keeps
    every learned edge — the maze did not change).

**Why a frame-keyed transition-graph frontier explorer (the design here).**
The token's (shape, color, rotation) is fully visible in the avatar sprite's
own pixels, and every static structure (walls, goal previews, goal markers)
never moves. So a canonicalisation of the frame that DROPS only the
per-action HUD noise is a faithful key for the true game state
``(avatar position, token appearance)`` — no avatar-identity tracking, no
attribute decoding, and no changer-cell semantics need to be hand-coded. The
adapter simply:

  1. keys each observation by :meth:`_state_key` — the multiset of live
     region signatures ``(color, size, bbox)``, EXCLUDING thin bands pinned
     to a frame edge (the step-counter bar and any HUD strip; this is
     ``admorphiq.adapters25.tu93``'s edge-pinned-thin HUD convention, sized
     as fractions of the frame, never hardcoded pixel rows). MEASURED:
     under this key a move-and-reverse (up then down) returns to the exact
     same key while the counter has advanced two steps — i.e. the key is
     counter-invariant and position/appearance-sensitive, exactly what a
     transition graph needs;
  2. records every observed ``(from_key, action, to_key)`` edge into a
     transition store (self-loops — blocked moves and no-op overlay frames —
     included);
  3. explores by pure frontier expansion (there is NO known goal key to plan
     toward — the goal reveals itself only by the engine completing the
     level): take an untried action from the current key; when the current
     key is exhausted, route via :func:`admorphiq.kernels.configuration_path`
     (BFS over the discovered edges) to the nearest key that still has an
     untried action. ``configuration_path`` is used rather than
     ``reachable_frontier`` because a FRESHLY-reached key (visited as an
     edge's destination but never yet acted from) has no outgoing edges of
     its own, so ``reachable_frontier``'s "already-observed edges only"
     universe cannot surface it — yet that is exactly the frontier worth
     reaching; ``configuration_path``'s ``goal_test`` fires on such a key the
     moment BFS reaches it as a successor. (Same limitation
     ``admorphiq.adapters25.tu93`` documents for the identical need.)

A decisive advantage of keying on the frame (vs the position-tracking
``dc22``/``m0r0``/``tu93`` adapters): the key SELF-LOCATES after every
life-loss reposition and GAME_OVER restart — the post-reset frame simply
hashes back to a key already in the graph, so no restart detection, no
identity re-acquisition, and no per-attempt bookkeeping is needed at all.
Only a level change (``levels_completed`` increment → a genuinely new maze)
clears the graph.

**Measured result: L1 cleared in ~606 actions (human baseline 22), 1/7.**
BFS-from-start over the frame-keyed graph reliably finds L1's shallow
13-action gold solution. This is a generic clear (no hardcoded coordinates,
palettes, or level solutions — only the frame-keyed graph and kernel BFS).

**Banked wall — L2+ (honest; reopen pointer here).** Three compounding
obstacles, each measured from the game source (read offline for
understanding only) and/or live:
  1. **Hidden-counter non-determinism — real, but its "obvious" fix is a
     MEASURED DEAD END (R56 2026-07-15).** The masked step counter is hidden
     state: two frames with the same ``(position, appearance)`` but different
     remaining steps hash identically, yet one steps normally and the other
     dies and repositions — so ``(key, action)`` is not perfectly
     deterministic (a mild ``admorphiq.tools.dealias`` inter-collision;
     MEASURED: 83.3% of repeated L2 edges are consistent, so ~17% collide).
     The tempting dealias fix — fold the last K actions into the key — DOES
     lift per-edge determinism (K=3 → 93.9%), but it is COUNTERPRODUCTIVE
     overall: it fragments the state space (L2 distinct nodes 33 → 3676) and
     destroys the frame key's SELF-LOCATING property, which is exactly what
     the BFS-from-start relies on — so with K≥2 even L1 stops clearing (the
     1/7 floor regresses). Determinism was never the L2 bottleneck;
     TRACTABILITY (a small, self-locating graph) is, and augmentation trades
     it away. So the last-seen edge stays; the counter is left aliased.
  2. **Refill-gated long solutions.** L2's human baseline is 123 actions but
     a life is only ~21 steps (StepCounter 42 / default StepsDecrement 2),
     and EVERY life-loss resets position, token, AND goal progress. The level
     is only solvable by collecting step-REFILL cells mid-run to extend the
     life — a state the frame-keyed graph does capture (a refill cell's
     region vanishes), but the search must LEARN to route through refills
     before the goal, which blind BFS-from-start does not prioritise.
  3. **Moving hazards + fog.** L2+ add moving-hazard sprites (making
     ``(key, action)`` genuinely non-deterministic) and, on later levels, a
     Fog flag that hides structure — both break the static-structure
     assumption the frame key relies on.
Reopen order (RE-REVISED after the R56b refill measurement, 2026-07-15):
obstacle 1's key-augmentation is OFF the table (regresses the floor), and a
REFILL-AWARE search was BUILT and MEASURED — the refill arithmetic CLOSES but
does NOT clear L2, because obstacle 1 (not 2) is the binding wall. Measured
facts (offline joint BFS over the engine-extracted L2 maze + faithful live
replay):
  - L2 IS solvable in **45 actions** (human 123) — a single life-chain that
    hits the lone rotation changer (0->270 needs 3 passes) and collects a
    refill mid-run to survive past the 21-action life. Refills ARE
    frame-separable: a step-refill pickup both drops a region (the cell
    vanishes) AND grows the counter band (rows 61-62, filled-cell count =
    current_steps) — a clean two-signal detector.
  - BUT the online frame-keyed BFS-from-start WEDGES at ~11-14 states with the
    token rotation NEVER leaving 0 — it never reaches the changer at (49,45),
    ~20 actions out. This wedge is present in the BASELINE too (measured, not
    caused by refill logic): a plan long enough to reach the changer crosses
    the death boundary, and with ~17% per-edge counter-aliasing a ~20-action
    plan survives intact only ~0.83^20 ~= 3% of the time, so the agent cannot
    reliably reach and EXPAND the far states where a refill would even matter.
  - So refill-awareness is NECESSARY-but-not-SUFFICIENT: the binding L2 gate is
    exploration REACH under obstacle-1 non-determinism, not the refill
    arithmetic (obstacle 2, now shown solvable-in-principle). The refill layer
    was reverted (inert while the wedge dominates; kept the floor byte-clean).
Reopen order (RE-REVISED again after the R56c open-loop measurement, 2026-07-15):
an OPEN-LOOP execution + deepest-first exploration + refill layer was BUILT and
MEASURED. It confirmed the team-lead's reframe — **open-loop legs SURVIVE**
(measured: 49/50 committed 21-action legs complete, ZERO deaths mid-leg) — so
the environment IS deterministic under an action sequence and the earlier "~3%
survival" was a per-step re-keying artifact, not real dying. Two real bugs were
found and fixed along the way: (a) the start anchor was captured from the
level-TRANSITION frame, not the settled full-life start, so ``cur == start``
never matched and no leg ever launched — fixed by anchoring on full-life frames;
(b) death detection by ``cur == start`` conflated a blocked first move with a
death — fixed via COUNTER-GROWTH (steps only jump up on death/refill). With
those, deepest-first-by-SHORTEST-PATH legs (deepest-by-action-count finds
21-step LOOPS) lifted L2 coverage from ~13 to **37 states**.

BUT L2 still does NOT clear: coverage PLATEAUS at 37 of ~56 life-reachable
positions (flat from action 800 through 3200) and NEVER reaches the changer
(max avatar x = 39 vs the changer's 49; rotation stays 0). The binding wall is
now precisely located: it is NOT open-loop survival (confirmed working) and NOT
the refill arithmetic — it is **frame-key GRAPH FIDELITY**. Counter-aliasing
corrupts the recorded edges enough that the discovered graph represents only a
37-state subset that does not contain the changer path, so BFS over it caps
there. The whole experimental build was reverted (no L2 clear = no score, and it
was not L1-byte-identical); L2 stays 1/7, floor pristine.

The ACTION-PREFIX reopen was then PROTOTYPED (R56d, 2026-07-15) and MEASURED —
and it too banks, closing the L2 investigation for the frame-keyed paradigm.
Prefix-keying is sound in principle (replaying a stored prefix from root is
deterministic, so it reaches its frontier reliably where the aliased graph did
not), but the prototype exposed the compounding blocker: to replay ANY prefix
the agent must first be cleanly AT ROOT, and reaching root goes through the
death -> full-frame OVERLAY -> settle transition, during which the frame does
NOT hash to root (measured: root detection ``root_ok=False`` on every attempt),
so replays never land on their frontier (``reached=False``). Behind that sits
the irreducible cost: every frontier must be RE-REACHED from root each 21-action
life (deaths reset position/token/goal), so covering the ~56-state life-reachable
pocket is O(states x depth) ~ >1000 actions before the deep 45-action solution
can even be stumbled on. Across FOUR rounds (refill / open-loop / deepest-first /
prefix) coverage peaked at 37 of 56 states and the agent NEVER reached the
rotation changer (max avatar x = 39 vs its 49). L2 rests at 1/7.

Settled conclusion: L2 is winnable (validated 45-action live plan) but NOT via
frame-keyed online exploration under full-reset 21-action lives — the
exploration economics don't close in budget. A future attempt would need a
different substrate entirely: an OFFLINE maze reconstruction (walls/changer/
refills/goal parsed from the frame, like the sk48 simulator) + the already-proven
joint BFS, executed open-loop. Obstacle 3 (moving hazards + fog) stays banked for
L3+.

Composition from ``admorphiq.kernels``:
  - :func:`admorphiq.kernels.find_regions` segments each frame into the
    avatar, static structures, and (excluded) HUD bands for the state key.
  - :func:`admorphiq.kernels.configuration_path` BFS-plans the shortest
    known-edge action sequence from the current key to the nearest key that
    still has an untried action.
"""

from __future__ import annotations

from typing import Any

from admorphiq.adapters25.base import (
    GameAction,
    GameAdapter,
    available_action_ids,
    canonical_layer,
    has_frame,
    most_common_color,
    reset_action,
    simple_action,
    state_name,
)
from admorphiq.kernels import configuration_path, find_regions

GAME_ID = "ls20"

Region = dict[str, Any]
StateKey = frozenset[tuple[int, int, int, int, int, int]]

# Per-level safety cap, mirroring every other script25 adapter's giveup
# convention so the harness never spins forever inside this one.
_GIVEUP_DEFAULT = 4000

# HUD-band geometry as FRACTIONS of the frame's own dimensions (never
# hardcoded pixel rows) — a thin region is a status bar / counter when it
# either spans most of an axis or is pinned against a frame edge. Matches
# admorphiq.adapters25.tu93's edge-pinned-thin convention; the LS20 step
# counter sits on the bottom two rows (an edge band) and must be excluded
# from the state key or every action fragments the key (measured).
_THIN_FRACTION = 0.06
_SPAN_FRACTION = 0.4
_EDGE_FRACTION = 0.05

# Bound on how many keys configuration_path expands when routing to the
# nearest unexplored frontier key. The discovered graph for one level stays
# small (bounded by reachable positions × observed token appearances), so
# this is a generous safety cap, not a tuned parameter.
_FRONTIER_SEARCH_BUDGET = 100_000


def _is_hud_band(region: Region, height: int, width: int) -> bool:
    r0, c0, r1, c1 = region["bbox"]
    h, w = r1 - r0 + 1, c1 - c0 + 1
    thin_h = max(1, int(height * _THIN_FRACTION))
    thin_w = max(1, int(width * _THIN_FRACTION))
    edge = max(1, int(height * _EDGE_FRACTION))
    edge_w = max(1, int(width * _EDGE_FRACTION))
    if h <= thin_h and (w >= width * _SPAN_FRACTION or r0 <= edge - 1 or r1 >= height - edge):
        return True
    if w <= thin_w and (h >= height * _SPAN_FRACTION or c0 <= edge_w - 1 or c1 >= width - edge_w):
        return True
    return False


class Adapter(GameAdapter):
    """Frame-keyed transition-graph frontier explorer composed from admorphiq.kernels."""

    GAME_ID = GAME_ID

    def __init__(self, giveup: int = _GIVEUP_DEFAULT) -> None:
        # Keep learned edges across a GAME_OVER restart — the maze layout is
        # unchanged, only the current attempt (and hidden step counter) reset.
        self.restart_on_game_over = True

        self._giveup = giveup
        self._step = 0
        self._levels_seen = -1

        # Discovered transition graph for THIS level: every observed
        # (from_key, action, to_key) triple, self-loops included. Reset on a
        # level change (new maze); kept across mid-level restarts.
        self._transitions: list[tuple[StateKey, int, StateKey]] = []
        self._tried_from: dict[StateKey, set[int]] = {}

        # The level-start key (position + token both reset to start on every
        # life-loss AND level begin). Captured on the first frame of a level;
        # the BFS-from-start expansion order is anchored here (see _decide).
        self._start_key: StateKey | None = None

        # A committed replay plan from start toward the globally-nearest
        # unexpanded frontier, drained one action per decision. Each entry of
        # ``_plan_expected`` is the key we expect to be at BEFORE popping the
        # matching ``_plan`` action — a mismatch (a life-loss reset mid-plan,
        # or the hidden-counter non-determinism) invalidates the rest.
        self._plan: list[int] = []
        self._plan_expected: list[StateKey] = []

        self._pending_action: int | None = None
        self._pending_key: StateKey | None = None

    # ── harness contract ────────────────────────────────────────────────

    def is_done(self, frames: list[Any], latest_frame: Any) -> bool:
        return state_name(latest_frame) == "WIN" or self._step >= self._giveup

    def choose_action(self, frames: list[Any], latest_frame: Any) -> GameAction:
        state = state_name(latest_frame)
        if state == "GAME_OVER":
            self._pending_action = None
            self._pending_key = None
            return reset_action()
        if state == "NOT_PLAYED" or not has_frame(latest_frame):
            self._pending_action = None
            self._pending_key = None
            self._levels_seen = -1
            return reset_action()

        grid = canonical_layer(latest_frame)
        levels = int(getattr(latest_frame, "levels_completed", 0) or 0)
        if levels != self._levels_seen:
            self._on_level_up(levels)

        self._step += 1
        cur_key = self._state_key(grid)
        if self._start_key is None:
            self._start_key = cur_key
        self._observe_result(cur_key)

        simple_ids, _action6_ok = available_action_ids(latest_frame)
        move_ids = sorted(a for a in simple_ids if a in (1, 2, 3, 4))
        if not move_ids:
            self._pending_action = None
            self._pending_key = None
            return simple_action(simple_ids[0]) if simple_ids else reset_action()

        action = self._decide(cur_key, move_ids)
        self._pending_action = action
        self._pending_key = cur_key
        return simple_action(action)

    # ── level bookkeeping ────────────────────────────────────────────────

    def _on_level_up(self, levels: int) -> None:
        """A level change means a genuinely new maze — drop every learned
        edge. (A mid-level life-loss / GAME_OVER does NOT come through here;
        those keep the graph, since the maze is unchanged and the post-reset
        frame simply re-hashes to a key already in the graph.)"""
        self._levels_seen = levels
        self._pending_action = None
        self._pending_key = None
        self._transitions = []
        self._tried_from = {}
        self._start_key = None
        self._plan = []
        self._plan_expected = []

    # ── state key ────────────────────────────────────────────────────────

    def _state_key(self, grid: tuple[tuple[int, ...], ...]) -> StateKey:
        """Multiset of live-region signatures, excluding HUD bands — a
        counter-invariant, position/appearance-sensitive key (see module
        docstring's measurement)."""
        if not grid:
            return frozenset()
        height, width = len(grid), len(grid[0])
        bg = most_common_color(grid)
        regions = find_regions(grid, background=bg)
        return frozenset(
            (r["color"], r["size"], *r["bbox"])
            for r in regions
            if not _is_hud_band(r, height, width)
        )

    # ── measurement: record the edge the pending action produced ──────────

    def _observe_result(self, cur_key: StateKey) -> None:
        action = self._pending_action
        from_key = self._pending_key
        self._pending_action = None
        self._pending_key = None
        if action is None or from_key is None:
            return
        self._transitions.append((from_key, action, cur_key))
        self._tried_from.setdefault(from_key, set()).add(action)

    # ── planning: BFS-from-start frontier exploration ─────────────────────

    def _decide(self, cur_key: StateKey, move_ids: list[int]) -> int:
        """Expand the graph in order of distance FROM THE START key.

        The level's start (position + token) is where every life-loss returns
        us for free, and the winning state is shallow (measured: L1's gold
        solution is 13 actions). So the right order is BFS from start — expand
        the globally-shallowest unexpanded frontier first — NOT depth-first
        from the current node, which gets lost deepening one arbitrary branch
        of a large (position × token-appearance) space before ever reaching
        the shallow goal (measured: DFS-order found 147 states in 1000 actions
        without clearing). There is no known goal key to plan toward: a solved
        level reveals itself only when expanding a state steps onto the goal
        with a matching token and the engine completes the level.
        """
        successors = self._successors()

        # 1. Drain a committed contiguous plan while reality still matches it.
        if self._plan_expected and self._plan_expected[0] == cur_key:
            self._plan_expected.pop(0)
            return self._plan.pop(0)
        self._plan = []
        self._plan_expected = []

        # 2. Find the globally-shallowest unexpanded frontier (BFS FROM START)
        #    and the contiguous path start->frontier.
        target = self._shallowest_frontier(move_ids, successors)
        if target is not None:
            target_key, from_start = target
            if cur_key == target_key:
                return self._untried(cur_key, move_ids)[0]  # expand it now
            anchor = self._start_key if cur_key == self._start_key else cur_key
            route = (
                from_start
                if anchor == self._start_key
                else configuration_path(
                    cur_key, lambda k: k == target_key, successors, max_states=_FRONTIER_SEARCH_BUDGET
                )
            )
            if route:
                return self._launch(anchor, route, successors)

        # 3. The globally-shallowest frontier is unreachable from this deep
        #    position (a different branch, no known edge back except via
        #    start) — expand the current node if it still can be, else burn a
        #    step (cycling by step so a single self-loop can't wedge the run)
        #    to let the counter return us to start, where the BFS plan above
        #    becomes executable again.
        untried_here = self._untried(cur_key, move_ids)
        if untried_here:
            return untried_here[0]
        return move_ids[self._step % len(move_ids)]

    def _shallowest_frontier(self, move_ids, successors):
        """``(frontier_key, path_from_start)`` for the unexpanded key nearest
        the start key, via BFS over the discovered edges. ``None`` when the
        start key is unknown or every reachable key is fully expanded.
        ``configuration_path`` from the start returns the shortest such path,
        so the first-found frontier is the globally shallowest."""
        if self._start_key is None:
            return None

        def goal_test(key: StateKey) -> bool:
            return bool(self._untried(key, move_ids))

        path = configuration_path(
            self._start_key, goal_test, successors, max_states=_FRONTIER_SEARCH_BUDGET
        )
        if path is None:
            return None
        target_key = self._replay(self._start_key, path, successors)
        if target_key is None:
            return None
        return target_key, path

    def _replay(self, anchor: StateKey, actions, successors) -> StateKey | None:
        """The key reached by replaying ``actions`` from ``anchor`` over the
        known edges, or ``None`` if any action has no recorded edge yet."""
        cur = anchor
        for action in actions:
            edges = dict(successors(cur))
            if action not in edges:
                return None
            cur = edges[action]
        return cur

    def _launch(self, anchor: StateKey, plan, successors) -> int:
        """Commit ``plan`` (a contiguous action path from ``anchor`` == the
        current key) with its per-step expected keys, then execute the first
        action. Later decisions drain the rest as long as reality tracks the
        expected keys (a life-loss reset mid-plan invalidates it)."""
        self._plan = list(plan)
        expected = [anchor]
        cur = anchor
        for action in plan[:-1]:
            cur = dict(successors(cur))[action]
            expected.append(cur)
        self._plan_expected = expected
        self._plan_expected.pop(0)  # anchor == current key, consumed now
        return self._plan.pop(0)

    def _untried(self, key: StateKey, move_ids: list[int]) -> list[int]:
        tried = self._tried_from.get(key, set())
        return [a for a in move_ids if a not in tried]

    def _successors(self):
        """Closure over the discovered edges, shaped as
        :func:`admorphiq.kernels.configuration_path` requires — ``state ->
        iterable of (action, next_state)`` — with the LAST-seen destination
        kept per ``(state, action)`` (the counter is hidden state, so a
        ``(key, action)`` can rarely resolve to different keys across
        attempts; the freshest observation is the best available guess)."""
        edges: dict[StateKey, dict[int, StateKey]] = {}
        for from_key, action, to_key in self._transitions:
            edges.setdefault(from_key, {})[action] = to_key

        def successors(key: StateKey):
            return list(edges.get(key, {}).items())

        return successors
