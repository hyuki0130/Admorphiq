"""R98 spread sweep — score candidate FLANK-CHOICE rules without adopting any.

Purpose
-------
The bench residual is lateral: the model spawns on BOTH flanks of a blocked droplet
while the engine's spread is asymmetric. Each variant here picks a side by an
observable property of the flank and is scored on the physics column, exactly as the
five reach rules were. It is NOT a reach sweep — every variant keeps the adopted
reach untouched.

The script loads the propagator's own source and rewrites one branch, so a variant
never enters the repository to be measured. **idx0 is scored separately and printed
beside every total**, because a rule was once adopted in this round for halving the
sweep and took the live gate to 0/3 — the sweep could not see it, since the contract
board was not in it.

Expected feedback
-----------------
A variant that beats the baseline AND leaves idx0 at 0 is worth measuring live. Any
idx0 above 0 is refuted on the spot, whatever its total.
"""
from __future__ import annotations

import json
import sys
import types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from rule_bench import _board, _captures, _union_board  # noqa: E402

SRC = Path("src/admorphiq/hypothesis_select/propagate_flow.py").read_text()
BASE = """                for i, f in enumerate(targets):
                    if table.piece_direction == "outward_turned":
                        direction = (0, -1) if i == 0 else (0, 1)
                    else:
                        direction = (dr, dc)
                    if 0 <= walked >= WALK_REACH:
                        continue  # the walk along this piece is spent
"""
GUARD = BASE + """                    if _VARIANT(board, f, targets, (dr, dc), wall):
                        continue
"""
# A rule may also SPEND the losing side rather than suppress it: the engine still
# renders a cell there, it just never walks on from it. `walked = WALK_REACH` is
# exactly "this droplet's walk is over" in the propagator's own terms.
SPEND = BASE + """                    if _VARIANT(board, f, targets, (dr, dc), wall):
                        spawn(f, direction, WALK_REACH)
                        continue
"""
FIRST = BASE + """                    if _VARIANT(board, f, targets, (dr, dc), wall, walked):
                        spawn(f, direction, WALK_REACH)
                        continue
"""

def _support_run(board, cell, step, d, wall) -> int:
    """How many consecutive cells from ``cell`` outward along ``step`` are SUPPORTED —
    the length of the surface a droplet could slide along on that side.

    Out of bounds counts as supported, exactly as walk_probe.py counts it, because a
    droplet at the board's edge is not standing over free space."""
    n = 0
    probe = cell
    while n < board.size:
        if _free(board, (probe[0] + d[0], probe[1] + d[1]), wall):
            break
        n += 1
        probe = (probe[0] + step[0], probe[1] + step[1])
    return n


# Suppressing variants: the flank gets no cell at all.
VARIANTS = {
    "baseline (both flanks)": None,
    "only the flank that is SUPPORTED (cannot fall)":
        lambda board, f, targets, d, wall: _free(board, (f[0] + d[0], f[1] + d[1]), wall),
    "only the flank that can FALL":
        lambda board, f, targets, d, wall: not _free(board, (f[0] + d[0], f[1] + d[1]), wall),
    "not onto a flank standing over a piece":
        lambda board, f, targets, d, wall: (f[0] + d[0], f[1] + d[1]) in board.piece_cells,
}

# Spending variants: the flank still gets its cell, but cannot walk on from it.
# Measured by walk_probe.py across all sixteen observed spread events: ONE side walks
# and the other stops after a single cell, and the side that walks is the one with the
# longer run of SUPPORTED cells.
SPEND_VARIANTS = {
    "only the longer SUPPORTED run walks":
        lambda board, f, targets, d, wall: _loses(board, f, targets, d, wall),
    # walk_probe only ever saw this at a FALLING droplet's first collision, so the
    # unrestricted rule above is firing at collisions it was never measured on. The
    # propagator marks a droplet that has not yet walked with walked == -1, and the
    # patch site can read it.
    "...but only at a falling droplet's FIRST collision":
        lambda board, f, targets, d, wall, walked=None: (
            walked == -1 and _loses(board, f, targets, d, wall)),
}


def _loses(board, f, targets, d, wall) -> bool:
    """Is this flank the side with the SHORTER supported run?

    The flanks are built as (cell - lateral, cell + lateral) with lateral = (dc, dr),
    so index 0 walks outward by -lateral and index 1 by +lateral. Deriving the side
    from the cell's own coordinates instead is what made the first version of this
    score a rule nobody had measured."""
    if len(targets) != 2 or f not in targets:
        return False
    lateral = (d[1], d[0])
    i = targets.index(f)
    out = [(-lateral[0], -lateral[1]), lateral]
    mine = _support_run(board, f, out[i], d, wall)
    other = _support_run(board, targets[1 - i], out[1 - i], d, wall)
    return mine < other


def _free(board, cell, wall):
    r, c = cell
    if not (0 <= r < board.size and 0 <= c < board.size):
        return False
    return (cell not in board.piece_cells and cell not in board.absorber_cells
            and cell not in board.hazard_cells and cell not in wall
            and board.sink_of(cell) is None)


def _module(rule, shape=None):
    src = SRC if rule is None else SRC.replace(BASE, shape or GUARD)
    mod = types.ModuleType("pf_variant")
    # dataclasses resolves annotations through sys.modules, so the module has to be
    # registered before the class bodies run
    sys.modules["pf_variant"] = mod
    mod.__dict__["_VARIANT"] = rule
    mod.__dict__["_free"] = _free
    exec(compile(src, "pf_variant", "exec"), mod.__dict__)
    return mod


def score(mod):
    total = idx0 = 0
    for path in _captures():
        payload = json.load(open(path))
        board = _union_board(_board(payload), payload)
        board = mod.Board(**{f: getattr(board, f) for f in board.__dataclass_fields__})
        pred = {c for layer in mod.predict(board, mod.ORACLE).frontier for c in layer}
        obs = {tuple(c) for layer in payload["observed"] for c in layer}
        err = len(pred - obs) + len(obs - pred)
        total += err
        if "idx0" in path.stem:
            idx0 = err
    return total, idx0


for name, rule in VARIANTS.items():
    total, idx0 = score(_module(rule))
    flag = "  <- BREAKS THE CONTRACT BOARD" if idx0 else ""
    print(f"{name:48s} physics {total:4d}   idx0 {idx0}{flag}")
for name, rule in SPEND_VARIANTS.items():
    shape = FIRST if "FIRST" in name else SPEND
    total, idx0 = score(_module(rule, shape))
    flag = "  <- BREAKS THE CONTRACT BOARD" if idx0 else ""
    print(f"{name:48s} physics {total:4d}   idx0 {idx0}{flag}")
