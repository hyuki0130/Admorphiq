"""ls20 level 7: the two things left after ordering has been ruled out in both directions.

Established, so this probe is not re-deriving it:

  `_ls20_gap32.py`    the target cell is walkable from tick 54, the demanded token enters the rule
                      closure at tick 168, and the winning route appears on that exact tick. The
                      cost is TOKEN LEARNING, not search and not the map.
  `_ls20_marklag.py`  colour sighted@9 pressed@66, shape sighted@10 pressed@68, and the third mark
                      SIGHTED AT TICK 30 AND PRESSED AT 137 — a lag of 107 ticks on the one mark
                      that gates the closure. Ranking marks ahead of the frontier LOSES the level.
  `_ls20_pressnear.py` finishing a changer's table while standing on it loses at EVERY radius from
                      2 to unbounded (6/7, ~504 actions, the third mark never learned) — the sink
                      the tool's own docstring names.

So policy ordering has now been swept in both directions and both lose. What is left are two facts
about the third mark specifically, neither of which is an ordering change:

  1. It PATROLS, and `_motion_of` wants `_MOTION_MIN` = 3 pairs before it will believe a rigid
     motion. The level demands two quarter-turns, so the three identification presses leave the
     token one turn PAST the demand and the route found at 168 is thirty-three steps — a second
     round trip to the same far corner. Two pairs is not a looser test: the uniqueness clause that
     lets `_motion_of` say NO is untouched, only the amount of evidence a unique answer needs.
  2. The AMBUSH only runs while the mark is VISIBLE. `_intercept` — stand at the far end of the
     remembered beat and let the patrol come back — is called for marks in `self.mark`, i.e. drawn
     in the frame right now. Once the mover leaves the fog disc it survives only in `self.sighted`,
     and the plan then walks to the single cell it was last seen in, finds it empty, marks the
     sighting checked and leaves for fifty ticks. The lane is remembered; the ambush is not used.

  0  control        1  _MOTION_MIN 2        2  _MOTION_MIN 4
  3  ambush a SIGHTED mover at its remembered beat, not only a visible one
  4  1 + 3          5  control repeated (determinism)

Expected feedback: 237 is the control and 186 the human baseline at which ls20 scores 1.0000. A
variant below 237 with `levels` = 7 is a real gain; anything at 237 exactly is inert and anything
above it with `levels` = 6 says the mechanism it removed was load-bearing.
"""
from __future__ import annotations

import json
import sys
from collections import Counter

NVAR = 6
# motion_min, ambush_sighted
CFG: dict[int, tuple[int, bool]] = {
    0: (3, False),
    1: (2, False),
    2: (4, False),
    3: (3, True),
    4: (2, True),
    5: (3, False),
}


def _mk(variant: int):
    from admorphiq.tools import fogscout as FS

    motion_min, ambush = CFG[variant]
    FS._MOTION_MIN = motion_min

    class V(FS.FogScoutTool):
        """FogScoutTool with the motion-evidence threshold and/or the offscreen ambush swapped."""

        def __init__(self) -> None:
            self.dry = 0
            self._was_zero = False
            self.pair_at: dict[object, int] = {}
            self.win_at: int | None = None
            super().__init__()

        def _plan(self, shape):
            if not ambush:
                return super()._plan(shape)
            # Present each REMEMBERED mover as if it were drawn where it was last seen, so the
            # plan's own interception clause runs on it. Removed again immediately: a remembered
            # mark is not a present one, and `_ingest` must keep seeing that distinction.
            added = []
            for sig, c in list(self.sighted.items()):
                if c in self.mark or len(self.lane.get(sig, ())) <= 1:
                    continue
                if sig in self.kind or sig in self.inert or sig in self.refill_marks:
                    continue
                self.mark[c] = sig
                added.append(c)
            try:
                return super()._plan(shape)
            finally:
                for c in added:
                    self.mark.pop(c, None)

        def propose(self, frames, obs):
            out = super().propose(frames, obs)
            for sig in self.kind:
                self.pair_at.setdefault(sig, self.tick)
            if self.win_at is None and self.pos is not None and self.goal is not None \
                    and self.target is not None and self.reason.split("[")[0] == "win":
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
    out = {"arg": arg, "v": variant, "cfg": list(CFG[variant]), "levels": lvl, "total": n,
           "lvl7": per_level[6], "dry": fog.dry, "winat": fog.win_at,
           "pairs": sorted(fog.pair_at.values()), "why": dict(fog.census.most_common(8))}
    print(json.dumps(out), flush=True)


if __name__ == "__main__":
    main()
