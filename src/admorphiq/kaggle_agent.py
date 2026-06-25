"""Efficiency-aware cheap-explore agent for the ARC-AGI-3 Kaggle submission.

This is the v0 submission agent. It subclasses the official
``agents.agent.Agent`` interface and plays a single game per instance.

Design goals (in priority order):

1. **It runs and submits.** No placeholders, no brute force, no crashes.
2. **Efficiency-aware.** The ARC-AGI-3 score squares the human/agent
   efficiency ratio, so every wasted action is penalised. The agent
   therefore (a) stops immediately on WIN, (b) prefers actions that have
   actually produced a frame change, and (c) bounds its own action count.

Behaviour summary
------------------
* On ``GAME_OVER`` (or before the first frame), send ``RESET``.
* Probe each available simple action a small number of times; record
  whether it changed the frame.
* Once probing is done, prefer the simple action with the best observed
  change-rate (epsilon-greedy so it keeps sampling under-tried actions).
* When ``ACTION6`` is available, click the centroid of the rarest-colour
  cluster on the frame — rare colours are usually the interactive
  objects / targets rather than the background.
* ``is_done`` returns ``True`` on ``WIN`` (and as a safety net when the
  agent has exhausted ``MAX_ACTIONS``).

The agent reads only the official frame observation (``frame``, ``state``,
``available_actions``); it never touches game internals, so it transfers
to the private Kaggle test set.
"""

from __future__ import annotations

import random
from collections import Counter, defaultdict

from arcengine import FrameData, GameAction, GameState

from admorphiq._agents_shim import load_agent_class

Agent = load_agent_class()

# How many times we probe a simple action before trusting its change-rate.
_PROBE_BUDGET = 2
# Probability of taking an exploratory (non-greedy) action once probing done.
_EPSILON = 0.15
# Simple (no-coordinate) actions we may try, in id order.
_SIMPLE_ACTION_IDS = (1, 2, 3, 4, 5, 7)


def _frame_signature(frame: FrameData) -> tuple:
    """Cheap hashable signature of the visible grid.

    Uses the full multi-layer frame so any visible change is detected.
    Returns an empty tuple when no frame data is present.
    """
    grid = frame.frame
    if not grid:
        return ()
    return tuple(tuple(tuple(row) for row in layer) for layer in grid)


def _top_layer(frame: FrameData) -> list[list[int]] | None:
    """Return the last (top-most) layer of the frame, or None if empty."""
    grid = frame.frame
    if not grid:
        return None
    return grid[-1]


def _rare_color_centroid(layer: list[list[int]]) -> tuple[int, int] | None:
    """Centroid (x, y) of the rarest non-background colour cluster.

    Background is taken to be the single most frequent colour. Among the
    remaining colours we pick the rarest one (most likely an interactive
    object / target) and return the average column/row of its cells.
    Coordinates are clamped to the 0-63 grid. Returns None if the layer is
    uniform (nothing to click).
    """
    counts: Counter[int] = Counter()
    for row in layer:
        counts.update(row)
    if len(counts) <= 1:
        return None

    background, _ = counts.most_common(1)[0]
    # Rarest colour that is not the background.
    candidates = [c for c in counts if c != background]
    if not candidates:
        return None
    rarest = min(candidates, key=lambda c: counts[c])

    xs: list[int] = []
    ys: list[int] = []
    for y, row in enumerate(layer):
        for x, val in enumerate(row):
            if val == rarest:
                xs.append(x)
                ys.append(y)
    if not xs:
        return None
    cx = max(0, min(63, sum(xs) // len(xs)))
    cy = max(0, min(63, sum(ys) // len(ys)))
    return cx, cy


class CheapExploreAgent(Agent):
    """Minimal efficiency-aware explore agent (v0 Kaggle submission)."""

    MAX_ACTIONS = 80

    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)
        self._rng = random.Random(0)
        self._last_sig: tuple = ()
        # Per-simple-action stats: tries and observed changes.
        self._tries: dict[int, int] = defaultdict(int)
        self._changes: dict[int, int] = defaultdict(int)
        # The action we issued on the previous step (to credit its outcome).
        self._pending_action_id: int | None = None
        # Round-robin cursors.
        self._simple_cursor = 0
        self._a6_targets: list[tuple[int, int]] = []
        self._a6_cursor = 0

    # ----- official interface ------------------------------------------------

    def is_done(self, frames: list[FrameData], latest_frame: FrameData) -> bool:
        """Stop on a win; otherwise keep playing until MAX_ACTIONS.

        Returning True early on WIN is the single biggest efficiency lever:
        the score squares the action-efficiency ratio.
        """
        if latest_frame.state == GameState.WIN:
            return True
        return self.action_counter >= self.MAX_ACTIONS

    def choose_action(
        self, frames: list[FrameData], latest_frame: FrameData
    ) -> GameAction:
        """Pick the next action from the current frame observation."""
        self._credit_previous(latest_frame)

        avail = set(latest_frame.available_actions or [])

        # Need a (re)start: no frame yet, game over, or RESET is the only move.
        if (
            latest_frame.state == GameState.GAME_OVER
            or not latest_frame.frame
            or avail == {0}
            or not avail
        ):
            return self._issue(GameAction.RESET, latest_frame)

        # Prefer a coordinate click when ACTION6 is offered and we have a
        # sensible target — rare-colour clusters are usually the objects of
        # interest.
        if 6 in avail:
            action = self._maybe_action6(latest_frame)
            if action is not None:
                return action

        simple = [a for a in _SIMPLE_ACTION_IDS if a in avail]
        if simple:
            return self._issue(self._pick_simple(simple), latest_frame)

        # Only complex action available but we had no click target: still try
        # ACTION6 at the grid centre as a last resort.
        if 6 in avail:
            return self._issue_action6(latest_frame, 32, 32)

        # Nothing actionable — reset to recover.
        return self._issue(GameAction.RESET, latest_frame)

    # ----- helpers -----------------------------------------------------------

    def _credit_previous(self, latest_frame: FrameData) -> None:
        """Update change-stats for the action issued on the previous step."""
        sig = _frame_signature(latest_frame)
        if self._pending_action_id is not None and self._pending_action_id != 0:
            changed = sig != self._last_sig
            self._tries[self._pending_action_id] += 1
            if changed:
                self._changes[self._pending_action_id] += 1
        self._last_sig = sig
        self._pending_action_id = None

    def _pick_simple(self, simple: list[int]) -> GameAction:
        """Choose a simple action: probe under-tried ones, then exploit.

        Among useful (change-producing) actions we round-robin rather than
        spamming the single best one — in movement games every direction
        changes the frame, so cycling explores the level instead of walking
        into one wall repeatedly.
        """
        under_probed = [a for a in simple if self._tries[a] < _PROBE_BUDGET]
        if under_probed:
            choice = under_probed[0]
        elif self._rng.random() < _EPSILON:
            choice = self._rng.choice(simple)
        else:
            best = max(self._change_rate(a) for a in simple)
            if best <= 0.0:
                # Nothing has helped; rotate through everything.
                useful = simple
            else:
                # Round-robin among actions within 80% of the best rate.
                useful = [a for a in simple if self._change_rate(a) >= 0.8 * best]
            choice = useful[self._simple_cursor % len(useful)]
            self._simple_cursor += 1
        return GameAction.from_id(choice)

    def _change_rate(self, action_id: int) -> float:
        tries = self._tries[action_id]
        if tries == 0:
            return 0.0
        return self._changes[action_id] / tries

    def _maybe_action6(self, latest_frame: FrameData) -> GameAction | None:
        """Issue an ACTION6 click at the next rare-colour target, if any."""
        if not self._a6_targets:
            self._a6_targets = self._compute_a6_targets(latest_frame)
            self._a6_cursor = 0
        if not self._a6_targets:
            return None
        x, y = self._a6_targets[self._a6_cursor % len(self._a6_targets)]
        self._a6_cursor += 1
        return self._issue_action6(latest_frame, x, y)

    def _compute_a6_targets(self, latest_frame: FrameData) -> list[tuple[int, int]]:
        """Build a short ordered list of click targets from the frame."""
        layer = _top_layer(latest_frame)
        if layer is None:
            return []
        targets: list[tuple[int, int]] = []
        centroid = _rare_color_centroid(layer)
        if centroid is not None:
            targets.append(centroid)
        # Always keep the grid centre as a fallback probe.
        if (32, 32) not in targets:
            targets.append((32, 32))
        return targets

    def _issue_action6(self, latest_frame: FrameData, x: int, y: int) -> GameAction:
        action = GameAction.ACTION6
        action.set_data({"x": int(x), "y": int(y), "game_id": latest_frame.game_id})
        self._pending_action_id = 6
        return action

    def _issue(self, action: GameAction, latest_frame: FrameData) -> GameAction:
        """Record the issued action id and (for ACTION6) attach coordinates."""
        if action.is_complex():
            action.set_data({"x": 32, "y": 32, "game_id": latest_frame.game_id})
        self._pending_action_id = action.value
        return action
