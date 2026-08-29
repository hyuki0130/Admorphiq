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
    13: {"POOL"}, 14: {"POOL", "INC"}, 15: {"POOL", "INC", "APP"},
    16: {"INV"}, 17: {"POOL", "INV"}, 18: {"POOL", "INV", "INC"},
    19: {"DEPTH"}, 20: {"DEPTH", "INC"}, 21: {"DEPTH", "POOL", "INC"},
    22: {"DEPTH", "POOL", "INV", "INC"},
    23: {"INCC"}, 24: {"POOL", "INCC"}, 25: {"DEPTH", "POOL", "INCC"},
    26: {"DEPTH", "POOL", "INV", "INCC"}, 27: {"POOL", "INCC", "APP"},
    28: {"DEPTHB"}, 29: {"DEPTHB", "INC"}, 30: {"DEPTHB", "INV", "INC"},
    31: {"INV", "INC", "APPALL"}, 32: {"INV", "TIGHT"},
    33: {"DEPTHB", "INV", "INC", "APPALL"}, 34: {"DEPTHB", "INV"},
    35: {"DEPTHB", "INV", "TIGHT"},
    36: {"DEPTHB", "INV", "INCC", "APPALL"}, 37: {"DEPTHB", "INC", "APPALL"},
    38: {"DEPTHB", "INV", "INC", "APP"},
    39: {"DEPTHB", "INV", "INC", "APPALL", "TIGHT"},
    40: {"DEPTHB", "INV", "INC", "APPALL", "NONUDGE"},
    41: {"DEPTHB", "INC", "APPALL", "TIGHT"},
    42: {"DEPTHB", "INV", "INCC", "APPALL", "TIGHT"},
    43: {"DEPTHB", "INV", "INC", "APPALL", "POOL"},
    44: {"DEPTHB", "APPALL"}, 45: {"DEPTHB", "INV", "APPALL"},
    46: {"DEPTHB", "INV", "APPALL", "TIGHT"}, 47: {"DEPTHB", "INV", "INC"},
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

    if "INCC" in feat:
        feat = feat | {"INC"}

    log: dict = {"acts": []}
    base_probe = cp.CyclePressTool._next_probe
    base_propose = cp.CyclePressTool.propose
    base_nudge = cp.CyclePressTool._nudge
    base_learn = cp.CyclePressTool._learn

    def replays_all(perm, pairs):
        return bool(pairs) and all(cp._replays(perm, b, a) for b, a in pairs)

    def learn(self, tiles):
        """Fold the press in, then look for controls the SAME permutation already explains.

        ⛔ The point measured on lp85 level 4: sixteen buttons drive four controls, one press each
        recovers SIX distinct permutations (two of them wrong) and NO press sequence to the
        markers exists until the twenty-sixth action. Recovery from one press is ambiguous, and
        the four presses that are really the same control are four separate single presses. Pooling
        their evidence makes the recovery as strong as four presses of one button, without
        spending an action — and it rests on observed transitions, never on how a button LOOKS,
        which is unsound here: seven of the eight levels draw different controls identically.
        """
        control = self._pending
        base_learn(self, tiles)
        if control is None or control not in self._pairs:
            return
        if "POOL" in feat:
            mine = self._pairs[control]
            for other in list(self._pairs):
                if other == control or self._pairs[other] is mine:
                    continue
                joint = self._pairs[other] + [p for p in mine if p not in self._pairs[other]]
                if len(joint) <= len(self._pairs[other]):
                    continue
                perm = cp.recover_permutation(self._slots, joint, self._pitch)
                if perm is None:
                    continue
                for c in (control, other):
                    self._perm[c] = perm
                    self._pairs[c] = joint
                    if len(joint) >= 2:
                        self._streak[c] = cp._CONFIRM_STREAK
                break
        if "INV" in feat:
            mine = self._perm.get(control)
            if mine is None:
                return
            back = {v: k for k, v in mine.items()}
            for other, perm in list(self._perm.items()):
                if other == control or perm != back:
                    continue
                if replays_all(mine, self._pairs[control]) and \
                        replays_all(perm, self._pairs[other]):
                    self._streak[control] = cp._CONFIRM_STREAK
                    self._streak[other] = cp._CONFIRM_STREAK
                    break

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

    def stop_now(self, tiles, marks):
        """Is the model on hand good enough to stop probing and start pressing?

        ⛔ "A plan exists" is NOT good enough, and this is measured: on level 1 -- two controls,
        budget thirteen -- stopping at the first plan took the level from 7 actions to 27, because
        a permutation that replays one press always exists and the plan built on it is fiction.
        INCC additionally requires every control the plan USES to have predicted a press.
        """
        if not self._perm:
            return False
        ready = cp.plan_presses(tiles, marks, self._perm)
        if not ready:
            return False
        if "INCC" in feat:
            return all(self._streak.get(c, 0) >= cp._CONFIRM_STREAK for c in set(ready))
        return True

    def next_probe(self, controls, tiles, marks):
        unpressed = [c for c in controls if c not in self._pairs and c not in self._inert]
        if feat & {"DEPTH", "DEPTHB"}:
            # ⛔ Breadth-first probing presses every button once before any of them is trusted,
            # and on lp85 level 4 that is sixteen actions against a human budget of sixteen.
            # Depth-first spends the same evidence on ONE control until its permutation predicts
            # a press, which is also the only press order that can be on-plan by accident: the
            # level's exact solution is one control four times and another eight times.
            self._settle()
            owed = [c for c in controls
                    if c in self._pairs and self._streak.get(c, 0) < cp._CONFIRM_STREAK
                    and len(self._pairs[c]) < cp._MAX_PRESSES]
            if owed:
                # ⛔ Depth-first has to answer to the same allowance the shipped confirmations
                # do. Ungated it takes level 1 -- two controls, thirteen actions -- from 7 to 59,
                # because the level is LOST and retried and the score pays for both attempts.
                left = self._budget.remaining(self._last_frame)
                afford = "DEPTHB" not in feat or (
                    left is not None and left >= len(owed) + cp._PROBE_RESERVE)
                if afford:
                    if "INC" in feat and stop_now(self, tiles, marks):
                        return None
                    return owed[0]
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
            if stop_now(self, tiles, marks):
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
    cp.CyclePressTool._learn = learn
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
