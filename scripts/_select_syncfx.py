"""Is railpeg's `detect` perturbation the PLANNER or the frame-LEARNING? One arm each.

⛔ ENUMERATE BEFORE PROBING (rule 7h). `railpeg.detect` does two things that can move state, and
the 823 -> 827 measurement cannot tell them apart:

  (a) `_ensure_plan` — the PLANNER. Spends `_sincecapture` / `_barren`.
  (b) `_sync`        — the LEARNER. It folds the frame into the model. Its per-frame memo stops it
                       re-learning the SAME frame; it cannot stop it learning a frame the tool
                       would otherwise never have been shown. An instrument sampling off the
                       harness's cadence hands the tool exactly such frames.

If (b) alone reproduces +4, then the per-frame plan memo is a correct change that does NOT account
for the perturbation, and the perturbation is a property of ASKING a stateful tool out of band —
an instrument defect, not a tool defect. Those two conclusions want opposite follow-ups, so they
are measured together rather than assumed.

    seed 1 -> control: touch nothing            (expect the baseline)
    seed 2 -> `_sync` only, every 10th action   (the LEARNER alone)
    seed 3 -> full `detect`, every 10th action  (both halves, for comparison on the same tree)

    bash scripts/pfan.sh selsync scripts/_select_syncfx.py 3 "" 3
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
BASELINE_ACTIONS = 823
_EVERY = 10


class SyncFxAgent(UnifiedAgent):
    def _sf_init(self, mode: str) -> None:
        self._sf_mode = mode           # "none" | "sync" | "detect"
        self._sf_tick = 0
        self._sf_last = -10**9
        self._sf_samples = 0

    def choose_action(self, frames, latest_frame):
        act = super().choose_action(frames, latest_frame)
        if self._sf_mode == "none":
            return act
        self._sf_tick += 1
        if self._sf_tick - self._sf_last >= _EVERY and self._current not in (None, "code"):
            self._sf_last = self._sf_tick
            rp = self.tools.get("railpeg")
            if rp is not None:
                self._sf_samples += 1
                try:
                    if self._sf_mode == "detect":
                        rp.detect(self._recent_frames, self._last_obs)
                    else:
                        g = rp._grid(self._recent_frames, self._last_obs)
                        if g is not None:
                            rp._sync(g)
                except Exception:  # noqa: BLE001
                    pass
        return act


def main() -> None:
    seed = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    mode = {1: "none", 2: "sync", 3: "detect"}.get(seed)
    if mode is None:
        return

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
        a.__class__ = SyncFxAgent
        a._sf_init(mode)
        holder["agent"] = a
        return a

    t0 = time.time()
    res = run_game(arcade, env_info.game_id, env_info.baseline_actions,
                   agent_name="unified", max_actions=4000, adapter_factory=factory)
    a = holder.get("agent")
    rp = a.tools.get("railpeg") if a is not None else None
    acts = res.get("total_actions")
    print(json.dumps({
        "seed": seed,
        "mode": mode,
        "total_actions": acts,
        "delta_vs_baseline": (acts - BASELINE_ACTIONS) if acts is not None else None,
        "game_score": res.get("game_score"),
        "levels": res.get("levels_completed"),
        "samples": getattr(a, "_sf_samples", 0),
        "railpeg_builds": sum(getattr(rp, "_tiers", {}).values()) if rp is not None else None,
        "railpeg_tiers": dict(getattr(rp, "_tiers", {})) if rp is not None else None,
        "elapsed_s": round(time.time() - t0, 1),
        "error": res.get("error"),
    }), flush=True)


if __name__ == "__main__":
    main()
