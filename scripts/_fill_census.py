"""How many of the 25 games' actions are the HARNESS's empty-proposal fill, and are they refused?

Purpose. When the active tool's `propose` returns nothing, `loop._fill_from_current` ends
``self._queue = legal or self._probe(simple_ids, action6)`` and `_probe` returns
``simple_ids[0]`` — the LOWEST-NUMBERED action — for every such turn. The ls20 handover census
(rounds/r101_ls20-fog-cost) measured eight consecutive such turns, every one REFUSED by the engine.
This asks the same question of all 25 games, because the fill is harness-wide and ls20 is one board.

⛔ RULE 7ax, applied to the answer rather than to the count. A fill spent inside an attempt that is
lost for another reason, or on a level the run never clears, is not a recoverable cost — saving it
moves the failure, not the score. So every filled turn is filed under BOTH its level and its attempt,
and the aggregate reports how many fills are charged to a level the run went on to clear, and how
many to an attempt that did not end in a death.

The agent is the DEPLOYED one (`score_efficiency._make_agent("unified")`, so giveup/stall/ctx and the
tool set are the runner's), subclassed for recording only, and the env stepping and scoring are
`score_efficiency.run_game` ITSELF via `adapter_factory` — not a mirror of it, so the per-level
counts and game_score are the runner's own arithmetic.

"Refused" is read from the frames the agent already sees: the board-level change flag
(`segment.board_changed`, which ignores the outer HUD band) between the frame the action was chosen
on and the next one. ⚠️ Raw `!=` is reported beside it and is NOT the measure — a board with an
action counter at the frame edge changes on every action, which is the trap that made a 94%-inert
board read as fully live.

Expected feedback. Per game: total actions, filled turns, and how many of those the board refused.
A game with zero fills is untouched by this axis. If the filled turns are concentrated on levels the
run never clears, the axis closes at this census: the harness would be pressing a better key inside
an attempt that is lost anyway.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

TITLES = ["ar25", "bp35", "cd82", "cn04", "dc22", "ft09", "g50t", "ka59", "lf52", "lp85",
          "ls20", "m0r0", "r11l", "re86", "s5i5", "sb26", "sc25", "sk48", "sp80", "su15",
          "tn36", "tr87", "tu93", "vc33", "wa30"]


def main() -> None:
    arm = int(sys.argv[1])
    title = TITLES[arm - 1]

    import numpy as np
    import score_efficiency as se
    from arc_agi import Arcade, OperationMode

    from admorphiq.harness.loop import UnifiedAgent
    from admorphiq.tools.base import frame_2d, has_frame, levels_completed, state_name
    from admorphiq.tools.segment import board_changed as _board_changed

    class Census(UnifiedAgent):
        """The deployed loop with a recorder on the ONE line that spends an unplanned action."""

        def __init__(self, *a: Any, **k: Any) -> None:
            self.rows: list[dict[str, Any]] = []
            self._fill = False
            self._attempt = 0
            super().__init__(*a, **k)

        def _probe(self, simple_ids, action6):
            self._fill = True
            return super()._probe(simple_ids, action6)

        def choose_action(self, frames, obs):
            # Attribute the PREVIOUS row's outcome: `_prev_frame` is still the frame that row's
            # action was chosen on, because super() only overwrites it at the end of its own call.
            if self.rows and self._prev_frame is not None and has_frame(obs):
                f = frame_2d(obs).astype(np.int16)
                if self._prev_frame.shape == f.shape:
                    self.rows[-1]["chg"] = bool((self._prev_frame != f).any())
                    self.rows[-1]["bchg"] = bool(_board_changed(self._prev_frame, f))
            st = state_name(obs)
            if st == "GAME_OVER":
                self._attempt += 1
            self._fill = False
            act = super().choose_action(frames, obs)
            self.rows.append({
                "fill": self._fill, "lv": levels_completed(obs), "att": self._attempt,
                "cur": self._current, "st": st, "chg": None, "bchg": None,
            })
            return act

    holder: dict[str, Any] = {}

    def factory():
        base = se._make_agent("unified")
        agent = Census(
            list(base.tools.values()), base.llm,
            giveup=base.giveup, stall=base.stall, ctx_budget=base.ctx_budget,
            no_progress=base.no_progress,
        )
        holder["agent"] = agent
        return agent

    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    info = next(i for i in arcade.get_environments()
                if (i.title or i.game_id).lower().startswith(title))
    res = se.run_game(arcade, info.game_id, info.baseline_actions,
                      max_actions=4000, adapter_factory=factory)

    rows = holder["agent"].rows
    cleared = len(res.get("per_level", []) and [p for p in res["per_level"]
                                               if p.get("agent_actions")])
    # Which attempts ENDED in a death: an attempt index that is followed by a higher one.
    last_att = rows[-1]["att"] if rows else 0
    fills = [r for r in rows if r["fill"]]
    by_lv: dict[int, int] = {}
    refused = 0
    for r in fills:
        by_lv[r["lv"]] = by_lv.get(r["lv"], 0) + 1
        if r["bchg"] is False:
            refused += 1
    # Rule 7ax: a fill is RECOVERABLE only if the level it sits on was later cleared AND the
    # attempt it sits in did not end in a death.
    recoverable = sum(1 for r in fills
                      if r["lv"] < cleared and r["att"] == last_att)
    print(json.dumps({
        "arm": arm, "title": title, "game_score": res.get("game_score"),
        "levels_cleared": cleared, "per_level": [p.get("agent_actions") for p in res.get("per_level", [])],
        "actions": len(rows), "fills": len(fills), "fills_refused": refused,
        "fills_board_changed": sum(1 for r in fills if r["bchg"] is True),
        "fills_by_level": by_lv, "attempts": last_att + 1,
        "fills_on_cleared_level_and_final_attempt": recoverable,
        "tools_filling": sorted({str(r["cur"]) for r in fills}),
        "error": res.get("error"),
    }), flush=True)


if __name__ == "__main__":
    main()
