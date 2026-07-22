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
import json
from pathlib import Path
from typing import Any, Optional

import numpy as np

from admorphiq.hypothesis_select import (
    HypothesisTemplate,
    state_signature_for,
    templates_for_game,
)

Grid = tuple[tuple[int, ...], ...]
Cell = tuple[int, int]

_TRACE_DIR = Path("data/traces")
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
    template: HypothesisTemplate, transitions: list[Transition], game: str
) -> tuple[Optional[float], int]:
    """Fraction of ACTION6 transitions whose predicted change-set matches the
    observed one, over transitions where the template makes a claim. Returns
    ``(accuracy_or_None, n_claims)`` — None when the template claims nothing."""
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

    per_template: dict[str, dict[str, Any]] = {}
    keys_train: dict[str, tuple] = {}
    keys_heldout: dict[str, tuple] = {}
    signatures: dict[str, tuple] = {}
    ranking_train: list[tuple[float, float, str]] = []
    ranking_heldout: list[tuple[float, float, str]] = []
    for template in templates:
        dyn_train, _n_claims_train = _dynamics_accuracy(template, train, game)
        dyn_heldout, _n_claims_heldout = _dynamics_accuracy(template, heldout, game)
        _all, n_claims_all = _dynamics_accuracy(template, transitions, game)
        tpr_all, fpr, win_train, win_heldout = _win_metrics(
            template, win_by_level, non_win_frames
        )
        per_template[template.name] = {
            "dynamics_train": dyn_train,
            "dynamics_heldout": dyn_heldout,
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


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--game", required=True, choices=["ft09", "sc25"])
    parser.add_argument("--out", required=True, help="output JSON path")
    args = parser.parse_args()

    report = evaluate(args.game)
    Path(args.out).write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
