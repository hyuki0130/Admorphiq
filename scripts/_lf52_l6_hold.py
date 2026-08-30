"""WHY railpeg STOPS on lf52 level 6 — with the position's fate measured at the moment it stops.

⛔ The record already says what is NOT wrong. Perception drops nothing (R101LF52PERC Q1), widening
the map does not change the move (Q2), and the level is no longer destroyed (R101LF52PART). What is
NOT measured is the state of railpeg's own planner at the action it hands the board on, and whether
the board it hands on is still WINNABLE. Those are different failures wanting opposite repairs:

  * hands on a WINNABLE board with tiers exhausted  -> a missing PLAN, and the tier that is missing
    is named by `_why` at that action;
  * hands on a DEAD board                           -> the repair is survivability, not tenure;
  * never hands on at all, runs out of level        -> the repair is tenure and nothing else.

METHOD. `score_efficiency.run_game` drives (rule 7aj.1). `RailPegTool._ensure_plan` and `propose`
are wrapped where the tool calls them (rule 7ah — `detect` is never sampled off-schedule). Per
level-6 action the ENGINE's own state is read, and the fate of a position is decided by
`scripts/_lf52_l6_model.py`, the simulator the live 91-action clear was planned from.

THREE CONTROLS, printed before any verdict (rule 7ai):
  NEGATIVE  per-level actions [8, 52, 60, 64, 139] / 823 total. A different run describes nothing.
  POSITIVE  the wrapper must fire; `ctrl_root_winnable` must be TRUE — a fate oracle that cannot
            say YES about the opening has measured nothing.
  INVARIANT the stepping stones must not move; the offline model holds them static.

Expected feedback: `retire.winnable` true with a dominant `_why` key names the missing tier and
makes it a lever. `retire.winnable` false moves the whole question back to survivability. No
retirement at all (railpeg holding to the end of the level) makes it tenure.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from collections import Counter, deque
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

BANKED = [8, 52, 60, 64, 139]
BANKED_TOTAL = 823
NODE_CAP = 700_000

_M = importlib.util.spec_from_file_location(
    "lf52_l6_model", Path(__file__).resolve().parent / "_lf52_l6_model.py")
L6 = importlib.util.module_from_spec(_M)
_M.loader.exec_module(L6)


def _key(s):
    return (tuple((c, 1 if "red" in n else 0) for c, n in s[0]), s[1], s[2])


def winnable(state) -> tuple[bool, bool, int]:
    seen = {_key(state)}
    q = deque([state])
    n = 0
    while q:
        s = q.popleft()
        if len(s[0]) == 2:
            return True, False, n
        n += 1
        if n > NODE_CAP:
            return False, True, n
        for ns, _mv in L6.successors(s):
            k = _key(ns)
            if k not in seen:
                seen.add(k)
                q.append(ns)
    return False, False, n


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
        pads = grid.ndtvadsrqf("fozwvlovdui")
        carts = grid.whdmasyorl("hupkpseyuim2")
        stones = grid.ndtvadsrqf("dgxfozncuiz")
    except Exception:
        return None
    return {
        "lvl": int(getattr(sc, "whtqurkphir", -1)),
        "cam": list(getattr(grid, "cdpcbbnfdp", (0, 0))),
        "pads": sorted((tuple(p.chahdtpdoz), str(p.name)) for p in pads),
        "carts": sorted(tuple(c.chahdtpdoz) for c in carts),
        "stones": sorted(tuple(s.chahdtpdoz) for s in stones),
    }


def _state_of(row):
    pads = tuple(sorted((tuple(c), n) for c, n in row["pads"]))
    return (pads, tuple(sorted(tuple(c) for c in row["carts"])), row["cam"][0])


def _loop_of(obj):
    seen, stack = set(), [obj]
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

    from admorphiq.tools.railpeg import RailPegTool, _aboard

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

    rows: list[dict] = []            # one per action, engine truth + acting tool
    decisions: list[dict] = []       # one per railpeg _ensure_plan call on level 6
    empties: list[dict] = []         # one per railpeg propose returning []
    fired = [0]
    at6 = [False]
    cur = {"i": -1}

    raw_ensure = RailPegTool._ensure_plan
    raw_propose = RailPegTool.propose

    def ensure(self, m):
        before_why = Counter(self._why)
        before_tiers = Counter(self._tiers)
        bid = raw_ensure(self, m)
        if not at6[0]:
            return bid
        fired[0] += 1
        dw = {k: v for k, v in (Counter(self._why) - before_why).items()}
        dt = {k: v for k, v in (Counter(self._tiers) - before_tiers).items()}
        st = m.state()
        decisions.append({
            "i": cur["i"], "bid": round(float(bid), 3),
            "known": len(m.known()), "pieces": len(m.pieces), "carts": len(m.carts),
            "aboard": _aboard(st), "elsewhere": bool(self._elsewhere),
            "barren": int(self._barren), "sincecapture": int(self._sincecapture),
            "touched": len(self._touched), "plan": len(self._plan),
            "head": None if not self._plan else [self._plan[0][0], self._plan[0][1],
                                                self._plan[0][2]],
            "why": dw, "tier": dt,
        })
        return bid

    def propose(self, frames, obs):
        steps = raw_propose(self, frames, obs)
        if at6[0] and not steps:
            empties.append({"i": cur["i"], "settles": int(self._settles),
                            "peaked": int(self._peaked), "plan": len(self._plan)})
        return steps

    RailPegTool._ensure_plan = ensure
    RailPegTool.propose = propose

    real_factory = se._make_agent

    def factory():
        inner = real_factory("unified", game_id=info.game_id)

        class Watch:
            restart_on_game_over = getattr(inner, "restart_on_game_over", False)

            def is_done(self, frames, obs):
                return inner.is_done(frames, obs)

            def choose_action(self, frames, obs):
                o = _oracle(held.get("env"))
                at6[0] = bool(o is not None and o["lvl"] == 6)
                cur["i"] = sum(1 for r in rows if r["lvl"] == 6)
                loop = _loop_of(inner)
                act = inner.choose_action(frames, obs)
                if o is not None:
                    o["tool"] = None if loop is None else loop._current
                    rows.append(o)
                return act

        return Watch()

    res = se.run_game(arcade, info.game_id, info.baseline_actions,
                      agent_name="unified", max_actions=4000, adapter_factory=factory)

    per = [p["agent_actions"] for p in res.get("per_level", [])]
    out: dict = {
        "probe": "lf52_l6_hold",
        "levels_completed": int(res.get("levels_completed", -1)),
        "per_level": per,
        "total_actions": int(res.get("total_actions", -1)),
        "game_score": res.get("game_score"),
        "ctrl_neg_ok": per == BANKED and int(res.get("total_actions", -1)) == BANKED_TOTAL,
        "ctrl_fired": fired[0],
    }
    six = [r for r in rows if r["lvl"] == 6]
    out["l6_actions"] = len(six)
    if not six or not fired[0]:
        print(json.dumps(out))
        return

    out["ctrl_stones_static"] = len({tuple(map(tuple, r["stones"])) for r in six}) == 1
    root = _state_of(six[0])
    w0, c0, _n = winnable(root)
    out["ctrl_root_winnable"] = w0
    out["ctrl_root_capped"] = c0
    out["ctrl_root_matches"] = root == (tuple(sorted(L6.PADS0.items())), L6.CARTS0, L6.OX0)

    # tenure and the frontier of railpeg's hold
    ten = Counter(r["tool"] for r in six)
    out["tenure"] = dict(ten)
    peg_idx = [i for i, r in enumerate(six) if r["tool"] == "railpeg"]
    out["railpeg_first"] = peg_idx[0] if peg_idx else None
    out["railpeg_last"] = peg_idx[-1] if peg_idx else None
    out["cams"] = sorted({r["cam"][0] for r in six})
    out["known_max"] = max(d["known"] for d in decisions)
    out["aboard_max"] = max(d["aboard"] for d in decisions)
    out["decisions"] = len(decisions)
    out["why_total"] = dict(Counter(k for d in decisions for k, v in d["why"].items()
                                    for _ in range(v)).most_common(14))
    out["tier_total"] = dict(Counter(k for d in decisions for k, v in d["tier"].items()
                                     for _ in range(v)))
    out["empties"] = len(empties)
    out["first_empty"] = empties[0] if empties else None
    out["tail"] = decisions[-8:]

    # THE QUESTION: the fate of the board at the action railpeg lets go of it.
    memo: dict = {}

    def fate(i: int):
        s = _state_of(six[i])
        k = _key(s)
        if k not in memo:
            w, c, n = winnable(s)
            memo[k] = {"winnable": w, "capped": c, "states": n}
        return memo[k]

    if peg_idx:
        j = min(peg_idx[-1] + 1, len(six) - 1)
        out["retire"] = {"i": peg_idx[-1], "next_tool": six[j]["tool"],
                         "pads": len(six[peg_idx[-1]]["pads"]),
                         "cam": six[peg_idx[-1]]["cam"][0], **fate(peg_idx[-1])}
    caps = [i for i in range(1, len(six)) if len(six[i]["pads"]) < len(six[i - 1]["pads"])]
    out["captures"] = [{"i": i, "tool": six[i - 1]["tool"], "pads_after": len(six[i]["pads"]),
                        **fate(i)} for i in caps]
    out["end"] = {"i": len(six) - 1, "pads": len(six[-1]["pads"]), **fate(len(six) - 1)}
    print(json.dumps(out))


if __name__ == "__main__":
    main()
