"""When does lf52 level 6 actually become UNWINNABLE, and WHICH TOOL makes that move?

⛔ THE BRIEFING THIS PROBE TESTS. Rule 7au names one move: "at level-6 action 124 the tool jumps
(14,2) over (15,2) onto (16,2) while red stands on (6,6), which calls `pchvqimdvj()`, the author's
own 'this branch is lost' marker". That is a statement about where the ENGINE reacts. It is NOT the
same statement as "this is the move that lost the level" — a position can be dead several captures
earlier and the reaction only fire when the last legal jump is spent, or the reaction can mean
something other than a loss. Those want opposite repairs, so they are separated by measurement.

⛔ AND IT TESTS THE ATTRIBUTION. `scripts/_lf52_who.py` measured that the third capture is made by
`pegjump` and the level-restarting click by `graph`, not by `railpeg`. A fix aimed at the wrong tool
is inert by construction, so the losing move is reported WITH ITS AUTHOR.

METHOD. `score_efficiency.run_game` drives the steps (rule 7aj.1 — the loop is never
re-implemented); `arcade.make` is wrapped only to capture the env and the adapter only to READ.
Per action the ENGINE's own state is recorded: pad cells AND names, cart cells, stepping-stone
cells, camera offset, plus which tool `UnifiedAgent` had in hand.

The verdict comes from `scripts/_lf52_l6_model.py` — the offline simulator the live 91-action clear
was planned from, whose rules were each checked against a live frame. A recorded engine state is
rebuilt as one of its states and searched for a two-pad position. WINNABILITY IS MONOTONE along a
played line (if a successor is winnable so is its parent), so the first losing move is found by
BINARY SEARCH over the attempt, not by 500 searches.

THREE CONTROLS, all printed before any verdict is read (rule 7ai):
  NEGATIVE   per-level actions must be [8, 52, 60, 64, 139] and the total 823. A different number
             means this probe is describing a different run (rule 7aj.2).
  POSITIVE   the rebuilt state at level-6 action 0 must EQUAL the offline model's own root, and the
             search must return WINNABLE for it. A solver that cannot say YES has measured nothing.
  INVARIANT  the stepping stones `dgxfozncuiz` must not move for the whole level — the offline
             model holds them static, so a level in which they move is one this probe cannot read.

Expected feedback:
  `lost_at` at the first captures (≈14/16, railpeg) -> the branch is lost by the CHEAPEST-FIRST
             opening and action 124 is only where the engine reacts. The repair is survivability at
             capture ONE, and it is railpeg's.
  `lost_at` at the third capture (≈124, pegjump)    -> rule 7au has the move right and the author
             wrong; the repair belongs to `pegjump`.
  `lost_at` null with `attempt1_end_winnable` true  -> the level is never LOST at all; it is merely
             never FINISHED, and every "disarm the trap" arm was aimed at a trap that is not one.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from collections import deque
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
    """A compact hashable stand-in for a state — the names carry one bit, so `seen` stays small."""
    return (tuple((c, 1 if "red" in n else 0) for c, n in s[0]), s[1], s[2])


def winnable(state) -> tuple[bool, bool, int]:
    """(win, capped, states). A two-pad position reachable from here under the camera?"""
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
        "used": int(getattr(sc, "asqvqzpfdi", -1)),
        "cam": list(getattr(grid, "cdpcbbnfdp", (0, 0))),
        "pads": sorted((tuple(p.chahdtpdoz), str(p.name)) for p in pads),
        "carts": sorted(tuple(c.chahdtpdoz) for c in carts),
        "stones": sorted(tuple(s.chahdtpdoz) for s in stones),
        "zv": bool(getattr(sc, "zvcnglshzcx", False)),
    }


def _loop_of(obj):
    """The UnifiedAgent inside whatever the factory returned — found, never assumed."""
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


def _state_of(row):
    pads = tuple(sorted((tuple(c), n) for c, n in row["pads"]))
    return (pads, tuple(sorted(tuple(c) for c in row["carts"])), row["cam"][0])


def main() -> None:
    from arc_agi import Arcade, OperationMode

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
                act = inner.choose_action(frames, obs)
                if o is not None:
                    dat = getattr(act, "action_data", None)
                    o["xy"] = ([int(getattr(dat, "x", -1)), int(getattr(dat, "y", -1))]
                               if dat is not None and hasattr(dat, "x") else None)
                    o["act"] = getattr(act, "name", str(act))
                    o["tool"] = None if loop is None else loop._current
                    rows.append(o)
                return act

        return Watch()

    res = se.run_game(arcade, info.game_id, info.baseline_actions,
                      agent_name="unified", max_actions=4000, adapter_factory=factory)

    per = [p["agent_actions"] for p in res.get("per_level", [])]
    out: dict = {
        "probe": "lf52_fate",
        "levels_completed": int(res.get("levels_completed", -1)),
        "per_level": per,
        "total_actions": int(res.get("total_actions", -1)),
        "game_score": res.get("game_score"),
        "control_neg_ok": per == BANKED and int(res.get("total_actions", -1)) == BANKED_TOTAL,
    }

    six = [r for r in rows if r["lvl"] == 6]
    out["l6_actions"] = len(six)
    if not six:
        print(json.dumps(out))
        return

    # --- INVARIANT: the offline model holds the stepping stones static ----------------------
    stones = {tuple(map(tuple, r["stones"])) for r in six}
    out["ctrl_stones_static"] = len(stones) == 1

    # --- POSITIVE: the rebuilt opening state IS the offline model's own root, and it wins ---
    root_model = (tuple(sorted(L6.PADS0.items())), L6.CARTS0, L6.OX0)
    root_live = _state_of(six[0])
    out["ctrl_root_matches"] = root_live == root_model
    w0, cap0, n0 = winnable(root_live)
    out["ctrl_root_winnable"] = w0
    out["ctrl_root_capped"] = cap0
    out["ctrl_root_states"] = n0

    # --- attempt boundaries -----------------------------------------------------------------
    # ⛔ The FIRST row with MORE pads is already POST-restart. Taking it as the attempt's last row
    # asks the solver about a board just handed back whole, which of course answers WINNABLE — the
    # first version of this probe did exactly that and reported "never lost" for the wrong reason.
    restarts = [i for i in range(1, len(six)) if len(six[i]["pads"]) > len(six[i - 1]["pads"])]
    out["restarts_at"] = restarts
    last1 = (restarts[0] - 1) if restarts else (len(six) - 1)
    out["attempt1_last"] = last1

    caps = [i for i in range(1, len(six)) if len(six[i]["pads"]) < len(six[i - 1]["pads"])]
    out["captures"] = [{"i": i, "tool": six[i - 1]["tool"], "act": six[i - 1]["act"],
                        "xy": six[i - 1]["xy"], "pads_after": len(six[i]["pads"])}
                       for i in caps]
    out["zv_from"] = next((i for i, r in enumerate(six) if r["zv"]), None)

    memo: dict = {}

    def win_at(i: int) -> tuple[bool, bool]:
        s = _state_of(six[i])
        k = _key(s)
        if k not in memo:
            w, c, _n = winnable(s)
            memo[k] = (w, c)
        return memo[k]

    # --- the direct question: still winnable right after each capture? ----------------------
    out["after_capture"] = [{"i": i, "tool": six[i - 1]["tool"],
                             "winnable": win_at(i)[0], "capped": win_at(i)[1]} for i in caps]

    w_end, c_end = win_at(last1)
    out["attempt1_end_winnable"] = w_end
    out["attempt1_end_capped"] = c_end
    if restarts:
        w2, c2 = win_at(len(six) - 1)
        out["attempt2_end_winnable"] = w2
        out["attempt2_end_capped"] = c2

    # --- BINARY SEARCH the first losing move over attempt 1 (winnability is monotone) --------
    if not w0:
        out["lost_at"] = 0
    elif w_end:
        out["lost_at"] = None          # attempt 1 was never LOST — it was merely never FINISHED
    else:
        lo, hi = 0, last1              # win_at(lo) True, win_at(hi) False
        while hi - lo > 1:
            mid = (lo + hi) // 2
            if win_at(mid)[0]:
                lo = mid
            else:
                hi = mid
        out["lost_at"] = hi
        loser = six[hi - 1]
        out["losing_move"] = {"i": hi - 1, "tool": loser["tool"], "act": loser["act"],
                              "xy": loser["xy"], "used": loser["used"],
                              "pads_before": [[list(c), n] for c, n in _state_of(loser)[0]],
                              "pads_after": [[list(c), n] for c, n in _state_of(six[hi])[0]],
                              "carts_before": [list(c) for c in _state_of(loser)[1]],
                              "carts_after": [list(c) for c in _state_of(six[hi])[1]],
                              "ox_before": _state_of(loser)[2], "ox_after": _state_of(six[hi])[2]}
    out["queries"] = len(memo)
    out["any_capped"] = any(c for _w, c in memo.values())
    print(json.dumps(out))


if __name__ == "__main__":
    main()
