"""CENSUS — is a bp35 kind that KILLS distinguishable, in the frame, from one that does not?

⛔ A census, not a classifier. bp35's whole remaining headroom is exploratory deaths on boards it
ALREADY clears (L2 = 8+34 spike deaths before a 43-action clear against a human 48; L5 = 14+14
before a 30 against 33 — the winning attempt beats the human both times), worth 0.2220 -> 0.3304,
+0.0043 on the 25-game mean. That is only reachable if lethality is READABLE BEFORE CONTACT. If it
is not, the headroom is unreachable by perception and that is equally worth knowing.

Ground truth is the engine's own: a kind kills iff landing on it sets `landed_on_spike`, which is
the tags `ubhhgljbnpu` / `hzusueifitk`. Everything else drawn on the board is safe to land on.

Two questions, answered separately because they can disagree:

  1. TABLE — over the kinds actually PRESENT on each board, is the lethal colour set disjoint from
     the safe one? Reported as the exclusive colours, with counts, per board.
  2. FRAME — do those distinguishing colours actually survive into the rendered frame, and where?
     A colour that only exists in the sprite table is not readable. Reported as pixel counts and
     the rows they occupy, so an edge-pinned HUD row can be told from board content.

⛔ Prints counts, never a verdict inferred from one board.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, "src")

SPIKES = {"ubhhgljbnpu", "hzusueifitk"}


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    spec = importlib.util.spec_from_file_location(
        "bp35mod", root / "environment_files/bp35/0a0ad940/bp35.py")
    m = importlib.util.module_from_spec(spec)
    sys.modules["bp35mod"] = m
    spec.loader.exec_module(m)

    simspec = importlib.util.spec_from_file_location(
        "bp35sim", Path(__file__).resolve().parent / "_bp35_sim.py")
    sim = importlib.util.module_from_spec(simspec)
    simspec.loader.exec_module(sim)

    table = m.ymmwcccrhb

    # ⛔ Use the engine's OWN rasteriser, not a re-read of the art strings. `ieikpxxuml()` is
    # what actually gets drawn (-1 where the sprite paints nothing), so the census counts the
    # pixels the board shows rather than a second interpretation of the same table. The first
    # version of this probe pulled the fields off `vars(spr)`, which is empty on a `__slots__`
    # class — every kind was silently skipped and the report came back with zero kinds and empty
    # colour sets on all six boards, which reads exactly like a clean negative.
    def raster(kind: str):
        return table[kind].ieikpxxuml()

    per_board = []
    for lvl in range(1, 7):
        scene, s = sim.make_level(m, lvl)
        present = Counter()
        for names in s.cells.values():
            for n in names:
                present[n] += 1
        lethal_cols: Counter = Counter()
        safe_cols: Counter = Counter()
        kinds = {"lethal": [], "safe": []}
        skipped = []
        for kind, n_cells in present.items():
            if kind not in table:
                skipped.append(kind)
                continue
            arr = raster(kind)
            cols = Counter()
            for v in arr.ravel().tolist():
                if v >= 0:
                    cols[int(v)] += 1
            bucket = "lethal" if kind in SPIKES else "safe"
            kinds[bucket].append({"kind": kind, "cells": n_cells,
                                  "colours": sorted(cols)})
            (lethal_cols if bucket == "lethal" else safe_cols).update(cols)
        excl_lethal = sorted(set(lethal_cols) - set(safe_cols))
        excl_safe = sorted(set(safe_cols) - set(lethal_cols))

        frame = scene.srlqyenmue()
        rows_of = {}
        for c in excl_lethal:
            ys = sorted({int(y) for y, x in zip(*(frame == c).nonzero())})
            rows_of[str(c)] = {"pixels": int((frame == c).sum()),
                               "rows": ys[:12], "n_rows": len(ys)}
        per_board.append({
            "board": lvl,
            "kinds_not_in_table": skipped,
            "n_lethal_kinds": len(kinds["lethal"]),
            "lethal_kinds": kinds["lethal"],
            "n_safe_kinds": len(kinds["safe"]),
            "safe_kinds": kinds["safe"],
            "lethal_colours": sorted(lethal_cols),
            "safe_colours": sorted(safe_cols),
            "colours_ONLY_on_lethal": excl_lethal,
            "colours_only_on_safe": excl_safe,
            "in_frame": rows_of,
        })

    print(json.dumps({"boards": per_board}, default=int))


if __name__ == "__main__":
    main()
