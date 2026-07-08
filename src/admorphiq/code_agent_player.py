"""CodeAgentPlayer — full game-playing agent driven by LLM-written code.

The frontier lever realized: each time its action queue empties, it asks the
offline model to WRITE a Python block (inspect current_frame with numpy, queue
1-8 actions via act()); the block runs in the code_agent sandbox and refills the
queue. Reason -> write code -> execute -> observe -> repeat, with a bounded
history for context. Game-agnostic (no game ids). Needs an ollama model at
runtime; benched via scripts/score_efficiency.py --agent code_agent on the VM.
"""

from __future__ import annotations

import json
import os
import urllib.request
from typing import Any

import numpy as np

from admorphiq.graph_frontier_agent import (
    _availability,
    _frame_2d,
    _has_frame,
    _levels_completed,
    _state_name,
)
from admorphiq.tools.code_agent import build_code_prompt, run_code

# combined-logit index for a simple action id (ACTIONk -> k-1); ACTION6 = click.
_SIMPLE_NAME = {1: "UP", 2: "DOWN", 3: "LEFT", 4: "RIGHT", 5: "SPACE", 7: "ACTION7"}


class CodeAgentPlayer:
    """Harness-contract agent: LLM writes code that queues actions."""

    def __init__(self, giveup: int = 8000) -> None:
        from admorphiq.adapter import AdmorphiqAdapter
        self._convert = AdmorphiqAdapter._convert_action
        self.giveup = giveup
        self.model = os.environ.get("CODE_AGENT_MODEL", "gemma4:31b-it-q8_0")
        self.host = os.environ.get("CODE_AGENT_HOST", "http://localhost:11434")
        self.max_tokens = int(os.environ.get("CODE_AGENT_MAX_TOKENS", "1024"))
        self._reset_level()

    def _reset_level(self) -> None:
        self._queue: list[tuple[str, tuple[int, int] | None]] = []
        self._history: list[dict[str, Any]] = []
        self._prev_frame: np.ndarray | None = None
        self._prev_label: str | None = None
        self._steps = 0
        self._last_levels = 0

    def is_done(self, frames: list[Any], latest_frame: Any) -> bool:
        if _state_name(latest_frame) == "WIN":
            return True
        return self._steps >= self.giveup

    def _llm(self, prompt_messages: list[dict[str, str]]) -> str:
        body = {
            "model": self.model, "stream": False, "think": False,
            "messages": prompt_messages,
            "options": {"temperature": 0.0, "num_ctx": 16384, "num_predict": self.max_tokens},
        }
        req = urllib.request.Request(
            f"{self.host}/api/chat", data=json.dumps(body).encode(),
            headers={"Content-Type": "application/json"}, method="POST",
        )
        with urllib.request.urlopen(req, timeout=180) as r:
            return json.loads(r.read())["message"]["content"]

    def choose_action(self, frames: list[Any], latest_frame: Any) -> Any:
        from admorphiq.types import ActionType, GameAction
        obs = latest_frame
        state = _state_name(obs)

        levels = _levels_completed(obs)
        if levels > self._last_levels:
            self._reset_level()
            self._last_levels = levels

        if state in ("GAME_OVER", "NOT_PLAYED"):
            self._prev_frame = None
            self._queue.clear()
            return self._convert(GameAction.reset())
        if not _has_frame(obs):
            return self._convert(GameAction.reset())

        frame = _frame_2d(obs).astype(np.int16)
        # record what the previous action did (for the LLM's context)
        if self._prev_frame is not None and self._prev_label is not None \
                and self._prev_frame.shape == frame.shape:
            changed = bool((self._prev_frame != frame).any())
            self._history.append({"action": self._prev_label, "changed": changed})
            self._history = self._history[-20:]

        simple_ids, action6_ok = _availability(obs)
        valid = [_SIMPLE_NAME[i] for i in simple_ids if i in _SIMPLE_NAME]
        if action6_ok:
            valid.append("MOUSE")

        # Refill the queue by asking the model to WRITE code when empty.
        if not self._queue:
            try:
                text = self._llm(build_code_prompt(frame, self._history, valid))
                res = run_code(text, frame, self._history, valid)
                self._queue = [a for a in res.actions if self._legal(a, simple_ids, action6_ok)]
            except Exception:  # noqa: BLE001 - offline-safe: fall back to a probe
                self._queue = []
            if not self._queue:
                self._queue = self._fallback(simple_ids, action6_ok, frame)

        act_name, xy = self._queue.pop(0)
        self._steps += 1
        self._prev_frame = frame
        self._prev_label = act_name if xy is None else f"{act_name}{xy}"
        if xy is not None:
            internal = GameAction.coordinate(int(xy[0]), int(xy[1]))
        else:
            internal = GameAction.simple(ActionType(int(act_name.replace("ACTION", ""))))
        return self._convert(internal)

    def _legal(self, a: tuple[str, Any], simple_ids: list[int], action6_ok: bool) -> bool:
        name, xy = a
        if xy is not None:
            return action6_ok
        aid = int(name.replace("ACTION", ""))
        # ACTION7 is usable when the game offers no 1-5 movement (adapter rule).
        return aid in simple_ids or (aid == 7 and not simple_ids)

    def _fallback(
        self, simple_ids: list[int], action6_ok: bool, frame: np.ndarray
    ) -> list[tuple[str, tuple[int, int] | None]]:
        """A single safe probe when the LLM yields no legal action."""
        if simple_ids:
            return [(f"ACTION{simple_ids[0]}", None)]
        if action6_ok:
            return [("ACTION6", (32, 32))]
        return [("ACTION7", None)]
