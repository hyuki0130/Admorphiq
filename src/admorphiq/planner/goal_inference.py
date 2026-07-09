"""R33 goal inference at discovery — LLM hook + deterministic heuristic fallback.

ONCE per game, after the observation/probe phase (a few LLM calls per game, NOT
per action — fits the Kaggle 9h budget), the agent asks an offline LLM (Qwen via
the Ollama path used by :mod:`admorphiq.hypothesis.wiki_agent`) to name the
level-completion goal as a STRUCTURED :class:`~admorphiq.planner.goal.GoalSpec`.

The LLM call is INJECTABLE (a ``Callable[[str], str]``) so unit tests pass a
deterministic stub and never touch Ollama. If the LLM is unavailable, errors,
or returns JSON that fails validation, :func:`infer_goal` falls back to a
deterministic HEURISTIC goal guess computed from the observed probe deltas — so
the agent is NEVER blocked on the LLM.

The prompt describes the frames + observed probe changes compactly and pins the
output to the closed goal-type enum. The response is parsed and validated back
into a :class:`GoalSpec`.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable

import numpy as np

from .goal import (
    BACKGROUND_COLORS,
    GRID,
    NUM_COLORS,
    GoalSpec,
    GoalType,
    _component_stats,
    score_goal,
)

# Injected LLM: takes a prompt, returns raw text (expected to contain JSON).
LLMCall = Callable[[str], str]

# JSON schema hint embedded in the prompt (and usable as an Ollama `format`).
GOAL_JSON_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "goal_type": {
            "type": "string",
            "enum": [g.value for g in GoalType],
        },
        "color": {"type": "integer", "minimum": 0, "maximum": NUM_COLORS - 1},
        "y": {"type": "integer", "minimum": 0, "maximum": GRID - 1},
        "x": {"type": "integer", "minimum": 0, "maximum": GRID - 1},
        "radius": {"type": "integer", "minimum": 0, "maximum": GRID},
    },
    "required": ["goal_type"],
}


def build_goal_prompt(
    color_histogram: dict[int, int],
    probe_changes: list[dict],
    grid_shape: tuple[int, int] = (GRID, GRID),
) -> str:
    """Build the compact discovery-time prompt asking the LLM for a goal spec.

    Args:
        color_histogram: mapping colour-index -> cell count in the current frame.
        probe_changes: per-probe summaries, each a dict with keys like
            ``action`` (str/int), ``changed_cells`` (int), ``top_new_color`` (int).
        grid_shape: (h, w) of the frame.

    Returns:
        A single prompt string. Kept short — the LLM only needs the observable
        signature, not raw pixels.
    """
    hist_lines = ", ".join(
        f"color {c}: {n} cells" for c, n in sorted(color_histogram.items())
    )
    probe_lines = []
    for p in probe_changes[:12]:
        probe_lines.append(
            f"  action={p.get('action')}: {p.get('changed_cells', 0)} cells changed"
            f", most-common new color={p.get('top_new_color')}"
        )
    probes_block = "\n".join(probe_lines) if probe_lines else "  (no probe changes observed)"
    enum_values = ", ".join(g.value for g in GoalType)
    return (
        "You are inferring the LEVEL-COMPLETION GOAL of an unfamiliar grid game.\n"
        f"Grid: {grid_shape[0]}x{grid_shape[1]}, colours 0..{NUM_COLORS - 1} "
        "(0 is background).\n"
        f"Current colour histogram: {hist_lines}.\n"
        "Observed action probes (what each action changed):\n"
        f"{probes_block}\n\n"
        f"Choose ONE goal_type from: {enum_values}.\n"
        "Return ONLY a JSON object with keys: goal_type (required), and the "
        "relevant params color/y/x/radius as integers. Example: "
        '{"goal_type": "FILL_COLOR", "color": 3}. '
        "For MOVE_TO_REGION give y, x, radius. No prose.\n"
    )


def _extract_json(text: str) -> dict | None:
    """Pull the first JSON object out of raw LLM text, or None if none parses."""
    text = text.strip()
    # Strip common code-fence wrappers.
    text = re.sub(r"^```(?:json)?|```$", "", text, flags=re.MULTILINE).strip()
    # Find the first balanced {...} block.
    start = text.find("{")
    if start == -1:
        return None
    depth = 0
    for i in range(start, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                try:
                    obj = json.loads(text[start : i + 1])
                except json.JSONDecodeError:
                    return None
                return obj if isinstance(obj, dict) else None
    return None


def parse_goal_spec(raw: str) -> GoalSpec | None:
    """Parse + validate raw LLM text into a :class:`GoalSpec`, or None if invalid.

    Validation rejects unknown goal types, non-integer params, and out-of-range
    colour / coordinate values. A None return signals the caller to use the
    heuristic fallback.
    """
    obj = _extract_json(raw)
    if obj is None:
        return None
    gt_raw = obj.get("goal_type")
    if not isinstance(gt_raw, str):
        return None
    try:
        gt = GoalType(gt_raw)
    except ValueError:
        return None

    def _int(key: str, lo: int, hi: int) -> int | None:
        v = obj.get(key, 0)
        if isinstance(v, bool) or not isinstance(v, int):
            return None
        return v if lo <= v <= hi else None

    color = _int("color", 0, NUM_COLORS - 1)
    y = _int("y", 0, GRID - 1)
    x = _int("x", 0, GRID - 1)
    radius = _int("radius", 0, GRID)
    if color is None or y is None or x is None or radius is None:
        return None
    return GoalSpec(goal_type=gt, color=color, y=y, x=x, radius=radius)


def heuristic_goal(
    color_histogram: dict[int, int],
    probe_changes: list[dict],
) -> GoalSpec:
    """Deterministic goal guess from observed probes when the LLM can't help.

    Heuristic: the colour that appeared MOST as a "new colour" across probes is
    the colour the game is trying to grow => FILL_COLOR(that colour). If no
    probe introduced a new colour, fall back to FILL_COLOR of the rarest
    non-background colour present (the plausible "target" to complete). This is
    a best-effort, never-blocking default — it is intentionally simple.
    """
    new_color_votes: dict[int, int] = {}
    for p in probe_changes:
        c = p.get("top_new_color")
        changed = int(p.get("changed_cells", 0) or 0)
        if isinstance(c, int) and c != 0 and changed > 0:
            new_color_votes[c] = new_color_votes.get(c, 0) + changed
    if new_color_votes:
        target = max(new_color_votes, key=lambda k: new_color_votes[k])
        return GoalSpec(goal_type=GoalType.FILL_COLOR, color=target)

    non_bg = {c: n for c, n in color_histogram.items() if c != 0 and n > 0}
    if non_bg:
        rarest = min(non_bg, key=lambda k: non_bg[k])
        return GoalSpec(goal_type=GoalType.FILL_COLOR, color=rarest)
    return GoalSpec(goal_type=GoalType.FILL_COLOR, color=1)


def infer_goal(
    color_histogram: dict[int, int],
    probe_changes: list[dict],
    llm_call: LLMCall | None = None,
    grid_shape: tuple[int, int] = (GRID, GRID),
) -> GoalSpec:
    """Infer the level goal once at discovery: LLM if given & valid, else heuristic.

    Args:
        color_histogram: colour-index -> cell count.
        probe_changes: observed per-probe change summaries.
        llm_call: optional injected LLM callable (prompt -> raw text). ``None``
            (default) skips the LLM entirely and uses the heuristic — the
            configuration unit tests run under and the safe offline default.
        grid_shape: frame (h, w).

    Returns:
        A valid :class:`GoalSpec` (never None — the heuristic guarantees a spec).
    """
    if llm_call is not None:
        prompt = build_goal_prompt(color_histogram, probe_changes, grid_shape)
        try:
            raw = llm_call(prompt)
        except Exception:
            raw = ""
        spec = parse_goal_spec(raw)
        if spec is not None:
            return spec
    return heuristic_goal(color_histogram, probe_changes)


def color_histogram_from_frame(frame: np.ndarray) -> dict[int, int]:
    """Compute {colour_index: cell_count} for a ``(64, 64)`` int frame."""
    vals, counts = np.unique(np.asarray(frame), return_counts=True)
    return {int(v): int(c) for v, c in zip(vals, counts, strict=False)}


# ─────────────────── R46 semantic-progress goal inference ────────────────────
#
# A game-agnostic tracker that watches a bounded FAMILY of frame-computable
# progress measures over the agent's productive transitions and infers WHICH
# measure trends toward the level-clear. Two inference signals:
#
#   * within-level TREND — a measure that moves with a consistent sign under
#     productive actions is a candidate goal even before any level has cleared.
#   * level-clear JUMP  — when a level clears, the measure that increased most
#     over that level is snapshotted and its TYPE carried to the next level
#     (deep levels are where the squared-efficiency metric pays off).
#
# Everything is computed from the (64,64) int colour-index frame — no game id.

_MAX_SALIENT = 4          # object colours considered per frame
_FIELD_FRAC = 0.5         # colours filling > this frac of the grid are "field"
_MIN_TREND_SAMPLES = 8    # productive observations before a trend is trusted
_MIN_TREND_CONSISTENCY = 0.6  # min directional consistency in [-1, 1]
_MIN_TREND_NET = 3.0      # min |net measure movement| for a real trend


def salient_object_colors(color_histogram: dict[int, int]) -> list[int]:
    """Return non-background OBJECT colours, rarest first (bounded to K).

    Object colours are those present with a cell count below the field cutoff
    (``_FIELD_FRAC`` of the grid) — this excludes the play-field / background
    region so pair- and order-goals reason over movable pieces, not the board.
    Rarest-first because targets / pieces are typically rarer than the field.
    """
    total = GRID * GRID
    objs = {
        c: n
        for c, n in color_histogram.items()
        if c not in BACKGROUND_COLORS and 0 < n < total * _FIELD_FRAC
    }
    return [c for c, _ in sorted(objs.items(), key=lambda kv: kv[1])][:_MAX_SALIENT]


def candidate_goals(
    frame: np.ndarray, color_histogram: dict[int, int] | None = None
) -> list[GoalSpec]:
    """Bounded family of candidate GoalSpecs derived from one frame.

    Covers the fill / count / order / pair progress shapes over the frame's
    salient object colours. The family is intentionally small (a few dozen at
    most) so the trend tracker can score every member each observation.
    """
    if color_histogram is None:
        color_histogram = color_histogram_from_frame(frame)
    colors = salient_object_colors(color_histogram)
    specs: list[GoalSpec] = []
    for c in colors:
        specs.append(GoalSpec(GoalType.FILL_COLOR, color=c))
        specs.append(GoalSpec(GoalType.MINIMIZE_OBJECT_COUNT, color=c))
        specs.append(GoalSpec(GoalType.MAXIMIZE_OBJECT_COUNT, color=c))
    specs.append(GoalSpec(GoalType.ORDER, axis=0))
    specs.append(GoalSpec(GoalType.ORDER, axis=1))
    for i, ci in enumerate(colors):
        for j, cj in enumerate(colors):
            if i != j:
                specs.append(GoalSpec(GoalType.ON_TARGET, color=ci, color_b=cj))
    return specs


def goal_signature(goal: GoalSpec) -> str:
    """Stable string identity for a GoalSpec (keys the trend tracker)."""
    return f"{goal.goal_type.value}:{goal.color}:{goal.color_b}:{goal.axis}"


def instantiate_goal_type(
    frame: np.ndarray,
    goal_type: GoalType,
    axis: int = 0,
    color_histogram: dict[int, int] | None = None,
) -> GoalSpec | None:
    """Re-derive a concrete GoalSpec of ``goal_type`` on a new level's frame.

    Used to CARRY a goal TYPE across a level boundary: the next level's colours
    differ, so the role-appropriate colours are re-selected from the new frame
    (rarest object colour for FILL, the two most-salient for an ON_TARGET pair,
    the most-fragmented for a count goal). Returns None when the frame has no
    object colours to instantiate the type on.
    """
    if color_histogram is None:
        color_histogram = color_histogram_from_frame(frame)
    colors = salient_object_colors(color_histogram)
    if goal_type is GoalType.ORDER:
        return GoalSpec(GoalType.ORDER, axis=axis)
    if goal_type is GoalType.ON_TARGET and len(colors) >= 2:
        return GoalSpec(GoalType.ON_TARGET, color=colors[0], color_b=colors[1])
    if goal_type in (GoalType.MINIMIZE_OBJECT_COUNT, GoalType.MAXIMIZE_OBJECT_COUNT) and colors:
        best = max(colors, key=lambda c: len(_component_stats(frame, c)))
        return GoalSpec(goal_type, color=best)
    if goal_type is GoalType.FILL_COLOR and colors:
        return GoalSpec(GoalType.FILL_COLOR, color=colors[0])
    return None


class GoalMeasureTracker:
    """Tracks progress-measure trends over productive transitions (R46).

    Each :meth:`observe` scores the frame under the :func:`candidate_goals`
    family and folds the per-signature value into running trend statistics.
    :meth:`best_trend` names the measure moving most consistently upward within
    the level; :meth:`best_jump` names the measure that increased most cleanly
    over the whole level (snapshotted at a level clear to carry its TYPE
    forward). Reset per level via :meth:`reset`.
    """

    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self._first: dict[str, float] = {}
        self._last: dict[str, float] = {}
        self._up: dict[str, float] = {}
        self._down: dict[str, float] = {}
        self._n: dict[str, int] = {}
        self._spec: dict[str, GoalSpec] = {}

    def observe(self, frame: np.ndarray) -> None:
        """Fold one frame's measure vector into the running trend statistics."""
        for goal in candidate_goals(frame):
            sig = goal_signature(goal)
            val = score_goal(frame, goal)
            self._spec[sig] = goal
            if sig not in self._n:
                self._n[sig] = 1
                self._first[sig] = val
                self._last[sig] = val
                self._up[sig] = 0.0
                self._down[sig] = 0.0
                continue
            delta = val - self._last[sig]
            if delta > 0:
                self._up[sig] += delta
            elif delta < 0:
                self._down[sig] += -delta
            self._last[sig] = val
            self._n[sig] += 1

    def best_trend(self) -> tuple[GoalSpec, float] | None:
        """Signature with the strongest trusted upward monotone trend, or None."""
        best_sig: str | None = None
        best_consistency = 0.0
        for sig, n in self._n.items():
            if n < _MIN_TREND_SAMPLES:
                continue
            up, down = self._up[sig], self._down[sig]
            net = up - down
            if net < _MIN_TREND_NET:
                continue
            consistency = net / (up + down + 1e-9)
            if consistency >= _MIN_TREND_CONSISTENCY and consistency > best_consistency:
                best_consistency = consistency
                best_sig = sig
        if best_sig is None:
            return None
        return self._spec[best_sig], best_consistency

    def best_jump(self) -> GoalSpec | None:
        """Signature whose measure rose most cleanly over the level, or None.

        Ranks by net increase normalised by the measure's own total movement, so
        a measure that only ever went up (norm ~= 1) beats one that oscillated to
        the same net value. This snapshot is taken at a level clear to decide
        which goal TYPE to carry into the next level.
        """
        best_sig: str | None = None
        best_norm = 0.0
        for sig, n in self._n.items():
            if n < 2:
                continue
            net = self._last[sig] - self._first[sig]
            if net <= 0:
                continue
            scale = self._up[sig] + self._down[sig] + 1e-9
            norm = net / scale
            if norm > best_norm:
                best_norm = norm
                best_sig = sig
        return self._spec[best_sig] if best_sig else None
