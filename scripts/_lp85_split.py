"""Where lp85's actions go, and what each candidate probing rule does to them.

lp85 clears all eight levels and loses only EFFICIENCY: level 4 spends 33 actions against a human
baseline of 16, and the game's own cycle data says the level is winnable in TWELVE presses
(scripts/_lp85_oracle.py). Level 4 also draws SIXTEEN button sprites over only FOUR distinct
controls, and `cyclepress` presses every unpressed control once before it plans -- sixteen actions
of discovery on a level whose whole human budget is sixteen.

VARIANT is the first argument so every candidate rule is measured at once with scripts/pfan.sh,
one process per rule, on the same game through the same harness.

  1  INC              stop pressing unpressed controls once the model on hand yields a plan
  2  INC+APP          ... and press one control of each unseen APPEARANCE class first
  3  INC+APPALL       every appearance class must be sampled before the early stop is allowed
  4  ADOPT0           give a pressed control's permutation to its whole appearance class, unconfirmed
  5  ADOPT2           ... confirmed, so the class is never probed again
  6  TIGHT            confirmations bounded at ONE plan length instead of max(2, len(plan))
  7  --               control: the shipped rule, unmodified
  8  INC+APP+TIGHT
  9  ADOPT2+TIGHT
 10  INC+APPALL+TIGHT
 11  NONUDGE          drop the off-board click the solved-board test spends
 12  INC+APP+NONUDGE

⚠️ Appearance is NOT a sound proxy in general and this is measured: seven of the eight levels draw
two or more DIFFERENT controls with identical pixels (scripts/_lp85_appear.py). Level 4 is the one
level where appearance and control coincide. That is why ADOPT* is measured rather than assumed.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, "src")

META = Path(__file__).resolve().parent.parent / "environment_files/lp85/305b61c3/metadata.json"

FEATURES = {
    1: {"INC"}, 2: {"INC", "APP"}, 3: {"INC", "APPALL"},
    4: {"ADOPT0"}, 5: {"ADOPT2"}, 6: {"TIGHT"}, 7: set(),
    8: {"INC", "APP", "TIGHT"}, 9: {"ADOPT2", "TIGHT"}, 10: {"INC", "APPALL", "TIGHT"},
    11: {"NONUDGE"}, 12: {"INC", "APP", "NONUDGE"},
}


def _class_of(g, cell):
    """(colour, size, height, width) of the 4-connected same-colour region under a press point."""
    n = len(g)
    y0, x0 = cell
    col = int(g[y0][x0])
    seen = {(y0, x0)}
    stack = [(y0, x0)]
    while stack:
        y, x = stack.pop()
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            ny, nx = y + dy, x + dx
            if 0 <= ny < n and 0 <= nx < n and (ny, nx) not in seen and int(g[ny][nx]) == col:
                seen.add((ny, nx))
                stack.append((ny, nx))
    ys = [c[0] for c in seen]
    xs = [c[1] for c in seen]
    return (col, len(seen), max(ys) - min(ys), max(xs) - min(xs))


def install(feat: set[str]) -> dict:
    from admorphiq.tools import cyclepress as cp

    log: dict = {"acts": []}
    base_probe = cp.CyclePressTool._next_probe
    base_propose = cp.CyclePressTool.propose
    base_nudge = cp.CyclePressTool._nudge

    def classes(self, controls):
        g = self._last_frame
        if g is None:
            return {}
        out = {}
        for c in controls:
            try:
                out[c] = _class_of(g, c)
            except Exception:
                out[c] = c
        return out

    def next_probe(self, controls, tiles, marks):
        unpressed = [c for c in controls if c not in self._pairs and c not in self._inert]
        if unpressed and (feat & {"ADOPT0", "ADOPT2"}):
            cls = classes(self, controls)
            for c in list(unpressed):
                for other in list(self._perm):
                    if other != c and cls.get(other) is not None and cls.get(other) == cls.get(c):
                        self._perm[c] = self._perm[other]
                        self._pairs[c] = list(self._pairs.get(other, []))
                        self._streak[c] = cp._CONFIRM_STREAK if "ADOPT2" in feat else 0
                        break
            unpressed = [c for c in controls if c not in self._pairs and c not in self._inert]
        if unpressed and ("INC" in feat):
            if feat & {"APP", "APPALL"}:
                cls = classes(self, controls)
                seen = {cls.get(c) for c in controls if c in self._pairs or c in self._inert}
                fresh = [c for c in unpressed if cls.get(c) not in seen]
                if fresh:
                    if "APPALL" in feat:
                        return fresh[0]
                    unpressed = fresh + [c for c in unpressed if c not in fresh]
            if self._perm and cp.plan_presses(tiles, marks, self._perm):
                return None
            return unpressed[0]
        got = base_probe(self, controls, tiles, marks)
        if got is not None and "TIGHT" in feat and got in self._pairs and self._perm:
            ready = cp.plan_presses(tiles, marks, self._perm)
            if ready and self._confirms >= len(ready):
                return None
        return got

    def wrapped(self, controls, tiles, marks):
        got = next_probe(self, controls, tiles, marks)
        self._probe_kind = None if got is None else ("first" if got not in self._pairs
                                                     else "confirm")
        return got

    def nudge(self, controls):
        if "NONUDGE" in feat:
            self._settled += 1
            return [(6, (controls[0][1], controls[0][0]))]
        return base_nudge(self, controls)

    def propose(self, frames, obs):
        before_pairs = set(self._pairs)
        before_replans = self._replans
        before_settled = self._settled
        self._probe_kind = None
        out = base_propose(self, frames, obs)
        kind = "plan"
        if self._probe_kind == "first" or (self._pending is not None
                                           and self._pending not in before_pairs):
            kind = "first"
        elif self._probe_kind == "confirm":
            kind = "confirm"
        if self._settled > before_settled:
            kind = "nudge"
        elif self._replans > before_replans:
            kind = "replan"
        log["acts"].append(kind if out else "idle")
        return out

    cp.CyclePressTool._next_probe = wrapped
    cp.CyclePressTool.propose = propose
    cp.CyclePressTool._nudge = nudge
    return log


def main() -> None:
    variant = int(sys.argv[1]) if len(sys.argv) > 1 else 7
    cap = int(sys.argv[2]) if len(sys.argv) > 2 else 4000
    log = install(FEATURES.get(variant, set()))

    from arc_agi import Arcade, OperationMode

    from admorphiq.harness.loop import UnifiedAgent
    from admorphiq.harness.registry import default_tools

    def _no_llm(*_a, **_k):
        raise RuntimeError("LLM-free: the signature fallback is what this measures")

    baselines = json.loads(META.read_text())["baseline_actions"]
    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    info = next(i for i in arcade.get_environments()
                if (i.title or i.game_id).lower().startswith("lp85"))
    env = arcade.make(info.game_id)
    obs = env.reset()
    agent = UnifiedAgent(default_tools(), _no_llm, giveup=cap, stall=80, ctx_budget=6000)
    frames = [obs]
    levels = 0
    start = 0
    per_level: list[dict] = []
    kinds_at = 0
    step = 0
    for step in range(cap):
        if agent.is_done(frames, obs):
            break
        act = agent.choose_action(frames, obs)
        who = str(agent._current)
        data = act.action_data.model_dump() if getattr(act, "action_data", None) else None
        obs = env.step(act, data=data) if data else env.step(act)
        frames.append(obs)
        now = int(getattr(obs, "levels_completed", levels) or 0)
        if now > levels:
            span = log["acts"][kinds_at:]
            kinds_at = len(log["acts"])
            counts: dict[str, int] = {}
            for k in span:
                counts[k] = counts.get(k, 0) + 1
            used = step + 1 - start
            human = baselines[levels] if levels < len(baselines) else None
            per_level.append({
                "level": levels + 1, "actions": used, "human": human, "who": who,
                "score": round(min(human / used, 1.0) ** 2, 4) if human else None,
                "kinds": counts,
            })
            print(f"  v{variant} lvl {levels + 1} -> {now}: {used} actions "
                  f"(human {human}) {counts}", flush=True)
            levels = now
            start = step + 1
        elif now < levels:
            print(f"  v{variant} COLLAPSE {levels} -> {now} at step {step}", flush=True)
            levels = now
        if step % 100 == 0:
            print(f"  v{variant} .. step {step} lvl {levels}", flush=True)
    num = sum((i + 1) * (p["score"] or 0) for i, p in enumerate(per_level))
    den = sum(range(1, len(baselines) + 1))
    print(json.dumps({
        "variant": variant, "levels": levels, "actions": step + 1,
        "game_score": round(num / den, 4),
        "per_level": per_level,
    }))


if __name__ == "__main__":
    main()
