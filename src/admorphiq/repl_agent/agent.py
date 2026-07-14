"""ReplAgent — the full code-REPL turn loop (R55 module 6).

Wires the five offline modules into one harness-contract agent so the Kaggle
LLM-wiring is a pure client swap:

    SceneTracker.update -> TurnPacketBuilder -> LLMClient.complete ->
    parse (code block or action/macro JSON) -> sandbox execute (inspection) ->
    ActionGovernor-vetted action(s) -> TranscriptRecorder

The LLM is an INJECTED :class:`LLMClient` protocol with two implementations:
:class:`MockLLM` (scripted, for offline tests — no network) and
:class:`OpenAICompatClient` (a thin OpenAI-compatible HTTP client that works for
both vLLM-serve and ollama; endpoint + model via ``REPL_LLM_BASE_URL`` /
``REPL_LLM_MODEL``). Decisions happen at boundaries only (queue empty / macro
end) — never one LLM call per action.

Generic (no game ids). The model-facing action names UP/DOWN/LEFT/RIGHT/SPACE/
UNDO/MOUSE map to ACTION1-7 by a fixed default here; the LEARNED per-game mapping
is a later round's job.
"""

from __future__ import annotations

import json
import os
import re
import time
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Callable, Protocol

import numpy as np

from admorphiq.repl_agent.governor import ActionGovernor, ActionRequest, MacroStep
from admorphiq.repl_agent.sandbox import ObservationStore, run_code
from admorphiq.repl_agent.segmentation import SceneTracker
from admorphiq.repl_agent.transcript import TranscriptRecorder, TurnRecord, image_hash
from admorphiq.repl_agent.turn_packet import (
    EnvironmentMemory,
    HistoryTiers,
    TurnPacketBuilder,
)
from admorphiq.tools.base import base_hash

# Model-facing action names -> env ACTION ids (default; learned mapping later).
ID_BY_NAME = {"UP": 1, "DOWN": 2, "LEFT": 3, "RIGHT": 4, "SPACE": 5,
              "MOUSE": 6, "UNDO": 7}
NAME_BY_ID = {v: k for k, v in ID_BY_NAME.items()}

_CODE_BLOCK = re.compile(r"```(?:python)?\s*\n(.*?)```", re.DOTALL | re.IGNORECASE)


class LLMClient(Protocol):
    """A minimal completion interface — the only model dependency of the loop."""

    def complete(self, prompt: str, images: list[str] | None = None) -> str:
        ...


class MockLLM:
    """Scripted client for offline tests. Returns responses in order (a string or
    a ``prompt -> str`` callable); the last response repeats once exhausted."""

    def __init__(self, responses: list[str | Callable[[str], str]]) -> None:
        self._responses = list(responses)
        self.calls: list[str] = []

    def complete(self, prompt: str, images: list[str] | None = None) -> str:
        self.calls.append(prompt)
        idx = min(len(self.calls) - 1, len(self._responses) - 1)
        r = self._responses[idx] if self._responses else ""
        return r(prompt) if callable(r) else r


class OpenAICompatClient:
    """Thin OpenAI-compatible /chat/completions client (vLLM serve or ollama).

    Endpoint + model come from ``REPL_LLM_BASE_URL`` / ``REPL_LLM_MODEL`` (or
    constructor args). Constructing without a base URL raises immediately, so
    ``--agent repl`` fails fast offline instead of hanging. Runtime only — never
    used in tests.
    """

    def __init__(self, base_url: str | None = None, model: str | None = None,
                 timeout: float = 120.0) -> None:
        self.base_url = (base_url or os.environ.get("REPL_LLM_BASE_URL", "")).rstrip("/")
        if not self.base_url:
            raise RuntimeError("REPL_LLM_BASE_URL is not set — cannot serve the REPL agent")
        self.model = model or os.environ.get("REPL_LLM_MODEL", "")
        self.timeout = timeout

    def complete(self, prompt: str, images: list[str] | None = None) -> str:
        content: Any = prompt
        if images:
            content = [{"type": "text", "text": prompt}]
            for b64 in images:
                content.append({"type": "image_url",
                                "image_url": {"url": f"data:image/png;base64,{b64}"}})
        body = {
            "model": self.model,
            "messages": [{"role": "user", "content": content}],
            "temperature": 0.0,
            "stream": False,
        }
        req = urllib.request.Request(
            f"{self.base_url}/chat/completions", data=json.dumps(body).encode(),
            headers={"Content-Type": "application/json"}, method="POST",
        )
        with urllib.request.urlopen(req, timeout=self.timeout) as r:
            data = json.loads(r.read())
        return data["choices"][0]["message"]["content"]


@dataclass
class ParsedOutput:
    """Normalized parse of a model reply."""

    kind: str  # "code" | "actions" | "macro" | "none"
    code: str | None = None
    actions: list[dict[str, Any]] = field(default_factory=list)
    macro: list[dict[str, Any]] = field(default_factory=list)


def _extract_json(text: str) -> dict[str, Any] | None:
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        return None
    try:
        obj = json.loads(text[start:end + 1])
        return obj if isinstance(obj, dict) else None
    except (json.JSONDecodeError, ValueError):
        return None


def parse_model_output(raw: str) -> ParsedOutput:
    """Parse a reply into code / action(s) / macro / none (deterministic)."""
    m = _CODE_BLOCK.search(raw or "")
    if m:
        return ParsedOutput(kind="code", code=m.group(1).strip())
    obj = _extract_json(raw or "")
    if obj is not None:
        if isinstance(obj.get("macro"), list):
            return ParsedOutput(kind="macro", macro=obj["macro"])
        if isinstance(obj.get("plan"), list):
            return ParsedOutput(kind="actions", actions=obj["plan"])
        if "action" in obj:
            return ParsedOutput(kind="actions", actions=[obj])
    return ParsedOutput(kind="none")


def normalize_parse(raw: str) -> list[dict[str, Any]]:
    """The parsed_tool_calls form recorded in the transcript (replay-stable)."""
    p = parse_model_output(raw)
    if p.kind == "code":
        return [{"tool": "code", "code": p.code}]
    if p.kind == "macro":
        return [{"tool": "macro", "steps": p.macro}]
    if p.kind == "actions":
        return [{"tool": "action", **a} for a in p.actions]
    return []


class ReplAgent:
    """Harness-contract code-REPL agent (is_done / choose_action)."""

    restart_on_game_over = True

    def __init__(
        self,
        llm: LLMClient,
        *,
        giveup: int = 8000,
        recorder: TranscriptRecorder | None = None,
        token_budget: int = 3000,
    ) -> None:
        from admorphiq.adapter import AdmorphiqAdapter

        self._convert = AdmorphiqAdapter._convert_action
        self._llm = llm
        self.giveup = giveup
        self._recorder = recorder
        self._builder = TurnPacketBuilder(token_budget=token_budget)
        self.last_hypothesis: str | None = None
        self._game_id = ""
        # Game-lifetime observability counters (read by the bench diagnostics).
        self.llm_calls = 0
        self.parse_failures = 0
        self.governor_rejections = 0
        self.sandbox_errors = 0
        self._reset_game()

    def _reset_game(self) -> None:
        self._tracker = SceneTracker()
        self._store = ObservationStore()
        self._governor = ActionGovernor()
        self._memory = EnvironmentMemory()
        self._history = HistoryTiers()
        self._queue: list[dict[str, Any]] = []
        self._prev_frame: np.ndarray | None = None
        self._prev_scene = None
        self._prev_action: dict[str, Any] | None = None
        self._macro_active = False
        self._turn = 0
        self._steps = 0
        self._last_levels = 0

    # ----- harness contract ---------------------------------------------------
    def is_done(self, frames: list[Any], latest_frame: Any) -> bool:
        return self._is_win(latest_frame) or self._steps >= self.giveup

    def choose_action(self, frames: list[Any], latest_frame: Any) -> Any:
        from admorphiq.types import GameAction

        obs = latest_frame
        state = _state_name(obs)
        levels = _levels_completed(obs)
        level_up = levels > self._last_levels
        if level_up:
            self._on_level_up(levels)

        if state in ("GAME_OVER", "NOT_PLAYED") or not _has_frame(obs):
            self._queue.clear()
            self._macro_active = False
            self._prev_frame = None
            self._prev_action = None
            return self._convert(GameAction.reset())

        frame = _frame_2d(obs).astype(np.int16)
        scene = self._tracker.update(frame)
        self._store.add(frame, scene)
        self._record_transition(frame, scene, state, level_up)

        if not self._queue:
            self._decide(obs, frame, scene)
        if not self._queue:
            self._queue = [self._fallback(obs)]

        action = self._queue.pop(0)
        self._governor.record_executed(action, base_hash(frame))
        self._prev_frame = frame
        self._prev_scene = scene
        self._prev_action = action
        self._turn += 1
        self._steps += 1
        return self._to_gameaction(action, obs)

    # ----- loop internals -----------------------------------------------------
    def _on_level_up(self, levels: int) -> None:
        self._tracker = SceneTracker()
        self._governor.reset_level()
        self._history.reset_level()
        self._queue.clear()
        self._macro_active = False
        self._prev_scene = None
        self._last_levels = levels

    def _record_transition(self, frame: np.ndarray, scene: Any, state: str,
                           level_up: bool) -> None:
        if self._prev_action is None or self._prev_frame is None:
            return
        changed = not np.array_equal(frame, self._prev_frame)
        events = [f"{e['type']} {e.get('id', '')}".strip() for e in scene.events]
        self._history.push({"action": self._prev_action, "changed": changed}, events)
        if self._macro_active:
            status = self._governor.observe_after(
                board_changed=changed, level_completed=level_up,
                game_over=(state == "GAME_OVER"))
            if status == "continue":
                step = self._governor.current_macro_step()
                if step is not None:
                    self._queue.append(step.request().to_dict())
            else:  # macro_done / macro_aborted / idle
                self._macro_active = False

    def _decide(self, obs: Any, frame: np.ndarray, scene: Any) -> None:
        legal = _legal_names(obs)
        hw = frame.shape
        state_hash = base_hash(frame)
        packet = self._builder.build(
            game=self._game_ctx(obs, legal), last_action=self._last_action_dict(),
            scene=scene, prev_scene=self._prev_scene, frame=frame,
            prev_frame=self._prev_frame, history=self._history, memory=self._memory)
        prompt = self._builder.to_yaml(packet)

        t0 = time.time()
        raw = self._llm.complete(prompt, None)
        latency_ms = (time.time() - t0) * 1000.0
        self.llm_calls += 1

        parsed = parse_model_output(raw)
        if parsed.kind == "none":
            self.parse_failures += 1
        sandbox_out = sandbox_err = ""
        chosen: dict[str, Any] | None = None

        if parsed.kind == "code" and parsed.code:
            res = run_code(parsed.code, self._store)
            sandbox_out, sandbox_err = res.stdout, res.error
            if res.error:
                self.sandbox_errors += 1
            for req in res.actions:
                d = self._govern_single(req, legal, hw, state_hash)
                if d is not None:
                    self._queue.append(d)
        elif parsed.kind == "macro":
            self._arm_macro(parsed.macro, legal, hw)
        elif parsed.kind == "actions":
            for a in parsed.actions:
                d = self._govern_single(a, legal, hw, state_hash)
                if d is not None:
                    self._queue.append(d)

        chosen = self._queue[0] if self._queue else None
        self._record_turn(obs, prompt, raw, parsed, sandbox_out, sandbox_err,
                          chosen, frame, latency_ms)

    def _govern_single(self, a: dict[str, Any], legal: set[str],
                       hw: tuple[int, int], state_hash: str) -> dict[str, Any] | None:
        req = ActionRequest(str(a.get("action", "")).upper(),
                            _as_int(a.get("row")), _as_int(a.get("col")))
        dec = self._governor.check_single(req, legal=legal, board_hw=hw,
                                          state_hash=state_hash)
        if not dec.accepted:
            self.governor_rejections += 1
            return None
        return dec.action

    def _arm_macro(self, macro: list[dict[str, Any]], legal: set[str],
                   hw: tuple[int, int]) -> None:
        steps = [
            MacroStep(
                action=str(s.get("action", "")).upper(),
                precondition=str(s.get("precondition", "")),
                predicted_invariant=str(s.get("predicted_invariant", s.get("invariant", ""))),
                row=_as_int(s.get("row")), col=_as_int(s.get("col")),
            )
            for s in macro if isinstance(s, dict)
        ]
        dec = self._governor.submit_macro(steps, legal=legal, board_hw=hw)
        if dec.accepted and dec.action is not None:
            self._queue.append(dec.action)
            self._macro_active = True
        else:
            self.governor_rejections += 1

    def _fallback(self, obs: Any) -> dict[str, Any]:
        legal = _legal_names(obs)
        for name in ("UP", "DOWN", "LEFT", "RIGHT", "SPACE"):
            if name in legal:
                return {"action": name}
        if "MOUSE" in legal:
            return {"action": "MOUSE", "row": 32, "col": 32}
        return {"action": "UNDO"} if "UNDO" in legal else {"action": "RESET"}

    # ----- packet / transcript helpers ---------------------------------------
    def _game_ctx(self, obs: Any, legal: set[str]) -> dict[str, Any]:
        return {
            "game_id": self._game_id,
            "level": self._last_levels + 1,
            "turn_in_level": self._turn,
            "total_actions": self._governor.total_actions,
            "legal_actions": sorted(legal),
            "coordinate_rule": "MOUSE(row, col), zero-based",
        }

    def _last_action_dict(self) -> dict[str, Any] | None:
        if self._prev_action is None:
            return None
        return {"action": self._prev_action.get("action")}

    def _record_turn(self, obs: Any, prompt: str, raw: str, parsed: ParsedOutput,
                     sandbox_out: str, sandbox_err: str,
                     chosen: dict[str, Any] | None, frame: np.ndarray,
                     latency_ms: float) -> None:
        if self._recorder is None:
            return
        rec = TurnRecord(
            turn=self._turn, game_id=self._game_id, level=self._last_levels,
            total_actions=self._governor.total_actions,
            legal_actions=sorted(_legal_names(obs)),
            prompt_text=prompt, image_hash=image_hash(None), raw_output=raw,
            parsed_tool_calls=normalize_parse(raw),
            sandbox_stdout=sandbox_out, sandbox_error=sandbox_err,
            action=chosen, frame_after_hash=base_hash(frame),
            memory_after=self._memory.to_dict(), latency_ms=latency_ms,
        )
        self._recorder.record(rec)

    def _to_gameaction(self, action: dict[str, Any], obs: Any) -> Any:
        from admorphiq.types import ActionType, GameAction

        name = str(action.get("action", "")).upper()
        if name == "RESET":
            return self._convert(GameAction.reset())
        if name == "MOUSE":
            col = _as_int(action.get("col")) or 0
            row = _as_int(action.get("row")) or 0
            return self._convert(GameAction.coordinate(x=col, y=row))
        aid = ID_BY_NAME.get(name, 1)
        return self._convert(GameAction.simple(ActionType(aid)))

    def _is_win(self, obs: Any) -> bool:
        return _state_name(obs) == "WIN"


def _as_int(v: Any) -> int | None:
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return int(v)
    if isinstance(v, str) and v.lstrip("-").isdigit():
        return int(v)
    return None


# --- observation helpers (shared with the other agents) ---------------------
from admorphiq.graph_frontier_agent import (  # noqa: E402
    _availability,
    _frame_2d,
    _has_frame,
    _levels_completed,
    _state_name,
)


def _legal_names(obs: Any) -> set[str]:
    simple_ids, action6_ok = _availability(obs)
    legal = {NAME_BY_ID[i] for i in simple_ids if i in NAME_BY_ID}
    if action6_ok:
        legal.add("MOUSE")
    return legal
