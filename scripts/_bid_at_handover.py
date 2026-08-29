"""When the board falls through to `graph`, had anything else bid — and could it have played?

⛔ THE QUESTION, and why `scripts/bid_matrix.py` cannot answer it. That script reads every tool's
`detect` on each game's FIRST frame. The boards that are stuck are stuck on level 5, 6 or 7, and the
tool line-up there is not the one that bid at level 1: measured today, lf52's sixth level is held by
railpeg for 121 actions, pegjump for 11, and then `graph` for 366; dc22's by gantry 12, phase_grid
12, then graph 474. A first-frame bid matrix is blind to all of it.

So the bid is taken WHERE THE HANDOVER HAPPENS. Every time `UnifiedAgent._redecide` runs, this
records the full bid vector it was deciding on, the set of tools already retired at that moment, and
what it picked — which separates the two outcomes that need completely different work:

  nothing bid above zero        the board genuinely has no specialist; the answer is a new tool
  something bid and lost        a ROUTING defect, and it would be costing us on boards we already
                                believe we can solve

⚠️ AND THOSE ARE NOT THE ONLY TWO. On dc22 `gantry` bids, wins the board, and latches dead at
action 6; `phase_grid` lasts 12. So "something bid" and "something could have PLAYED" are different
questions, and reading a dying specialist as a routing win is the trap. Every switch therefore
carries the outgoing tool's TENURE and the REASON it ended:

  empty   `_fill_from_current` retired it after `_EMPTY_TOLERANCE` = 8 consecutive proposals of
          nothing. The record's standing claim is that every stuck game retires its specialist this
          way; this measures it per game rather than repeating it.
  stall   `_redecide` retired the incumbent because `_since_progress` reached the stall window and
          some other non-failed tool detected strictly better.

⚠️ Faithful to the scored configuration: `choose_action([], obs)`, giveup 8000, stall 80, ctx 6000,
an LLM that raises so the signature fallback runs, and — the defect that cost two silent runs today
— `GameAction.RESET` on a death, because `UnifiedAgent.restart_on_game_over` is True and the scorer
revives rather than stopping.

Run it with `bash scripts/snaprun.sh bidhand scripts/_bid_at_handover.py 6 "lf52 bp35" 4000`.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

# ⛔ Resolve `src` against THIS FILE, never the cwd: a private snapshot runs with the cwd on the
# SHARED tree (that is where `environment_files` lives), and a relative insert would silently
# select the shared tree's code — rule 7n.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))


def main() -> None:
    import numpy as np
    from arc_agi import Arcade, OperationMode
    from arcengine import GameAction

    from admorphiq.harness.loop import UnifiedAgent, frame_2d, has_frame, levels_completed
    from admorphiq.harness.registry import default_tools
    from admorphiq.tools.segment import board_changed

    title = (sys.argv[1] if len(sys.argv) > 1 else "lf52").strip().lower()
    cap = int(sys.argv[2]) if len(sys.argv) > 2 else 4000

    def _no_llm(*_a, **_k):
        raise RuntimeError("LLM-free: the signature fallback is what the scorer measures here")

    agent = UnifiedAgent(default_tools(), _no_llm, giveup=8000, stall=80, ctx_budget=6000)

    switches: list[dict] = []
    retire: list[dict] = []
    state = {"lvl": 0, "step": 0, "tenure_start": 0}

    def _bids(obs) -> dict[str, float]:
        out: dict[str, float] = {}
        for name, t in agent.tools.items():
            try:
                out[name] = round(float(t.detect(agent._recent_frames, obs)), 3)
            except Exception:  # noqa: BLE001 - a tool that throws bids nothing, as the loop treats it
                out[name] = 0.0
        return out

    orig_redecide = agent._redecide

    def _tagged_redecide(frames, obs, sig):
        # ⛔ Snapshot BEFORE the call. `_redecide` adds the outgoing tool to `_failed` and then
        # picks, so a snapshot taken afterwards cannot tell "was already retired" from "was retired
        # by this very decision" — and that difference is the whole routing question.
        before = sorted(agent._failed)
        outgoing = agent._current
        # ⛔ THE SWEEP ITSELF IS UNDER TEST. `BID_NOSWEEP=1` records the switch without asking any
        # tool for a bid, so the two arms differ ONLY by one extra `detect` pass at a point the
        # harness already sweeps. If the arms disagree, `detect` is a mutator in the routing path
        # and no bid can be read without changing the thing being measured.
        bids = {} if os.environ.get("BID_NOSWEEP") else _bids(obs)
        orig_redecide(frames, obs, sig)
        top = sorted(bids.items(), key=lambda kv: -kv[1])[:8]
        switches.append({
            "step": state["step"], "level": state["lvl"],
            "from": str(outgoing), "to": str(agent._current),
            "tenure": state["step"] - state["tenure_start"],
            "failed_before": before,
            "bids": {k: v for k, v in top if v > 0.0} or {"ALL_ZERO": 0.0},
            "nonzero_bidders": sum(1 for v in bids.values() if v > 0.0),
            "best_available": max(
                (v for k, v in bids.items() if k not in before and k != outgoing), default=0.0),
        })
        state["tenure_start"] = state["step"]

    agent._redecide = _tagged_redecide  # type: ignore[method-assign]

    orig_fill = agent._fill_from_current

    def _tagged_fill(frames, obs):
        was = agent._current
        n_before = len(agent._failed)
        orig_fill(frames, obs)
        if len(agent._failed) > n_before and was is not None:
            # The EMPTY path: `_fill_from_current` retired it for proposing nothing 8 times running.
            retire.append({"step": state["step"], "level": state["lvl"],
                           "tool": str(was), "reason": "empty"})

    agent._fill_from_current = _tagged_fill  # type: ignore[method-assign]

    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    info = next(i for i in arcade.get_environments()
                if (i.title or i.game_id).lower().startswith(title))
    env = arcade.make(info.game_id)
    obs = env.observation_space
    human = list(getattr(info, "baseline_actions", []) or [])

    lvl = levels_completed(obs)
    prev_board = frame_2d(obs).astype(np.int16) if has_frame(obs) else None
    per_tool: dict[str, list[int]] = {}
    n = 0
    deaths = 0
    stop = "budget"
    print(f"{title} start", flush=True)

    for _ in range(cap):
        if agent.is_done([], obs):
            stop = "is_done"
            break
        state["lvl"], state["step"] = lvl, n
        # ⛔ NO OUT-OF-BAND BID SWEEP. `detect` IS NOT A PURE QUERY: `socketmerge.detect` resets
        # four of its own fields, and clonewalk, ledge, paint_flood, railpeg, swivel and toggle all
        # assign to `self` inside it. Sweeping every tool at each level start therefore CHANGED THE
        # RUN — measured: dc22 came back as `gantry` holding all 925 actions where the unswept run
        # is gantry 12, phase_grid 12, then graph 474. Bids are now captured ONLY inside
        # `_redecide`, where the harness sweeps anyway, so the instrument perturbs at points that
        # were already being perturbed rather than inventing new ones.
        act = agent.choose_action([], obs)
        tool = str(agent._current)
        data = act.action_data.model_dump() if getattr(act, "action_data", None) else None
        obs = env.step(act, data=data) if data else env.step(act)
        if obs is None:
            stop = "obs_none"
            break
        n += 1
        board = frame_2d(obs).astype(np.int16) if has_frame(obs) else None
        ch = 0
        if prev_board is not None and board is not None and prev_board.shape == board.shape:
            ch = int(board_changed(prev_board, board))
        r = per_tool.setdefault(tool, [0, 0])
        r[0] += 1
        r[1] += 1 - ch
        prev_board = board
        now = levels_completed(obs)
        # ⛔ `> lvl`, never `!=` — a collapse and a clear are the same boolean (rule 7f).
        if now > lvl:
            lvl = now
        st = str(getattr(obs, "state", ""))
        if st.endswith("GAME_OVER"):
            deaths += 1
            # ⛔ The ENUM MEMBER, as score_efficiency.py uses it. `.reset()` is
            # `admorphiq.types.GameAction`'s API and raises here — on the death path only, which is
            # how two runs exited 0 with an empty log this afternoon.
            obs = env.step(GameAction.RESET)
            if obs is None:
                stop = "obs_none_after_reset"
                break
            prev_board = frame_2d(obs).astype(np.int16) if has_frame(obs) else None
            continue
        if st.endswith("WIN"):
            stop = "win"
            break
        if n % 250 == 0:
            print(f"{title} n={n} lvl={lvl} tool={tool}", flush=True)

    out = {
        "nosweep": bool(os.environ.get("BID_NOSWEEP")),
        "game": title, "stop": stop, "deaths": deaths, "levels": lvl, "actions": n,
        "human": human, "switches": switches, "retired_empty": retire,
        "per_tool": {k: v for k, v in sorted(per_tool.items(), key=lambda kv: -kv[1][0])},
    }
    print(json.dumps(out), flush=True)


if __name__ == "__main__":
    main()
