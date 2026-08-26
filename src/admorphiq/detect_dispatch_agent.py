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
_BAIL_ACTIONS = 2000
_PROBE_ACTION = GameAction.ACTION3


class DetectDispatchAgent:
    """Route a game to a ported adapter by frame evidence, else to ``fallback``."""

    def __init__(self, fallback: Any) -> None:
        self._fallback = fallback
        # Bail-out. A dispatch is decided from ONE frame and was never revisited, so a
        # detector that fires on an unseen private game costs that game entirely — the
        # adapter burns the budget and the fallback, which would have scored something,
        # never runs. The public 25 cannot show this (every detector is gated to 0/24
        # there), and the hidden set says v3 scored 0.20 where dispatch scores 0.18.
        #
        # MEASURED threshold. Among the thirteen DISPATCHED public games the slowest
        # first clear is sc25 at 461 actions and every other is <= 25; lf52 (377), tu93
        # (696) and vc33 (3656) are slower but run the FALLBACK, which a dispatch bail
        # cannot touch. On the archived RE-RENDERS first-clear counts are identical 7 of
        # 7, so a different render of the same mechanic costs nothing in time.
        #
        # 2000, not 1000, and the difference is sc25. It is a frontier SEARCHER, and its
        # per-level cost swings 150x: level 1 takes 461 actions, level 2 takes 9, level 3
        # takes 1,379. A single level of a search-based adapter is therefore ALREADY
        # measured above 1,000, so a private board of that kind needing >1,000 for its
        # FIRST level is not hypothetical. 2000 still recovers half the 4,000 budget from
        # a wrong dispatch, and no public game clears its first level between 461 and
        # 2,000, so the card stays byte-identical either way.
        self._acted = 0
        self._bailed = False
        self._chosen: Any | None = None
        self._probe_before: Any | None = None
        self._probe_sent = False
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

        if self._probe_sent:
            # The probe has been SPENT, so this frame is genuinely after it. Arming and
            # reading must be separate states: the runner calls is_done and choose_action
            # with the SAME frame in one iteration, so a version that read the probe as
            # soon as it was armed compared a frame with itself, saw no displacement, and
            # fell back on every board — measured, dispatched_to stayed "fallback" for the
            # whole run.
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
            self._probe_sent = True
            return _PROBE_ACTION
        self._acted += 1
        if (
            not self._bailed
            and agent is not self._fallback
            and self._acted >= _BAIL_ACTIONS
            and int(getattr(latest_frame, "levels_completed", 0) or 0) == 0
        ):
            # Cleared nothing in a thousand actions: this dispatch was wrong. Hand the
            # rest of the budget to the fallback rather than spend it all on a mechanic
            # the board does not have.
            self._bailed = True
            self._chosen = self._fallback
            agent = self._fallback
        return agent.choose_action(frames, latest_frame)
