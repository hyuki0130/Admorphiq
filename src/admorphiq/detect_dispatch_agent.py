"""Detection dispatch: pick a ported mechanic solver from the FRAME, else fall back.

Why this exists
---------------
The shipped card selects nothing by game id, because the 110 private evaluation games carry
no id we know. The script25 adapters reach 0.3296 mean where the card reaches 0.0566, and
that depth is unreachable today only because `script25.py` selects an adapter by `game_id`
substring. This agent is the bridge: on the first frame it asks every PORTED adapter
whether its mechanic is present, and hands the game to the one that says yes.

The safety property is asymmetric and deliberate. When no detector fires — the expected
case on an unfamiliar game — the fallback agent plays exactly as it does today, so the card
cannot regress. When two fire, the frame does not identify a mechanic and the fallback
plays; ambiguity is not a coin toss. A detector may only ship after
`scripts/detector_falsepos.py` measures it at zero false positives across the 25 public
games (ft09's ladder: ring discovery alone 9/24 -> click-only 4/24 -> complete ring 0/24).

The decision is taken ONCE, on the first frame that carries one, and never revisited: a
mechanic does not appear halfway through a game, and re-deciding mid-run would let a
transient board state hand the game to a different solver than the one that has been
building state for it.
"""

from __future__ import annotations

from typing import Any

from arcengine import GameAction

from admorphiq.adapters25 import discover_adapters
from admorphiq.adapters25.base import GameAdapter, available_action_ids, has_frame

#: The probe is HORIZONTAL. Measured: a vertical probe leaves m0r0 and ka59
#: indistinguishable, because both move their pieces the same way under ACTION1.
_PROBE_ACTION_ID = 3
_PROBE_ACTION = GameAction.ACTION3


class DetectDispatchAgent:
    """Route a game to a ported adapter by frame evidence, else to ``fallback``."""

    def __init__(self, fallback: Any) -> None:
        self._fallback = fallback
        self._chosen: Any | None = None
        self._probe_before: Any | None = None
        # A classmethod accessed on a class yields a NEW bound object each time, so
        # `cls._detect_mechanic is not GameAdapter._detect_mechanic` is ALWAYS true and
        # marked all 25 adapters as ported. Compare the underlying functions.
        self._ported: dict[str, type[GameAdapter]] = {
            name: cls
            for name, cls in discover_adapters().items()
            if cls._detect_mechanic.__func__ is not GameAdapter._detect_mechanic.__func__
        }
        self._probed: dict[str, type[GameAdapter]] = {
            name: cls
            for name, cls in discover_adapters().items()
            if cls._detect_mechanic_probed.__func__
            is not GameAdapter._detect_mechanic_probed.__func__
        }

    def __getattr__(self, name: str) -> Any:
        """Forward duck-typed harness attributes to whoever will actually play.

        The runner reads capability flags off the agent OBJECT, not through the two
        contract methods — `restart_on_game_over` decides whether a GAME_OVER revives the
        attempt or ends the run. Omitting it cost a real level: MEASURED on lf52, where
        no detector fires and the fallback plays, the card scores 0.000132 with 1 level
        twice over while dispatch scored 0.0000 with 0 levels twice over, because
        `getattr(adapter, "restart_on_game_over", False)` found nothing on the wrapper and
        the run ended at the first GAME_OVER instead of restarting.

        ⚠️ The runner reads those flags ONCE, before the first frame exists, so they
        resolve against the FALLBACK — a ported adapter cannot change them by firing.
        Every adapter that needs the flag sets it True, as the fallback does, so the two
        agree today; an adapter needing False would need the runner to re-read after
        dispatch.
        """
        if name.startswith("_"):
            raise AttributeError(name)
        return getattr(self._chosen or self._fallback, name)

    @property
    def dispatched_to(self) -> str:
        """Which solver is playing — an adapter name, or ``"fallback"``."""
        return getattr(self._chosen, "_dispatch_name", "fallback")

    def _decide(self, latest_frame: Any) -> Any:
        if self._chosen is not None or not has_frame(latest_frame):
            return self._chosen or self._fallback

        if self._probe_before is not None:
            # The probe has been spent; read it and decide, whatever it says.
            fired = [n for n, cls in self._probed.items()
                     if cls.detect_probed(self._probe_before, latest_frame)]
            self._chosen = self._probed[fired[0]]() if len(fired) == 1 else self._fallback
            if len(fired) == 1:
                self._chosen._dispatch_name = fired[0]
            return self._chosen

        fired = [n for n, cls in self._ported.items() if cls.detect(latest_frame)]
        if len(fired) == 1:
            chosen = self._ported[fired[0]]()
            chosen._dispatch_name = fired[0]
            self._chosen = chosen
            return self._chosen
        if fired:
            # Two detectors on one board: the frame does not identify a mechanic, and a
            # probe cannot un-say that. Fall back rather than break the tie by guessing.
            self._chosen = self._fallback
            return self._chosen

        if self._probed and self._probe_available(latest_frame):
            self._probe_before = latest_frame
            return None  # signals choose_action to spend the probe

        self._chosen = self._fallback
        return self._chosen

    def _probe_available(self, latest_frame: Any) -> bool:
        """Only probe a board that offers the probe action.

        The probe must move along the axis a mirror would mirror — MEASURED, a vertical
        probe leaves m0r0 and ka59 indistinguishable because both move their pieces the
        same way under it.
        """
        simple_ids, _has_click = available_action_ids(latest_frame)
        return _PROBE_ACTION_ID in simple_ids

    def is_done(self, frames: list[Any], latest_frame: Any) -> bool:
        agent = self._decide(latest_frame)
        if agent is None:
            return False  # a probe is pending; the game is certainly not over
        return agent.is_done(frames, latest_frame)

    def choose_action(self, frames: list[Any], latest_frame: Any) -> Any:
        agent = self._decide(latest_frame)
        if agent is None:
            return _PROBE_ACTION
        return agent.choose_action(frames, latest_frame)
