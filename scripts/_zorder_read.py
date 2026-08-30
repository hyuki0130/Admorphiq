"""WHICH READ consumes the buried object? Attribute g50t's and tu93's zeros to a line.

Why this probe exists
---------------------
Rule 7ck: g50t and tu93 fall 1.0000 -> 0.0000 under the paint-order arm.
`scripts/_zorder_tape.py`: the mutation is RENDER-ONLY on both — each replays its own tape to
the same levels in the same per-level action counts — so the zeros are the tools'.
`scripts/_zorder_who.py`: tu93 buries its avatar and its goal under the board sprite on EVERY
level; g50t buries nothing on the authored boards, so its burial happens only during play.
`scripts/rounds/R101VISCENSUS/fallback_arm.jsonl`: g50t is played 296/296 actions by
`CloneWalkTool`, tu93 187/187 by `LatticeMazeTool`.

⛔ WHAT IS STILL MISSING IS THE LINE, and there are two very different candidates that a score
cannot separate: the tool's `detect` may DECLINE the mutated board (the harness then never
picks it, and the loss is a routing failure), or `detect` may still claim it and the tool go
blind inside `propose` (a perception failure). This runs both games clean and mutated with
every registered tool's `detect`/`propose` counted, and — for tu93 — `lattice_maze`'s own
board parse and `_locate` instrumented, since `_locate` is the site rule 7cl censused and
7cn showed is the ONLY one repaired by dead reckoning.

Both controls
-------------
POSITIVE — the clean arm must reproduce the game's banked R101SHIPPED score and show its owner
tool proposing on every action (g50t 296, tu93 187). An instrument that cannot see the tool
working has measured nothing.
NEGATIVE — under `zshuf00`, the identity drawn through the same code path, every count must
equal the clean arm's.

    bash scripts/pfan.sh zread scripts/_zorder_read.py 6 "" 6     # arm -> (game, mutation)
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT / "src"))
sys.path.insert(0, str(_ROOT / "scripts"))

BUDGET = 4000
GAMES = ["g50t", "tu93"]
ARMS = ["clean", "zshuf00", "zrevall"]


def main() -> None:
    import score_efficiency as se
    from arc_agi import Arcade, OperationMode

    from admorphiq.harness import registry
    from admorphiq.tools import lattice_maze as lm
    from admorphiq.zorder_mutation import ZOrderPatch, build

    arm = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    title = GAMES[(arm - 1) // len(ARMS) % len(GAMES)]
    mutation = ARMS[(arm - 1) % len(ARMS)]

    det: dict[str, dict] = {}
    prop: dict[str, int] = {}

    def wrap(cls: type) -> None:
        if cls.__dict__.get("_zr_wrapped"):
            return
        nm, od, op = cls.__name__, cls.detect, cls.propose

        def detect(self, frames, obs):  # noqa: ANN001
            v = od(self, frames, obs)
            d = det.setdefault(nm, {"calls": 0, "max": 0.0, "nonzero": 0})
            d["calls"] += 1
            d["max"] = max(d["max"], float(v))
            d["nonzero"] += 1 if float(v) > 0 else 0
            return v

        def propose(self, frames, obs):  # noqa: ANN001
            prop[nm] = prop.get(nm, 0) + 1
            return op(self, frames, obs)

        cls.detect, cls.propose, cls._zr_wrapped = detect, propose, True

    for t in registry.default_tools():
        wrap(type(t))

    # -- lattice_maze's own reads, the site 7cl censused and 7cn found repaired ----------
    lat = {"parse_calls": 0, "parse_none": 0, "pieces_max": 0,
           "locate_calls": 0, "locate_none": 0, "body_none": 0}
    orig_parse = lm.parse_board

    def parse_board(*a, **k):  # noqa: ANN002, ANN003
        b = orig_parse(*a, **k)
        lat["parse_calls"] += 1
        if b is None:
            lat["parse_none"] += 1
        else:
            lat["pieces_max"] = max(lat["pieces_max"], len(getattr(b, "pieces", {}) or {}))
        return b

    lm.parse_board = parse_board

    orig_locate = lm.LatticeMazeTool._locate

    def locate(self, board):  # noqa: ANN001, ANN202
        lat["locate_calls"] += 1
        if getattr(self, "_body", None) is None:
            lat["body_none"] += 1
        out = orig_locate(self, board)
        if out is None:
            lat["locate_none"] += 1
        return out

    lm.LatticeMazeTool._locate = locate

    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    envs = [e for e in arcade.get_environments()
            if title in f"{e.game_id} {e.title or ''}".lower()]
    if not envs:
        print(json.dumps({"game": title, "error": "no such env"}))
        return
    info = envs[0]

    patch = ZOrderPatch(build(mutation)).install() if mutation != "clean" else None
    try:
        res = se.run_game(arcade, info.game_id, info.baseline_actions,
                          agent_name="unified", max_actions=BUDGET)
    finally:
        rep = patch.close() if patch is not None else {}

    banked = _ROOT / "scripts" / "rounds" / "R101SHIPPED" / "games" / f"{title}.json"
    ref = round(float(json.loads(banked.read_text())["total_score"]), 6) \
        if banked.exists() else None
    print(json.dumps({
        "game": title,
        "mutation": mutation,
        "banked": ref,
        "score": round(float(res.get("game_score", 0.0)), 6),
        "levels": res.get("levels_completed"),
        "per_level": [p.get("agent_actions") for p in res.get("per_level", [])],
        "proposed": prop,
        "detect": {k: v for k, v in det.items() if v["nonzero"]},
        "lattice": lat if title == "tu93" else None,
        "buried_max": rep.get("buried_max"),
        "cells_changed": rep.get("cells_changed"),
        "frames_changed": rep.get("frames_changed"),
    }, sort_keys=True))


if __name__ == "__main__":
    main()
