"""Which tool's `detect` is NOT side-effect-free? One arm per tool, on lf52.

⛔ THE CONTRACT. `detect` is a QUESTION: the harness asks every registered tool whether it
recognises a board. Asking must not change the board, and must not change the tool's own state.
MEASURED 2026-08-30 (R101SELECT part 2): sampling every tool's `detect` every 10th action moved
lf52 from **823 actions to 827**, score identical. So at least one tool answers by moving.

WHY IT MATTERS MORE THAN FOUR ACTIONS ON ONE GAME:
  * it makes every bid measurement suspect — an instrument that samples often is measuring a run it
    perturbed, and it does not look wrong;
  * it is a silent cross-tool coupling: a tool that mutates in `detect` can be perturbed by ANOTHER
    tool's detect running first, which no amount of reading one file will reveal;
  * on the private 110 the tool set is the same and the boards are not.

METHOD (bisect by arm, all arms in one fan):
    seed 1  -> NEGATIVE CONTROL: sample nothing. MUST return 823, or the game is not deterministic
               and no other arm means anything.
    seed 2  -> POSITIVE CONTROL: sample ALL tools, exactly as R101SELECT part 2 did. MUST return
               827, or the perturbation does not reproduce and the fan is measuring nothing.
    seed k>=3 -> sample EXACTLY ONE tool, `list(agent.tools)[k-3]`. An arm != 823 names its tool.

⚠️ If every single-tool arm returns 823 while the positive control returns 827, the perturbation is
a COMBINATION (tool A mutates only once tool B's detect has run) and the next step is a halving
bisect over the set, not a per-tool one. That outcome is a real result, not a failed run.

The sampling gate is copied verbatim from `_select_overtake.py` — same monotonic tick, same
`_current not in (None, "code")` guard — because an arm that samples on a different schedule is not
testing the same thing. ⛔ NOT `self._steps`: it is level-local and resets on every level-up, which
silently stopped that probe sampling after the first clear until it was caught.

Instrumentation is subclass-only; `loop.py` is shared by every concurrent agent and is not touched.

    bash scripts/pfan.sh detfx scripts/_select_detectfx.py 50 "" 8
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from arc_agi import Arcade, OperationMode  # noqa: E402
from score_efficiency import _make_agent, run_game  # noqa: E402

from admorphiq.harness.loop import UnifiedAgent  # noqa: E402

GAME = "lf52"
BASELINE_ACTIONS = 823      # HEAD, scripts/rounds/R101GRAPHOWN/games/lf52.json
PERTURBED_ACTIONS = 827     # scripts/rounds/R101SELECT/overtakes.jsonl, all-tools sampling
_EVERY = 10


class DetectFxAgent(UnifiedAgent):
    def _fx_init(self, mode: str, which: int) -> None:
        self._fx_mode = mode          # "none" | "all" | "one"
        self._fx_which = which        # index into list(self.tools) when mode == "one"
        self._fx_tick = 0
        self._fx_last = -10**9
        self._fx_samples = 0
        self._fx_name = (list(self.tools)[which]
                         if mode == "one" and which < len(self.tools) else None)

    def choose_action(self, frames, latest_frame):
        act = super().choose_action(frames, latest_frame)
        if self._fx_mode == "none":
            return act
        self._fx_tick += 1
        if self._fx_tick - self._fx_last >= _EVERY and self._current not in (None, "code"):
            self._fx_last = self._fx_tick
            self._fx_samples += 1
            names = list(self.tools) if self._fx_mode == "all" else [self._fx_name]
            for n in names:
                if n is None:
                    continue
                try:
                    self.tools[n].detect(self._recent_frames, self._last_obs)
                except Exception:  # noqa: BLE001
                    pass
        return act


def main() -> None:
    seed = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    if seed == 1:
        mode, which = "none", -1
    elif seed == 2:
        mode, which = "all", -1
    else:
        mode, which = "one", seed - 3

    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    envs = [e for e in arcade.get_environments()
            if GAME in f"{e.game_id} {e.title or ''}".lower()]
    if not envs:
        print(json.dumps({"seed": seed, "error": "no env"}), flush=True)
        return
    env_info = envs[0]
    holder: dict = {}

    def factory():
        a = _make_agent("unified")
        a.__class__ = DetectFxAgent
        a._fx_init(mode, which)
        holder["agent"] = a
        return a

    # An out-of-range arm must say so rather than silently reporting the control's number.
    probe = _make_agent("unified")
    n_tools = len(probe.tools)
    if mode == "one" and which >= n_tools:
        print(json.dumps({"seed": seed, "mode": "unused_arm", "n_tools": n_tools}), flush=True)
        return

    t0 = time.time()
    res = run_game(arcade, env_info.game_id, env_info.baseline_actions,
                   agent_name="unified", max_actions=4000, adapter_factory=factory)
    a = holder.get("agent")
    acts = res.get("total_actions")
    # ⛔ MEASURE THE COUNTERS, NOT JUST THE SCORE (rule 7g). The perturbation is 4 actions on a
    # level that scores zero, so an unchanged score says NOTHING about whether the per-frame plan
    # memo fired. `_tiers` and `_why` are __init__-only on this tool — they survive `reset()` and
    # therefore count every planning decision of the whole GAME, which is exactly the quantity the
    # memo is supposed to reduce. Sampling `detect` must leave them untouched.
    rp = (a.tools.get("railpeg") if a is not None else None)
    counters = None
    if rp is not None:
        counters = {
            "builds": sum(getattr(rp, "_tiers", {}).values()),
            "tiers": dict(getattr(rp, "_tiers", {})),
            "barren_cap": getattr(rp, "_why", {}).get("barren-cap", 0),
            "elsewhere_set": getattr(rp, "_why", {}).get("elsewhere:set", 0),
            "sincecapture": getattr(rp, "_sincecapture", None),
            "barren": getattr(rp, "_barren", None),
        }
    print(json.dumps({
        "seed": seed,
        "mode": mode,
        "tool": getattr(a, "_fx_name", None),
        "n_tools": n_tools,
        "total_actions": acts,
        "delta_vs_baseline": (acts - BASELINE_ACTIONS) if acts is not None else None,
        "game_score": res.get("game_score"),
        "levels": res.get("levels_completed"),
        "samples": getattr(a, "_fx_samples", 0),
        "railpeg_counters": counters,
        "elapsed_s": round(time.time() - t0, 1),
        "error": res.get("error"),
    }), flush=True)


if __name__ == "__main__":
    main()
