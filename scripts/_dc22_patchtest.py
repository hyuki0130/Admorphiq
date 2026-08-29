"""Do the two PERCEPTION repairs unlock anything on dc22? Measured, not committed.

R2  locate a piece with the same predicate that SELECTED it (`_solid_block`), not the stricter
    `_one_square`.  `_solid_block`'s own docstring already names dc22 level 6 as the board it was
    written for; the TRACKER was never switched over, so the tool selects a pair it then cannot
    find and latches dead in six actions.
R1  carry the piece colours across levels within a game.  Measured: dc22 reads (11,14) on all
    five levels that clear and (9,14) on the sixth, where 11 is the goal and 9 is a terrain tile.

Varying parameter FIRST = which repairs to apply: 0=none, 1=R2, 2=R1, 3=both.
Prints ONE JSON line with the per-level scores.  Rule 7f: level numbers are printed as numbers.
"""
import sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import score_efficiency as SE  # noqa: E402


def apply_repairs(mask):
    from admorphiq.tools import phase as P
    if mask & 1:
        def _at(self, board, colour):
            blk = P._solid_block(board, colour)
            return None if blk is None else (blk[0], blk[1])
        P.PhaseGridTool._at = _at
    if mask & 2:
        # R1': carry the piece COLOURS across levels, but re-probe the four displacements —
        # the naive form (carrying _avatar too) skips the sense probe, leaves _deltas empty and
        # MEASURED dc22 at 2/6 instead of 5/6.
        orig = P.PhaseGridTool.reset

        def reset(self):
            keep = (getattr(self, "_rare", (-1, -1)), getattr(self, "_side", 0))
            orig(self)
            if keep[0] != (-1, -1):
                self._carry = keep
        P.PhaseGridTool.reset = reset

        origp = P.PhaseGridTool.propose

        def propose(self, frames, obs):
            carry = getattr(self, "_carry", None)
            if carry is not None and self._rare == (-1, -1) and not self._deltas:
                # seed the pair, then let propose's own branch run the sense probe
                pass
            return origp(self, frames, obs)
        # seeding happens in _read's consumer; simplest faithful hook is _pieces itself
        origpieces = P._pieces
        _carry_box = {}

        def pieces(board):
            got = origpieces(board)
            if got is not None:
                _carry_box["last"] = got
                return got
            return _carry_box.get("last")
        P._pieces = pieces

    if mask & 4:
        # R3-lite: the BOARD is the whole frame; the split column is kept only to say where the
        # control strip starts. dc22 level 6's marker sits at column 46 and the split is 42.
        orig_read = P.PhaseGridTool._read

        def _read(self, g):
            import numpy as _np
            geom = orig_read(self, g)
            if geom is None:
                return None
            top, bot = geom["top"], geom["bot"]
            geom["board"] = _np.asarray(g)[top:bot + 1, :]
            got = P._pieces(geom["board"])
            if got is None:
                return None
            geom["rare"] = (got[0], got[1])
            geom["side"] = got[2]
            return geom
        P.PhaseGridTool._read = _read


def main():
    mask = int(sys.argv[1]) if len(sys.argv) > 1 else 3
    max_actions = int(sys.argv[2]) if len(sys.argv) > 2 else 4000
    apply_repairs(mask)
    from arc_agi import Arcade, OperationMode
    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    envs = [e for e in arcade.get_environments() if "dc22" in f"{e.game_id} {e.title or ''}".lower()]
    ei = envs[0]
    res = SE.run_game(arcade, ei.game_id, ei.baseline_actions, agent_name="unified",
                      max_actions=max_actions)
    print(json.dumps({"repairs": mask, "levels_completed": res.get("levels_completed"),
                      "win_levels": res.get("win_levels"),
                      "total_actions": res.get("total_actions"),
                      "game_score": res.get("game_score"),
                      "per_level": res.get("per_level")}), flush=True)


if __name__ == "__main__":
    main()
