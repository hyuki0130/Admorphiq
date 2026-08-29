"""Are bp35's two lethal kinds the SAME hazard drawn upside down — and does crag see them as one?

The census showed colour 11 is painted by every lethal kind and no safe kind. This asks the
follow-up that decides whether one death teaches the tool about the other: `ubhhgljbnpu` and
`hzusueifitk` are declared with the same art, one reversed, and the engine gives BOTH the metadata
name `ubhhgljbnpu`. Board 5 carries both (7 cells and 6) and costs exactly two spike deaths.

Prints the two rasters, whether one is the vertical mirror of the other, and the signature crag
computes for each — because if the signatures differ, dying on one teaches nothing about the other
and the second death is structural rather than exploratory.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

sys.path.insert(0, "src")


def main() -> None:
    import numpy as np

    from admorphiq.tools.crag import _sig

    root = Path(__file__).resolve().parents[1]
    spec = importlib.util.spec_from_file_location(
        "bp35mod", root / "environment_files/bp35/0a0ad940/bp35.py")
    m = importlib.util.module_from_spec(spec)
    sys.modules["bp35mod"] = m
    spec.loader.exec_module(m)
    table = m.ymmwcccrhb

    a = table["ubhhgljbnpu"].ieikpxxuml()
    b = table["hzusueifitk"].ieikpxxuml()
    out = {
        "a_shape": list(a.shape), "b_shape": list(b.shape),
        "identical": bool(a.shape == b.shape and (a == b).all()),
        "b_is_vertical_mirror_of_a": bool(a.shape == b.shape and (a == b[::-1]).all()),
        "engine_metadata_name": [table["ubhhgljbnpu"].name, table["hzusueifitk"].name],
        "a_rows": [[int(v) for v in row] for row in a],
        "b_rows": [[int(v) for v in row] for row in b],
    }
    # crag reads a tile's CORE. Take the same interior both ways so the comparison is fair.
    for name, arr in (("a", a), ("b", b)):
        core = arr[1:-1, 1:-1]
        out[f"sig_{name}"] = str(_sig(np.asarray(core)))
    out["signatures_agree"] = out["sig_a"] == out["sig_b"]
    print(json.dumps(out))


if __name__ == "__main__":
    main()
