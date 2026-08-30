"""ls20: can `fogscout` LEARN THE MECHANIC on levels 1-6 without driving them?

Purpose. `scripts/_ls20_carry.py` measured the prize: re-installing four layout-independent facts
(`kind` = mark glyph -> token permutation, `inert`, `refill_marks`, `dirs`) at every `reset()` takes
level 7 from 231 actions to 167 -- the level to 1.0000 and the GAME to 1.0000 -- and moves the tick
at which a win route first exists from 168 to 74. That measurement carried facts learned on level 7
itself, so it is an upper bound and not a build. This probe is the build's first half: it asks
whether those same facts are OBSERVABLE on levels 1-6, which `fogscout` does not play.

The game's own source says they should be. `environment_files/ls20/*/ls20.py` gives the mechanic its
own names -- `ttfwljgohq` cycles the shape, `soyhouuebz` the colour, `rhsxkxzdjz` the rotation,
`npxgalaybz` refills the tank, `rjlbuycveu` is the goal -- and the rotation changer is on the board
from level 1, the refill ring from level 2, the colour changer from level 3. They are the SAME
sprite objects, so the glyph a mark is keyed by is identical on every level.

Method. `fogscout` becomes an AUGMENTER, which is the one flag `harness/loop.py` reads to feed a
tool transitions it did not cause. While the board is unfogged the tool never plans; it only
perceives, through its own `_ingest`, with the fog's truthful disc replaced by the whole frame. The
four facts above survive `reset()`; the map, the goal and the demanded token do not, because those
are properties of a level and not of the game.

⛔ THE INSTRUMENT IS THE RISK, not the idea. `_read_panel` finds the token display by looking
OUTSIDE the visible disc, and unfogged there is no disc — so the probe reports the panel box, the
token values read, and every learned signature PER LEVEL, and the check that matters is whether the
signatures learned on levels 1-6 are the ones the driving tool learns on level 7.

Arms (argv[1]) -- the build is now IN `src/admorphiq/tools/fogscout.py`, so the arms suppress
pieces of it rather than add them:
  1  the build, exactly as shipped (all four facts carried).
  2  watching OFF, carry OFF -- the pre-change tool. Must return the banked
     [17,101,63,66,67,100,231] / 0.912085, or nothing else here is about the shipped tool.
  3  watching ON, carry OFF  -- separates "watching changed the run" from "carrying did".
  4  watching OFF, carry ON  -- there is nothing to carry without watching, so this must equal
     arm 2; if it does not, `reset` is losing per-level state it should be losing.
  11..15 the same with the watcher REFUSING fogged frames (11 all four, 12 kind+dirs, 13 dirs,
     14 kind, 15 nothing) -- the tool is fed the fogged board for the ten actions before the
     harness hands it over, and on a fogged frame the commonest colour is the fog itself.
  16, 17 the direction map SEEDED from a literal instead of carried -- 16 with the watcher off and
     17 with it on. Arm 5 of the oracle sweep carried the same four entries and scored 302 while
     the watcher's identical four LOSE the level, so these separate the map from the watching.
  5..10 watching ON with SUBSETS carried: 5 kind+dirs, 6 kind, 7 dirs, 8 kind+refill+dirs,
     9 kind+inert+dirs, 10 refill+dirs. The oracle sweep found every subset containing both `kind`
     and `dirs` at the 1.0 cap, so a subset that loses here is a fact the watcher gets WRONG.

Expected feedback. Arm 2 reproduces the bank. Arm 1's `learned` block must show three changer
signatures present BEFORE level 7 starts, matching the three the driving tool learns ON level 7,
and its level-7 count is the answer. Arm 3 must equal arm 2 exactly.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))


def _mk(watch: bool, carry: tuple[str, ...], guard: bool, seed_dirs: bool):
    from admorphiq.tools.fogscout import FogScoutTool, fog_view

    class Probe(FogScoutTool):
        """The shipped tool with one or both halves of the carry suppressed."""

        def __init__(self) -> None:
            super().__init__()
            self.log: list[dict[str, Any]] = []

        def reset(self) -> None:
            super().reset()
            for field, blank in (("kind", {}), ("inert", set()),
                                 ("refill_marks", set()), ("dirs", {})):
                if field not in carry:
                    # A fresh container every level = the pre-change lifecycle for that fact.
                    setattr(self, field, blank)
            if seed_dirs:
                # ⛔ The direction map as a LITERAL, so "carrying dirs" can be told apart from
                # "having watched". Arm 5 of the oracle sweep carried exactly this map, learned on
                # level 7 by the driving tool, and scored 302; the watcher learns the same four
                # entries and the level is LOST, so one of the two claims is false and only a seed
                # that skips the watcher entirely can say which.
                self.dirs = {1: (-1, 0), 2: (1, 0), 3: (0, -1), 4: (0, 1)}
            if not watch:
                # `_drove` is what gates `observe`'s watching branch.
                self._drove = True

        def _watch(self, g) -> None:
            # ⛔ The tool is fed the fogged board too, for the ten actions before the harness hands
            # it over — and on a fogged frame the commonest colour IS the fog, so an unguarded
            # watcher reads the whole hidden board as ordinary floor and writes whatever it makes
            # of it into facts that now outlive the level.
            if guard and g is not None and g.ndim == 2 and fog_view(g) is not None:
                return
            super()._watch(g)

        def snapshot(self, tag: str) -> None:
            self.log.append({
                "at": tag,
                "panel": list(self.panel) if self.panel else None,
                "tok": self.tok is not None,
                "watched": self._watched,
                "dirs": dict(sorted(self.dirs.items())),
                "kind": sorted(len(v) for v in self.kind.values()),
                "kind_sigs": sorted(str(sorted(k))[:38] for k in self.kind),
                "kind_full": {str(sorted(k)): {str(a): str(b) for a, b in v.items()}
                              for k, v in self.kind.items()},
                "inert": len(self.inert),
                "refill": len(self.refill_marks),
            })

    return Probe


def main() -> None:
    from arc_agi import Arcade, OperationMode
    from arcengine import GameAction, GameState

    from admorphiq.harness.loop import UnifiedAgent
    from admorphiq.harness.registry import default_tools

    arm = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    all4 = ("kind", "inert", "refill_marks", "dirs")
    watch, carry = {
        1: (True, all4),
        2: (False, ()),
        3: (True, ()),
        4: (False, all4),
        5: (True, ("kind", "dirs")),
        6: (True, ("kind",)),
        7: (True, ("dirs",)),
        8: (True, ("kind", "refill_marks", "dirs")),
        9: (True, ("kind", "inert", "dirs")),
        10: (True, ("refill_marks", "dirs")),
    }.get(arm, (True, ()))
    guard = arm >= 11
    seed_dirs = arm in (16, 17)
    if arm in (16, 17):
        watch, carry, guard = arm == 17, (), arm == 17
    elif arm >= 11:
        watch, carry = True, {11: all4, 12: ("kind", "dirs"), 13: ("dirs",),
                              14: ("kind",), 15: ()}[arm]

    def _no_llm(*_a, **_k):
        raise RuntimeError("LLM-free: the signature fallback is what this measures")

    fog = _mk(watch, carry, guard, seed_dirs)()
    tools = [fog if t.name == "fogscout" else t for t in default_tools()]

    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    info = next(i for i in arcade.get_environments()
                if (i.title or i.game_id).lower().startswith("ls20"))
    env = arcade.make(info.game_id)
    obs = env.observation_space
    agent = UnifiedAgent(tools, _no_llm, giveup=4000, stall=80, ctx_budget=6000)
    human = list(getattr(info, "baseline_actions", []) or [])

    prev_levels = int(obs.levels_completed)
    total = this = 0
    per: list[int] = []
    win_tick: int | None = None
    restart = bool(getattr(agent, "restart_on_game_over", False))

    while total < 4000:
        if agent.is_done([], obs):
            break
        act = agent.choose_action([], obs)
        if not isinstance(act, GameAction):
            break
        obs = env.step(act, data=act.action_data.model_dump()) if act.is_complex() else env.step(act)
        if obs is None:
            break
        total += 1
        this += 1
        if prev_levels == 6 and win_tick is None and fog.reason.startswith("win"):
            win_tick = fog.tick
        cur = int(obs.levels_completed)
        if cur > prev_levels:
            for _ in range(cur - prev_levels):
                per.append(this)
                this = 0
            fog.snapshot(f"end of level {cur}")
            prev_levels = cur
        if obs.state == GameState.WIN:
            break
        if obs.state == GameState.GAME_OVER:
            if not restart:
                break
            obs = env.step(GameAction.RESET)
            total += 1
            this += 1
            if obs is None:
                break

    fog.snapshot("end of run")
    weight = sum(range(1, len(human) + 1))
    got = 0.0
    for i, h in enumerate(human, start=1):
        mine = per[i - 1] if i - 1 < len(per) else 0
        got += i * (min(h / mine, 1.0) ** 2 if mine else 0.0)
    print(json.dumps({
        "arm": arm, "watch": watch, "guard": guard, "seed_dirs": seed_dirs, "carry": list(carry),
        "levels": prev_levels, "per_level": per, "score": round(got / weight, 6),
        "win_tick": win_tick, "learned": fog.log,
    }, default=str), flush=True)


if __name__ == "__main__":
    main()
