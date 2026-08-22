"""R98 near-OOD screen — Codex binding correction 7.

Purpose
-------
A control only counts as near-OOD if an agent could plausibly SELECT this family
from what it observes and only then be proven wrong by the mechanics. A game that
is rejected on sight — no commit-like action, no scripted multi-tick consequence,
no source/target structure — is not near-OOD, it is unrelated.

The full certification needs the grounding service, which does not exist yet, so
this is the OBSERVABLE PRE-SCREEN it must pass first. It measures the family's
structural tell across candidate games: does some single action trigger a scripted
consequence that the engine exposes as MANY frame layers at once? That is the
signature that would make an agent reach for a place-then-propagate model.

Expected feedback
-----------------
Games ranked by their maximum single-action layer burst. A candidate with a burst
comparable to the oracle's is structurally confusable and survives the screen; a
candidate whose every action returns a single layer is rejected as unrelated and
must not be labelled near-OOD.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from arc_agi import Arcade, OperationMode  # noqa: E402
from arcengine import GameAction  # noqa: E402

CANDIDATES = ["sp80", "re86", "sk48", "ls20", "wa30", "tn36", "cn04", "tu93"]
SIMPLE = [GameAction.ACTION1, GameAction.ACTION2, GameAction.ACTION3,
          GameAction.ACTION4, GameAction.ACTION5, GameAction.ACTION7]


def probe(arcade, game_id: str) -> dict:
    env = arcade.make(game_id)
    obs = env.step(GameAction.RESET)
    bursts: dict[str, int] = {}

    def record(name: str, frame) -> None:
        bursts[name] = max(bursts.get(name, 0), len(frame))

    # two passes over the simple actions: a commit-like action often only fires
    # once the board has been armed by an earlier press
    for _ in range(2):
        for action in SIMPLE:
            try:
                obs = env.step(action)
            except Exception:
                continue
            record(action.name, obs.frame)

    # clicks matter too — a cascade can be click-triggered rather than
    # commit-triggered, and screening only the simple actions would miss it
    for gy in range(2, 64, 12):
        for gx in range(2, 64, 12):
            try:
                obs = env.step(GameAction.ACTION6, data={"x": gx, "y": gy})
            except Exception:
                continue
            record("ACTION6", obs.frame)

    return {"game_id": game_id, "bursts": bursts, "max": max(bursts.values(), default=0)}


def main() -> int:
    arcade = Arcade(
        operation_mode=OperationMode.OFFLINE,
        environments_dir=os.environ.get("ARC_ENVIRONMENTS_DIR") or None,
    )
    envs = {e.game_id.split("-")[0]: e.game_id for e in arcade.get_environments()}

    rows = []
    for name in CANDIDATES:
        gid = envs.get(name)
        if gid is None:
            rows.append({"game_id": name, "bursts": {}, "max": 0, "missing": True})
            continue
        rows.append(probe(arcade, gid))

    rows.sort(key=lambda r: -r["max"])
    oracle = next((r for r in rows if r["game_id"].startswith("sp80")), None)
    ref = oracle["max"] if oracle else 0

    print(f"reference (the oracle family) max single-action layer burst: {ref}\n")
    print("candidate            max burst   per-action bursts")
    for r in rows:
        if r.get("missing"):
            print(f"  {r['game_id']:<18} (env not available)")
            continue
        detail = " ".join(f"{k}:{v}" for k, v in sorted(r["bursts"].items()))
        print(f"  {r['game_id']:<18} {r['max']:>6}      {detail}")

    survivors = [r for r in rows
                 if not r.get("missing")
                 and not r["game_id"].startswith("sp80")
                 and r["max"] >= 3]
    print()
    if survivors:
        print("[near-OOD screen] SURVIVES: "
              + ", ".join(f"{r['game_id']} (burst {r['max']})" for r in survivors))
        print("  These produce a scripted multi-tick consequence from one action, so "
              "an agent could plausibly reach for this family and be wrong on the "
              "mechanics — the near-OOD property. Full certification still requires "
              "the grounding service.")
    else:
        print("[near-OOD screen] NO SURVIVOR — every candidate answers each action "
              "with a single frame, so none is structurally confusable with a "
              "place-then-propagate family. Labelling any of them near-OOD would be "
              "false; the control must be reconsidered.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
