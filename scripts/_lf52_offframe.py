#!/usr/bin/env python3
"""lf52 — at each of `pegjump`'s decisions, how much board is OFF-FRAME, and can any action show it?

⛔ THE QUESTION (the coordinator's, rule 7bq's shape): lf52's tools do not run out of PATIENCE, they
run out of BOARD. `pegjump` retires with a 24-cell map on a 28-column board. So the capability the
game wants is planning on a board WIDER THAN THE FRAME — and before building for that, the board is
asked whether the capability is even exercisable from where the tool stands.

WHAT THE GAME'S OWN SOURCE SAYS (`environment_files/lf52/271a04aa/lf52.py`, dev-time reading; the
TOOL stays frame-only) — on level 6 the camera offset `grid.cdpcbbnfdp` moves in exactly three ways:

  (a) a JUMP landing on cell (7, 6)  while the offset is exactly (5, 5)     -> (-20, 0)
  (b) a cart DRIVE while a plain piece RIDES that cart                      -> (-dx*6, 0)
  (c) a JUMP landing on cell (18, 2) while the offset is exactly (-57, 5)   -> (-44, 0)

So at every decision there is a decidable oracle answer to "could the camera move from here?":
  aboard > 0                                   -> rule (b) is armed, a drive scrolls
  a legal jump lands on the armed script square -> rule (a)/(c) is armed
Neither -> NO action available at this instant opens the board, and the tier that is missing is not
missing at THIS point.

ARMS (by seed). ⚠️ `pegjump`'s real tenure is 19 actions, too few to census, so the patient+hold
levers from `scripts/_lf52_patience.py` (measured to change NO per-level count) buy 378 decisions to
look at. Both the unlevered and the levered arm are run, and the unlevered one is the control.

  pure      no wrapping.               CONTROL: must be [8,52,60,64,139] / 823 (rule 7ai).
  oracle    engine census, no levers.  ALSO must be [8,52,60,64,139] / 823.
  patient   engine census, pegjump never latches `_barren` and is never retired (378 decisions).
  rphold    engine census, railpeg never retired (310 decisions) — the other half of the board.

⛔ MIRRORS `score_efficiency.py:run_game` (rule 7x) by DRIVING it, never re-implementing it.

Usage:  uv run python scripts/_lf52_offframe.py <seed 1..8>
"""
from __future__ import annotations

import importlib.util
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

DIRS = [(0, -1), (1, 0), (0, 1), (-1, 0)]
BANKED = [8, 52, 60, 64, 139]
BANKED_TOTAL = 823
#: The two scripted camera squares and the offsets that arm them (read from the game's source).
SCRIPT = {(5, 5): (7, 6), (-57, 5): (18, 2)}

ARMS = ["pure", "oracle", "oracle", "patient", "patient", "rphold", "pure", "patient"]


def _scene(env):
    g = getattr(env, "_game", None) or getattr(env, "game", None)
    return getattr(g, "ikhhdzfmarl", None) if g is not None else None


def _oracle(env) -> dict | None:
    sc = _scene(env)
    if sc is None:
        return None
    grid = getattr(sc, "hncnfaqaddg", None)
    if grid is None:
        return None
    try:
        pieces = grid.ndtvadsrqf("fozwvlovdui")
        carts = grid.whdmasyorl("hupkpseyuim2")
    except Exception:
        return None
    cartset = {c.chahdtpdoz for c in carts}
    aboard = sum(1 for p in pieces if p.chahdtpdoz in cartset)
    cam = tuple(getattr(grid, "cdpcbbnfdp", (0, 0)))
    legal = boarding = 0
    landings: set = set()
    for p in pieces:
        pos = p.chahdtpdoz
        for d in DIRS:
            try:
                ok = bool(sc.qikmikecdf(pos, d))
            except Exception:
                continue
            if not ok:
                continue
            legal += 1
            land = (pos[0] + 2 * d[0], pos[1] + 2 * d[1])
            landings.add(land)
            if land in cartset:
                boarding += 1
    armed = SCRIPT.get(cam)
    return {
        "lvl": int(getattr(sc, "whtqurkphir", -1)),
        "cam": cam,
        "pieces": len(pieces),
        "carts": len(carts),
        "aboard": aboard,
        "legal": legal,
        "boarding": boarding,
        # ⛔ THE ORACLE ANSWER: can the camera move from HERE, by the engine's own three rules?
        "scroll_by_drive": aboard > 0,
        "scroll_by_jump": bool(armed is not None and armed in landings),
        "armed_square": armed,
        "pcells": sorted(p.chahdtpdoz for p in pieces),
        "cartcells": sorted(cartset),
    }


def main() -> None:
    seed = int(sys.argv[1])
    mode = ARMS[(seed - 1) % len(ARMS)]

    from arc_agi import Arcade, OperationMode

    from admorphiq.tools import pegjump as pj

    _spec = importlib.util.spec_from_file_location(
        "score_eff", Path(__file__).resolve().parent / "score_efficiency.py")
    se = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(se)

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

    # pegjump's own view, sampled where the TOOL itself decides (never by calling detect off-schedule).
    view: dict = {"known": None, "cols": None, "mpieces": None, "score": None}
    raw_plan = pj.PegJumpTool._ensure_plan

    def wrapped_plan(self, m):
        score = raw_plan(self, m)
        known = m.sockets | m.rails | m.blockers | m.carriers
        cols = [c[1] for c in known] or [0]
        view.update(known=len(known), cols=(min(cols), max(cols)),
                    mpieces=len(m.pieces), score=score, barren=self._barren)
        if mode == "patient" and self._barren >= 3:
            self._barren = 2
        return score

    if mode in ("oracle", "patient", "rphold"):
        pj.PegJumpTool._ensure_plan = wrapped_plan

    rows: list[dict] = []
    real_factory = se._make_agent

    def factory():
        inner = real_factory("unified", game_id=info.game_id)
        keep = "pegjump" if mode == "patient" else ("railpeg" if mode == "rphold" else None)

        class Watch:
            restart_on_game_over = getattr(inner, "restart_on_game_over", False)

            def is_done(self, frames, obs):
                return inner.is_done(frames, obs)

            def choose_action(self, frames, obs):
                if keep and getattr(inner, "_current", None) == keep:
                    inner._empty_runs = 0
                o = _oracle(held.get("env"))
                act = inner.choose_action(frames, obs)
                if o is not None and mode != "pure":
                    o["who"] = getattr(inner, "_current", None) or "HARNESS"
                    o["known"] = view["known"]
                    o["cols"] = view["cols"]
                    o["mpieces"] = view["mpieces"]
                    o["lvl_done"] = int(getattr(obs, "levels_completed", -1))
                    rows.append(o)
                return act

        return Watch()

    res = se.run_game(arcade, info.game_id, info.baseline_actions,
                      agent_name="unified", max_actions=4000, adapter_factory=factory)

    per = [p["agent_actions"] for p in res.get("per_level", [])]
    out: dict = {
        "arm": {"mode": mode, "seed": seed},
        "per_level": per,
        "total_actions": int(res.get("total_actions", -1)),
        "game_score": res.get("game_score"),
        "control_ok": per == BANKED and int(res.get("total_actions", -1)) == BANKED_TOTAL,
        "rows": len(rows),
    }

    l6 = [r for r in rows if r["lvl_done"] == 5]
    out["l6_actions"] = len(l6)
    out["l6_tenure"] = dict(Counter(r["who"] for r in l6))
    out["l6_cams"] = sorted({r["cam"] for r in l6}, key=str)
    # POSITIVE control: the oracle must be able to say YES somewhere.
    out["pos_scroll_by_drive_levels"] = sorted({r["lvl_done"] for r in rows if r["scroll_by_drive"]})
    out["pos_scroll_by_jump_levels"] = sorted({r["lvl_done"] for r in rows if r["scroll_by_jump"]})
    out["pos_multi_cam_levels"] = sorted(
        L for L in {r["lvl_done"] for r in rows}
        if len({r["cam"] for r in rows if r["lvl_done"] == L}) > 1)

    per_tool = {}
    for who in sorted({r["who"] for r in l6}):
        rs = [r for r in l6 if r["who"] == who]
        per_tool[who] = {
            "actions": len(rs),
            "cams": len({r["cam"] for r in rs}),
            "aboard_gt0": sum(1 for r in rs if r["aboard"] > 0),
            "boarding_gt0": sum(1 for r in rs if r["boarding"] > 0),
            "scroll_possible": sum(1 for r in rs if r["scroll_by_drive"] or r["scroll_by_jump"]),
            "engine_pieces": sorted({r["pieces"] for r in rs}),
            "model_pieces": sorted({r["mpieces"] for r in rs if r["mpieces"] is not None}),
            "known": sorted({r["known"] for r in rs if r["known"] is not None}),
            "cols": sorted({str(r["cols"]) for r in rs if r["cols"] is not None}),
            "legal_range": [min(r["legal"] for r in rs), max(r["legal"] for r in rs)],
        }
    out["l6_per_tool"] = per_tool
    if l6:
        out["l6_first"] = {k: l6[0][k] for k in
                           ("cam", "pieces", "carts", "aboard", "legal", "boarding",
                            "scroll_by_drive", "scroll_by_jump", "armed_square",
                            "pcells", "cartcells", "known", "cols", "mpieces", "who")}
        out["l6_last"] = {k: l6[-1][k] for k in
                          ("cam", "pieces", "carts", "aboard", "legal", "boarding",
                           "scroll_by_drive", "scroll_by_jump", "armed_square",
                           "pcells", "cartcells", "known", "cols", "mpieces", "who")}
    # every action of the peg tools' own tenures, compactly
    out["l6_peg_rows"] = [
        {"i": i, "who": r["who"], "cam": r["cam"], "ab": r["aboard"], "bd": r["boarding"],
         "lg": r["legal"], "kn": r["known"], "mp": r["mpieces"], "sd": r["scroll_by_drive"],
         "sj": r["scroll_by_jump"]}
        for i, r in enumerate(l6) if r["who"] in ("pegjump", "railpeg")
    ][:420]
    print(json.dumps(out))


if __name__ == "__main__":
    main()
