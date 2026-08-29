"""ls20 level 7: how long does a changer sit SEEN-BUT-UNPRESSED before its rule is learned?

`scripts/_ls20_gap32.py` settled the previous round's open question and refuted its framing. The
goal cell is walkable from tick 54; the demanded token enters the rule closure at tick 168; and the
winning route appears on that exact tick. So there is no 32-tick search defect — the whole of the
gap is TOKEN LEARNING, and inside it one window dominates:

    t=54   goal and demanded token known, target cell already reachable
    t=66   colour mark: first pair
    t=68   shape mark: first pair
    t=137  THIRD mark: first pair          <- 69 ticks with nothing learned
    t=140  third mark recognised as a rigid motion (3 pairs)
    t=168  shape table reaches six pairs -> demanded token in closure -> win route

This probe asks the only question that decides whether that 69-tick window is recoverable: was the
third mark ALREADY VISIBLE during it? `_plan` runs the frontier sweep (`map`) BEFORE the unlearned-
mark clause, so a mark that is sighted early is not visited until every frontier is exhausted. If
the sig is first seen far before 137, the window is ordering, not discovery.

  first_seen[sig]   the tick a mark's signature first appears anywhere on the board
  first_pair[sig]   the tick its table gets its first entry
  lag               the difference — the recoverable part, if any

Variants (all inside the tool's own plan/identity layer, level-7 actions with `levels` held at 7):

  0  instrument only (control; expect 237)
  1  unlearned MARKS ranked ahead of the frontier sweep
  2  the same, but only once the goal and the demanded token are known
  3  mark identity made translation-invariant, so the same glyph drawn at two different sub-cell
     offsets is ONE kind and a press on either teaches both
  4  3 + 1        5  3 + 2        6  _SIGHT_RETRY 20 (re-check a stale sighting sooner)
  7  1 + 6        8  control repeated (determinism)        9  3 + 6
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from typing import Any

NVAR = 10
# mark_first, mark_first_after_target, norm_ident, sight_retry
CFG: dict[int, tuple[bool, bool, bool, int]] = {
    0: (False, False, False, 0),
    1: (True,  False, False, 0),
    2: (False, True,  False, 0),
    3: (False, False, True,  0),
    4: (True,  False, True,  0),
    5: (False, True,  True,  0),
    6: (False, False, False, 20),
    7: (True,  False, False, 20),
    8: (False, False, False, 0),
    9: (False, False, True,  20),
}


def _mk(variant: int):
    from admorphiq.tools import fogscout as FS

    mark_first, mark_after, norm_ident, retry = CFG[variant]

    if norm_ident:
        _orig_mark = FS.cell_mark

        def _norm_mark(blk, ground):
            sig = _orig_mark(blk, ground)
            if sig is None:
                return None
            y0 = min(y for y, _, _ in sig)
            x0 = min(x for _, x, _ in sig)
            return frozenset((y - y0, x - x0, c) for y, x, c in sig)

        FS.cell_mark = _norm_mark
    if retry:
        FS._SIGHT_RETRY = retry

    class V(FS.FogScoutTool):
        """FogScoutTool with the seen-vs-pressed instrument and one policy swapped in."""

        def __init__(self) -> None:
            self.first_seen: dict[Any, int] = {}
            self.first_pair: dict[Any, int] = {}
            self.trace: list[dict[str, Any]] = []
            self.dry = 0
            self._was_zero = False
            super().__init__()

        def _unlearned(self) -> Any:
            def f(sig):
                return (sig not in self.kind and sig not in self.inert
                        and sig not in self.refill_marks)
            return f

        def _plan(self, shape):
            if mark_first or (mark_after and self.goal is not None and self.target is not None):
                if self.goal is not None and self.target is not None:
                    win = self._search(
                        shape, lambda c, t: c == self.goal and t == self.target, False)
                    if win is not None:
                        self._say("win")
                        return win
                un = self._unlearned()
                fresh = set()
                for c, sig in self.mark.items():
                    if c == self.goal or not un(sig):
                        continue
                    fresh.add(self._intercept(c, sig, shape))
                fresh |= {c for sig, c in self.sighted.items()
                          if c != self.goal and un(sig)
                          and self.tick - self.checked.get(sig, -FS._SIGHT_RETRY) >= FS._SIGHT_RETRY}
                if self.pos in fresh:
                    hold = self._hold(shape)
                    if hold is not None:
                        self._say("wait")
                        return hold
                    fresh.discard(self.pos)
                if fresh:
                    step = self._walk(shape, lambda c: c in fresh)
                    if step is not None:
                        self._say("mark-first")
                        return step
            return super()._plan(shape)

        def propose(self, frames, obs):
            out = super().propose(frames, obs)
            for sig in set(self.mark.values()) | set(self.sighted):
                self.first_seen.setdefault(sig, self.tick)
            for sig in self.kind:
                self.first_pair.setdefault(sig, self.tick)
            if self.bar_drop:
                z = self.moves_left() == 0
                if z and not self._was_zero:
                    self.dry += 1
                self._was_zero = z
            if variant == 0:
                self.trace.append({
                    "t": self.tick, "why": self.reason.split("[")[0], "pos": list(self.pos or ()),
                    "marks": len(self.mark), "sighted": len(self.sighted),
                    "kinds": len(self.kind), "inert": len(self.inert),
                    "refill": len(self.refill_marks), "stood": len(self.stood),
                })
            return out

    return V()


def main() -> None:
    from arc_agi import Arcade, OperationMode

    from admorphiq.harness.loop import UnifiedAgent
    from admorphiq.harness.registry import default_tools

    arg = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    variant = (arg - 1) % NVAR

    def _no_llm(*_a, **_k):
        raise RuntimeError("LLM-free")

    fog = _mk(variant)
    tools = [fog if t.name == "fogscout" else t for t in default_tools()]

    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    info = next(i for i in arcade.get_environments()
                if (i.title or i.game_id).lower().startswith("ls20"))
    env = arcade.make(info.game_id)
    obs = env.reset()
    agent = UnifiedAgent(tools, _no_llm, giveup=4000, stall=80, ctx_budget=6000)
    frames = [obs]
    lvl = 0
    per_level: Counter[int] = Counter()
    n = 0
    print(f"v{variant} start", flush=True)
    for _ in range(4000):
        if agent.is_done(frames, obs):
            break
        act = agent.choose_action(frames, obs)
        data = act.action_data.model_dump() if getattr(act, "action_data", None) else None
        obs = env.step(act, data=data) if data else env.step(act)
        frames.append(obs)
        n += 1
        now = int(getattr(obs, "levels_completed", 0) or 0)
        per_level[lvl] += 1
        # ⛔ `> lvl`, never `!=` — a collapse and a clear are the same boolean (rule 7f).
        if now > lvl:
            lvl = now
        if n % 120 == 0:
            print(f"v{variant} n={n} lvl={lvl + 1} l7={per_level[6]}", flush=True)
    lag = sorted((fog.first_pair.get(s, -1), fog.first_seen[s]) for s in fog.first_seen)
    if variant == 0:
        with open(f"/tmp/ls20marklag_trace_{arg}.json", "w") as fh:
            json.dump({"trace": fog.trace,
                       "seen": {str(sorted(s)): t for s, t in fog.first_seen.items()},
                       "pair": {str(sorted(s)): t for s, t in fog.first_pair.items()}}, fh,
                      default=str)
    out = {"arg": arg, "v": variant, "levels": lvl, "total": n, "lvl7": per_level[6],
           "dry": fog.dry, "nseen": len(fog.first_seen), "nkind": len(fog.first_pair),
           "lag": lag[:14]}
    print(json.dumps(out), flush=True)


if __name__ == "__main__":
    main()
