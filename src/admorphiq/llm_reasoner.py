"""Optional LLM reasoning layer: goal/strategy hypothesis from a COMPACT
symbolic description of the game (NOT the raw 64x64 grid).

Frontier models score <1% on raw ARC pixel grids, so we never dump the grid.
Instead we feed a short symbolic summary built from the same feature extraction
the deterministic ``general_agent`` already runs:

  * per distinct non-background colour — count of components, size range,
    example centroids, and whether that colour MOVED under which probe action;
  * the observed action -> effect map (shift vector / pixels-changed /
    level-up / no-op);
  * the available actions and the grid size.

The LLM is called ONCE per discovery (a handful per game), never per action —
the 9h / 110-game budget forbids per-step calls. Its output is a hypothesis
(goal text, target colour, per-action meaning, plan) that the deterministic
planner verifies and can override; on ANY LLM error/timeout the caller falls
back to the pure deterministic path.

These functions are pure / backend-agnostic so they unit-test without Ollama:
``build_symbolic_state`` is string formatting over plain dicts, and
``hypothesize`` takes any object with a ``generate(prompt, max_tokens,
json_schema)`` method (the ``LLMBackend`` protocol).
"""

from __future__ import annotations

import json
from typing import Any

import numpy as np

from .general_agent import connected_components

# The closed set of executable primitives the agent can dispatch. The LLM's
# ``primitive`` choice is enum-bound to exactly these names so it can never name
# a strategy that does not exist (the anchor/hallucination failure mode the
# wiki-routing rounds repeatedly hit). ``explore`` is the always-safe fallback.
PRIMITIVE_CHOICES: tuple[str, ...] = ("nav", "toggle", "paint", "explore")

# JSON Schema enforced at the decoder (Ollama `format` / llama.cpp grammar).
# Closed shapes only: ``primitive`` is enum-bound to the dispatchable set,
# ``confidence`` gates whether the selection is trusted, goal/plan are free
# text, target_color is an int or null, action_meaning is a free string map.
HYPOTHESIS_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "primitive": {"type": "string", "enum": list(PRIMITIVE_CHOICES)},
        "confidence": {"type": "number"},
        "goal": {"type": "string"},
        "target_color": {"type": ["integer", "null"]},
        "action_meaning": {
            "type": "object",
            "additionalProperties": {"type": "string"},
        },
        "plan": {"type": "array", "items": {"type": "string"}},
    },
    "required": [
        "primitive",
        "confidence",
        "goal",
        "target_color",
        "action_meaning",
        "plan",
    ],
}


def _summarize_colors(
    layer: np.ndarray,
    background: int,
    dir_map: dict[int, tuple[int, int]] | None,
    player: int | None,
) -> list[str]:
    """One compact line per distinct non-background colour.

    Reports component count, size range, up to two example centroids, and a
    movement tag when that colour is the learned player (so the LLM sees which
    entity the deterministic layer already believes is controllable).
    """
    comps = connected_components(layer, background)
    by_color: dict[int, list[dict]] = {}
    for c in comps:
        by_color.setdefault(c["color"], []).append(c)

    lines: list[str] = []
    for color in sorted(by_color):
        cs = by_color[color]
        sizes = sorted(c["size"] for c in cs)
        examples = ", ".join(
            f"({int(round(c['cx']))},{int(round(c['cy']))})" for c in cs[:2]
        )
        tag = ""
        if player is not None and color == player:
            if dir_map:
                moves = " ".join(
                    f"a{aid}->({dx:+d},{dy:+d})" for aid, (dx, dy) in sorted(dir_map.items())
                )
                tag = f"  [PLAYER, moves under: {moves}]"
            else:
                tag = "  [PLAYER]"
        lines.append(
            f"- color {color}: {len(cs)} object(s), "
            f"size {sizes[0]}..{sizes[-1]}, e.g. centroid {examples}{tag}"
        )
    return lines


def _summarize_probes(
    probes: list[dict],
    background: int,
) -> list[str]:
    """One line per probe action describing its observed effect.

    Each probe is ``{"aid", "before", "after", ...}`` (frames as 2-D arrays).
    Effect is summarised as the player-scale centroid shift of the largest
    mover, the count of changed pixels, and whether it was a no-op — a compact
    action->effect map for the LLM to reason about action semantics.
    """
    lines: list[str] = []
    for probe in probes:
        aid = probe.get("aid")
        before = probe.get("before")
        after = probe.get("after")
        if before is None or after is None or np.asarray(before).shape != np.asarray(after).shape:
            lines.append(f"- action {aid}: no observation")
            continue
        before = np.asarray(before)
        after = np.asarray(after)
        changed = int(np.count_nonzero(before != after))
        if changed == 0:
            lines.append(f"- action {aid}: NO-OP (0 pixels changed)")
            continue
        # Largest mover: match nearest same-colour twin among small components.
        shift = _largest_shift(before, after, background)
        if shift is not None:
            dx, dy = shift
            lines.append(
                f"- action {aid}: shifted an object by ({dx:+d},{dy:+d}); "
                f"{changed} pixels changed"
            )
        else:
            lines.append(f"- action {aid}: {changed} pixels changed (no clear object move)")
    return lines


def _largest_shift(
    before: np.ndarray, after: np.ndarray, background: int
) -> tuple[int, int] | None:
    """Quantised (dx, dy) of the largest small component that translated.

    Returns None when no compact component has a clear nearest-twin in the
    after frame. Coarse on purpose — this is a human-readable summary, not the
    precise vector the deterministic layer infers.
    """
    cb = [c for c in connected_components(before, background) if c["size"] <= 64]
    ca = connected_components(after, background)
    by_color: dict[int, list[dict]] = {}
    for c in ca:
        by_color.setdefault(c["color"], []).append(c)
    best: tuple[int, int] | None = None
    best_size = 0
    for b in sorted(cb, key=lambda c: -c["size"]):
        cands = by_color.get(b["color"], [])
        if not cands:
            continue
        nearest = min(
            cands, key=lambda a: (a["cx"] - b["cx"]) ** 2 + (a["cy"] - b["cy"]) ** 2
        )
        dx = int(round(nearest["cx"] - b["cx"]))
        dy = int(round(nearest["cy"] - b["cy"]))
        if (dx == 0 and dy == 0) or (dx * dx + dy * dy) ** 0.5 < 2.0:
            continue
        if b["size"] > best_size:
            best = (dx, dy)
            best_size = b["size"]
    return best


def build_symbolic_state(
    layer: np.ndarray,
    probes: list[dict],
    avail: list[int],
    dir_map: dict[int, tuple[int, int]] | None,
    player: int | None,
) -> str:
    """Compact symbolic description of the game state for the LLM (< ~1500 tok).

    Combines the entity summary (per colour), the action->effect map (per
    probe), available actions, and grid size into a short prompt body. No raw
    pixel grid is ever emitted — frontier models are near-0% on those.
    """
    layer = np.asarray(layer)
    if layer.size == 0:
        h = w = 0
        background = 0
    else:
        h, w = layer.shape
        vals, counts = np.unique(layer, return_counts=True)
        background = int(vals[int(counts.argmax())])

    parts: list[str] = []
    parts.append(f"Grid: {h}x{w}, background color = {background}.")
    parts.append(f"Available actions (ids): {sorted(avail)}.")
    parts.append("")
    parts.append("Entities (connected components by color):")
    color_lines = _summarize_colors(layer, background, dir_map, player)
    parts.extend(color_lines if color_lines else ["- (none above background)"])
    parts.append("")
    parts.append("Observed action effects (probes):")
    probe_lines = _summarize_probes(probes, background)
    parts.extend(probe_lines if probe_lines else ["- (no probes recorded)"])
    if player is not None:
        parts.append("")
        parts.append(f"Deterministic layer's player guess: color {player}.")
    return "\n".join(parts)


_SYSTEM = (
    "You are the routing brain of an ARC-AGI-3 game agent. From a COMPACT "
    "symbolic summary (entities by color + how each action changed the frame) "
    "you SELECT which solver PRIMITIVE the agent should run, and parameterize "
    "it. Respond with JSON only.\n\n"
    "Choose exactly one primitive:\n"
    '  "nav"    — a controllable PLAYER object moves under the actions; reach a '
    "target cell. Pick this when one color is tagged [PLAYER] and there is a "
    "distinct goal/exit marker. Set target_color to the goal color.\n"
    '  "toggle" — a grid/lattice of clickable cells must be flipped to a uniform '
    "or matching pattern (lights-out style). Pick when ACTION6 is available and "
    "the board is many small same-shaped cells, no moving player.\n"
    '  "paint"  — two congruent regions: copy a reference pattern onto an '
    "editable canvas by clicking palette+cells. Pick when ACTION6 is available "
    "and you see a reference region plus a blank/uniform twin region.\n"
    '  "explore" — none of the above clearly fit; let the agent probe. Use this '
    "(low confidence) whenever the signature is ambiguous.\n\n"
    "Schema:\n"
    '  primitive: one of "nav" | "toggle" | "paint" | "explore".\n'
    "  confidence: number in [0,1]; how sure you are of the primitive choice. "
    "Below 0.5 the agent ignores your pick and falls back to its deterministic "
    "detectors, so only go high when the signature is clear.\n"
    '  goal: one short sentence describing the win condition.\n'
    '  target_color: the integer color id of the goal/target cell to reach '
    "(nav) or the key palette color (paint), or null if there is no single "
    "target.\n"
    '  action_meaning: map of action-id (string) -> short meaning '
    '(e.g. "move up", "no effect").\n'
    '  plan: list of short imperative steps.\n'
)


def hypothesize(state_text: str, llm: Any) -> dict[str, Any]:
    """Ask the LLM for a goal/strategy hypothesis; parse defensively.

    ``llm`` is any object with ``generate(prompt, max_tokens, json_schema)``
    (the ``LLMBackend`` protocol). The decoder is constrained by
    ``HYPOTHESIS_SCHEMA`` but the model may still emit stray tokens, so parsing
    extracts the first JSON object and coerces each field to its declared type,
    returning safe defaults for anything missing/malformed. Never raises on
    bad LLM output — only the ``llm.generate`` call itself may raise (the
    caller treats that as "no LLM available" and falls back).
    """
    prompt = _SYSTEM + "\n" + state_text + "\n\nJSON:"
    raw = llm.generate(prompt, max_tokens=512, json_schema=HYPOTHESIS_SCHEMA)
    return _parse_hypothesis(raw)


def _parse_hypothesis(raw: str) -> dict[str, Any]:
    """Coerce raw LLM text into the hypothesis dict with safe defaults."""
    default: dict[str, Any] = {
        "primitive": None,
        "confidence": 0.0,
        "goal": "",
        "target_color": None,
        "action_meaning": {},
        "plan": [],
    }
    obj = _extract_json_object(raw)
    if not isinstance(obj, dict):
        return default

    prim = obj.get("primitive")
    if isinstance(prim, str) and prim in PRIMITIVE_CHOICES:
        default["primitive"] = prim

    conf = obj.get("confidence")
    if isinstance(conf, bool):  # bool is an int subclass; not a confidence
        default["confidence"] = 0.0
    elif isinstance(conf, (int, float)):
        default["confidence"] = max(0.0, min(1.0, float(conf)))
    elif isinstance(conf, str):
        try:
            default["confidence"] = max(0.0, min(1.0, float(conf.strip())))
        except ValueError:
            default["confidence"] = 0.0

    goal = obj.get("goal")
    default["goal"] = goal if isinstance(goal, str) else ""

    tc = obj.get("target_color")
    if isinstance(tc, bool):  # bool is an int subclass; reject it explicitly
        default["target_color"] = None
    elif isinstance(tc, int):
        default["target_color"] = tc
    elif isinstance(tc, str) and tc.strip().lstrip("-").isdigit():
        default["target_color"] = int(tc.strip())
    else:
        default["target_color"] = None

    am = obj.get("action_meaning")
    if isinstance(am, dict):
        default["action_meaning"] = {
            str(k): str(v) for k, v in am.items() if v is not None
        }

    plan = obj.get("plan")
    if isinstance(plan, list):
        default["plan"] = [str(p) for p in plan if p is not None]
    elif isinstance(plan, str):
        default["plan"] = [plan]

    return default


def _extract_json_object(raw: str) -> Any:
    """Best-effort: parse ``raw`` as JSON, else the first balanced ``{...}``."""
    if not isinstance(raw, str) or not raw.strip():
        return None
    text = raw.strip()
    try:
        return json.loads(text)
    except (json.JSONDecodeError, ValueError):
        pass
    start = text.find("{")
    if start < 0:
        return None
    depth = 0
    for i in range(start, len(text)):
        ch = text[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(text[start : i + 1])
                except (json.JSONDecodeError, ValueError):
                    return None
    return None
