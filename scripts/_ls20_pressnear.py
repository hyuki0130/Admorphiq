"""ls20 level 7: a press is priced by DISTANCE, and the tool pays the far price twice.

What the two prior instruments established, so this one is not re-deriving it:

  `_ls20_gap32.py`   the target cell is walkable from tick 54 and the demanded token enters the
                     rule closure at tick 168 — the winning route appears on that exact tick, so
                     the previous round's "the search refuses a route it could return" is refuted.
                     The whole gap is TOKEN LEARNING. Motion conjugation, a deeper commutation
                     loop and press-before-map are all inert or harmful.
  `_ls20_marklag.py` first_seen vs first_pair per mark: colour seen at 9 pressed at 66, shape seen
                     at 10 pressed at 68, and the THIRD mark seen at tick 30 and not pressed until
                     137. Translation-invariant mark identity and a shorter sighting retry are both
                     exactly inert; ranking marks ahead of the frontier sweep LOSES the level (6/7,
                     ~503 actions) because a mark is dropped from that clause after ONE pair, so the
                     tables never fill.

The structure that follows. The two static changers sit two cells apart and are both pressed once,
at ticks 66 and 68, and then ABANDONED — their tables are not filled until ticks 150-168, long
after the tool has walked to the far corner for the third mark and back. The third mark patrols,
needs three pairs before its motion is believed, and those three presses leave the token one
quarter-turn PAST what the target demands, so the route found at 168 is thirty-three steps: it is a
second round trip to the same far corner.

The lever this probe measures is not "explore less" — every version of that has now lost twice. It
is that a press costs its DISTANCE: one under your feet costs two actions, one across the board
costs twenty-five. So an unmeasured press within a short radius pre-empts the frontier sweep, and
the sweep still happens, only after the cheap presses have been taken. The radius is the sweep.

  0  control (expect 237)          1..6  radius 2, 3, 4, 6, 8, 12
  7  radius 2 but only once the goal and demanded token are known
  8  unbounded radius (the degenerate case — press always beats mapping)
  9  control repeated (determinism)

Expected feedback: 237 is the control and 186 the human baseline at which ls20 scores 1.0000. A
variant below 237 with `levels` = 7 is a real gain; a flat curve across radii says the ordering is
not the cost after all and the 107-tick lag is interception, not priority.
"""
from __future__ import annotations

import json
import sys
from collections import Counter, deque
from typing import Any

NVAR = 10
CFG: dict[int, tuple[int, bool]] = {
    0: (0, False),
    1: (2, False),
    2: (3, False),
    3: (4, False),
    4: (6, False),
    5: (8, False),
    6: (12, False),
    7: (2, True),
    8: (1 << 20, False),
    9: (0, False),
}


def _mk(variant: int):
    from admorphiq.tools.fogscout import _MOVE_IDS, FogScoutTool

    radius, after_target = CFG[variant]

    class V(FogScoutTool):
        """FogScoutTool with a distance-bounded 'finish the press under your feet' clause."""

        def __init__(self) -> None:
            self.win_at: int | None = None
            self.pair_at: dict[Any, int] = {}
            self.dry = 0
            self._was_zero = False
            super().__init__()

        def _press_near(self, shape, limit: int) -> int | None:
            """First action toward an UNMEASURED press no further than ``limit`` steps away."""
            if self.pos is None or self.tok is None:
                return None
            q: deque[tuple[Any, Any, int | None, int]] = deque([(self.pos, self.tok, None, 0)])
            seen = {(self.pos, self.tok)}
            acts = [a for a in self.dirs if a in _MOVE_IDS]
            while q:
                c, t, first, d = q.popleft()
                if d >= limit:
                    continue
                for a in acts:
                    nb = self._step_to(c, a)
                    if nb == self.goal or not self._passable(nb, shape):
                        continue
                    head = a if first is None else first
                    nt = self._tok_after(nb, t)
                    if nt is None:
                        self._aim_cell = nb
                        self._plan_dist = d + 1
                        return head
                    key = (nb, nt)
                    if key in seen:
                        continue
                    seen.add(key)
                    q.append((nb, nt, head, d + 1))
            return None

        def _plan(self, shape):
            if radius and self.kind and not (after_target and self.target is None):
                if self.goal is not None and self.target is not None:
                    win = self._search(
                        shape, lambda c, t: c == self.goal and t == self.target, False)
                    if win is not None:
                        self._say("win")
                        return win
                near = self._press_near(shape, radius)
                if near is not None:
                    self._say("press-near")
                    return near
            return super()._plan(shape)

        def _win_len(self, shape) -> int | None:
            if self.pos is None or self.tok is None or self.goal is None or self.target is None:
                return None
            q: deque[tuple[Any, Any, int]] = deque([(self.pos, self.tok, 0)])
            seen = {(self.pos, self.tok)}
            acts = [a for a in self.dirs if a in _MOVE_IDS]
            while q:
                c, t, d = q.popleft()
                for a in acts:
                    nb = self._step_to(c, a)
                    if nb == self.goal:
                        if t == self.target:
                            return d + 1
                        continue
                    if not self._passable(nb, shape):
                        continue
                    nt = self._tok_after(nb, t)
                    if nt is None or (nb, nt) in seen:
                        continue
                    seen.add((nb, nt))
                    q.append((nb, nt, d + 1))
            return None

        def propose(self, frames, obs):
            out = super().propose(frames, obs)
            for sig in self.kind:
                self.pair_at.setdefault(sig, self.tick)
            if self.pos is not None and self.win_at is None and self._win_len((64, 64)) is not None:
                self.win_at = self.tick
            if self.bar_drop:
                z = self.moves_left() == 0
                if z and not self._was_zero:
                    self.dry += 1
                self._was_zero = z
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
    out = {"arg": arg, "v": variant, "radius": CFG[variant][0], "levels": lvl, "total": n,
           "lvl7": per_level[6], "dry": fog.dry, "winat": fog.win_at,
           "pairs": sorted(fog.pair_at.values()), "why": dict(fog.census.most_common(8))}
    print(json.dumps(out), flush=True)


if __name__ == "__main__":
    main()
