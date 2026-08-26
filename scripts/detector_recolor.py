"""Do the detectors survive a COLOUR PERMUTATION of their own board?

Purpose: four ports (ft09, ls20, sb26, tr87) have no archived second version, so
`detector_transfer.py` cannot ask whether they read the mechanic or this board. Recolouring is
the closest available stand-in: version hashes differ in exactly this kind of surface detail,
and a detector that reads STRUCTURE should not care which colour index carries it.

⚠️ It is a stand-in, not the real question. A real variant changes layout and internals too;
this changes only the palette. Surviving it is necessary, not sufficient.

Expected feedback: per detector, whether it still fires when every non-background colour index
is permuted. A detector that stops firing was keying on a colour VALUE.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from arc_agi import Arcade, OperationMode  # noqa: E402

from admorphiq.adapters25 import discover_adapters  # noqa: E402
from admorphiq.adapters25.base import canonical_layer, most_common_color  # noqa: E402


class _Recoloured:
    """A frame whose colour indices are permuted, everything else untouched."""

    def __init__(self, frame: object, shift: int) -> None:
        grid = canonical_layer(frame)
        background = most_common_color(grid)
        used = sorted({v for row in grid for v in row if v != background})
        # A cyclic shift within the used palette: a bijection, so structure is preserved
        # exactly and only the labels move.
        mapping = {c: used[(i + shift) % len(used)] for i, c in enumerate(used)}
        self.frame = [[[mapping.get(v, v) for v in row] for row in grid]]
        self.available_actions = getattr(frame, "available_actions", [])
        self.state = getattr(frame, "state", None)


def main() -> int:
    names = sys.argv[1:] or ["ft09", "ls20", "sb26", "tr87"]
    adapters = discover_adapters()
    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    failed = 0
    for name in names:
        cls = adapters.get(name)
        if cls is None:
            print(f"{name}: no such adapter")
            failed += 1
            continue
        for env_info in arcade.get_environments():
            if name not in (env_info.title or env_info.game_id).lower():
                continue
            env = arcade.make(env_info.game_id)
            if env is None or env.observation_space is None:
                break
            frame = env.observation_space
            plain = cls.detect(frame)
            shifted = [cls.detect(_Recoloured(frame, s)) for s in (1, 2, 3)]
            ok = plain and all(shifted)
            failed += not ok
            print(f"{name}: own board {plain}, recoloured {shifted} "
                  f"{'OK' if ok else '⛔ keys on a colour VALUE'}")
            break
    print("\n" + ("PASS — every detector reads structure, not palette"
                  if not failed else f"⛔ {failed} detector(s) depend on colour values"))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
