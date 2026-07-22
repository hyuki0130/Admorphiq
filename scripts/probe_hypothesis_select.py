"""R95a discriminative-selection probe (PART 1 — offline, CPU, no LLM).

Scores a finite set of hand-authored mechanic hypotheses (the oracle + hard
negatives, from :mod:`admorphiq.hypothesis_select`) on recorded transitions for
one game, and compares against an exhaustive replay-ranking baseline (no LLM).
The thesis (``docs/design_hypothesis_dsl_r95.md`` §R95a): if exhaustive ranking
already picks the oracle on held-out transitions, an LLM adds no value at this
selection layer and R95b need not be built. This script measures exactly that
baseline; the LLM arm (part 2) plugs the same templates into a guided-json
selection call and is compared against these numbers.

Two axes, reported separately (never collapsed into one score):

* **dynamics** — fraction of ACTION6 transitions where a template's predicted
  changed-cell set matches the observed one (exact for single-cell claims,
  Jaccard >= 0.5 for multi-cell). Split deterministically per level: even-index
  transitions are TRAIN evidence, odd are HELD-OUT. No RNG anywhere.
* **win** — the true-positive rate of ``predict_win`` on each level's cast/win
  frame (the after-frame of that level's last gold ACTION6) and its
  false-positive rate on 20 evenly-sampled non-winning gold frames.

Usage::

    python scripts/probe_hypothesis_select.py --game ft09 --out ft09.json
    python scripts/probe_hypothesis_select.py --game sc25 --out sc25.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any, Callable, Optional

import numpy as np

from admorphiq.adapters25.base import most_common_color
from admorphiq.hypothesis_select import (
    HypothesisTemplate,
    state_signature_for,
    templates_for_game,
)
from admorphiq.kernels import find_regions

Grid = tuple[tuple[int, ...], ...]
Cell = tuple[int, int]

_TRACE_DIR = Path(os.environ.get("R95A_TRACES_DIR", "data/traces"))
_N_SPECIFICITY_FRAMES = 20

# Where the cast/win STATE is observed within a level's gold block. ft09's win
# is an explicit solving click, so its RESULT (the after-frame of the last gold
# ACTION6) is the solved board. sc25 auto-casts on a pattern match with no
# dedicated cast click: the matched grid is observed as the BEFORE-frame of the
# last gold ACTION6 (the engine consumes the match on that next action, whose
# after-frame is already the post-cast redraw with the preview gone). Measured
# directly on both traces (docstring of ``_win_frames``).
_WIN_FRAME_SIDE = {"ft09": "after", "sc25": "before"}


def _to_grid(frame: np.ndarray) -> Grid:
    """A stored frame as a plain ``(row, col)`` int grid. Frames are ``(H, W)``;
    a ``(L, H, W)`` frame keeps its LAST layer (the canonical rendered layer)."""
    arr = np.asarray(frame)
    if arr.ndim == 3:
        arr = arr[-1]
    return tuple(tuple(int(v) for v in row) for row in arr)


class Transition:
    """One recorded ``env.step``: the before/after grids, the action + click, the
    level index, and whether the row is gold (part of a level-clearing block)."""

    __slots__ = ("index", "action", "xy", "level", "is_gold", "before", "after", "levels_after")

    def __init__(
        self,
        index: int,
        action: int,
        xy: tuple[int, int],
        level: int,
        is_gold: bool,
        before: Grid,
        after: Grid,
        levels_after: int,
    ) -> None:
        self.index = index
        self.action = action
        self.xy = xy
        self.level = level
        self.is_gold = is_gold
        self.before = before
        self.after = after
        self.levels_after = levels_after


def _load_transitions(game: str) -> list[Transition]:
    path = _TRACE_DIR / f"{game}.npz"
    if not path.exists():
        raise FileNotFoundError(f"no trace at {path}")
    data = np.load(path, allow_pickle=False)
    frames = data["frames"]
    next_frames = data["next_frames"]
    actions = data["actions"]
    coords_x = data["coords_x"]
    coords_y = data["coords_y"]
    level_index = data["level_index"]
    levels_after = data["levels_completed_after"]
    is_gold = data["is_gold"]
    out: list[Transition] = []
    for i in range(len(actions)):
        out.append(
            Transition(
                index=i,
                action=int(actions[i]),
                xy=(int(coords_x[i]), int(coords_y[i])),
                level=int(level_index[i]),
                is_gold=bool(is_gold[i]),
                before=_to_grid(frames[i]),
                after=_to_grid(next_frames[i]),
                levels_after=int(levels_after[i]),
            )
        )
    return out


def _split_by_level(transitions: list[Transition]) -> tuple[list[Transition], list[Transition]]:
    """Deterministic per-level even/odd split: within each level's transitions
    (in trace order) the even positions are TRAIN, the odd are HELD-OUT."""
    order: dict[int, int] = {}
    train: list[Transition] = []
    heldout: list[Transition] = []
    for t in transitions:
        pos = order.get(t.level, 0)
        order[t.level] = pos + 1
        (train if pos % 2 == 0 else heldout).append(t)
    return train, heldout


def _non_hud(cell: Cell, game: str, height: int, width: int) -> bool:
    """Whether ``cell = (row, col)`` is outside the game's HUD chrome. ft09's HUD
    is the bottom status row; sc25's is the left/right vertical budget-bar
    strip. Changed cells inside the HUD are excluded from dynamics scoring."""
    row, col = cell
    if game == "ft09":
        return row < height - 1
    if game == "sc25":
        return 0 < col < width - 1
    return True


def _observed_changes(t: Transition, game: str) -> set[Cell]:
    height = len(t.before)
    width = len(t.before[0]) if t.before else 0
    changed = np.argwhere(np.asarray(t.before) != np.asarray(t.after))
    return {
        (int(r), int(c))
        for r, c in changed
        if _non_hud((int(r), int(c)), game, height, width)
    }


def _prediction_matches(pred: set[Cell], observed: set[Cell]) -> bool:
    """A single-cell claim (<= 1 cell) must equal the observed set exactly; a
    multi-cell claim matches when Jaccard(pred, observed) >= 0.5."""
    if len(pred) <= 1:
        return pred == observed
    if not pred and not observed:
        return True
    union = pred | observed
    if not union:
        return True
    return len(pred & observed) / len(union) >= 0.5


def _dynamics_accuracy(
    template: HypothesisTemplate,
    transitions: list[Transition],
    game: str,
    mask: Optional[Mask] = None,
) -> tuple[Optional[float], int]:
    """Fraction of ACTION6 transitions whose predicted change-set matches the
    observed one, over transitions where the template makes a claim. Returns
    ``(accuracy_or_None, n_claims)`` — None when the template claims nothing.
    When a ``mask`` is supplied, masked chrome pixels are removed from the
    observed set (used for the separately-reported ``dynamics_heldout_masked``);
    with ``mask=None`` the behaviour is byte-identical to the frozen part-1
    scoring."""
    claims = 0
    hits = 0
    for t in transitions:
        if t.action != 6:
            continue
        pred = template.predict_click(t.before, t.xy)
        if pred is None:
            continue
        claims += 1
        observed = _observed_changes(t, game)
        if mask is not None:
            observed = observed - _masked_cells(game, t, mask)
        pred_non_hud = {
            c for c in pred if _non_hud(c, game, len(t.before), len(t.before[0]))
        }
        if _prediction_matches(pred_non_hud, observed):
            hits += 1
    if claims == 0:
        return None, 0
    return hits / claims, claims


def _win_frames(transitions: list[Transition], side: str) -> dict[int, list[Grid]]:
    """Per level, the cast/win frames. A level-up event is a row where
    ``levels_completed_after`` increases; for that event we locate the last gold
    ACTION6 at or before it within the same level and take that click's ``side``
    frame (``"after"`` = the solved board, ``"before"`` = the matched
    auto-cast state — see ``_WIN_FRAME_SIDE``). A level whose gold block has no
    click (e.g. sc25 L2, which was navigated without a captured cast click)
    contributes no win frame."""
    by_level: dict[int, list[Grid]] = {}
    prev_levels = transitions[0].levels_after if transitions else 0
    for pos, t in enumerate(transitions):
        first = pos == 0
        if not first and t.levels_after > prev_levels:
            frame = _last_gold_click_frame(transitions, pos, t.level, side)
            if frame is not None:
                by_level.setdefault(t.level, []).append(frame)
        prev_levels = t.levels_after
    return by_level


def _last_gold_click_frame(
    transitions: list[Transition], event_pos: int, level: int, side: str
) -> Optional[Grid]:
    for j in range(event_pos, -1, -1):
        tj = transitions[j]
        if tj.level != level:
            break
        if tj.is_gold and tj.action == 6:
            return tj.after if side == "after" else tj.before
    return None


def _is_cast_state(
    frame: Grid, win_grids: set[Grid], win_sigs: set[object], sig_fn
) -> bool:
    """Whether ``frame`` is a genuine cast/win state — byte-identical to a
    selected win frame, OR (when the game supplies a colour-canonical state
    signature) the same board CONFIGURATION as a win frame. sc25's gold trace
    lingers on the matched state through the auto-cast animation, producing many
    frames that are the same cast configuration but not byte-identical (transient
    cursor colours differ); those are genuine cast states, not negatives, and
    must be kept out of the false-positive pool."""
    if frame in win_grids:
        return True
    if sig_fn is not None:
        sig = sig_fn(frame)
        if sig is not None and sig in win_sigs:
            return True
    return False


def _specificity_frames(
    transitions: list[Transition], win_grids: list[Grid], game: str
) -> tuple[list[Grid], str]:
    """Up to 20 evenly-spaced NON-cast gold ACTION6 after-frames — the pool for
    measuring each ``predict_win``'s false-positive rate. Genuine cast/win states
    (byte- or configuration-identical to a selected win frame) are excluded via
    ``_is_cast_state``.

    Deliberately gold-only, NOT widened to the whole trace: in sc25 the matched
    spell pattern PERSISTS through the post-cast navigate phase and across levels
    (including L2, which has no gold-click ground truth), so most non-gold frames
    are still cast states — pulling them in would count genuine cast states as
    false positives (an artifact, measured: it inflated the oracle's FP to 0.9).
    The honest consequence is that when a game's whole gold block is cast states
    (sc25), the clean-negative pool is EMPTY and the false-positive rate is
    UNDEFINED — reported as such rather than fabricated. Returns ``(frames,
    source)`` where source is ``"gold"`` or ``"none_clean_negatives"``."""
    sig_fn = state_signature_for(game)
    win_set = set(win_grids)
    win_sigs: set[object] = set()
    if sig_fn is not None:
        for g in win_grids:
            s = sig_fn(g)
            if s is not None:
                win_sigs.add(s)

    seen: set[Grid] = set()
    gold_pool: list[Grid] = []
    for t in transitions:
        if not (t.is_gold and t.action == 6):
            continue
        f = t.after
        if f in seen or _is_cast_state(f, win_set, win_sigs, sig_fn):
            continue
        seen.add(f)
        gold_pool.append(f)

    if not gold_pool:
        return [], "none_clean_negatives"
    if len(gold_pool) <= _N_SPECIFICITY_FRAMES:
        return gold_pool, "gold"
    idx = np.linspace(0, len(gold_pool) - 1, _N_SPECIFICITY_FRAMES).round().astype(int)
    return [gold_pool[i] for i in idx], "gold"


def _win_metrics(
    template: HypothesisTemplate,
    win_by_level: dict[int, list[Grid]],
    non_win_frames: list[Grid],
) -> tuple[float, Optional[float], float, float]:
    """Returns ``(tpr_all, fpr, win_score_train, win_score_heldout)``. Win events
    are split per level even/odd (train/heldout) exactly like dynamics; the win
    score = TPR * specificity, where specificity = 1 - FPR. ``fpr`` is ``None``
    when there are NO clean non-cast negatives (specificity is then undefined and
    treated as 1.0 for the score, so the win axis reduces to TPR — which still
    separates a template that misses the win, e.g. sc25's absolute_preview)."""
    all_frames: list[Grid] = []
    train_frames: list[Grid] = []
    heldout_frames: list[Grid] = []
    for _level, frames in sorted(win_by_level.items()):
        for pos, frame in enumerate(frames):
            all_frames.append(frame)
            (train_frames if pos % 2 == 0 else heldout_frames).append(frame)

    def tpr(frames: list[Grid]) -> float:
        if not frames:
            return 0.0
        return sum(1 for f in frames if template.predict_win(f)) / len(frames)

    fpr: Optional[float] = None
    if non_win_frames:
        fpr = sum(1 for f in non_win_frames if template.predict_win(f)) / len(non_win_frames)
    specificity = 1.0 - (fpr or 0.0)
    return tpr(all_frames), fpr, tpr(train_frames) * specificity, tpr(heldout_frames) * specificity


def _flatten_win_frames(win_by_level: dict[int, list[Grid]]) -> list[Grid]:
    return [f for _level, frames in sorted(win_by_level.items()) for f in frames]


def _behaviour_signature(
    template: HypothesisTemplate,
    transitions: list[Transition],
    win_frames: list[Grid],
    spec_frames: list[Grid],
    game: str,
) -> tuple:
    """A template's full per-item behaviour on the scored data: for every
    ACTION6 transition, ``N`` (no claim) / ``1`` (dynamics match) / ``0`` (miss);
    then ``predict_win`` on every win frame and every specificity frame, all in
    fixed order. Two templates with an identical signature are behaviourally
    INDISTINGUISHABLE on this trace — a genuine equivalence class, not an
    ordering artifact. This is stricter than equal aggregate scores (it forbids
    compensating per-item differences)."""
    dyn: list[str] = []
    for t in transitions:
        if t.action != 6:
            continue
        pred = template.predict_click(t.before, t.xy)
        if pred is None:
            dyn.append("N")
            continue
        observed = _observed_changes(t, game)
        pred_non_hud = {
            c for c in pred if _non_hud(c, game, len(t.before), len(t.before[0]))
        }
        dyn.append("1" if _prediction_matches(pred_non_hud, observed) else "0")
    win = tuple(template.predict_win(f) for f in win_frames)
    spec = tuple(template.predict_win(f) for f in spec_frames)
    return (tuple(dyn), win, spec)


def _tie_group(oracle_name: str, signatures: dict[str, tuple]) -> list[str]:
    """Templates (other than the oracle) whose behaviour signature is identical
    to the oracle's — the oracle's equivalence class on this trace."""
    oracle_sig = signatures[oracle_name]
    return sorted(
        name for name, sig in signatures.items() if name != oracle_name and sig == oracle_sig
    )


def _oracle_strictly_wins(
    oracle_name: str, keys: dict[str, tuple], tie_group: set[str]
) -> bool:
    """The oracle wins only when every OTHER template is either a genuine
    behavioural tie (in ``tie_group``) or scores STRICTLY below the oracle on the
    ranking key. No silent order-based winner: an equal-scoring template that is
    NOT a behavioural tie makes this False (the selection test cannot separate
    them and the tie is not justified)."""
    oracle_key = keys[oracle_name]
    for name, key in keys.items():
        if name == oracle_name or name in tie_group:
            continue
        if not key < oracle_key:
            return False
    return True


def evaluate(game: str) -> dict[str, Any]:
    """Score every candidate template on ``game`` and rank them against the
    exhaustive replay baseline. Returns the full JSON-serialisable report."""
    transitions = _load_transitions(game)
    templates, oracle_name = templates_for_game(game)
    train, heldout = _split_by_level(transitions)

    win_by_level = _win_frames(transitions, _WIN_FRAME_SIDE.get(game, "after"))
    win_grids = [g for frames in win_by_level.values() for g in frames]
    win_flat = _flatten_win_frames(win_by_level)
    non_win_frames, spec_source = _specificity_frames(transitions, win_grids, game)

    # Transient-chrome mask (task #125), derived from TRAIN. Used ONLY for the
    # separately-reported dynamics_heldout_masked — the frozen dynamics_train /
    # dynamics_heldout and the ranking keys stay unmasked (part-1 numbers frozen).
    mask = _compute_transient_mask(game, train)

    per_template: dict[str, dict[str, Any]] = {}
    keys_train: dict[str, tuple] = {}
    keys_heldout: dict[str, tuple] = {}
    signatures: dict[str, tuple] = {}
    ranking_train: list[tuple[float, float, str]] = []
    ranking_heldout: list[tuple[float, float, str]] = []
    for template in templates:
        dyn_train, _n_claims_train = _dynamics_accuracy(template, train, game)
        dyn_heldout, _n_claims_heldout = _dynamics_accuracy(template, heldout, game)
        dyn_heldout_masked, _n = _dynamics_accuracy(template, heldout, game, mask)
        _all, n_claims_all = _dynamics_accuracy(template, transitions, game)
        tpr_all, fpr, win_train, win_heldout = _win_metrics(
            template, win_by_level, non_win_frames
        )
        per_template[template.name] = {
            "dynamics_train": dyn_train,
            "dynamics_heldout": dyn_heldout,
            "dynamics_heldout_masked": dyn_heldout_masked,
            "n_click_claims": n_claims_all,
            "win_true_positive_rate": tpr_all,
            "win_false_positive_rate": fpr,
        }
        keys_train[template.name] = ((dyn_train or 0.0), win_train)
        keys_heldout[template.name] = ((dyn_heldout or 0.0), win_heldout)
        signatures[template.name] = _behaviour_signature(
            template, transitions, win_flat, non_win_frames, game
        )
        ranking_train.append(((dyn_train or 0.0), win_train, template.name))
        ranking_heldout.append(((dyn_heldout or 0.0), win_heldout, template.name))

    ranking_train.sort(key=lambda e: (-e[0], -e[1], e[2]))
    ranking_heldout.sort(key=lambda e: (-e[0], -e[1], e[2]))

    tied = _tie_group(oracle_name, signatures)
    tie_set = set(tied)
    oracle_wins_train = _oracle_strictly_wins(oracle_name, keys_train, tie_set)
    oracle_wins_heldout = _oracle_strictly_wins(oracle_name, keys_heldout, tie_set)

    return {
        "game": game,
        "n_transitions": len(transitions),
        "n_train": len(train),
        "n_heldout": len(heldout),
        "n_win_events": sum(len(v) for v in win_by_level.values()),
        "n_specificity_frames": len(non_win_frames),
        "specificity_source": spec_source,
        "transient_mask": {
            "hud_edges": sorted(mask["edges"]),
            "cursor_colours": sorted(mask["cursor_colours"]),
        },
        "templates": per_template,
        "ranking_train": [name for *_score, name in ranking_train],
        "ranking_heldout": [name for *_score, name in ranking_heldout],
        "oracle_name": oracle_name,
        "exhaustive_train_winner": ranking_train[0][2],
        "exhaustive_heldout_winner": ranking_heldout[0][2],
        "tied_with_oracle": tied,
        "oracle_wins_train": oracle_wins_train,
        "oracle_wins_heldout": oracle_wins_heldout,
    }


# ── PART 2: LLM selection ask (guided-json, no held-out data, no names) ───────

# Fresh NEUTRAL one-paragraph descriptions per template — no template names, no
# "oracle"/historical labels, no game ids. Keyed by the internal template name
# (used only to map back after the model answers by neutral id). These are the
# ONLY template information the model sees; the leak-guard test asserts none of
# the internal names / "oracle" / game ids appear in the assembled prompt.
_NEUTRAL_DESCRIPTIONS: dict[str, dict[str, str]] = {
    "ft09": {
        "glyph_constraints": (
            "Clicking a cell changes only that one cell, advancing its colour by one "
            "step through a short repeating cycle. The board is complete when every "
            "cell simultaneously satisfies a set of relational colour requirements set "
            "by nearby marker symbols: each requirement says a cell must either equal "
            "or differ from a specific marker's colour, a cell can be governed by "
            "several markers at once, and all of its requirements must hold together."
        ),
        "gf2_stencil": (
            "Clicking a cell changes that cell together with its four immediate "
            "up/down/left/right neighbours, which flip as a single plus-shaped group. "
            "The board is complete when every cell simultaneously satisfies the "
            "relational colour requirements set by nearby marker symbols."
        ),
        "nearest_glyph_only": (
            "Clicking a cell changes only that one cell, advancing its colour one step. "
            "The board is complete when every cell satisfies the colour requirement of "
            "only its single closest marker symbol; requirements from any farther marker "
            "are ignored."
        ),
        "uniform_colour": (
            "Clicking a cell changes only that one cell, advancing its colour one step. "
            "The board is complete when every interactive cell shows one and the same "
            "colour."
        ),
        "all_ink_equal": (
            "Clicking a cell changes only that one cell, advancing its colour one step. "
            "The board is complete when every cell equals the colour of each nearby "
            "marker symbol that governs it — every requirement is an equality, there are "
            "no 'must differ' requirements."
        ),
    },
    "sc25": {
        "binary_flip_xor": (
            "Clicking a grid cell flips only that one cell between its two possible "
            "colours. The configuration is complete when the grid's pattern of flipped "
            "cells EXACTLY matches a separately displayed target pattern."
        ),
        "colour_cycle": (
            "Clicking a grid cell advances only that cell, and cells can take three or "
            "more different colours in a repeating cycle. The configuration is complete "
            "when the grid shows more than two distinct colours at once."
        ),
        "near_match_threshold": (
            "Clicking a grid cell flips only that one cell. The configuration is complete "
            "when the grid's pattern matches the displayed target pattern in most cells; "
            "a few mismatched cells are still acceptable."
        ),
        "neighbour_stencil": (
            "Clicking a grid cell flips that cell together with at least one adjacent "
            "grid cell. The configuration is complete when the grid's pattern EXACTLY "
            "matches the displayed target pattern."
        ),
        "absolute_preview": (
            "Clicking a grid cell flips only that one cell. The configuration is complete "
            "when the grid cells directly show the same colours as the displayed target "
            "markers themselves."
        ),
    },
}

_CONFIDENCE_VALUES = ("low", "medium", "high")


def _shuffle_order(game: str, names: list[str]) -> list[str]:
    """A DETERMINISTIC permutation of ``names`` keyed on the game string via
    hashlib (no `random` module) — so the same game always yields the same
    T1..T5 assignment, but the order carries no oracle-first bias."""
    def key(name: str) -> int:
        digest = hashlib.sha256(f"{game}:{name}".encode()).digest()
        return int.from_bytes(digest[:8], "big")

    return sorted(names, key=key)


def _parse_skeleton(game: str, frame: Grid) -> str:
    """A one-line structural summary of a representative (TRAIN) frame — the
    ring count (ft09) or lattice cell count (sc25). Pure perception, no template
    identity."""
    if game == "ft09":
        from admorphiq.adapters25.ft09 import _discover_rings

        return f"{len(_discover_rings(frame))} repeating marker-and-ring group(s) detected"
    if game == "sc25":
        from admorphiq.hypothesis_select.templates import _sc25_lattice

        lattice = _sc25_lattice(frame)
        n = len(lattice["index"]) if lattice else 0
        return f"an interactive lattice of {n} equal-size cells detected"
    return "no structural summary available"


# ── transient chrome masking (task #125 — binding layer #1) ──────────────────
#
# The observation package must count INTERACTIVE game cells, not click-driven
# chrome. Two generic, trace-derived signatures are masked before the histogram:
#
#  (1) HUD edge bar — a vertical UI strip against a left/right frame edge that
#      redraws on (nearly) every click regardless of WHERE the click lands (e.g.
#      a click-budget fill bar). Detected as "a changed region touching this edge
#      appears in >= _HUD_EDGE_FRACTION of clicks"; then every changed region
#      touching that edge is masked. Measured: sc25 right-edge touch = 0.86 (the
#      budget bar, cols 62-63, leaking past the col-63 HUD mask) vs ft09 = 0.06,
#      so the threshold fixes sc25 and leaves ft09 byte-identical.
#  (2) Relocating cursor — a small changed region at/near the click xy that
#      MOVES to the next click's xy while its previous location REVERTS. Detected
#      from consecutive same-level click transitions; with < 2 consecutive clicks
#      in a level no relocation can be confirmed, so nothing is masked (honest
#      default). (Neither public trace exhibits one — the sc25 click-markers
#      persist as toggle state — so this is a generic guard, inert here.)
_HUD_EDGE_FRACTION = 0.8
_CURSOR_RADIUS = 4  # cells; "near the click" for cursor attribution
# A genuine cursor move is LOCALIZED (remove the old overlay + repaint at the new
# xy + maybe one toggle). A decoy->reveal / level-transition redraw touches many
# regions and would otherwise coincidentally satisfy the strict cursor test on
# random colour matches, so both clicks of a candidate pair must be this local.
_CURSOR_MAX_REGIONS = 4
# A real cursor relocates on (nearly) EVERY click, so its colour is confirmed by
# a large fraction of consecutive localized pairs. Requiring a fraction — not a
# single pair — rejects the occasional coincidental colour match a 2-value toggle
# cycle produces (measured: ft09 yields lone spurious hits that never approach
# this share), the same fractional-evidence logic the HUD edge rule uses.
_CURSOR_CONFIRM_FRACTION = 0.5

Mask = dict[str, Any]


def _changed_regions(game: str, t: Transition) -> list[dict[str, Any]]:
    """The small non-chrome regions on the before-frame whose pixels changed
    under this click — the candidate interactive cells."""
    changed = _observed_changes(t, game)
    if not changed:
        return []
    before = t.before
    total = len(before) * len(before[0]) if before else 1
    max_size = max(1, int(0.15 * total))
    bg = most_common_color(before)
    return [
        r
        for r in find_regions(before, background=bg)
        if r["size"] <= max_size and (set(r["cells"]) & changed)
    ]


def _touches_edges(regions: list[dict[str, Any]], width: int) -> tuple[bool, bool]:
    """Whether any region touches the left (col<=1) / right (col>=width-2) edge."""
    left = any(r["bbox"][1] <= 1 for r in regions)
    right = any(r["bbox"][3] >= width - 2 for r in regions)
    return left, right


def _detect_cursor_colours(game: str, transitions: list[Transition]) -> set[int]:
    """Colours behaving as a relocating cursor: an overlay of ONE colour that a
    click paints at its xy, which the NEXT same-level click removes (that cell
    reverts to its pre-click underlying colour) while repainting the SAME colour
    at the new click's xy. All four conditions are required, so a persistent
    toggle (a cell that stays changed — ft09/sc25) and a colour cycle (a cell
    that changes to a DIFFERENT colour) both fail to register. Per-level
    consecutive clicks only; a level with < 2 consecutive clicks confirms nothing
    (the honest no-mask default)."""
    by_level: dict[int, list[Transition]] = {}
    for t in transitions:
        if t.action == 6 and _observed_changes(t, game):
            by_level.setdefault(t.level, []).append(t)
    confirmations: dict[int, int] = {}
    localized_pairs = 0
    for clicks in by_level.values():
        for a, b in zip(clicks, clicks[1:]):
            regions_a = _changed_regions(game, a)
            regions_b = _changed_regions(game, b)
            if len(regions_a) > _CURSOR_MAX_REGIONS or len(regions_b) > _CURSOR_MAX_REGIONS:
                continue  # a wholesale redraw, not a localized cursor move
            localized_pairs += 1
            ax, ay = a.xy
            cand = _nearest_region(regions_a, ay, ax)
            if cand is None:
                continue
            cr, cc = round(cand["centroid"][0]), round(cand["centroid"][1])
            overlay = int(a.after[cr][cc])
            underlying = int(a.before[cr][cc])
            if overlay == underlying:
                continue  # the click did not paint a distinct overlay here
            if (cr, cc) not in _observed_changes(b, game):
                continue  # the previous location was not touched by the next click
            if int(b.after[cr][cc]) != underlying:
                continue  # it did not revert to its pre-click underlying colour
            bx, by = b.xy
            new_region = _nearest_region(regions_b, by, bx)
            if new_region is None:
                continue
            nr, nc = round(new_region["centroid"][0]), round(new_region["centroid"][1])
            if int(b.after[nr][nc]) != overlay:
                continue  # the overlay did not reappear (same colour) at the new xy
            confirmations[overlay] = confirmations.get(overlay, 0) + 1
    if localized_pairs < 2:
        return set()  # too few consecutive clicks to confirm relocation (honest default)
    return {
        colour
        for colour, count in confirmations.items()
        if count / localized_pairs >= _CURSOR_CONFIRM_FRACTION
    }


def _nearest_region(
    regions: list[dict[str, Any]], row: int, col: int
) -> Optional[dict[str, Any]]:
    """The region whose centroid is nearest (<= _CURSOR_RADIUS) to (row, col)."""
    best: Optional[tuple[float, dict[str, Any]]] = None
    for r in regions:
        rr, rc = r["centroid"]
        dist = abs(rr - row) + abs(rc - col)
        if dist <= 2 * _CURSOR_RADIUS and (best is None or dist < best[0]):
            best = (dist, r)
    return best[1] if best else None


def _compute_transient_mask(game: str, transitions: list[Transition]) -> Mask:
    """Derive the transient-chrome mask (HUD edges + cursor colours) from
    ``transitions`` (TRAIN). Pure detection — no game-specific colours/positions."""
    width = len(transitions[0].before[0]) if transitions and transitions[0].before else 0
    clicks = [t for t in transitions if t.action == 6 and _observed_changes(t, game)]
    edges: set[str] = set()
    if clicks:
        left = right = 0
        for t in clicks:
            tl, tr = _touches_edges(_changed_regions(game, t), width)
            left += int(tl)
            right += int(tr)
        if left / len(clicks) >= _HUD_EDGE_FRACTION:
            edges.add("left")
        if right / len(clicks) >= _HUD_EDGE_FRACTION:
            edges.add("right")
    return {"edges": edges, "width": width, "cursor_colours": _detect_cursor_colours(game, transitions)}


def _is_transient_region(region: dict[str, Any], t: Transition, mask: Mask) -> bool:
    """Whether ``region`` is masked chrome under ``mask``: a HUD edge bar, or a
    relocating cursor sitting at this click's xy."""
    _r0, c0, _r1, c1 = region["bbox"]
    if "left" in mask["edges"] and c0 <= 1:
        return True
    if "right" in mask["edges"] and c1 >= mask["width"] - 2:
        return True
    if mask["cursor_colours"]:
        rr, cc = round(region["centroid"][0]), round(region["centroid"][1])
        x, y = t.xy
        near = abs(rr - y) <= _CURSOR_RADIUS and abs(cc - x) <= _CURSOR_RADIUS
        if near and int(t.after[rr][cc]) in mask["cursor_colours"]:
            return True
    return False


def _masked_cells(game: str, t: Transition, mask: Mask) -> set[Cell]:
    """The pixel cells belonging to masked chrome regions in this transition."""
    cells: set[Cell] = set()
    for r in _changed_regions(game, t):
        if _is_transient_region(r, t, mask):
            cells |= set(r["cells"])
    return cells


def _changed_unit_count(game: str, t: Transition, mask: Optional[Mask] = None) -> int:
    """The number of distinct INTERACTIVE CELLS (small non-chrome regions on the
    before-frame) whose pixels changed under this click — the logical-cell count
    the templates speak in, NOT a raw pixel count. A single button/lattice cell
    is one region of many pixels; reporting pixels would read as a multi-cell
    change and bias the model toward the neighbourhood-stencil hypothesis. When a
    ``mask`` is supplied, masked chrome regions (HUD bar / cursor) are excluded."""
    return sum(
        1
        for r in _changed_regions(game, t)
        if mask is None or not _is_transient_region(r, t, mask)
    )


def _observation_summary(game: str, train: list[Transition]) -> str:
    """A neutral observation block computed from TRAIN transitions ONLY: action
    usage, the per-click changed-CELL-count histogram (logical interactive cells,
    not pixels), three example clicks, the completion-moment full-frame pixel
    change magnitude (per R57), and the parse skeleton. No held-out data, no
    template scores."""
    action_names = {1: "ACTION1", 2: "ACTION2", 3: "ACTION3", 4: "ACTION4", 6: "CLICK(ACTION6)", 7: "ACTION7"}
    counts: dict[str, int] = {}
    for t in train:
        label = action_names.get(t.action, f"ACTION{t.action}")
        counts[label] = counts.get(label, 0) + 1
    usage = ", ".join(f"{k}={v}" for k, v in sorted(counts.items()))

    mask = _compute_transient_mask(game, train)
    hist: dict[int, int] = {}
    examples: list[str] = []
    for t in train:
        if t.action != 6:
            continue
        if not _observed_changes(t, game):
            continue
        units = _changed_unit_count(game, t, mask)
        hist[units] = hist.get(units, 0) + 1
        if len(examples) < 3:
            x, y = t.xy
            before_near = _near_colours(t.before, x, y)
            examples.append(
                f"  click at (x={x}, y={y}); colours in the 3x3 area around the click "
                f"before it: {before_near}; number of interactive cells that changed: {units}"
            )
    hist_text = (
        ", ".join(f"{k}cell(s)->{v}click(s)" for k, v in sorted(hist.items())) or "none observed"
    )

    completion = _completion_summary(train)

    skeleton = _parse_skeleton(game, train[0].before) if train else ""

    lines = [
        "OBSERVATIONS (computed from one half of the recorded play — the other half is withheld):",
        f"- Action usage: {usage or 'none'}",
        "- When a click changed the board, how many distinct interactive cells changed "
        f"(histogram): {hist_text}",
        "- Example click transitions:",
        *examples,
        f"- Board-completion moments: {completion}",
        f"- Structure: {skeleton}",
    ]
    return "\n".join(lines)


def _near_colours(frame: Grid, x: int, y: int) -> list[list[int]]:
    """The 3x3 block of colours centred on ``(row=y, col=x)`` (clamped), as a
    small nested list for the prompt."""
    h = len(frame)
    w = len(frame[0]) if frame else 0
    block: list[list[int]] = []
    for r in range(y - 1, y + 2):
        row: list[int] = []
        for c in range(x - 1, x + 2):
            row.append(frame[r][c] if 0 <= r < h and 0 <= c < w else -1)
        block.append(row)
    return block


def _completion_summary(train: list[Transition]) -> str:
    """The full-frame change magnitude at completion (level-up) transitions
    within TRAIN, per R57's 'the full-block diff carries the effect' note. Falls
    back to the largest full-frame change observed when no completion transition
    is in this subset."""
    ups: list[int] = []
    prev = train[0].levels_after if train else 0
    for pos, t in enumerate(train):
        if pos > 0 and t.levels_after > prev:
            ups.append(int(np.count_nonzero(np.asarray(t.before) != np.asarray(t.after))))
        prev = t.levels_after
    if ups:
        return (
            f"{len(ups)} completion transition(s) observed; total pixels that changed on the "
            f"full frame at each completion: {ups}"
        )
    if not train:
        return "none observed"
    largest = max(
        int(np.count_nonzero(np.asarray(t.before) != np.asarray(t.after))) for t in train
    )
    return f"no completion transition in this subset; the largest single full-frame change was {largest} pixels"


def build_ask_prompt(
    game: str, transitions: list[Transition]
) -> tuple[list[dict[str, str]], dict[str, str], str]:
    """Assemble the selection ask: five NEUTRAL template descriptions under
    deterministically-shuffled ids T1..T5, plus the TRAIN-only observation
    summary. Returns ``(messages, id->template_name mapping, observation_text)``.
    Contains no template names, no 'oracle', no game id, and no held-out data."""
    templates, _oracle = templates_for_game(game)
    names = [t.name for t in templates]
    order = _shuffle_order(game, names)
    mapping = {f"T{i + 1}": name for i, name in enumerate(order)}
    descriptions = _NEUTRAL_DESCRIPTIONS[game]

    train, _heldout = _split_by_level(transitions)
    observation = _observation_summary(game, train)

    template_block = "\n\n".join(
        f"{tid}: {descriptions[mapping[tid]]}" for tid in sorted(mapping)
    )
    system = (
        "You are analysing a small interactive grid puzzle from recorded play. "
        "You are given several candidate rules that each claim to explain how the "
        "puzzle works and when it is complete, plus observations from actual play. "
        "Choose the ONE candidate rule that best explains the observations."
    )
    user = (
        "CANDIDATE RULES:\n\n"
        f"{template_block}\n\n"
        f"{observation}\n\n"
        "Which single candidate rule best explains these observations? Weigh BOTH "
        "how each click changes the board AND what the completion condition appears "
        "to be. Respond with ONLY a JSON object, no other text:\n"
        '{"choice": "T1"|"T2"|"T3"|"T4"|"T5", "confidence": "low"|"medium"|"high", '
        '"evidence": "<=2 sentences citing the specific observation that decided it"}'
    )
    messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
    return messages, mapping, observation


def _parse_choice(text: str, valid_ids: set[str]) -> tuple[Optional[dict[str, Any]], str]:
    """Extract and validate the ask JSON from the model's text. Returns
    ``(parsed_or_None, error)``. Tolerant of surrounding prose: takes the last
    balanced ``{...}`` object. Validates choice in ``valid_ids``, confidence in
    the closed set, and a string evidence field."""
    matches = re.findall(r"\{[^{}]*\}", text, re.DOTALL)
    if not matches:
        return None, "no JSON object found in the response"
    obj: Optional[dict[str, Any]] = None
    for candidate in reversed(matches):
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict) and "choice" in parsed:
            obj = parsed
            break
    if obj is None:
        return None, "no JSON object with a 'choice' field parsed"
    choice = obj.get("choice")
    if choice not in valid_ids:
        return None, f"choice {choice!r} is not one of {sorted(valid_ids)}"
    confidence = obj.get("confidence", "low")
    if confidence not in _CONFIDENCE_VALUES:
        confidence = "low"
    evidence = obj.get("evidence", "")
    if not isinstance(evidence, str):
        evidence = str(evidence)
    return {"choice": choice, "confidence": confidence, "evidence": evidence[:500]}, ""


def ask_once(
    llm: Callable[[list[dict[str, str]]], str],
    messages: list[dict[str, str]],
    valid_ids: set[str],
) -> dict[str, Any]:
    """One selection ask + validate, with ONE error-feedback retry (mirroring
    ``probe_template_holdout.ask_adaptation``'s validate-and-retry shape).
    Returns ``{choice, confidence, evidence, attempts, error}`` — choice is
    ``None`` on a hard failure."""
    convo = list(messages)
    try:
        text = llm(convo)
    except Exception as exc:  # noqa: BLE001 - offline-safe, record and stop
        return {"choice": None, "confidence": None, "evidence": "", "attempts": 1, "error": str(exc)}
    parsed, err = _parse_choice(text, valid_ids)
    if parsed is not None:
        return {**parsed, "attempts": 1, "error": None}

    convo.append({"role": "assistant", "content": text})
    convo.append({"role": "user", "content": (
        f"Your response was not valid ({err}). Respond with ONLY the JSON object: "
        '{"choice": one of T1..T5, "confidence": low|medium|high, "evidence": "<=2 sentences"}.'
    )})
    try:
        text2 = llm(convo)
    except Exception as exc:  # noqa: BLE001
        return {"choice": None, "confidence": None, "evidence": "", "attempts": 2, "error": str(exc)}
    parsed2, err2 = _parse_choice(text2, valid_ids)
    if parsed2 is not None:
        return {**parsed2, "attempts": 2, "error": None}
    return {"choice": None, "confidence": None, "evidence": "", "attempts": 2, "error": err2}


def _score_choice(
    choice: Optional[str], mapping: dict[str, str], equivalence_class: set[str]
) -> tuple[Optional[str], bool]:
    """Map a neutral id back to its template name and score it: PASS iff the
    mapped template is in the oracle equivalence class (oracle + ties). An
    unmappable / null choice is a FAIL."""
    mapped = mapping.get(choice) if choice is not None else None
    return mapped, mapped in equivalence_class


def run_ask(game: str, reps: int, llm: Callable[[list[dict[str, str]]], str]) -> dict[str, Any]:
    """Run the LLM selection ask ``reps`` times on ``game`` and score each pick
    against part-1's oracle equivalence class. PASS = the mapped template is in
    ``tied_with_oracle ∪ {oracle}``; a strictly-dominated negative is FAIL."""
    report = evaluate(game)
    equivalence_class = sorted(set(report["tied_with_oracle"]) | {report["oracle_name"]})
    eq_set = set(equivalence_class)

    transitions = _load_transitions(game)
    messages, mapping, _obs = build_ask_prompt(game, transitions)
    valid_ids = set(mapping)

    ask_results: list[dict[str, Any]] = []
    passes = 0
    for rep in range(reps):
        res = ask_once(llm, messages, valid_ids)
        mapped, is_pass = _score_choice(res["choice"], mapping, eq_set)
        passes += int(is_pass)
        ask_results.append({
            "rep": rep,
            "choice": res["choice"],
            "mapped_template_name": mapped,
            "in_equivalence_class": "PASS" if is_pass else "FAIL",
            "confidence": res["confidence"],
            "evidence": res["evidence"],
            "attempts": res["attempts"],
            "error": res["error"],
        })

    report["ask_reps"] = reps
    report["shuffle_mapping"] = mapping
    report["equivalence_class"] = equivalence_class
    report["exhaustive_winner_control"] = report["exhaustive_train_winner"]
    report["ask_results"] = ask_results
    report["pass_rate"] = passes / reps if reps else 0.0
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--game", required=True, choices=["ft09", "sc25"])
    parser.add_argument("--out", help="output JSON path")
    parser.add_argument("--ask", action="store_true", help="run the LLM selection ask")
    parser.add_argument("--reps", type=int, default=3, help="LLM ask repetitions per game")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="assemble and print the ask prompt + shuffle mapping without any LLM call",
    )
    args = parser.parse_args()

    if args.dry_run:
        transitions = _load_transitions(args.game)
        messages, mapping, _obs = build_ask_prompt(args.game, transitions)
        print("=== SHUFFLE MAPPING (neutral id -> internal template name) ===")
        print(json.dumps(mapping, indent=2))
        print("\n=== SYSTEM ===\n" + messages[0]["content"])
        print("\n=== USER ===\n" + messages[1]["content"])
        return

    if args.ask:
        from admorphiq.harness.registry import openai_compat_llm

        llm = openai_compat_llm(
            num_predict=int(os.environ.get("HARNESS_PATCH_NUM_PREDICT", "2048")),
            timeout=float(os.environ.get("HARNESS_PATCH_TIMEOUT", "900")),
        )
        report = run_ask(args.game, args.reps, llm)
    else:
        report = evaluate(args.game)

    text = json.dumps(report, indent=2)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
