"""lf52 level 6 — THE CENSUS AT THE THIRD CAPTURE, and what the tool clicks at afterwards.

Rule 7au names the target: at level-6 action 124 `railpeg` jumps (14,2) over (15,2) onto (16,2),
which the engine's own level-6 branch treats as "this branch is lost" WHEN the red piece stands on
(6,6). `plan_level`'s docstring says seven of the eight candidates at that capture are dead ends and
the eighth finishes the level. This instrument asks, without designing anything:

  Q1  WHAT IS THE CANDIDATE LIST the tool actually ranks at that decision, in order, with the
      `capture_reachable` verdict it computes for each — recorded by wrapping the real function, so
      the search is never re-implemented (rule 7aj.1).
  Q2  WHICH candidate is the engine's fatal one, and is the eighth even IN the tool's list?
  Q3  WHAT, IF ANYTHING, SEPARATES THEM using only what the tool can see — recorded per candidate:
      pieces left per colour, closest capturable pair, successor count, whether the landing cell
      sits on the edge of the known map, and how much of the model each touches.
  Q4  AFTER the fatal capture, how many actions does the tool spend while the ENGINE offers zero
      legal moves, and does the tool's OWN model also offer zero? Those want opposite repairs: if
      the model says zero too, "propose nothing when nothing is legal" is a local test the tool can
      already make; if the model says otherwise, the model is stale and the test needs the frame.

CONTROLS (rule 7ai)
  NEGATIVE  per-level actions must be [8, 52, 60, 64, 139] and the total 823 — this probe reads and
            never steers. A different number means it is describing a different run.
  POSITIVE  `cand_turns` > 0 and `fatal_idx` not None: the instrument must be able to FIND the
            documented capture. Zero candidates recorded anywhere would mean it measured nothing.

Expected feedback:
  `fatal_idx` == 0 with a later candidate whose engine verdict is survivable -> the ordering is the
      defect and Q3's columns are where a discriminator could live.
  `model_legal_after` == 0 across the tail -> task (1) is a pure local test.
  `model_legal_after` > 0 while `engine_legal` == 0 -> the model is stale and the test must be
      grounded in the frame, not the simulation.
"""
from __future__ import annotations

import importlib.util
import json
import os
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

DIRS = [(0, -1), (1, 0), (0, 1), (-1, 0)]
BANKED = [8, 52, 60, 64, 139]
BANKED_TOTAL = 823


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
    legal = 0
    for p in pieces:
        for d in DIRS:
            try:
                if sc.qikmikecdf(p.chahdtpdoz, d):
                    legal += 1
            except Exception:
                pass
    named = sorted((p.chahdtpdoz, p.name) for p in pieces)
    red = [c for c, n in named if "red" in n]
    return {
        "lvl": int(getattr(sc, "whtqurkphir", -1)),
        "used": int(getattr(sc, "asqvqzpfdi", -1)),
        "cam": tuple(getattr(grid, "cdpcbbnfdp", (0, 0))),
        "legal": legal,
        "zv": bool(getattr(sc, "zvcnglshzcx", False)),
        "pcells": [[list(c), n] for c, n in named],
        "red": list(red[0]) if red else None,
        "ncarts": len(cartset),
    }


def main() -> None:
    from arc_agi import Arcade, OperationMode

    from admorphiq.tools import railpeg as rp

    out_path = Path(os.environ.get("LF52_CENS_OUT", "/tmp/lf52_cens_%s.txt" % (sys.argv[1] if len(sys.argv) > 1 else "0")))
    fh = out_path.open("w")

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

    # --- record the candidate ranking out of the REAL final loop of plan_level ----------------
    cand_log: list = []          # per plan_level call: list of (state, verdict)
    cur: list = []
    real_cr = rp.capture_reachable

    def cr(state, ground, noncapture, node_cap=25_000):
        v = real_cr(state, ground, noncapture, node_cap)
        cur.append((state, bool(v)))
        return v

    rp.capture_reachable = cr

    peg: dict = {}
    real_plan = rp.plan_level

    def plan(m, noncapture, **kw):
        del cur[:]
        res = real_plan(m, noncapture, **kw)
        peg["cands"] = list(cur)
        peg["plan_res"] = None if res is None else ([list(x) for x in res[0]], bool(res[1]))
        peg["ground"] = (frozenset(m.sockets), frozenset(m.rails), frozenset(m.obstacles))
        peg["noncapture"] = frozenset(noncapture)
        return res

    rp.plan_level = plan

    raw_ensure = rp.RailPegTool._ensure_plan

    def wrapped(self, m):
        peg["cands"] = []
        peg["plan_res"] = "not-called"
        score = raw_ensure(self, m)
        known = m.known()
        cols = [c[1] for c in known] or [0]
        rows_ = [c[0] for c in known] or [0]
        ground = (frozenset(m.sockets), frozenset(m.rails), frozenset(m.obstacles))
        succ = list(rp._successors(m.state(), ground, self._noncapture))
        peg.update(known=len(known), cols=(min(cols), max(cols)),
                   rows=(min(rows_), max(rows_)),
                   elsewhere=bool(self._elsewhere), score=score,
                   mpieces=dict(m.pieces), window=len(m.window),
                   njump=sum(1 for _s, mv, _c in succ if mv[0] == "jump"),
                   ndrive=sum(1 for _s, mv, _c in succ if mv[0] == "drive"),
                   sockets=len(m.sockets), touched=len(self._touched),
                   nonc=sorted(self._noncapture))
        peg["state"] = m.state()
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
                peg["cands"] = None
                peg["plan_res"] = "no-plan-call"
                act = inner.choose_action(frames, obs)
                if o is not None:
                    dat = getattr(act, "action_data", None)
                    o["xy"] = ((int(getattr(dat, "x", -1)), int(getattr(dat, "y", -1)))
                               if dat is not None and hasattr(dat, "x") else None)
                    o["act"] = getattr(act, "name", str(act))
                    o["peg"] = dict(peg)
                    rows.append(o)
                return act

        return Watch()

    res = se.run_game(arcade, info.game_id, info.baseline_actions,
                      agent_name="unified", max_actions=4000, adapter_factory=factory)

    per = [p["agent_actions"] for p in res.get("per_level", [])]
    six = [r for r in rows if r["lvl"] == 6]

    # --- the offset between engine (x, y) and model (row, col), fitted on the pieces ----------
    def fit(r):
        eng = [tuple(c) for c, _n in r["pcells"]]
        mod = list((r["peg"].get("mpieces") or {}))
        best = None
        for e in eng:
            for mc in mod:
                off = (mc[0] - e[1], mc[1] - e[0])
                hit = sum(1 for a in eng if (a[1] + off[0], a[0] + off[1]) in set(mod))
                if best is None or hit > best[0]:
                    best = (hit, off)
        return best

    # --- Q1/Q2/Q3: every level-6 turn that produced a capture candidate list ------------------
    cand_turns = 0
    fatal_idx = None
    fatal_action = None
    summary_cands = None
    for i, r in enumerate(six):
        cands = r["peg"].get("cands")
        if not cands:
            continue
        cand_turns += 1
        best = fit(r)
        off = best[1] if best else (0, 0)
        # engine cell (x, y) -> model cell (y + off0, x + off1)
        eng_to_mod = lambda c: (c[1] + off[0], c[0] + off[1])          # noqa: E731
        mod_to_eng = lambda c: (c[1] - off[1], c[0] - off[0])          # noqa: E731
        prev_pieces = dict(r["peg"].get("mpieces") or {})
        red_eng = tuple(r["red"]) if r["red"] else None
        ground = r["peg"].get("ground")
        nonc = r["peg"].get("noncapture") or frozenset()
        lines = []
        for k, (st, verdict) in enumerate(cands):
            after = dict(st[0])
            gone = [c for c in prev_pieces if c not in after]
            arrived = [c for c in after if c not in prev_pieces]
            eng_land = [mod_to_eng(c) for c in arrived]
            colours = Counter(after.values())
            nsucc = len(list(rp._successors(st, ground, nonc))) if ground else -1
            njump = (sum(1 for _s, mv, _c in rp._successors(st, ground, nonc) if mv[0] == "jump")
                     if ground else -1)
            spread = rp._spread(st, nonc)
            lines.append({
                "k": k, "reachable": verdict,
                "land_model": [list(c) for c in arrived],
                "land_engine": [list(c) for c in eng_land],
                "gone_model": [list(c) for c in gone],
                "colours": dict(colours), "nsucc": nsucc, "njump": njump,
                "spread": spread,
                "FATAL_ENGINE": bool(red_eng == (6, 6) and (16, 2) in eng_land),
            })
        if fatal_idx is None:
            for ln in lines:
                if ln["FATAL_ENGINE"]:
                    fatal_idx = ln["k"]
                    fatal_action = i
                    summary_cands = lines
                    break
        print(f"\n=== level-6 action {i} (engine used={r['used']} cam={r['cam']} "
              f"legal={r['legal']} zv={r['zv']} red={r['red']}) offset={off} "
              f"match={best[0] if best else 0}/{len(r['pcells'])}", file=fh)
        print(f"    model pieces {sorted((list(c), v) for c, v in prev_pieces.items())}", file=fh)
        print(f"    engine pieces {r['pcells']}", file=fh)
        print(f"    known={r['peg'].get('known')} cols={r['peg'].get('cols')} "
              f"rows={r['peg'].get('rows')} elsewhere={r['peg'].get('elsewhere')} "
              f"nonc={r['peg'].get('nonc')} score={r['peg'].get('score')}", file=fh)
        pr = r["peg"].get("plan_res")
        print(f"    plan_res={pr if pr in (None, 'not-called', 'no-plan-call') else pr[0][:6]}",
              file=fh)
        for ln in lines:
            print("    " + json.dumps(ln), file=fh)

    # --- Q4: the tail after the engine stops offering anything --------------------------------
    tail = []
    zero_from = None
    for i, r in enumerate(six):
        if r["legal"] == 0 and zero_from is None:
            zero_from = i
        if zero_from is not None:
            tail.append(r)
    n_tail = len(tail)
    model_legal_after = [ (t["peg"].get("njump"), t["peg"].get("ndrive")) for t in tail
                          if t["peg"].get("njump") is not None ]
    print(f"\n=== TAIL: engine legal==0 from level-6 action {zero_from}, {n_tail} actions to the end",
          file=fh)
    for t in tail:
        print(f"  used={t['used']:4d} act={t['act']} xy={t['xy']} legal={t['legal']} zv={t['zv']} "
              f"cam={t['cam']} mjump={t['peg'].get('njump')} mdrive={t['peg'].get('ndrive')} "
              f"mp={len(t['peg'].get('mpieces') or {})} score={t['peg'].get('score')} "
              f"known={t['peg'].get('known')}", file=fh)

    out = {
        "probe": "lf52_cens",
        "levels_completed": int(res.get("levels_completed", -1)),
        "per_level": per,
        "total_actions": int(res.get("total_actions", -1)),
        "control_neg_ok": per == BANKED and int(res.get("total_actions", -1)) == BANKED_TOTAL,
        "l6_actions": len(six),
        "cand_turns": cand_turns,
        "fatal_idx": fatal_idx,
        "fatal_action": fatal_action,
        "ncands_at_fatal": len(summary_cands) if summary_cands else 0,
        "reachable_flags_at_fatal": [c["reachable"] for c in summary_cands] if summary_cands else [],
        "engine_zero_legal_from": zero_from,
        "tail_actions": n_tail,
        "tail_model_has_jump": sum(1 for j, _d in model_legal_after if j),
        "tail_model_planned": len(model_legal_after),
        "tail_action6": sum(1 for t in tail if t["act"] == "ACTION6"),
        "tail_zv": sum(1 for t in tail if t["zv"]),
        "out": str(out_path),
    }
    print(json.dumps(out), flush=True)
    fh.close()


if __name__ == "__main__":
    main()
