"""s5i5 level 7 — WHAT HAPPENS when swivel's plan executes, and which lever changes it.

Job 1 of `scripts/_s5i5_swiv.py` already settled the first three questions and they are NOT what
was assumed:

  * the model is EXACT — six bars with the source's own colours, the chain c11 -> c14 -> c9 -> c12,
    both riders and both destinations, the board-spanning wall correctly left as 417 static cells;
  * `plan()` DOES return a plan on this level — 25 clicks, via the one-rider-at-a-time branch;
  * the only thing missing from the alphabet is **`turn c8`**: the loose bar has no slider, so
    nothing else ever reveals what it carries, and `_assemble`'s colour-recovery refuses a bar
    "nothing has told us about". The engine's own A* needs that click twice.

So the level has a plan and still dies at the engine's 200-step counter. The hypotheses for that,
all run together (rule 7h):

  G1 the plan's clicks are REFUSED — the model calls legal what the engine does not — and the
     ban/replan cycle burns the budget
  G2 the plan runs to the end and the engine does not advance: the model's `solved` is not the
     engine's win predicate (rider centre off by a cell)
  G3 `_agrees` fails mid-plan, swivel goes dead, and the rest is another tool flailing
  G4 the level dies, RESTARTS, and each fresh attempt re-pays the probe cost
  G5 the missing `turn c8` is load-bearing: with it the plan is different and works
  G6 the one-rider decomposition is the wrong shape here and the joint search is needed

Variants (`job`):
  1 as shipped                       4 joint search forced, bigger open budget
  2 + `turn c8` recovered            5 both
  3 + longer level budget (is it budget-starved at all?)
  6 both, and 1500 actions

⛔ Levels are printed as NUMBERS and compared with `>`, never `!=` (rule 7f): on this game a
GAME_OVER restarts the run and the level number falls, which reads identically to a clear.

Run:  bash scripts/pfan.sh s5i5run7 scripts/_s5i5_run7.py 6 "" 6
"""
from __future__ import annotations

import json
import sys

sys.path.insert(0, "src")

TITLE = "s5i5"
STUCK = 6


def patch(add_turn: bool, force_joint: bool, max_open: int) -> None:
    import admorphiq.tools.swivel as sv

    if max_open:
        sv._MAX_OPEN = max_open
    if force_joint:
        sv.plan = lambda model, start, moves, banned=None: (
            [] if sv.solved(model, start) else
            (sv._joint(model, start, moves, banned) if model.pairing else None))
    if add_turn:
        orig = sv.SwivelArmTool._assemble

        def assemble(self):
            """Recover a TURN whose bar no other control ever drove.

            ⛔ The shipped rule refuses this: a bar nothing has driven has an unknown subtree, so
            assuming it carries nothing could be wrong. But a bar that is not in ANY driven bar's
            subtree and drives nothing itself is exactly the loose furniture case, and dropping
            its control costs the only click that moves it.
            """
            ok = orig(self)
            if not ok:
                return ok
            model = self._model
            have = {c for c in self._move_ctrl}
            for ctrl, (kind, _wd) in enumerate(self._controls):
                if kind != "turn" or ctrl in have:
                    continue
                colour = self._named[ctrl] if ctrl < len(self._named) else None
                owns = [i for i, c in enumerate(model.colours) if c == colour]
                if colour is None or len(owns) != 1:
                    continue
                bar = owns[0]
                if any(bar in k for k in model.kids):
                    continue          # it is carried by something; its own turn is not free
                if model.kids[bar]:
                    continue
                self._moves.append(("turn", colour, 0))
                self._move_ctrl.append(ctrl)
            return ok

        sv.SwivelArmTool._assemble = assemble


def main() -> None:
    job = int(sys.argv[1])
    add_turn = job in (2, 5, 6)
    force_joint = job in (4, 5, 6)
    cap = 1500 if job in (3, 6) else 900
    patch(add_turn, force_joint, 1_500_000 if force_joint else 0)

    from arc_agi import Arcade, OperationMode

    from admorphiq.harness.loop import UnifiedAgent
    from admorphiq.harness.registry import default_tools
    from admorphiq.tools.swivel import rider_at

    def _no_llm(*_a, **_k):
        raise RuntimeError("LLM-free")

    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    info = next(i for i in arcade.get_environments()
                if (i.title or i.game_id).lower().startswith(TITLE))
    env = arcade.make(info.game_id)
    obs = env.reset()
    tools = default_tools()
    agent = UnifiedAgent(tools, _no_llm, giveup=cap, stall=80, ctx_budget=6000)
    sw = agent.tools.get("swivel")
    frames = [obs]
    who: dict[str, int] = {}
    timeline: list[list[int]] = []          # [action, level] whenever the level MOVES
    lvl = 0
    best_lvl = 0
    arrived = None
    trace: list[dict] = []
    replans = 0
    prev_plan = None
    step = 0
    for step in range(cap):
        if agent.is_done(frames, obs):
            break
        act = agent.choose_action(frames, obs)
        who[str(agent._current)] = who.get(str(agent._current), 0) + 1
        data = act.action_data.model_dump() if getattr(act, "action_data", None) else None
        obs = env.step(act, data=data) if data else env.step(act)
        frames.append(obs)
        now = int(getattr(obs, "levels_completed", lvl) or 0)
        if now != lvl:
            timeline.append([step + 1, now])
            lvl = now
            best_lvl = max(best_lvl, now)
        if lvl >= STUCK and arrived is None:
            arrived = step + 1
        if lvl >= STUCK and sw is not None and getattr(sw, "_level", None) == lvl:
            m, cfg = sw._model, sw._cfg
            pl = len(sw._plan)
            if prev_plan is not None and pl > prev_plan:
                replans += 1
            prev_plan = pl
            if len(trace) < 400:
                trace.append({
                    "a": step + 1, "lvl": lvl, "plan": pl, "dead": bool(sw._dead),
                    "ill": len(m.illegal) if m else -1,
                    "off": len(m.offblocked) if m else -1,
                    "riders": [list(rider_at(cfg, b)) for b in m.riders] if (m and cfg) else [],
                    "places": [list(p) for p in m.places] if m else [],
                    "state": str(getattr(obs, "state", "")),
                })
    end_lvl = int(getattr(obs, "levels_completed", lvl) or 0)
    dead_at = next((t["a"] for t in trace if t["dead"]), None)
    solved_in_model = [t["a"] for t in trace
                       if t["places"] and all(p in t["riders"] for p in t["places"])]
    print(json.dumps({
        "job": job, "add_turn": add_turn, "force_joint": force_joint, "cap": cap,
        "actions_used": step + 1,
        "level_at_end": end_lvl, "best_level": best_lvl,
        "CLEARED_LEVEL7": best_lvl > STUCK,
        "level_timeline": timeline,
        "actions_to_level7": arrived,
        "who_acted": who,
        "swivel_dead_at": dead_at,
        "replans": replans,
        "model_says_solved_at": solved_in_model[:5],
        "illegal_final": trace[-1]["ill"] if trace else None,
        "offblocked_final": trace[-1]["off"] if trace else None,
        "trace_head": trace[:12],
        "trace_tail": trace[-8:],
    }))


if __name__ == "__main__":
    main()
