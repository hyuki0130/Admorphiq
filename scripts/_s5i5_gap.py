"""s5i5 level 7 — NAME the disagreement that kills swivel, cell by cell.

`scripts/_s5i5_run7.py` measured the death (action 224, 32 into level 7) and
`scripts/_s5i5_die.py` measures which of the five `_dead` sites fires. This one answers the next
question in the same breath rather than after it (rule 7h): WHICH CELLS disagree.

`_agrees` compares the model's predicted occupancy against `solid_cells` of the frame and returns
False on any mismatch. Three different defects produce that:

  * the turn or the grow is mispredicted for one bar — the difference is a bar-shaped block;
  * a bar has moved partly off the visible grid, so the frame legitimately shows less than the
    model holds — the difference is clipped at an edge;
  * the reading of what is FURNITURE drifted — the difference is scattered.

The shape of the difference tells them apart, so it is printed: the missing and extra cells, their
bounding boxes, and the click that preceded them.

Run:  bash scripts/pfan.sh s5i5gap scripts/_s5i5_gap.py 1 "" 2
"""
from __future__ import annotations

import json
import sys

sys.path.insert(0, "src")

TITLE = "s5i5"
STUCK = 6


def main() -> None:
    _job = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    import numpy as np

    import admorphiq.tools.swivel as sv

    found: list[dict] = []
    last_click: list = [None]

    orig = sv.SwivelArmTool._agrees

    def agrees(self, g, cfg):
        ok = orig(self, g, cfg)
        if ok or len(found) >= 3:
            return ok
        want = set()
        for box, _e in cfg.bars:
            want |= {(y, x) for y in range(box[0], box[2] + 1)
                     for x in range(box[1], box[3] + 1)}
        for box in cfg.freight:
            want |= {(y, x) for y in range(box[0], box[2] + 1)
                     for x in range(box[1], box[3] + 1)}
        if self._model.wall is not None:
            want |= self._model.static
        want -= self._chrome
        boxes = [w.box for w in self._widgets]
        seen, marked = sv.solid_cells(g, self._marker or 0, boxes)
        on = {c for c in want if 0 <= c[0] < g.shape[0] and 0 <= c[1] < g.shape[1]}
        extra = sorted(seen - on)              # the frame shows solid where the model says empty
        missing = sorted((on - seen) - marked)  # the model says solid where the frame shows nothing

        def bbox(cs):
            if not cs:
                return None
            ys = [c[0] for c in cs]
            xs = [c[1] for c in cs]
            return [min(ys), min(xs), max(ys), max(xs)]

        found.append({
            "click": last_click[0],
            "n_extra": len(extra), "extra_bbox": bbox(extra), "extra": extra[:40],
            "n_missing": len(missing), "missing_bbox": bbox(missing), "missing": missing[:40],
            "bars": [[list(b), e] for b, e in cfg.bars],
            "colours": list(self._model.colours),
            "n_offgrid_bars": sum(1 for b, _e in cfg.bars
                                  if b[0] < 0 or b[1] < 0 or b[2] > 63 or b[3] > 63),
            "extra_colours": sorted({int(np.asarray(g)[y, x]) for y, x in extra[:200]}),
        })
        return ok

    sv.SwivelArmTool._agrees = agrees

    from arc_agi import Arcade, OperationMode

    from admorphiq.harness.loop import UnifiedAgent
    from admorphiq.harness.registry import default_tools

    def _no_llm(*_a, **_k):
        raise RuntimeError("LLM-free")

    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    info = next(i for i in arcade.get_environments()
                if (i.title or i.game_id).lower().startswith(TITLE))
    env = arcade.make(info.game_id)
    obs = env.reset()
    agent = UnifiedAgent(default_tools(), _no_llm, giveup=400, stall=80, ctx_budget=6000)
    sw = agent.tools.get("swivel")
    frames = [obs]
    lvl = 0
    plan_at_death = None
    step = 0
    for step in range(400):
        if agent.is_done(frames, obs):
            break
        act = agent.choose_action(frames, obs)
        data = act.action_data.model_dump() if getattr(act, "action_data", None) else None
        last_click[0] = [step + 1, str(agent._current), (data or {}).get("x"),
                         (data or {}).get("y"),
                         len(sw._plan) if sw else -1,
                         list(sw._pending) if (sw and sw._pending) else None]
        obs = env.step(act, data=data) if data else env.step(act)
        frames.append(obs)
        lvl = int(getattr(obs, "levels_completed", lvl) or 0)
        if sw is not None and sw._dead and plan_at_death is None:
            plan_at_death = step + 1
        if found:
            break
    print(json.dumps({"job": 1, "level": lvl, "dead_at": plan_at_death,
                      "actions": step + 1, "disagreements": found}))


if __name__ == "__main__":
    main()
