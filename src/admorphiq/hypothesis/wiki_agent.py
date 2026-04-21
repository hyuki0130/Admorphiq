"""Wiki-driven hypothesis agent (Phase 8 Step 3, Task #9).

The agent's contract mirrors the Karpathy LLM-Wiki pattern:

  observe(live_env)  ──┐
                       ├─> prompt ─> LLMBackend.generate ─> JSON ─> dispatch
  load_wiki_context ──┘

It is intentionally thin — no state dump, no bundled weights, no agent-side
learning. All knowledge lives in `.wiki/` and is composed on demand from a
small, deterministic retrieval recipe (see `wiki_retrieval_recipe.md`).

The agent is **LLM-agnostic**: it calls `LLMBackend.generate(prompt)` and
does not care which model answers. Choose the candidate via `configs/llm.yaml`.

Deployment assumption: Kaggle T4, internet disabled. All wiki pages and
weights must be pre-staged. This module does no network I/O.
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from ..llm import LLMBackend

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
WIKI_DIR = REPO_ROOT / ".wiki" / "wiki"


@dataclass
class DiscoveryReport:
    """What we observed in the first ~N frames of a game. Used to prime the LLM.

    R2 (2026-04-21): expanded from 5 raw fields to include derived features so
    the LLM can distinguish movement / sokoban / hybrid / click subtypes without
    guessing from the game title. Reflection (R4) can add more fields by editing
    this dataclass + the corresponding `_derive_*` helper + prompt template.
    """

    # --- raw probe signals ---
    game_title: str
    available_actions: list[int]
    layer_count: int
    dominant_colors: list[tuple[int, int]]  # [(color, count), ...]
    probe_diffs: dict[int, int]  # action_id -> pixel count changed vs reset
    reset_levels: int
    frame_shape: tuple[int, int]
    # --- R2 derived features ---
    dir_map: dict[int, str] = field(default_factory=dict)
    """action_id -> 'N'|'S'|'E'|'W' when directional probe shows motion. Empty
    for click-only games. Populated by `_derive_dir_map`."""
    player_color: int | None = None
    """Color index of the pixel(s) that consistently disappear-and-reappear
    across directional probes. None if no consistent player."""
    movable_region_count: int = 0
    """Max count of connected diff components across directional probes. 1 for
    single-player games; ≥2 hints at multi-character or paired puzzles."""
    click_responsive_cells: list[dict] = field(default_factory=list)
    """For ACTION6 probes, per-coord records: {x, y, diff, color_before_at_click,
    color_after_at_click}. Used to tell 'paint' (color swap at click) from
    'click_rare' (sparse, tiny diffs) from 'merge_puzzle' (large diff after click)."""
    change_topology: str = "unknown"
    """One of: sprite_move | color_toggle | level_transition | mixed | no_change."""
    color_histogram: dict[int, float] = field(default_factory=dict)
    """Top colors as fraction of frame. Ordered by abundance."""
    symmetry_score: float = 0.0
    """Crude horizontal-flip similarity [0..1]. High = grid/board-like layout."""
    total_pixels: int = 0


@dataclass
class FeatureGap:
    """A frame-derivable observation the LLM would have used but did not have.

    Structured so the dev-time reflector (Claude Code) can read it and decide
    whether to add a new derive helper and extend DiscoveryReport.
    """

    name: str
    why_needed: str = ""
    derive_hint: str = ""


@dataclass
class WikiGap:
    """A wiki page/section the LLM would have consulted but found missing.

    Claude Code reviews these between rounds and either authors the page or
    extends an existing one. Entries with an empty `proposed_addition` are
    logged but not actioned — we never let the LLM write wiki content directly.
    """

    topic: str
    suggested_page: str = ""
    current_info_insufficient: str = ""
    proposed_addition: str = ""


@dataclass
class Hypothesis:
    """Parsed LLM response.

    R7 expanded the schema so every round's trace carries enough information
    to drive the next round without a second LLM call:

      confidence        - self-reported 0..1
      doubt             - short free-text on what the LLM is unsure about
      features_missing  - structured FeatureGap list (shape changed from R2)
      wiki_gaps         - structured WikiGap list for wiki authoring
      wiki_needs        - paths the LLM wants retrieved next round
    """

    game_type: str
    primary_strategy: str
    fallback_stack: list[str] = field(default_factory=list)
    rationale: str = ""
    confidence: float = 0.0
    doubt: str = ""
    features_missing: list[FeatureGap] = field(default_factory=list)
    wiki_gaps: list[WikiGap] = field(default_factory=list)
    wiki_needs: list[str] = field(default_factory=list)
    raw: str = ""


# ---------------------------------------------------------------------------
# R2 feature derivation helpers (pure — no env dependency).
# Each takes raw probe data and returns a single derived value. Kept as
# module-level functions so they can be unit-tested independently of a live
# env and so R4 reflection can add new ones without touching `discover`.
# ---------------------------------------------------------------------------


def _connected_components(mask):
    """Count 4-connected True components in a 2D bool mask. Simple BFS — no
    scipy dependency. For 64x64 masks this is ~1ms worst case."""
    import numpy as np

    mask = np.asarray(mask, dtype=bool)
    h, w = mask.shape
    visited = np.zeros_like(mask)
    count = 0
    for y in range(h):
        for x in range(w):
            if not mask[y, x] or visited[y, x]:
                continue
            count += 1
            stack = [(y, x)]
            while stack:
                cy, cx = stack.pop()
                if cy < 0 or cy >= h or cx < 0 or cx >= w:
                    continue
                if visited[cy, cx] or not mask[cy, cx]:
                    continue
                visited[cy, cx] = True
                stack.append((cy + 1, cx))
                stack.append((cy - 1, cx))
                stack.append((cy, cx + 1))
                stack.append((cy, cx - 1))
    return count


def _derive_dir_map(probes_raw):
    """From (before, after) pairs for directional actions, infer cardinal motion.

    Returns (dir_map, player_color). dir_map maps action id → 'N'|'S'|'E'|'W'.
    player_color is the most common color across probes of pixels that vacated
    their position (i.e., the player's own color).
    """
    import numpy as np

    dir_map: dict[int, str] = {}
    player_colors: list[int] = []
    for aid in (1, 2, 3, 4, 5):
        pair = probes_raw.get(aid)
        if pair is None:
            continue
        before, after = pair
        if not np.any(before != after):
            continue
        disappeared = (before != after) & (before != 0)
        appeared = (before != after) & (after != 0)
        if not np.any(disappeared) or not np.any(appeared):
            continue
        dy_d, dx_d = np.where(disappeared)
        dy_a, dx_a = np.where(appeared)
        cy_d, cx_d = dy_d.mean(), dx_d.mean()
        cy_a, cx_a = dy_a.mean(), dx_a.mean()
        dy = cy_a - cy_d
        dx = cx_a - cx_d
        if abs(dy) < 1.0 and abs(dx) < 1.0:
            continue
        if abs(dy) > abs(dx):
            dir_map[aid] = "S" if dy > 0 else "N"
        else:
            dir_map[aid] = "E" if dx > 0 else "W"
        vals = before[disappeared]
        if vals.size:
            u, c = np.unique(vals, return_counts=True)
            player_colors.append(int(u[c.argmax()]))
    player_color: int | None = None
    if player_colors:
        u, c = np.unique(player_colors, return_counts=True)
        player_color = int(u[c.argmax()])
    return dir_map, player_color


def _derive_click_responsive_cells(probes_a6):
    """Turn raw ACTION6 probe tuples into per-coord records."""
    import numpy as np

    records: list[dict] = []
    for cx, cy, before, after in probes_a6:
        diff_count = int(np.count_nonzero(before != after))
        if diff_count == 0:
            continue
        records.append(
            {
                "x": int(cx),
                "y": int(cy),
                "diff": diff_count,
                "color_before_at_click": int(before[cy, cx]),
                "color_after_at_click": int(after[cy, cx]),
            }
        )
    return records


def _derive_change_topology(probes_raw, total_pixels, dir_map):
    """Categorize each probe's change pattern, then aggregate.

    Returns one of: sprite_move, color_toggle, level_transition, mixed, no_change.
    """
    import numpy as np

    seen: list[str] = []
    for aid, (before, after) in probes_raw.items():
        if aid < 0:
            continue
        diff_count = int(np.count_nonzero(before != after))
        if diff_count == 0:
            continue
        pct = diff_count / max(total_pixels, 1)
        if pct > 0.5:
            seen.append("level_transition")
        elif aid in dir_map:
            seen.append("sprite_move")
        else:
            mask = before != after
            # `color_toggle` = same positions changed color without spatial displacement.
            # Heuristic: number of nonzero pixels roughly preserved AND diff mask
            # is not centroid-shifted (we already excluded dir_map).
            before_nonzero = int(np.count_nonzero(before[mask]))
            after_nonzero = int(np.count_nonzero(after[mask]))
            if abs(before_nonzero - after_nonzero) <= max(1, diff_count // 20):
                seen.append("color_toggle")
            else:
                seen.append("mixed")
    if not seen:
        return "no_change"
    if len(set(seen)) > 1:
        return "mixed"
    return seen[0]


def _derive_color_histogram(frame, topk: int = 8):
    """Top-K colors as {color: fraction_of_frame}."""
    import numpy as np

    unique, counts = np.unique(frame, return_counts=True)
    total = int(counts.sum())
    if total == 0:
        return {}
    ranked = sorted(zip(unique, counts), key=lambda t: -t[1])[:topk]
    return {int(c): round(float(n) / total, 4) for c, n in ranked}


def _derive_symmetry_score(frame):
    """Crude horizontal-flip similarity. Intentionally cheap — R4 reflection
    can replace this with a better feature if it turns out to carry signal."""
    import numpy as np

    flipped = frame[:, ::-1]
    return round(float(np.mean(frame == flipped)), 4)


def _derive_movable_region_count(probes_raw):
    """Max connected-component count across directional probes."""
    import numpy as np

    max_count = 0
    for aid, (before, after) in probes_raw.items():
        if aid < 0 or aid == 6:
            continue
        mask = before != after
        if not np.any(mask):
            continue
        n = _connected_components(mask)
        if n > max_count:
            max_count = n
    return max_count


_PROMPT_TEMPLATE = """You are the Admorphiq Phase 8 Hypothesis Engine, round {round_num}.

Your job on this game:
  (a) pick a primary strategy and up to three fallbacks from the whitelist;
  (b) report what you needed but did not have, so the next round can give
      it to you. The quality of (b) determines how fast this loop improves.

## Output schema

Emit EXACTLY ONE JSON object. No prose, no code fences.

{{
  "game_type":        "one of: movement | click | programming_puzzle | merge_puzzle | sokoban | platformer | transform | delivery | slider_puzzle | rotation | sort_puzzle | spell_cast | sequence | hybrid | unknown",
  "primary_strategy": "EXACT name from the Available Strategies list",
  "fallback_stack":   ["strategy_name", ...] up to 3, each from the whitelist,
  "rationale":        "1-2 sentences grounded in the observed probe signals",
  "confidence":       0.0 to 1.0,
  "doubt":            "one short sentence on what you are unsure about, or empty string",
  "features_missing": [{{"name": "...", "why_needed": "...", "derive_hint": "..."}}],
  "wiki_gaps":        [{{"topic": "...", "suggested_page": "...", "current_info_insufficient": "...", "proposed_addition": "..."}}],
  "wiki_needs":       ["relative/path/to/page.md", ...]
}}

## Hard rules

- `primary_strategy` and every `fallback_stack` entry MUST appear verbatim
  in Available Strategies. Case-sensitive. No invented names.
- If confidence < 0.5, set `game_type: "unknown"` and let `bfs_state_space`
  be the primary. Do not guess. Honest uncertainty is more useful than a
  confident wrong answer.
- When the game title lowercased matches a frame-only strategy in the
  whitelist (e.g., title SU15 <-> strategy `su15_frame_only`), prefer that
  strategy in the primary slot. Frame-only game-specific strategies carry
  more prior than generic ones.
- Use `dir_map`, `player_color`, and `movable_region_count` to detect
  movement / sokoban / multi-character games before defaulting to click.
- `change_topology == "level_transition"` means the probe already tripped
  a level reset; do not anchor a hypothesis on that signal alone.

## Wiki search guidance

The Wiki Context below was retrieved based on your discovery observations.
Page titles appear as `--- path ---` headers. Inside pages, `[[link]]` is
a reference to another wiki page.

- If you see a `[[link]]` to a page that is NOT in the context below and
  you judge it material to this decision, add its relative path to
  `wiki_needs`. The next round will include it.
- Do NOT hallucinate page contents you cannot see.
- Do NOT cite pages you did not read; if you rely on one, its path must
  be among the `--- path ---` headers in the context.

## Feedback discipline

This is the signal that drives the next round. Be specific or stay silent.

- `features_missing` entries MUST have all three fields: `name` (snake_case),
  `why_needed` (one clause naming which decision would change), and
  `derive_hint` (one-line recipe computable from the RESET frame and the
  per-action before/after frames already captured during discovery). No
  vague "more info would be nice" entries. Empty list is valid.
- `wiki_gaps` entries MUST have `topic` and `proposed_addition` (what
  content would make the missing or sparse page usable). Empty list is
  valid.
- `wiki_needs` is a list of relative paths you saw in `[[links]]` but not
  in the context. Empty list is valid.

Over-reporting weakens the signal. One well-stated gap beats five vague
complaints. Saying nothing is correct when nothing is missing.

## Carryover from prior rounds

{round_learnings}

## Available Strategies ({n_strategies})

{strategy_list}

## Wiki Context

{context}

## Live Discovery

Game title: {title}
Available actions: {avail}
Layer count: {layers}
Frame shape: {shape}
Dominant colors (color:count): {colors}
Color histogram (color:fraction): {color_hist}
Symmetry score (0..1): {symmetry}
Starting level: {lvl}

Probe-derived signals:
  probe_diffs (action: pixels changed; key -6 = # responsive click cells): {probes}
  dir_map (action -> N/S/E/W, empty if no movement): {dir_map}
  player_color (consistent moving-pixel color, null if none): {player_color}
  movable_region_count (max connected diff components): {movable_count}
  change_topology: {topology}
  click_responsive_cells: {click_cells}
"""


_DEFAULT_ROUND_LEARNINGS = (
    "(First round. No prior rounds' learnings to carry. Respond based on "
    "the discovery data and wiki context directly.)"
)


# JSON Schema for the Hypothesis output. When the backend supports schema-
# constrained decoding (Ollama 0.5+ via the `format` parameter), this shape
# is enforced by the decoder rather than asked-for in the prompt. Measured
# on 2026-04-21 R7 bench: without schema enforcement, Qwen 8B drifts and
# emits arbitrary keys (`"strategy"` instead of `"primary_strategy"`).
_HYPOTHESIS_JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "game_type": {
            "type": "string",
            "enum": [
                "movement",
                "click",
                "programming_puzzle",
                "merge_puzzle",
                "sokoban",
                "platformer",
                "transform",
                "delivery",
                "slider_puzzle",
                "rotation",
                "sort_puzzle",
                "spell_cast",
                "sequence",
                "hybrid",
                "unknown",
            ],
        },
        "primary_strategy": {"type": "string"},
        "fallback_stack": {
            "type": "array",
            "items": {"type": "string"},
            "maxItems": 3,
        },
        "rationale": {"type": "string"},
        "confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
        "doubt": {"type": "string"},
        "features_missing": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "why_needed": {"type": "string"},
                    "derive_hint": {"type": "string"},
                },
                "required": ["name"],
            },
        },
        "wiki_gaps": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "topic": {"type": "string"},
                    "suggested_page": {"type": "string"},
                    "current_info_insufficient": {"type": "string"},
                    "proposed_addition": {"type": "string"},
                },
                "required": ["topic"],
            },
        },
        "wiki_needs": {"type": "array", "items": {"type": "string"}},
    },
    "required": [
        "game_type",
        "primary_strategy",
        "fallback_stack",
        "rationale",
        "confidence",
    ],
}


# Wiki retrieval is graph-based (R7b). See `wiki_retrieval.py` for the BFS
# walk over `[[backlinks]]` and the seed-derivation rules. Static page lists
# were removed in the R7b commit — every env now gets a tailored slice based
# on its discovery signals.


def _parse_json_lenient(raw: str) -> dict[str, Any]:
    """Extract the first JSON object from an LLM response. Tolerates fences + prose."""
    if not raw:
        return {}
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, re.DOTALL)
    if m:
        raw = m.group(1)
    else:
        m = re.search(r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}", raw, re.DOTALL)
        if m:
            raw = m.group(0)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {}


def _parse_feature_gaps(raw_list) -> list[FeatureGap]:
    """Turn the LLM's `features_missing` field into structured FeatureGap objects.

    The prompt asks for dicts with {name, why_needed, derive_hint}. Models
    occasionally regress to a bare list of strings; that is accepted as
    name-only (why/hint empty) so we don't drop the signal, but such entries
    convey less actionable information downstream.
    """
    if not isinstance(raw_list, list):
        return []
    out: list[FeatureGap] = []
    for item in raw_list[:8]:
        if isinstance(item, dict):
            name = str(item.get("name", "")).strip()
            if not name:
                continue
            out.append(
                FeatureGap(
                    name=name,
                    why_needed=str(item.get("why_needed", "")),
                    derive_hint=str(item.get("derive_hint", "")),
                )
            )
        elif isinstance(item, str) and item.strip():
            out.append(FeatureGap(name=item.strip()))
    return out


def _parse_wiki_gaps(raw_list) -> list[WikiGap]:
    """Turn the LLM's `wiki_gaps` field into structured WikiGap objects. Bare
    strings are rejected here — a wiki-authoring signal without a topic is
    not actionable and should not pollute the trace."""
    if not isinstance(raw_list, list):
        return []
    out: list[WikiGap] = []
    for item in raw_list[:8]:
        if not isinstance(item, dict):
            continue
        topic = str(item.get("topic", "")).strip()
        if not topic:
            continue
        out.append(
            WikiGap(
                topic=topic,
                suggested_page=str(item.get("suggested_page", "")),
                current_info_insufficient=str(item.get("current_info_insufficient", "")),
                proposed_addition=str(item.get("proposed_addition", "")),
            )
        )
    return out


def _validate_whitelist(hyp: "Hypothesis", valid_names: set[str]) -> "Hypothesis":
    """Strip strategy names the LLM invented.

    Purpose: R6 measured that Qwen 3 14B hallucinated `seq_search` for FT09
    (a name never present in the 67-strategy whitelist). Such names silently
    produce `unknown_strategy` execution records and waste a fallback slot.
    This filter is the cheapest correct response: an invalid primary becomes
    empty (the run() loop then falls through to the next valid fallback),
    and invalid fallback entries are dropped outright.

    This function mutates neither the input dict nor the module state — it
    returns the corrected hypothesis for the caller to use.
    """
    if hyp.primary_strategy not in valid_names:
        hyp.primary_strategy = ""
    hyp.fallback_stack = [s for s in hyp.fallback_stack if s in valid_names]
    return hyp


def discover(env: Any, title: str = "UNKNOWN", probe_actions: list[int] | None = None) -> DiscoveryReport:
    """Reset the env, snapshot the opening frame, then probe each action once.

    The probe diffs are the single most useful signal for classifying a game —
    they tell the LLM which actions cause movement, which are no-ops, and which
    cause large scene changes (level transition, click-spawn, etc.).

    `title` is passed in (not read off the env) because the playable env from
    `arcade.make(game_id)` does not carry the human-readable game name; that
    metadata lives on the `EnvironmentInfo` sibling object.
    """
    import numpy as np

    # Import from arcengine (the base SDK, installed alongside arc_agi). The
    # playable env exposes .step + GameAction-compatible actions.
    from arcengine import GameAction

    obs = env.step(GameAction.RESET)
    if obs is None:
        raise RuntimeError("env.reset returned None")
    frame0 = np.array(obs.frame[0], dtype=np.int32)
    layers = len(obs.frame)
    avail = [int(a) for a in (obs.available_actions or []) if int(a) != 0]
    unique, counts = np.unique(frame0, return_counts=True)
    colors = sorted(
        ((int(c), int(n)) for c, n in zip(unique, counts) if c != 0),
        key=lambda t: -t[1],
    )[:6]

    if probe_actions is None:
        probe_actions = [a for a in avail if a != 6][:4]

    probes: dict[int, int] = {}
    # Retain raw (before, after) pairs so R2 derivations can run post-hoc
    # without re-stepping the env. Each pair is ~64x64 int32 = 16KB; 5 probes
    # + 5 ACTION6 probes ≈ 160KB — negligible vs any LLM context buffer.
    probes_raw: dict[int, tuple[Any, Any]] = {}
    for aid in probe_actions:
        obs_r = env.step(GameAction.RESET)
        if obs_r is None:
            continue
        f_before = np.array(obs_r.frame[0], dtype=np.int32)
        obs_a = env.step(GameAction.from_id(aid))
        if obs_a is None:
            continue
        f_after = np.array(obs_a.frame[0], dtype=np.int32)
        probes[aid] = int(np.count_nonzero(f_before - f_after))
        probes_raw[aid] = (f_before, f_after)

    # ACTION6 probe: many games are click-only, skipping ACTION6 leaves the
    # report empty. Sample a small grid (center + 4 corners) and take the max
    # diff as the "click responsiveness" signal. The per-coord diffs are also
    # recorded so the LLM can tell between sparse-rare-click and everywhere-
    # changes-equally game styles.
    probes_a6: list[tuple] = []
    if 6 in avail:
        coords = [(32, 32), (16, 16), (48, 16), (16, 48), (48, 48)]
        a6_diffs: list[int] = []
        for cx, cy in coords:
            obs_r = env.step(GameAction.RESET)
            if obs_r is None:
                continue
            f_before = np.array(obs_r.frame[0], dtype=np.int32)
            obs_a = env.step(GameAction.ACTION6, data={"x": cx, "y": cy})
            if obs_a is None:
                continue
            f_after = np.array(obs_a.frame[0], dtype=np.int32)
            a6_diffs.append(int(np.count_nonzero(f_before - f_after)))
            probes_a6.append((cx, cy, f_before, f_after))
        if a6_diffs:
            probes[6] = max(a6_diffs)
            probes[-6] = int(sum(d > 0 for d in a6_diffs))  # num responsive cells

    env.step(GameAction.RESET)

    # --- R2 derived features ---
    dir_map, player_color = _derive_dir_map(probes_raw)
    click_cells = _derive_click_responsive_cells(probes_a6)
    topology = _derive_change_topology(probes_raw, int(frame0.size), dir_map)
    color_hist = _derive_color_histogram(frame0)
    symmetry = _derive_symmetry_score(frame0)
    movable_count = _derive_movable_region_count(probes_raw)

    return DiscoveryReport(
        game_title=str(title),
        available_actions=avail,
        layer_count=layers,
        dominant_colors=colors,
        probe_diffs=probes,
        reset_levels=int(obs.levels_completed),
        frame_shape=tuple(frame0.shape),
        dir_map=dir_map,
        player_color=player_color,
        movable_region_count=movable_count,
        click_responsive_cells=click_cells,
        change_topology=topology,
        color_histogram=color_hist,
        symmetry_score=symmetry,
        total_pixels=int(frame0.size),
    )


class WikiAgent:
    """Reads `.wiki/` + a live discovery report, asks an LLM what to run, then dispatches.

    Parameters
    ----------
    llm: LLMBackend — any backend from `admorphiq.llm` that satisfies the protocol.
    strategy_registry: dict[str, Callable] — maps strategy names to **ctx-aware**
        callables with signature ``(env, budget, ctx) -> (levels, label, actions)``.
        After R3 (2026-04-21) every registered callable is a wrapper built by
        :func:`dispatcher._make_wrapper`; it pulls the args it needs (dir_actions,
        player_color, etc.) from ``ctx`` and calls the underlying `strat_*`
        function positionally. The WikiAgent builds ``ctx`` once per run from
        the DiscoveryReport via :func:`dispatcher.build_ctx`.
    retriever: GraphRetriever — R7b graph-based wiki walker. Defaults to a
        retriever rooted at the repo's `.wiki/wiki/`. Override with a retriever
        pointed at a different tree only for tests or experiments.
    context_chars: int — soft cap on prompt wiki length (default 8000, tuned for T4 budget).
    round_num, round_learnings: injected into the prompt so the LLM knows which
        round of the dev-time loop it is and what prior rounds concluded.
    """

    def __init__(
        self,
        llm: LLMBackend,
        strategy_registry: dict[str, Callable[..., tuple[int, str, int]]],
        retriever: "GraphRetriever | None" = None,
        context_chars: int = 16000,
        round_num: int = 1,
        round_learnings: str = _DEFAULT_ROUND_LEARNINGS,
    ) -> None:
        from .wiki_retrieval import GraphRetriever

        self.llm = llm
        self.strategies = strategy_registry
        self.context_chars = context_chars
        self.round_num = int(round_num)
        self.round_learnings = str(round_learnings)
        self.retriever = retriever or GraphRetriever(WIKI_DIR)
        # Populated by build_prompt; exposed to run() for trace emission.
        self._last_retrieved_pages: list[str] = []

    def build_prompt(
        self, report: DiscoveryReport, wiki_needs: list[str] | None = None
    ) -> str:
        context, retrieved = self.retriever.retrieve(
            report, wiki_needs=wiki_needs, budget_chars=self.context_chars
        )
        self._last_retrieved_pages = retrieved
        names = sorted(self.strategies.keys())
        return _PROMPT_TEMPLATE.format(
            round_num=self.round_num,
            round_learnings=self.round_learnings,
            context=context,
            title=report.game_title,
            avail=report.available_actions,
            layers=report.layer_count,
            shape=report.frame_shape,
            colors=report.dominant_colors,
            color_hist=report.color_histogram,
            symmetry=report.symmetry_score,
            probes=report.probe_diffs,
            dir_map=report.dir_map or "(none)",
            player_color=report.player_color if report.player_color is not None else "null",
            movable_count=report.movable_region_count,
            topology=report.change_topology,
            click_cells=report.click_responsive_cells or "(none)",
            lvl=report.reset_levels,
            n_strategies=len(names),
            strategy_list=", ".join(names),
        )

    def classify(self, report: DiscoveryReport, max_tokens: int = 512) -> Hypothesis:
        prompt = self.build_prompt(report)
        # Inject the live strategy whitelist as enum constraints on
        # primary_strategy and fallback_stack items. Measured on the
        # 2026-04-21 R7 bench (v1): the base schema (string type only)
        # still let Qwen 8B hallucinate invalid names 26/40 envs. With an
        # enum, the decoder physically cannot emit a non-whitelisted name.
        schema = dict(_HYPOTHESIS_JSON_SCHEMA)
        schema["properties"] = dict(schema["properties"])
        whitelist = sorted(self.strategies.keys())
        schema["properties"]["primary_strategy"] = {
            "type": "string",
            "enum": whitelist,
        }
        # uniqueItems forces Qwen to actually think of 3 *distinct* fallbacks
        # rather than padding with duplicates. 2026-04-21 R7 v3 bench showed
        # 4/40 envs with all-duplicate fallbacks (CD82 got click_color_order
        # four times in the stack), which wastes every fallback slot.
        schema["properties"]["fallback_stack"] = {
            "type": "array",
            "items": {"type": "string", "enum": whitelist},
            "maxItems": 3,
            "uniqueItems": True,
        }
        raw = self.llm.generate(prompt, max_tokens=max_tokens, json_schema=schema)
        parsed = _parse_json_lenient(raw)
        try:
            confidence = float(parsed.get("confidence", 0.0))
        except (TypeError, ValueError):
            confidence = 0.0
        hyp = Hypothesis(
            game_type=str(parsed.get("game_type", "unknown")),
            primary_strategy=str(parsed.get("primary_strategy", "")),
            fallback_stack=[str(s) for s in parsed.get("fallback_stack", [])][:3],
            rationale=str(parsed.get("rationale", "")),
            confidence=max(0.0, min(1.0, confidence)),
            doubt=str(parsed.get("doubt", "")),
            features_missing=_parse_feature_gaps(parsed.get("features_missing", [])),
            wiki_gaps=_parse_wiki_gaps(parsed.get("wiki_gaps", [])),
            wiki_needs=[str(p) for p in parsed.get("wiki_needs", [])][:10],
            raw=raw,
        )
        valid = set(self.strategies.keys())
        hyp = _validate_whitelist(hyp, valid)
        return hyp

    def run(self, env: Any, title: str = "UNKNOWN", budget_per_strategy: int = 5000) -> dict[str, Any]:
        """Full loop: discover → classify → dispatch primary → fallbacks on failure.

        Returns a trace suitable for JSON logging. Does not raise — strategy
        failures are captured as `{"status": "error", ...}`.
        """
        from .dispatcher import build_ctx

        t_start = time.time()
        try:
            report = discover(env, title=title)
        except Exception as exc:  # noqa: BLE001 - top-level guard for the inference loop
            return {"status": "error", "stage": "discover", "error": str(exc)}

        ctx = build_ctx(report)
        hyp = self.classify(report)
        trace: dict[str, Any] = {
            "game_title": report.game_title,
            "discovery": {
                "available_actions": report.available_actions,
                "layer_count": report.layer_count,
                "dominant_colors": report.dominant_colors,
                "probe_diffs": report.probe_diffs,
                # --- R2 features (fed to reflection) ---
                "dir_map": report.dir_map,
                "player_color": report.player_color,
                "movable_region_count": report.movable_region_count,
                "click_responsive_cells": report.click_responsive_cells,
                "change_topology": report.change_topology,
                "color_histogram": report.color_histogram,
                "symmetry_score": report.symmetry_score,
            },
            "hypothesis": {
                "game_type": hyp.game_type,
                "primary_strategy": hyp.primary_strategy,
                "fallback_stack": hyp.fallback_stack,
                "rationale": hyp.rationale,
                "confidence": hyp.confidence,
                "doubt": hyp.doubt,
                "features_missing": [
                    {"name": f.name, "why_needed": f.why_needed, "derive_hint": f.derive_hint}
                    for f in hyp.features_missing
                ],
                "wiki_gaps": [
                    {
                        "topic": g.topic,
                        "suggested_page": g.suggested_page,
                        "current_info_insufficient": g.current_info_insufficient,
                        "proposed_addition": g.proposed_addition,
                    }
                    for g in hyp.wiki_gaps
                ],
                "wiki_needs": hyp.wiki_needs,
            },
            "retrieved_pages": list(self._last_retrieved_pages),
            "executions": [],
            "best_levels": report.reset_levels,
        }

        best = report.reset_levels
        for sname in [hyp.primary_strategy, *hyp.fallback_stack]:
            if not sname or sname not in self.strategies:
                trace["executions"].append({"strategy": sname, "status": "unknown_strategy"})
                continue
            strat = self.strategies[sname]
            t0 = time.time()
            try:
                lvls, winning, used = strat(env, budget_per_strategy, ctx)
            except Exception as exc:  # noqa: BLE001 - isolate strategy crashes
                trace["executions"].append(
                    {"strategy": sname, "status": "error", "error": str(exc)}
                )
                continue
            trace["executions"].append(
                {
                    "strategy": sname,
                    "winning_label": winning,
                    "levels": int(lvls),
                    "actions": int(used),
                    "elapsed_s": round(time.time() - t0, 2),
                    "status": "ok",
                }
            )
            if lvls > best:
                best = int(lvls)
            if best > report.reset_levels:
                break  # primary or first successful fallback wins — stop

        trace["best_levels"] = best
        trace["total_elapsed_s"] = round(time.time() - t_start, 2)
        trace["status"] = "ok"
        return trace
