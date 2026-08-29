"""lf52 level 6 — WHERE in pegjump's pipeline do four of six pads go missing?

⛔ THE MEASUREMENT THIS FOLLOWS. `scripts/_lf52_fate.py` proved level 6 becomes unwinnable at
level-6 action 124 on a `pegjump` capture, and `scripts/_lf52_believe.py` measured that at action
122 the ENGINE has 6 pads and 3 carts while `pegjump`'s model holds 2 pieces and 2 carriers, with
0 of 10 model reads agreeing. Jumping one of two pieces over the other leaves one, so `plan_moves`
returns it with `solved=True` — a declared LEVEL WIN over a two-cell window. Porting railpeg's
survivability guard was measured INERT (refusals 0): a guard on capture ROUTES cannot see a plan
claiming to be a SOLUTION. So the remaining distance is PERCEPTION.

⛔ AND PERCEPTION HAS FOUR DISTINCT PLACES TO LOSE A PAD, which want four different repairs. This
probe separates them by instrumenting the pipeline itself rather than reasoning about it:

  A  CAMERA        the pad is not on the screen at all. `read_board` cannot invent it; only the
                   persistent model can carry it, so the repair is in the model's memory.
  B  ANCHOR        the pad IS on screen but `_anchors` never proposes its square — a shape or a
                   size filter (⚠️ this game renders its legal-move markers as FOUR TWO-PIXEL
                   BLOBS, so a minimum-size filter reads exactly like "there is nothing there").
  C  PHASE         `_anchors` finds it and the lattice phase filter drops it (`on_phase`).
  D  COLOUR        it survives to the cell loop and the socket/piece colour classification
                   refuses it, so it lands as a blocker or as nothing.

  and one more that is not perception at all:

  E  FORGETTING    the model HELD more pads earlier and threw them away — `_adopt` rebuilds the
                   model from a single frame after six unplaceable frames, and `_install` trusts
                   the frame inside the window.

Per `read_board` call the counts at every stage are recorded, so the pad that is lost is attributed
to the stage that lost it. Engine truth (pads, carts, camera) is read alongside at the same action.

⛔ `detect` is never called off-schedule (rule 7ah): `read_board` and `_adopt` are wrapped where the
tool itself calls them, and nothing here steers the run.

CONTROLS (rule 7ai)
  NEGATIVE  per-level actions must be [8, 52, 60, 64, 139] and the total 823. A different number
            means this probe is describing a different run (rule 7aj.2).
  POSITIVE  `reads` > 0 on level 6 — the instrument must actually see the tool read a board.

Expected feedback:
  `discs_in_frame` == `pads_engine` while `board_pieces` < that  -> B/C/D, a filter defect, and the
            stage counts say which one.
  `discs_in_frame` < `pads_engine` throughout                    -> A, the camera; the pads are off
            screen and the repair is the model's memory, not the reader.
  `model_pieces_peak` >= `pads_engine` at any point              -> E, the model DID know and threw
            it away; `adopts` and `installs` say where.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

BANKED = [8, 52, 60, 64, 139]
BANKED_TOTAL = 823

_F = importlib.util.spec_from_file_location(
    "lf52_fate", Path(__file__).resolve().parent / "_lf52_fate.py")
FATE = importlib.util.module_from_spec(_F)
_F.loader.exec_module(FATE)


def _stages(pj, g):
    """Every stage count `read_board` passes through, recomputed on the same frame it was given."""
    import numpy as np
    anchors = pj._anchors(g)
    discs = [a for a in anchors if a[3] >= 0]
    out = {"anchors": len(anchors), "anchor_discs": len(discs)}
    lat = pj._lattice(anchors)
    if lat is None:
        out["lattice"] = None
        return out
    pitch, ph_y, ph_x = lat
    out["lattice"] = [pitch, ph_y, ph_x]
    on_phase = [a for a in anchors if a[0] % pitch == ph_y and a[1] % pitch == ph_x]
    out["on_phase"] = len(on_phase)
    out["on_phase_discs"] = len([a for a in on_phase if a[3] >= 0])
    out["off_phase_discs"] = len([a for a in discs if a not in on_phase])
    socket_counts = Counter(a[2] for a in on_phase)
    piece_colours = {a[3] for a in on_phase if a[3] >= 0} - set(socket_counts)
    out["socket_colours"] = sorted(int(c) for c in socket_counts)
    out["piece_colours"] = sorted(int(c) for c in piece_colours)
    # A disc whose piece colour is ALSO a socket colour is refused by the classifier (stage D).
    out["disc_colour_refused"] = len([a for a in on_phase
                                      if a[3] >= 0 and a[3] not in piece_colours])
    out["shape"] = list(np.asarray(g).shape)
    return out


def main() -> None:
    from arc_agi import Arcade, OperationMode

    from admorphiq.tools import pegjump as pj

    _spec = importlib.util.spec_from_file_location(
        "score_eff", Path(__file__).resolve().parent / "score_efficiency.py")
    se = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(se)

    view: dict = {"reads": [], "adopts": 0, "installs": 0}
    raw_read = pj.read_board
    raw_adopt = pj.PegJumpTool._adopt
    raw_install = pj.PegJumpTool._install

    def wrapped_read(g):
        board = raw_read(g)
        rec = _stages(pj, g)
        if board is None:
            rec["board"] = None
        else:
            rec["board"] = {
                "pieces": len(board.pieces), "sockets": len(board.sockets),
                "carriers": len(board.carriers), "rails": len(board.rails),
                "blockers": len(board.blockers), "window": len(board.window),
                "moving": int(board.moving), "pitch": int(board.pitch),
            }
        view["reads"].append(rec)
        return board

    def wrapped_adopt(self, board):
        view["adopts"] += 1
        return raw_adopt(self, board)

    def wrapped_install(self, m, seen):
        before = len(m.pieces)
        raw_install(self, m, seen)
        view["installs"] += 1
        view.setdefault("install_deltas", []).append([before, len(m.pieces)])

    pj.read_board = wrapped_read
    pj.PegJumpTool._board.__globals__["read_board"] = wrapped_read
    pj.PegJumpTool._adopt = wrapped_adopt
    pj.PegJumpTool._install = wrapped_install

    model_view: dict = {"pieces": None, "carriers": None, "window": None, "sockets": None}
    raw_plan = pj.PegJumpTool._ensure_plan

    def wrapped_plan(self, m):
        score = raw_plan(self, m)
        model_view["pieces"] = sorted(list(c) for c in m.pieces)
        model_view["carriers"] = len(m.carriers)
        model_view["window"] = len(m.window)
        model_view["sockets"] = len(m.sockets)
        return score

    pj.PegJumpTool._ensure_plan = wrapped_plan

    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    info = next(i for i in arcade.get_environments()
                if (i.title or i.game_id).lower().startswith("lf52"))
    held: dict = {}
    real_make = arcade.make

    def make(gid, *a, **k):
        env = real_make(gid, *a, **k)
        held["env"] = env
        return env

    arcade.make = make
    rows: list[dict] = []
    real_factory = se._make_agent

    def factory():
        inner = real_factory("unified", game_id=info.game_id)

        class Watch:
            restart_on_game_over = getattr(inner, "restart_on_game_over", False)

            def is_done(self, frames, obs):
                return inner.is_done(frames, obs)

            def choose_action(self, frames, obs):
                o = FATE._oracle(held.get("env"))
                loop = FATE._loop_of(inner)
                view["reads"] = []
                model_view["pieces"] = None
                a0, i0 = view["adopts"], view["installs"]
                act = inner.choose_action(frames, obs)
                if o is not None:
                    o["tool"] = None if loop is None else loop._current
                    o["reads"] = list(view["reads"])
                    o["mp"] = model_view["pieces"]
                    o["mc"] = model_view["carriers"]
                    o["mw"] = model_view["window"]
                    o["ms"] = model_view["sockets"]
                    o["adopted"] = view["adopts"] - a0
                    o["installed"] = view["installs"] - i0
                    rows.append(o)
                return act

        return Watch()

    res = se.run_game(arcade, info.game_id, info.baseline_actions,
                      agent_name="unified", max_actions=4000, adapter_factory=factory)
    per = [p["agent_actions"] for p in res.get("per_level", [])]
    out: dict = {
        "probe": "lf52_pcen",
        "per_level": per,
        "total_actions": int(res.get("total_actions", -1)),
        "game_score": res.get("game_score"),
        "control_neg_ok": per == BANKED and int(res.get("total_actions", -1)) == BANKED_TOTAL,
    }
    six = [r for r in rows if r["lvl"] == 6]
    out["l6_actions"] = len(six)
    out["l6_reads"] = sum(len(r["reads"]) for r in six)
    out["control_pos_ok"] = out["l6_reads"] > 0
    out["adopts_l6"] = sum(r["adopted"] for r in six)
    out["installs_l6"] = sum(r["installed"] for r in six)

    def row(i):
        r = six[i]
        rd = r["reads"][0] if r["reads"] else None
        return {
            "i": i, "tool": r["tool"], "cam": r["cam"],
            "pads_engine": len(r["pads"]), "carts_engine": len(r["carts"]),
            "model_pieces": None if r["mp"] is None else len(r["mp"]),
            "model_carriers": r["mc"], "model_window": r["mw"], "model_sockets": r["ms"],
            "stages": rd,
        }

    out["at_122"] = row(122) if len(six) > 122 else None
    out["at_123"] = row(123) if len(six) > 123 else None
    out["first_10"] = [row(i) for i in range(min(10, len(six)))]
    # The pipeline's own history: what the reader found, action by action.
    disc_hist = []
    for i, r in enumerate(six):
        for rd in r["reads"]:
            disc_hist.append({
                "i": i, "anchor_discs": rd.get("anchor_discs"),
                "on_phase_discs": rd.get("on_phase_discs"),
                "refused": rd.get("disc_colour_refused"),
                "board_pieces": None if rd.get("board") is None else rd["board"]["pieces"],
                "pads": len(r["pads"]),
            })
    out["max_anchor_discs"] = max((d["anchor_discs"] or 0) for d in disc_hist) if disc_hist else 0
    out["max_board_pieces"] = max((d["board_pieces"] or 0) for d in disc_hist) if disc_hist else 0
    mp = [len(r["mp"]) for r in six if r["mp"] is not None]
    out["model_pieces_peak"] = max(mp) if mp else None
    out["model_reads"] = len(mp)
    # Every distinct (pads, anchor_discs, on_phase_discs, refused, board_pieces) shape, with counts.
    shapes = Counter((d["pads"], d["anchor_discs"], d["on_phase_discs"], d["refused"],
                      d["board_pieces"]) for d in disc_hist)
    out["stage_shapes"] = [{"pads": k[0], "anchor_discs": k[1], "on_phase_discs": k[2],
                            "colour_refused": k[3], "board_pieces": k[4], "n": n}
                           for k, n in shapes.most_common(20)]
    print(json.dumps(out))


if __name__ == "__main__":
    main()
