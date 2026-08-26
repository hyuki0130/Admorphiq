"""Does `induce.discover_lattice` find a board's responding cells, and on what pitch?

Purpose: T-D's first two steps are "find where the board responds" and "measure what each
response does". This runs them live on one game and reports what was recovered, so the tool's
premise is checked per game rather than assumed from ft09.

Expected feedback: responders found, the pitch inferred from their own coordinates, whether every
response flips the same number of cells (a uniform operator, i.e. a parity rule) or not, and the
probe cost. A game with zero responders is not class D on this evidence, whatever its wiki says.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from arc_agi import Arcade, OperationMode  # noqa: E402
from arcengine import GameAction  # noqa: E402

from admorphiq.adapters25.base import available_action_ids, canonical_layer  # noqa: E402
from admorphiq.tools.induce import discover_lattice, footprint_signature  # noqa: E402


def main() -> int:
    game = sys.argv[1]
    budget = int(sys.argv[2]) if len(sys.argv) > 2 else 120
    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    info = next((i for i in arcade.get_environments()
                 if (i.title or i.game_id).lower().startswith(game)), None)
    if info is None:
        print(f"{game}: no such game")
        return 1
    env = arcade.make(info.game_id)
    obs = env.reset()
    _simple, has_click = available_action_ids(obs)
    if not has_click:
        print(f"{game:6s} no click action — discover_lattice does not apply")
        return 0
    size = len(canonical_layer(obs))
    state = {"obs": obs}

    def probe(cell):
        before = canonical_layer(state["obs"])
        state["obs"] = env.step(GameAction.ACTION6, data={"x": cell[1], "y": cell[0]})
        return before, canonical_layer(state["obs"])

    out = discover_lattice(probe, size, budget=budget)
    sig = footprint_signature(out["live"])
    print(f"{game:6s} probes={out['probes']:3d} responders={sig['responders']:3d} "
          f"pitch={out['stride']} uniform={sig['uniform']} "
          f"footprints={sig['footprint_sizes'][:4]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
