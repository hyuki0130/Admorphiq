"""Is g50t's and tu93's 0.0000 the WORST case or the EXPECTED case?

Why this probe exists
---------------------
Rule 7ck ran the paint-order arm as a whole-list REVERSAL, which `zorder_mutation.py`'s own
`RandomOrder` docstring calls *"the MAXIMUM possible perturbation of paint order"*. Two games
fell from 1.0000 to 0.0000 under it. ⛔ A reversal is not what a re-render is: the
competition's own re-render of s5i5 changed the picture by ONE CELL.

`scripts/_zorder_tape.py` has already settled that the mutation is RENDER-ONLY on both games
— each replays its own tape to the same levels in the same per-level action counts — so the
zeros are the tools', not a broken board's. What is unmeasured is whether an ORDINARY
re-serialisation does the same thing, and that is the quantity the 110 private games actually
pose.

This runs the SAMPLED family: `zshufNN`, one fixed uniform re-ordering per seed, which the
module proves is simultaneously the conservative same-layer arm on the 22 layer-sorting games
and the true paint order on the three that never sort.

Both controls
-------------
POSITIVE — `zrevall` must reproduce 7ck's banked 0.0000 for the game. An arm that cannot
score its own known answer has measured nothing.
NEGATIVE — `zshuf00` is the IDENTITY by construction, drawn through the SAME code path as
every sample, and must return the game's banked R101SHIPPED score exactly.

    bash scripts/pfan.sh zexp scripts/_zorder_expect.py 18 "" 9    # arm -> (game, seed)
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
# seed 0 is the identity control; zrevall is the positive control; 1..7 are the samples.
ARMS = ["zshuf00", "zrevall", "zrev", "zrot", "zrotall", "zshuf01",
        "zshuf02", "zshuf03", "zshuf04", "zshuf05", "zshuf06", "zshuf07"]


def main() -> None:
    import score_efficiency as se
    from arc_agi import Arcade, OperationMode

    from admorphiq.zorder_mutation import ZOrderPatch, build

    arm = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    title = GAMES[(arm - 1) // len(ARMS) % len(GAMES)]
    mutation = ARMS[(arm - 1) % len(ARMS)]

    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    envs = [e for e in arcade.get_environments()
            if title in f"{e.game_id} {e.title or ''}".lower()]
    if not envs:
        print(json.dumps({"game": title, "error": "no such env"}))
        return
    info = envs[0]

    mut = build(mutation)
    # ⛔ COUNT WHETHER THE PERMUTATION EVER ACTUALLY REORDERS ANYTHING. `cells_changed == 0`
    # is ambiguous between "the re-ordering moved no pixel" and "no re-ordering happened",
    # and those are a finding and an instrument failure respectively. g50t reported 0 cells
    # on seven seeds while its AUTHORED board demonstrably moves 39 cells under a reversal,
    # which is exactly the contradiction that has to be resolved before either number is
    # quoted (rule 7z: the instrument that lies toward "nothing here" is the expensive one).
    orig_permute = mut.permute
    seen = {"calls": 0, "reordered": 0, "max_len": 0}

    def permute(sprites):  # noqa: ANN001, ANN202
        out = orig_permute(sprites)
        seen["calls"] += 1
        seen["max_len"] = max(seen["max_len"], len(sprites))
        if [id(s) for s in out] != [id(s) for s in sprites]:
            seen["reordered"] += 1
        return out

    mut.permute = permute
    patch = ZOrderPatch(mut).install()
    try:
        res = se.run_game(arcade, info.game_id, info.baseline_actions,
                          agent_name="unified", max_actions=BUDGET)
    finally:
        rep = patch.close()

    banked = _ROOT / "scripts" / "rounds" / "R101SHIPPED" / "games" / f"{title}.json"
    ref = None
    if banked.exists():
        ref = round(float(json.loads(banked.read_text())["total_score"]), 6)
    got = round(float(res.get("game_score", 0.0)), 6)
    out = {
        "game": title,
        "mutation": mutation,
        "banked": ref,
        "score": got,
        "levels": res.get("levels_completed"),
        "win_levels": res.get("win_levels"),
        "per_level": [p.get("agent_actions") for p in res.get("per_level", [])],
        "permute": seen,
    }
    if isinstance(rep, dict):
        for k in ("frames_seen", "frames_changed", "cells_changed", "buried_max",
                  "max_cells_changed_in_a_frame", "violations"):
            if k in rep:
                out[k] = rep[k]
    print(json.dumps(out, sort_keys=True))


if __name__ == "__main__":
    main()
