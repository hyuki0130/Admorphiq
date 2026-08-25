"""Official-framework wrapper deploying DETECTION DISPATCH on Kaggle.

The card the notebook shipped until now selects nothing by game identity, and neither
does this one — that property is preserved, not traded away. What changes is that nine
mechanic solvers, previously reachable only through `script25.py`'s `game_id` substring
selection, are now reached by FRAME EVIDENCE, so they can run on games whose id we have
never seen.

Measured full-25 on ceph-build, in parallel, both cards on the same day:

    chained (the previous card)   0.0566
    detection dispatch            0.2771
    adapter ceiling               0.3296

Every port lands EXACTLY on its ceiling, which is the property that says nothing was lost
in the move: the adapter selected by frame evidence scores what it scored when selected by
`game_id`. Ports: ft09 ls20 m0r0 r11l re86 sb26 sk48 su15 tr87.

Safety is asymmetric by construction. When no detector fires — the expected case on an
unfamiliar game — the chained card plays exactly as it did before, so this cannot regress
what shipped. When two fire, the frame does not identify a mechanic and the chained card
plays; ambiguity is not a coin toss. Each detector passed a measured **0/24 false
positives** across the public games before it was allowed in
(`scripts/detector_falsepos.py`), a gate that has already predicted a specific regression
on a specific game and been proved right by the run.
"""

from __future__ import annotations

import os
from typing import Any

from admorphiq._agents_shim import load_agent_class
from admorphiq.detect_dispatch_agent import DetectDispatchAgent
from admorphiq.kaggle_chained_agent import _action6_data, build_chained

Agent = load_agent_class()


def build_detect() -> DetectDispatchAgent:
    """The deployed dispatcher, buildable off-Kaggle for local verification."""
    return DetectDispatchAgent(build_chained())


class KaggleDetectAgent(Agent):  # type: ignore[misc,valid-type]
    """Official ``agents.agent.Agent`` deploying detection dispatch over the chained card."""

    #: Per-game action budget. MEASURED, not chosen for comfort — capping costs no score and
    #: buys the run back from the 9-hour limit:
    #:
    #:     no cap (100,000)   25 games, 48.4 min, mean 0.2772
    #:     cap  4,000         25 games,  3.3 min, mean 0.2772
    #:     cap  2,000         25 games,  3.0 min, mean 0.2772
    #:
    #: Identical score to four decimals, because RHAE squares efficiency and everything cleared
    #: past ~700 actions is already worth ~0 (the one full-score level near the edge is re86 L7
    #: at 588 cumulative actions, so ⛔ a cap at 500 would destroy 1.0 of real score).
    #: 4,000 over 2,000 because it costs 16 SECONDS — runtime tracks actions actually spent, not
    #: the cap — and leaves room for a hidden game that clears at full score past 2,000, which the
    #: public 25 cannot rule out.
    MAX_ACTIONS = int(os.environ.get("KAGGLE_DETECT_MAX_ACTIONS", "4000"))

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        os.environ.setdefault("GF_GIVEUP", "8000")
        self._agent = build_detect()

    # ----- official interface ------------------------------------------------

    def is_done(self, frames: list[Any], latest_frame: Any) -> bool:
        """Stop on the dispatched agent's verdict, and as a safety net at MAX_ACTIONS."""
        if self.action_counter >= self.MAX_ACTIONS:
            return True
        return self._agent.is_done(frames, latest_frame)

    def choose_action(self, frames: list[Any], latest_frame: Any) -> Any:
        return self._agent.choose_action(frames, latest_frame)

    def choose_action_with_data(
        self, frames: list[Any], latest_frame: Any
    ) -> tuple[Any, dict[str, int] | None]:
        """Return ``(action, data)`` — one agent step per call."""
        action = self._agent.choose_action(frames, latest_frame)
        return action, _action6_data(action)
