"""Why does railpeg's map of lf52 level 6 stop at 98 cells / column 25 of 28? An ORACLE census.

⛔ FOUR HYPOTHESES, AND THEY WANT DIFFERENT FIXES. This instrument separates them by reading the
ENGINE's own state beside the tool's, once per action, over the scored run:

  H1 the remaining board is behind an action the tool never proposes at that point
  H2 the camera cannot scroll further from any reachable position (a hard limit, not a defect)
  H3 growth is possible but never RANKED — nothing values a move that reveals board
  H4 the map grows but the model discards it (retraction / window mismatch / stale overwrite)

WHAT THE GAME'S OWN SOURCE SAYS (`environment_files/lf52/271a04aa/lf52.py`, dev-time reading only —
the TOOL stays frame-only). On level 6 the camera offset `grid.cdpcbbnfdp` moves in exactly three
ways and no others:

  (a) `cfilhtifcb`  a JUMP landing on cell (7, 6) while the offset is exactly (5, 5)   -> (-20, 0)
  (b) `tmhxwcojkh`  a cart DRIVE while a plain `fozwvlovdui` rides that cart           -> (-dx*6, 0)
  (c) `cfilhtifcb`  a JUMP landing on cell (18, 2) while the offset is exactly (-57,5) -> (-44, 0)

So map growth past the current screen REQUIRES either a scripted landing square or a piece ABOARD a
cart. That is a hypothesis about the engine; only a run says what happens, so it is measured.

METHOD. `score_efficiency.run_game` drives the steps — the loop is never re-implemented (rule 7aj.1),
`arcade.make` is wrapped only to capture the env, and the adapter is wrapped only to READ. Per action,
before the agent chooses, the oracle records from the engine: level, in-level action count, camera
offset, piece cells, cart cells, how many pieces ride a cart, and — computed with the engine's OWN
legality predicate `qikmikecdf` — how many jumps are legal and how many of those LAND ON A CART (the
boarding moves). Beside it, from railpeg: `len(model.known())`, the model's window column span, and
whether the tool has concluded the board extends past the screen.

TWO CONTROLS (rule 7ai), both printed before any arm is read:
  NEGATIVE  the instrument must not perturb: per-level actions must be [8, 52, 60, 64, 139] and the
            total 823. A different number means this probe is describing a different run (rule 7aj.2).
  POSITIVE  the oracle must be able to say YES. `pos_scroll_levels` names every level on which it
            saw the camera actually move, and `pos_boarding_seen` the levels where it found at least
            one boarding move. An oracle that reports zero everywhere has measured nothing, which is
            the failure mode nine instruments hit in two days.

Expected feedback:
  `l6.boarding_points` > 0 with `l6.boarding_taken` == 0        -> H3: the move exists and is never ranked.
  `l6.boarding_points` == 0 from the first action of the level  -> H2: no reachable boarding move at all.
  `l6.boarding_points` > 0 early, 0 after action K              -> H1/H3: the window CLOSED; what the
            tool did before K spent it, and the fix is to rank boarding while it is still available.
  `l6.known_drops` > 0 or `l6.known_final` < `l6.known_max`     -> H4: the model is discarding map.
  `l6.cam_last_move_at` far below the level's last action       -> the scroll stopped long before the
            tool did, and `actions_after_cam_stop` prices what that costs.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

DIRS = [(0, -1), (1, 0), (0, 1), (-1, 0)]
BANKED = [8, 52, 60, 64, 139]
BANKED_TOTAL = 823


def _scene(env):
    g = getattr(env, "_game", None) or getattr(env, "game", None)
    return getattr(g, "ikhhdzfmarl", None) if g is not None else None


def _oracle(env) -> dict | None:
    """The engine's own answer to 'what is on this board and what may move'."""
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
    legal = 0
    boarding = 0
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
            if (pos[0] + 2 * d[0], pos[1] + 2 * d[1]) in cartset:
                boarding += 1
    return {
        "lvl": int(getattr(sc, "whtqurkphir", -1)),
        "used": int(getattr(sc, "asqvqzpfdi", -1)),
        "cam": tuple(getattr(grid, "cdpcbbnfdp", (0, 0))),
        "pieces": len(pieces),
        "carts": len(carts),
        "aboard": aboard,
        "legal": legal,
        "boarding": boarding,
        # `zvcnglshzcx` is the engine's own "the restart control is live" flag. A tool that clicks
        # it throws the level away, and rule 7s says such a restart reads exactly like a level that
        # continues — so it is recorded rather than inferred.
        "zv": bool(getattr(sc, "zvcnglshzcx", False)),
    }


def main() -> None:
    from arc_agi import Arcade, OperationMode

    from admorphiq.tools import railpeg as rp

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

    # railpeg's own view, sampled where the tool itself decides — never by calling `detect`
    # off-schedule (rule 7ah: asking railpeg whether it recognises a board spends its give-up budget).
    peg_view: dict = {"known": None, "cols": None, "elsewhere": None, "score": None,
                      "mpieces": None}
    raw_plan = rp.RailPegTool._ensure_plan

    def wrapped(self, m):
        score = raw_plan(self, m)
        known = m.known()
        cols = [c[1] for c in known] or [0]
        peg_view.update(known=len(known), cols=(min(cols), max(cols)),
                        elsewhere=bool(self._elsewhere), score=score,
                        mpieces=len(m.pieces))
        return score

    rp.RailPegTool._ensure_plan = wrapped

    rows: list[dict] = []
    real_factory = se._make_agent

    def factory():
        inner = real_factory("unified", game_id=info.game_id)

        class Watch:
            restart_on_game_over = getattr(inner, "restart_on_game_over", False)

            def is_done(self, frames, obs):
                return inner.is_done(frames, obs)

            def choose_action(self, frames, obs):
                o = _oracle(held.get("env"))
                act = inner.choose_action(frames, obs)
                if o is not None:
                    o["known"] = peg_view["known"]
                    o["cols"] = peg_view["cols"]
                    o["elsewhere"] = peg_view["elsewhere"]
                    o["mpieces"] = peg_view["mpieces"]
                    o["lvl_done"] = int(getattr(obs, "levels_completed", -1))
                    o["state"] = str(getattr(obs, "state", "?")).split(".")[-1]
                    o["act"] = getattr(act, "name", str(act))
                    rows.append(o)
                return act

        return Watch()

    res = se.run_game(arcade, info.game_id, info.baseline_actions,
                      agent_name="unified", max_actions=4000, adapter_factory=factory)

    per = [p["agent_actions"] for p in res.get("per_level", [])]
    out: dict = {
        "probe": "lf52_map",
        "levels_completed": int(res.get("levels_completed", -1)),
        "per_level": per,
        "total_actions": int(res.get("total_actions", -1)),
        "game_score": res.get("game_score"),
        "control_neg_ok": per == BANKED and int(res.get("total_actions", -1)) == BANKED_TOTAL,
        "oracle_rows": len(rows),
    }

    # --- POSITIVE controls: the oracle must be able to say YES somewhere -------------------
    by_lvl: dict[int, list[dict]] = {}
    for r in rows:
        by_lvl.setdefault(r["lvl"], []).append(r)
    out["pos_scroll_levels"] = sorted(L for L, rs in by_lvl.items()
                                      if len({r["cam"] for r in rs}) > 1)
    out["pos_boarding_seen"] = sorted(L for L, rs in by_lvl.items()
                                      if any(r["boarding"] > 0 for r in rs))
    out["pos_aboard_seen"] = sorted(L for L, rs in by_lvl.items()
                                    if any(r["aboard"] > 0 for r in rs))
    out["levels_sampled"] = sorted(by_lvl)

    # --- per-level summary ------------------------------------------------------------------
    summ = {}
    for L, rs in sorted(by_lvl.items()):
        cams = [r["cam"] for r in rs]
        distinct = [cams[0]]
        last_move = 0
        for i, c in enumerate(cams):
            if c != distinct[-1]:
                distinct.append(c)
                last_move = i
        knowns = [r["known"] for r in rs if r["known"] is not None]
        drops = sum(1 for a, b in zip(knowns, knowns[1:]) if b < a)
        boarding_pts = [i for i, r in enumerate(rs) if r["boarding"] > 0]
        legal_zero = [i for i, r in enumerate(rs) if r["legal"] == 0]
        summ[str(L)] = {
            "actions": len(rs),
            "cam_track": distinct[:24],
            "cam_moves": len(distinct) - 1,
            "cam_last_move_at": last_move,
            "actions_after_cam_stop": len(rs) - 1 - last_move,
            "pieces_start": rs[0]["pieces"], "pieces_end": rs[-1]["pieces"],
            "carts": rs[0]["carts"],
            "aboard_max": max(r["aboard"] for r in rs),
            "aboard_points": sum(1 for r in rs if r["aboard"] > 0),
            "boarding_points": len(boarding_pts),
            "boarding_first": boarding_pts[0] if boarding_pts else None,
            "boarding_last": boarding_pts[-1] if boarding_pts else None,
            "legal_zero_points": len(legal_zero),
            "legal_zero_from": legal_zero[0] if legal_zero else None,
            "legal_max": max(r["legal"] for r in rs),
            "known_max": max(knowns) if knowns else None,
            "known_final": knowns[-1] if knowns else None,
            "known_drops": drops,
            "cols_final": rs[-1]["cols"],
            "elsewhere_final": rs[-1]["elsewhere"],
            "used_final": rs[-1]["used"],
            "used_resets": [i for i in range(1, len(rs)) if rs[i]["used"] < rs[i - 1]["used"]],
            "states": sorted({r.get("state", "?") for r in rs}),
            "reset_actions": sum(1 for r in rs if r.get("act") == "RESET"),
            "mpieces_final": rs[-1].get("mpieces"),
            "zv_points": sum(1 for r in rs if r.get("zv")),
        }
    out["levels"] = summ
    print(json.dumps(out), flush=True)

    # ⛔ A restart has NO state signal on this game (`obs.state` never leaves NOT_FINISHED), so the
    # only evidence of one is the engine's in-level counter falling. Print the twelve actions BEFORE
    # each fall: the cause is in that window and nowhere else.
    for L, rs in sorted(by_lvl.items()):
        for i in range(1, len(rs)):
            if rs[i]["used"] >= rs[i - 1]["used"]:
                continue
            print(f"\n# level {L}: in-level counter fell {rs[i - 1]['used']} -> {rs[i]['used']} "
                  f"at level-action {i} — the twelve before it:", file=sys.stderr)
            for j in range(max(0, i - 12), min(len(rs), i + 2)):
                r = rs[j]
                print(f"{j:4d} used={r['used']:4d} act={r.get('act')} cam={r['cam']} "
                      f"p={r['pieces']} legal={r['legal']} zv={r.get('zv')} "
                      f"mp={r.get('mpieces')} st={r.get('state')}", file=sys.stderr)

    # A human-readable level-6 timeline on stderr; the JSON line above is the machine answer.
    six = by_lvl.get(6, [])
    if six:
        print("\n# lf52 level 6 timeline (i used cam pieces carts aboard legal boarding known cols)",
              file=sys.stderr)
        prev = None
        for i, r in enumerate(six):
            key = (r["cam"], r["pieces"], r["aboard"], r["legal"], r["boarding"], r["known"],
                   r["cols"], r.get("state"), r.get("mpieces"))
            if key != prev or i < 3:
                print(f"{i:4d} {r['used']:4d} {r['cam']} p={r['pieces']} c={r['carts']} "
                      f"ab={r['aboard']} legal={r['legal']} board={r['boarding']} "
                      f"known={r['known']} cols={r['cols']} mp={r.get('mpieces')} "
                      f"st={r.get('state')} act={r.get('act')}", file=sys.stderr)
                prev = key


if __name__ == "__main__":
    main()
