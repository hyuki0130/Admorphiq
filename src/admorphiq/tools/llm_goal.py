"""LLM goal-inference tool — infer the level-completion target from frames.

Transform/arrangement games (recolor or rearrange a region into a target
pattern) are a frontier bottleneck for search-based tools: there is no local
signal telling a BFS/click tool WHICH resulting configuration counts as
"done" — the target must be INFERRED, not discovered by trial and error
alone. This tool asks an offline ollama model, once per level, "what is the
level-complete condition?" from the current frame + observed transitions, and
caches the answer as a structured :class:`~admorphiq.planner.goal.GoalSpec`,
reusing the generic prompt-building and response-parsing pieces of
:mod:`admorphiq.planner.goal_inference` (see :meth:`LLMGoalTool._infer_goal_once`
for why this tool does not reuse that module's heuristic-fallback wrapper
directly). Other tools can then consult the cached goal via
:meth:`LLMGoalTool.rank` to prefer candidate next-frames that are closer to
it, without themselves talking to the LLM.

Game-agnostic: only the ``(64, 64)`` colour-index frame and the FrameData API
(``frame_2d`` / ``availability`` / ``has_frame``) are read — no game ids,
titles, or sprite tags. Offline-safe: every LLM call is wrapped so a timeout,
connection error, or unparsable response degrades to "no goal yet" / ``[]``,
never a crash.
"""

from __future__ import annotations

import json
import os
import urllib.request
from collections.abc import Callable
from typing import Any

import numpy as np

from admorphiq.planner.goal_inference import (
    GoalSpec,
    GoalType,
    build_goal_prompt,
    color_histogram_from_frame,
    parse_goal_spec,
    score_goal,
)
from admorphiq.tools.base import (
    Step,
    availability,
    connected_components,
    diff_cells,
    frame_2d,
    has_frame,
)

__all__ = ["LLMGoalTool"]

_DEFAULT_MODEL = "gemma4:31b-it-q8_0"
_DEFAULT_HOST = "http://localhost:11434"
_MAX_EVIDENCE = 20             # bounded probe-change history fed to the prompt
_MOBILITY_LOW = 2.0            # avatar centroid displacement below this = "low"
_BIG_CHANGE_FRAC = 0.08        # mean per-transition diff fraction => "big region change"
_SMALL_COMPONENT_FRAC = 0.05   # candidate-avatar components must be <= this frac of the grid

# Injected LLM: takes a prompt, returns raw text. Matches the callable shape
# admorphiq.planner.goal_inference.infer_goal expects for ``llm_call``.
LLMChat = Callable[[str], str]


def _default_ollama_chat(model: str, host: str, timeout: int = 120) -> LLMChat:
    """Build a stdlib-only ``/api/chat`` closure (offline-safe by construction).

    Mirrors the request shape of :class:`admorphiq.ewm.core.OllamaChat` /
    ``graph_frontier_agent._infer_goal_via_llm`` but returns raw text only, the
    shape :func:`admorphiq.planner.goal_inference.infer_goal` expects. Any
    network failure raises through to the caller, which already wraps LLM
    calls in try/except — this closure itself does no swallowing.
    """
    endpoint = f"{host.rstrip('/')}/api/chat"

    def _call(prompt: str) -> str:
        body = {
            "model": model,
            "stream": False,
            "think": False,
            "messages": [{"role": "user", "content": prompt}],
            "options": {"temperature": 0.0, "num_ctx": 8192, "num_predict": 200},
        }
        req = urllib.request.Request(
            endpoint, data=json.dumps(body).encode(),
            headers={"Content-Type": "application/json"}, method="POST",
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        return payload.get("message", {}).get("content", "")

    return _call


class LLMGoalTool:
    """Infers the level-completion goal via an offline LLM, once per level.

    Lifecycle (see :mod:`admorphiq.tools.base` for the full Tool contract):

    * :meth:`detect` — frame-only confidence this is a transform/arrangement
      game: big regions recolor/rearrange while the smallest trackable
      foreground blob (the avatar proxy) barely moves. Pure navigation games
      (a small blob moving a lot, nothing else changing) score low.
    * :meth:`observe` — accumulates ``(action, changed_cells, top_new_color)``
      evidence from consecutive transitions, fed to the goal-inference prompt.
    * :meth:`propose` — infers the goal at most ONCE per level (cost control:
      this is a discovery-time call, not a per-action one), then proposes a
      single ACTION6 click that plausibly nudges the frame toward the goal.
    * :meth:`goal_frame` / :meth:`rank` — the hook other tools consult: the
      cached goal spec, and a distance-to-goal ordering of candidate frames.
    """

    name = "llm_goal"

    def __init__(self, llm_chat: LLMChat | None = None) -> None:
        """``llm_chat`` overrides the default ollama client — tests inject a stub."""
        self._model = os.environ.get("LLM_GOAL_MODEL", _DEFAULT_MODEL)
        self._host = os.environ.get("LLM_GOAL_HOST", _DEFAULT_HOST)
        self._llm_chat = llm_chat
        self.reset()

    def reset(self) -> None:
        """Drop the cached goal and transition evidence (called on level-up)."""
        self._goal: GoalSpec | None = None
        self._goal_attempted = False
        self._evidence: list[dict[str, Any]] = []
        self._last_prev: np.ndarray | None = None
        self._last_action: Step | None = None

    def detect(self, frames: list[Any], obs: Any) -> float:
        """Frame-only confidence this is a transform/arrangement game.

        Compares consecutive observed frames: HIGH (~0.7) when a large
        fraction of the grid changes per transition (big region recolor /
        rearrange) while the smallest trackable foreground blob barely moves
        (the avatar isn't the thing doing the work). Pure navigation — one
        small blob moving, nothing else changing — scores low.
        """
        grids = [frame_2d(o) for o in frames if has_frame(o)]
        if has_frame(obs):
            grids.append(frame_2d(obs))
        if len(grids) < 2:
            return 0.0
        total = grids[0].size

        diff_fracs = [
            diff_cells(a, b) / total
            for a, b in zip(grids, grids[1:])
            if diff_cells(a, b) > 0
        ]
        if not diff_fracs:
            return 0.0
        mean_diff_frac = float(np.mean(diff_fracs))
        mobility = self._avatar_mobility(grids, total)

        big_change = mean_diff_frac >= _BIG_CHANGE_FRAC
        low_mobility = mobility < _MOBILITY_LOW
        if big_change and low_mobility:
            return 0.7
        if big_change:
            return 0.3
        return 0.05

    @staticmethod
    def _avatar_mobility(grids: list[np.ndarray], total: int) -> float:
        """Mean step-to-step centroid displacement of the smallest foreground blob.

        The smallest non-background connected component is a generic proxy
        for a single controllable avatar. Returns ``inf`` (never "low") when
        no such small blob is trackable across at least two frames.
        """
        centroids: list[tuple[float, float]] = []
        for g in grids:
            small = [
                c for c in connected_components(g)
                if c["size"] <= _SMALL_COMPONENT_FRAC * total
            ]
            if not small:
                continue
            avatar = min(small, key=lambda c: c["size"])
            centroids.append(avatar["centroid"])
        if len(centroids) < 2:
            return float("inf")
        dists = [
            ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5
            for a, b in zip(centroids, centroids[1:])
        ]
        return float(np.mean(dists))

    def observe(self, prev: np.ndarray, action: Step, changed: bool) -> None:
        """Accumulate transition evidence for the goal-inference prompt.

        ``observe`` only receives the pre-action frame, so the ACTUAL effect
        of the previous action is recovered by diffing the previous call's
        ``prev`` against this call's ``prev`` (they are consecutive frames in
        the trajectory) — no forward model or extra frame argument needed.
        """
        prev = np.asarray(prev)
        if self._last_prev is not None and self._last_prev.shape == prev.shape:
            diff = self._last_prev != prev
            n = int(diff.sum())
            top_color = 0
            if n:
                vals, counts = np.unique(prev[diff], return_counts=True)
                top_color = int(vals[counts.argmax()])
            action_id = self._last_action[0] if self._last_action is not None else 0
            self._evidence.append(
                {"action": action_id, "changed_cells": n, "top_new_color": top_color}
            )
            if len(self._evidence) > _MAX_EVIDENCE:
                self._evidence.pop(0)
        self._last_prev = prev
        self._last_action = action

    def _infer_goal_once(self, frame: np.ndarray) -> None:
        """Call the LLM at most once per level; any failure leaves ``_goal`` None.

        Deliberately does NOT reuse :func:`goal_inference.infer_goal` end to
        end — that function's heuristic fallback always returns a guessed
        :class:`GoalSpec`, even when the LLM is unreachable, so ``_goal`` would
        never be ``None`` and callers could not tell "no evidence yet" apart
        from "the LLM said so". This tool's contract is stricter: an
        unreachable or unparsable LLM means NO goal (``propose`` degrades to
        ``[]``), so only the reusable pieces — :func:`build_goal_prompt` and
        :func:`parse_goal_spec` — are shared with ``infer_goal``.
        """
        if self._goal_attempted:
            return
        self._goal_attempted = True
        chat = self._llm_chat or _default_ollama_chat(self._model, self._host)
        try:
            hist = color_histogram_from_frame(frame)
            prompt = build_goal_prompt(hist, self._evidence, grid_shape=frame.shape)
            raw = chat(prompt)
        except Exception:  # noqa: BLE001 - offline-safe: never blocks the caller
            self._goal = None
            return
        self._goal = parse_goal_spec(raw)

    def propose(self, frames: list[Any], obs: Any) -> list[Step]:
        """Infer the goal (once per level) and propose a click that nudges toward it.

        Returns ``[]`` whenever there is no frame, the LLM call raised and the
        heuristic also declined, or no coordinate action is available this
        turn — never crashes.
        """
        if not has_frame(obs):
            return []
        frame = frame_2d(obs)
        self._infer_goal_once(frame)
        if self._goal is None:
            return []
        _simple, action6 = availability(obs)
        if not action6:
            return []
        target = self._pick_click_target(frame, self._goal)
        return [(6, target)] if target is not None else []

    @staticmethod
    def _pick_click_target(frame: np.ndarray, goal: GoalSpec) -> tuple[int, int] | None:
        """Best-effort click point that plausibly reduces distance to ``goal``.

        Frame-only, no forward model: this picks a component to interact with
        based on the goal's SHAPE (fill / clear / pair / order), not a
        simulated outcome — precise execution belongs to other tools; this is
        the coarse nudge the orchestrator can take when nothing more specific
        applies.
        """
        comps = connected_components(frame)
        if not comps:
            return None
        gt = goal.goal_type
        pick: dict[str, Any] | None = None

        if gt in (GoalType.FILL_COLOR, GoalType.MAXIMIZE_OBJECT_COUNT):
            others = [c for c in comps if c["color"] != goal.color]
            pick = max(others or comps, key=lambda c: c["size"])
        elif gt in (GoalType.CLEAR_COLOR, GoalType.MINIMIZE_OBJECT_COUNT):
            same = [c for c in comps if c["color"] == goal.color]
            pick = max(same, key=lambda c: c["size"]) if same else None
        elif gt is GoalType.ON_TARGET:
            a_comps = [c for c in comps if c["color"] == goal.color]
            b_comps = [c for c in comps if c["color"] == goal.color_b]
            if a_comps and b_comps:
                def _nearest_b_dist(c: dict[str, Any]) -> float:
                    ay, ax = c["centroid"]
                    return min(
                        ((ay - b["centroid"][0]) ** 2 + (ax - b["centroid"][1]) ** 2) ** 0.5
                        for b in b_comps
                    )
                pick = max(a_comps, key=_nearest_b_dist)
        elif gt is GoalType.ORDER:
            pick = max(comps, key=lambda c: c["size"])

        if pick is None:
            return None
        cy, cx = pick["centroid"]
        return int(round(cx)), int(round(cy))

    def goal_frame(self) -> GoalSpec | None:
        """The cached inferred goal, or ``None`` if not yet inferred / inference failed.

        Named per this tool's external hook contract; returns the structured
        :class:`~admorphiq.planner.goal.GoalSpec` used throughout this
        codebase's goal machinery (the LLM is asked for a closed-vocabulary
        goal TYPE + params, not a pixel-perfect target grid — see
        :func:`admorphiq.planner.goal_inference.build_goal_prompt`).
        """
        return self._goal

    def rank(self, candidate_next_frames: list[np.ndarray]) -> list[np.ndarray]:
        """Order candidate frames by closeness to the inferred goal (best first).

        Falls back to the input order unchanged when no goal is cached yet, so
        callers can consult this before/without goal inference completing
        without special-casing ``None`` themselves.
        """
        if self._goal is None or not candidate_next_frames:
            return list(candidate_next_frames)
        scored = [(score_goal(np.asarray(f), self._goal), f) for f in candidate_next_frames]
        scored.sort(key=lambda t: t[0], reverse=True)
        return [f for _, f in scored]
