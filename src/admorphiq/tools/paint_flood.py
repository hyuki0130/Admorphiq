"""Paint-flood tool — perception + click proposal for click-fills-a-region games.

Mechanic (measured in su15, R53): an ACTION6 click turns a connected background
region into one fill color (su15: dominant ``0 -> 5``, ~30-50 cells/click). This
tool is game-agnostic: it DETECTS the mechanic from observed transitions and,
given a current frame, PROPOSES click points that extend the fill toward the
uncovered target region. No game ids; triggers on frame features only.

This is the perception+planning CORE of the paint tool (the runtime model calls
these); wiring it into a full agent loop that clears a level end-to-end is the
next step and is measured separately.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from admorphiq.tools.base import Step, frame_2d, has_frame
from admorphiq.tools.solver_core import paint_core, paint_plan

BACKGROUND = 0  # colour index 0 is background across ARC-AGI-3 frames


@dataclass(frozen=True)
class FloodMechanic:
    """What a click does, inferred from observations."""

    detected: bool
    fill_color: int          # the colour clicks paint (e.g. 5 in su15)
    mean_fill_cells: float   # typical region size a click fills
    confidence: float        # fraction of click transitions matching the mechanic


def detect_flood_mechanic(
    frames: np.ndarray, actions: np.ndarray, next_frames: np.ndarray,
    click_action_min_idx: int = 5,
) -> FloodMechanic:
    """Infer whether ACTION6 clicks flood-fill a region with a single colour.

    A click transition "matches" when its changed cells are DOMINATED (>=60%) by
    a single ``old -> new`` recolouring whose ``old`` is background. The fill
    colour is the most common such ``new``; confidence is the matching fraction
    over click transitions.
    """
    from collections import Counter
    fill_votes: Counter = Counter()
    sizes: list[int] = []
    matched = clicks = 0
    for i in range(len(actions)):
        if int(actions[i]) < click_action_min_idx:
            continue
        clicks += 1
        diff = frames[i] != next_frames[i]
        n = int(diff.sum())
        if n == 0:
            continue
        olds = frames[i][diff]
        news = next_frames[i][diff]
        bg = olds == BACKGROUND
        if not bg.any():
            continue
        new_bg = news[bg]
        vals, counts = np.unique(new_bg, return_counts=True)
        top = int(vals[counts.argmax()])
        if counts.max() >= 0.6 * n:
            matched += 1
            fill_votes[top] += 1
            sizes.append(n)
    if clicks == 0 or not fill_votes:
        return FloodMechanic(False, -1, 0.0, 0.0)
    fill_color = fill_votes.most_common(1)[0][0]
    conf = matched / clicks
    return FloodMechanic(
        detected=conf >= 0.5,
        fill_color=fill_color,
        mean_fill_cells=float(np.mean(sizes)) if sizes else 0.0,
        confidence=conf,
    )


def propose_fill_clicks(
    frame: np.ndarray, fill_color: int, max_clicks: int = 14,
) -> list[tuple[int, int]]:
    """Propose ``(x, y)`` clicks to flood the remaining background regions.

    Targets the LARGEST still-background 4-connected components first (a click in
    each floods it), returning their centroids as ``(x=col, y=row)`` — the ACTION6
    convention. Delegates to ``solver_core.paint_plan`` so the region-selection
    logic has ONE implementation (the same code the paint core / LLM card runs);
    ``fill_color`` is accepted for API compatibility but region-finding is driven
    by the background colour.
    """
    return paint_plan(np.asarray(frame, dtype=np.int16),
                      background=BACKGROUND, max_clicks=max_clicks)


class PaintFloodTool:
    """``base.Tool`` wrapper around ``detect_flood_mechanic`` / ``propose_fill_clicks``.

    The Tool protocol's ``observe(prev, action, changed)`` does not carry the
    frame the action produced (only the frame BEFORE the action + whether it
    changed), so a click transition is completed lazily: ``observe`` queues
    ``(prev, action)`` when a click changed something, and the next call to
    ``detect``/``propose`` (which does receive the fresh ``obs``) pairs it with
    the frame that resulted, feeding it into ``detect_flood_mechanic``.

    Conservative by design (measured caveat, ``.wiki/wiki/tool_selector.md``
    2026-07-08: paint is NOT a fit for every click game -- su15 measured 0/9).
    Confidence stays 0.0 until at least one completed click transition is
    DOMINATED (>=60%, ``detect_flood_mechanic``'s own threshold) by a single
    background->colour recolouring; unrelated click games never trigger it.
    """

    name = "paint"

    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        """Drop accumulated click evidence (harness calls this on level-up)."""
        self._pending: tuple[np.ndarray, Step] | None = None
        self._frames: list[np.ndarray] = []
        self._acts: list[int] = []
        self._nexts: list[np.ndarray] = []
        self._xys: list[list[int] | None] = []  # click (x, y) per transition
        self._fill_color: int = -1
        self._trace: list[str] = []  # last propose()'s core decision log

    def observe(self, prev: np.ndarray, action: Step, changed: bool) -> None:
        """Queue a click transition; completed against the next frame we see."""
        if changed and action[0] == 6 and action[1] is not None:
            self._pending = (np.asarray(prev, dtype=np.int16), action)
        else:
            self._pending = None

    def _absorb_pending(self, obs: Any) -> None:
        """Complete a queued click transition against the frame just observed."""
        if self._pending is None or not has_frame(obs):
            return
        prev, action = self._pending
        self._pending = None
        cur = frame_2d(obs).astype(np.int16)
        if cur.shape != prev.shape:
            return
        xy = action[1]
        self._frames.append(prev)
        self._acts.append(6)
        self._nexts.append(cur)
        self._xys.append([int(xy[0]), int(xy[1])] if xy is not None else None)

    def _records(self) -> list[dict[str, Any]]:
        """Observed click transitions as the dict shape the core / sandbox reads:
        ``{"action", "xy": [x, y] | None, "before", "after"}``."""
        return [
            {"action": "CLICK", "xy": xy, "before": b, "after": n}
            for b, xy, n in zip(self._frames, self._xys, self._nexts)
        ]

    def detect(self, frames: list[Any], obs: Any) -> float:
        """Confidence this is a paint/flood game, from observed click fills only."""
        self._absorb_pending(obs)
        if not self._acts:
            return 0.0
        mechanic = detect_flood_mechanic(
            np.array(self._frames), np.array(self._acts), np.array(self._nexts)
        )
        if not mechanic.detected:
            return 0.0
        self._fill_color = mechanic.fill_color
        return min(1.0, mechanic.confidence)

    def propose(self, frames: list[Any], obs: Any) -> list[Step]:
        """Delegate the fill-or-probe decision to ``solver_core.paint_core`` — the
        SAME code the LLM patches and the code sandbox executes. The core infers
        the fill colour from the recorded click transitions and queues clicks
        toward the largest remaining background regions (or one probe click)."""
        self._absorb_pending(obs)
        if not has_frame(obs):
            return []
        frame = frame_2d(obs).astype(np.int16)
        self._trace = []
        plan: list[Step] = []

        def _act(name: str, x: int | None = None, y: int | None = None) -> None:
            if x is not None and y is not None:
                plan.append((6, (int(x), int(y))))

        paint_core(frame, self._records(), _act, self._trace)
        return plan
