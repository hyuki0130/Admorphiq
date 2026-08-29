"""What should the harness do when NO tool has a plan?

`UnifiedAgent._probe` fills such a turn with `simple_ids[0]` -- the lowest-numbered key -- and the
engine frequently refuses it. Measured across the 25 games: ls20 8 fills / 8 INERT, dc22 16/14,
lf52 13/8, bp35 8/4, and thirteen games with no fills at all. A refused action is not free: it is
one action of the RHAE denominator, and on ls20 it is also two units of fuel, because that game
decrements its allowance for any of ACTION1-4 whether or not the avatar actually moves
(`ls20.py` calls the counter after the wall test, not before it).

First argument is the POLICY so every candidate is measured at once, one process per policy:

  0  the shipped rule: the lowest available id
  1  UNTRIED first, then the id observed to change this board most often, LRU to break ties
  2  least recently used
  3  the id observed to change this board most often (no untried priority)
  4  avoid the id that was just refused, otherwise the shipped rule
  5  seeded round-robin over the available ids -- a CONTROL, so a gain can be attributed to the
     policy's reasoning rather than merely to "stop pressing the same key"
  6  least recently used among ids that have EVER changed this board, else LRU over all
  7  policy 1, and the ACTION6 fallback spreads over a coarse grid instead of the frame centre

⛔ A turn cannot be skipped, and this was checked rather than assumed: `scripts/score_efficiency.py`
calls `choose_action()` and steps the engine on every iteration, so there is no return value that
costs no action. "Propose nothing and let the turn pass" is void.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, "src")

ROOT = Path(__file__).resolve().parent.parent


def install(policy: int):
    """Replace the fallback probe with the numbered policy; count what it does."""
    from admorphiq.harness import loop as L

    log = {"fills": 0, "inert": 0, "picks": {}}

    def rates(self):
        """Per simple-action id: [times tried, times the BOARD changed]."""
        out: dict[int, list[int]] = {}
        for prev, step, nxt in self._transitions:
            if step[1] is not None:
                continue
            seen = out.setdefault(step[0], [0, 0])
            seen[0] += 1
            if prev.shape == nxt.shape and L._segment_board_changed(prev, nxt):
                seen[1] += 1
        return out

    def last_use(self, aid):
        for i in range(len(self._transitions) - 1, -1, -1):
            step = self._transitions[i][1]
            if step[1] is None and step[0] == aid:
                return i
        return -1

    def pick(self, simple_ids):
        seen = rates(self)
        if policy == 2:
            return min(simple_ids, key=lambda a: (last_use(self, a), a))
        if policy == 4:
            if self._transitions:
                prev, step, nxt = self._transitions[-1]
                if step[1] is None and step[0] in simple_ids and prev.shape == nxt.shape \
                        and not L._segment_board_changed(prev, nxt):
                    rest = [a for a in simple_ids if a != step[0]]
                    if rest:
                        return min(rest, key=lambda a: (last_use(self, a), a))
            return simple_ids[0]
        if policy == 5:
            return simple_ids[len(self._transitions) % len(simple_ids)]
        if policy == 6:
            live = [a for a in simple_ids if seen.get(a, [0, 0])[1] > 0]
            return min(live or simple_ids, key=lambda a: (last_use(self, a), a))
        if policy in (1, 7):
            untried = [a for a in simple_ids if a not in seen]
            if untried:
                return untried[0]
        if policy in (1, 3, 7):
            def rank(a):
                tried, changed = seen.get(a, [0, 0])
                return (-(changed / tried if tried else 0.0), last_use(self, a), a)
            return min(simple_ids, key=rank)
        return simple_ids[0]

    def probe(self, simple_ids, action6):
        log["fills"] += 1
        if simple_ids:
            got = pick(self, simple_ids)
            log["picks"][got] = log["picks"].get(got, 0) + 1
            return [(got, None)]
        if action6:
            if policy == 7:
                cells = [(16, 16), (48, 16), (16, 48), (48, 48), (32, 32)]
                got = cells[len(self._transitions) % len(cells)]
            else:
                got = (32, 32)
            log["picks"][f"click{got}"] = log["picks"].get(f"click{got}", 0) + 1
            return [(6, got)]
        log["picks"][7] = log["picks"].get(7, 0) + 1
        return [(7, None)]

    L.UnifiedAgent._probe = probe
    return log


def main() -> None:
    policy = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    title = sys.argv[2] if len(sys.argv) > 2 else "ls20"
    cap = int(sys.argv[3]) if len(sys.argv) > 3 else 4000
    log = install(policy)

    import numpy as np
    from arc_agi import Arcade, OperationMode

    from admorphiq.harness import loop as L
    from admorphiq.harness.loop import UnifiedAgent
    from admorphiq.harness.registry import default_tools
    from admorphiq.tools.base import frame_2d, has_frame

    def _no_llm(*_a, **_k):
        raise RuntimeError("LLM-free: the signature fallback is what this measures")

    meta = json.loads(next((ROOT / "environment_files" / title).glob("*/metadata.json")).read_text())
    baselines = meta["baseline_actions"]

    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    info = next(i for i in arcade.get_environments()
                if (i.title or i.game_id).lower().startswith(title))
    env = arcade.make(info.game_id)
    obs = env.reset()
    agent = UnifiedAgent(default_tools(), _no_llm, giveup=cap, stall=80, ctx_budget=6000)
    frames = [obs]
    levels = 0
    start = 0
    per_level: list[dict] = []
    step = 0
    for step in range(cap):
        if agent.is_done(frames, obs):
            break
        before = log["fills"]
        prev = frame_2d(obs).astype(np.int16) if has_frame(obs) else None
        act = agent.choose_action(frames, obs)
        was_fill = log["fills"] > before
        data = act.action_data.model_dump() if getattr(act, "action_data", None) else None
        obs = env.step(act, data=data) if data else env.step(act)
        frames.append(obs)
        if was_fill and prev is not None and has_frame(obs):
            now = frame_2d(obs).astype(np.int16)
            if prev.shape == now.shape and not L._segment_board_changed(prev, now):
                log["inert"] += 1
        now_lv = int(getattr(obs, "levels_completed", levels) or 0)
        if now_lv > levels:
            used = step + 1 - start
            human = baselines[levels] if levels < len(baselines) else None
            per_level.append({"level": levels + 1, "actions": used, "human": human,
                              "score": round(min(human / used, 1.0) ** 2, 4) if human else None})
            print(f"  p{policy} {title} lvl {levels + 1}: {used} actions (human {human}) "
                  f"fills {log['fills']}", flush=True)
            levels = now_lv
            start = step + 1
        elif now_lv < levels:
            print(f"  p{policy} {title} COLLAPSE {levels} -> {now_lv}", flush=True)
            levels = now_lv
        if step % 200 == 0:
            print(f"  p{policy} {title} .. step {step} lvl {levels} fills {log['fills']}",
                  flush=True)
    num = sum((i + 1) * (p["score"] or 0) for i, p in enumerate(per_level))
    den = sum(range(1, len(baselines) + 1))
    print(json.dumps({
        "policy": policy, "game": title, "levels": levels, "actions": step + 1,
        "game_score": round(num / den, 4), "fills": log["fills"], "inert": log["inert"],
        "picks": {str(k): v for k, v in log["picks"].items()},
        "per_level": [(p["level"], p["actions"]) for p in per_level],
    }))


if __name__ == "__main__":
    main()
