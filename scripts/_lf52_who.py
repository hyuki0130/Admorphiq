"""WHO makes lf52 level 6's fatal third capture, and who spends the 376 actions after it?

⛔ The census in `_lf52_cens.py` refuted the framing rule 7au handed over. At level-6 actions
114-121 `railpeg` sees exactly ONE capture candidate — the (16,2) landing — computes
`capture_reachable = False` for it, REFUSES it (`plan_res=None`, `plan:all-candidates-fatal`) and
bids 0.0. The veto is right and it fired. The jump still happened at action 124.

So the question is no longer "how should railpeg rank the candidates". It is: WHICH TOOL was holding
the board at action 124, and which tool spends the 376 actions after it. Those want different
repairs and the answer is one attribute on the harness.

Recorded per action of the WHOLE run (the loop is never re-implemented — rule 7aj.1):
  harness  `_current`, `_since_progress`, `_primary_owns`, sorted `_failed`
  engine   level, in-level counter, camera, piece cells + names, legal jumps, the dead-position flag
  action   name and xy

CONTROLS (rule 7ai)
  NEGATIVE  per-level actions [8, 52, 60, 64, 139] / 823 total, or this is a different run.
  POSITIVE  `tools_seen` must hold more than one name — a probe that reports one tool everywhere
            has read a constant, which is the shape nine instruments failed in two days.
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
    except Exception:
        return None
    legal = 0
    for p in pieces:
        for d in DIRS:
            try:
                if sc.qikmikecdf(p.chahdtpdoz, d):
                    legal += 1
            except Exception:
                pass
    return {
        "lvl": int(getattr(sc, "whtqurkphir", -1)),
        "used": int(getattr(sc, "asqvqzpfdi", -1)),
        "cam": list(getattr(grid, "cdpcbbnfdp", (0, 0))),
        "legal": legal,
        "zv": bool(getattr(sc, "zvcnglshzcx", False)),
        "p": len(pieces),
        "red": next((list(p.chahdtpdoz) for p in pieces if "red" in p.name), None),
    }


def _loop_of(obj):
    """The UnifiedAgent inside whatever the factory returned — found, never assumed."""
    seen = set()
    stack = [obj]
    while stack:
        o = stack.pop()
        if id(o) in seen:
            continue
        seen.add(id(o))
        if hasattr(o, "tools") and hasattr(o, "_current") and hasattr(o, "stall"):
            return o
        for a in ("agent", "_agent", "inner", "_inner", "loop", "_loop"):
            nxt = getattr(o, a, None)
            if nxt is not None:
                stack.append(nxt)
    return None


def main() -> None:
    from arc_agi import Arcade, OperationMode

    out_path = Path(os.environ.get(
        "LF52_WHO_OUT", "/tmp/lf52_who_%s.txt" % (sys.argv[1] if len(sys.argv) > 1 else "0")))
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
                loop = _loop_of(inner)
                before = None if loop is None else (loop._current, loop._since_progress)
                act = inner.choose_action(frames, obs)
                if o is not None:
                    dat = getattr(act, "action_data", None)
                    o["xy"] = ([int(getattr(dat, "x", -1)), int(getattr(dat, "y", -1))]
                               if dat is not None and hasattr(dat, "x") else None)
                    o["act"] = getattr(act, "name", str(act))
                    if loop is not None:
                        o["cur"] = loop._current
                        o["cur_before"] = before[0]
                        o["sp"] = int(loop._since_progress)
                        o["owns"] = bool(loop._primary_owns)
                        o["failed"] = sorted(loop._failed)
                    rows.append(o)
                return act

        return Watch()

    res = se.run_game(arcade, info.game_id, info.baseline_actions,
                      agent_name="unified", max_actions=4000, adapter_factory=factory)

    per = [p["agent_actions"] for p in res.get("per_level", [])]
    six = [r for r in rows if r["lvl"] == 6]
    tools_all = Counter(r.get("cur") for r in rows)
    tools_six = Counter(r.get("cur") for r in six)

    # who held the board at each level-6 action, printed whenever anything of interest changes
    prev = None
    for i, r in enumerate(six):
        key = (r.get("cur"), r["legal"], r["zv"], r["p"], tuple(r["cam"]))
        if key != prev or i < 4 or 110 <= i <= 135 or 255 <= i <= 275:
            print(f"{i:4d} used={r['used']:4d} cur={r.get('cur')} sp={r.get('sp')} "
                  f"owns={r.get('owns')} act={r['act']} xy={r['xy']} cam={r['cam']} "
                  f"p={r['p']} legal={r['legal']} zv={r['zv']} red={r['red']} "
                  f"failed={r.get('failed')}", file=fh)
            prev = key

    # the capture: the action at which the engine's piece count falls on level 6
    caps = [i for i in range(1, len(six)) if six[i]["p"] < six[i - 1]["p"]]
    out = {
        "probe": "lf52_who",
        "levels_completed": int(res.get("levels_completed", -1)),
        "per_level": per,
        "total_actions": int(res.get("total_actions", -1)),
        "control_neg_ok": per == BANKED and int(res.get("total_actions", -1)) == BANKED_TOTAL,
        "tools_seen": sorted(k for k in tools_all if k),
        "tools_whole_run": dict(tools_all),
        "tools_level6": dict(tools_six),
        "l6_capture_actions": caps,
        "l6_capture_by": [six[i - 1].get("cur") for i in caps],
        "l6_zv_by": dict(Counter(r.get("cur") for r in six if r["zv"])),
        "l6_after_zv_by": dict(Counter(r.get("cur") for r in six[124:])),
        "l6_restart_click_by": [six[i].get("cur") for i in range(len(six))
                                if six[i]["zv"] and six[i]["xy"]
                                and six[i]["xy"][0] < 16 and six[i]["xy"][1] > 48],
        "out": str(out_path),
    }
    print(json.dumps(out), flush=True)
    fh.close()


if __name__ == "__main__":
    main()
