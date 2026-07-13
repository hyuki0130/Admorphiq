"""ChainedAgent — the measured 3-pass per-game policy as ONE deployable agent.

The r53 card measurement (rounds/r53, 2026-07-11) found the per-game best
splits cleanly by pass: the R28 :class:`WorldModelAgent` clears the
arrangement/selection class EFFICIENTLY (sb26 259a, su15 2 levels/58a, ls20
88a, ar25 2 levels — deterministic), while the unified harness clears the
graph-class 12. RHAE squares efficiency and counts EVERY action taken on a
level, so pass ORDER is score-critical: the cheap worldmodel probe runs FIRST
(it self-terminates in ~50-260 actions on non-matching games, a negligible
prefix for the exhaustive graph clears that score ≈0 anyway), then the unified
harness owns the rest of the budget.

Frame-only, game-id-free: both members already transfer; this class only
sequences them.
"""

from __future__ import annotations

from typing import Any


class ChainedAgent:
    """Run the cheap worldmodel probe first, then hand over to unified.

    Exposes the harness contract ``is_done(frames, latest_frame)`` /
    ``choose_action(frames, latest_frame)``. The handover happens when the
    probe reports done WITHOUT a WIN: from then on every call delegates to the
    unified agent. A WIN during the probe ends the game immediately (the
    efficient clear is banked).
    """

    # The runner ends the game on the first GAME_OVER unless the agent opts
    # into restarts (the unified harness's measured fix #1 — games otherwise
    # end at the first avatar death, ~50-100 actions). The chain must opt in
    # for BOTH phases or every death-prone game dies in the probe prefix.
    restart_on_game_over = True

    def __init__(self, probe: Any, main: Any) -> None:
        self._probe = probe
        self._main = main
        self._phase = "probe"

    def _state_name(self, obs: Any) -> str:
        s = getattr(obs, "state", None)
        return getattr(s, "name", str(s) if s is not None else "")

    def is_done(self, frames: list, latest_frame: Any) -> bool:
        if self._phase == "probe":
            if not self._probe.is_done(frames, latest_frame):
                return False
            if self._state_name(latest_frame) == "WIN":
                return True
            self._phase = "main"  # probe gave up -> unified owns the rest
            return False
        return self._main.is_done(frames, latest_frame)

    def choose_action(self, frames: list, latest_frame: Any) -> Any:
        if self._phase == "probe":
            return self._probe.choose_action(frames, latest_frame)
        return self._main.choose_action(frames, latest_frame)
