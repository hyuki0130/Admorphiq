"""Score candidate FLANK-CHOICE rules on the physics column, adopting nothing.

The residual is lateral: the model spawns on BOTH flanks of a blocked droplet where
the engine is asymmetric. These variants each pick a side by an observable property
of the flank, and are scored exactly as the five reach rules were. Not a reach sweep
— the reach is untouched and every variant keeps it."""
import json, sys, types
from pathlib import Path
sys.path.insert(0, "scripts/rounds/R98")
from rule_bench import _board, _union_board, _captures

SRC = Path("src/admorphiq/hypothesis_select/propagate_flow.py").read_text()
BASE = """                for i, f in enumerate(targets):
                    if table.piece_direction == "outward_turned":
                        direction = (0, -1) if i == 0 else (0, 1)
                    else:
                        direction = (dr, dc)
                    if 0 <= walked >= WALK_REACH:
                        continue  # the walk along this piece is spent
"""
GUARD = BASE + """                    if _VARIANT(board, f, (dr, dc), wall):
                        continue
"""

VARIANTS = {
    "baseline (both flanks)": None,
    "only the flank that is SUPPORTED (cannot fall)":
        lambda board, f, d, wall: _free(board, (f[0] + d[0], f[1] + d[1]), wall),
    "only the flank that can FALL":
        lambda board, f, d, wall: not _free(board, (f[0] + d[0], f[1] + d[1]), wall),
    "not onto a flank standing over a piece":
        lambda board, f, d, wall: (f[0] + d[0], f[1] + d[1]) in board.piece_cells,
}


def _free(board, cell, wall):
    r, c = cell
    if not (0 <= r < board.size and 0 <= c < board.size):
        return False
    return (cell not in board.piece_cells and cell not in board.absorber_cells
            and cell not in board.hazard_cells and cell not in wall
            and board.sink_of(cell) is None)


def _module(rule):
    src = SRC if rule is None else SRC.replace(BASE, GUARD)
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
