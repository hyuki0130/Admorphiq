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
from admorphiq.repl_agent.transcript import (
    TranscriptRecorder,
    TurnRecord,
    image_hash,
)
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

# System-prompt preamble (v4): the v3 run showed the model NEVER used the REPL
# (0 code blocks / 0 inspection calls across 173 turns) and clicked illegally on
# movement games (55 illegal MOUSE proposals) — because nothing told it the
# sandbox exists or bound it to the legal set. This describes the REPL + tools +
# the legal-action rule + brevity. Generic (no game specifics).
_SYSTEM_PROMPT = (
    "/no_think\n"
    "You are an agent playing an unknown 2D grid game. GOAL: complete as many "
    "LEVELS as possible using FEW actions (action efficiency is scored).\n\n"
    "You control a stateless Python REPL pre-loaded with the current frames. "
    "Each turn do ONE of:\n"
    "  (A) Write a SINGLE ```python block to INSPECT and/or ACT with these "
    "functions:\n"
    "      objects(t=-1) -> [{id,color,bbox_rc,centroid_rc,area,holes,"
    "contained_by,adjacent,safe_click_rc}]  # _rc = (row,col)\n"
    "      crop((y0,x0,y1,x1),t=-1), ascii(region=None,t=-1), mask(id,t=-1), "
    "compare(t1,t2), relations(id,t=-1)\n"
    "      shortest_path(start, goals, passable_mask) -> path  # YOU supply "
    "start/goals/passability; pure BFS\n"
    "      action(kind, row=None, col=None)  # perform an action; MOUSE needs "
    "row,col\n"
    "     Inspect BEFORE acting when an effect is unknown; call action(...) in "
    "the block to move.\n"
    "  (B) Or, if the move is clear, output ONE action line: MOUSE(row, col) or "
    "UP / DOWN / LEFT / RIGHT / SPACE.\n\n"
    "HARD RULES:\n"
    "  - Use ONLY the actions in GAME.legal_actions. If MOUSE is not listed, DO "
    "NOT click — move instead.\n"
    "  - Coordinates are (row, col) = (y, x), each 0-63.\n"
    "  - Do NOT print the whole board. At most ~4 short lines of reasoning, then "
    "the code block or action line LAST.\n"
    "  - Before your action, add ONE line `PREDICT: changed` or `PREDICT: "
    "no_change` — whether your action will change the board — then a few words "
    "of why. This is scored against what actually happens."
)


def _legal_reminder(legal: set[str]) -> str:
    line = f"Legal actions THIS turn: {sorted(legal)}."
    if "MOUSE" not in legal:
        line += " MOUSE is NOT available — use a movement action."
    return "\n\n" + line + " Respond now with a python block or one action line."


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
                 timeout: float = 300.0, max_tokens: int = 512,
                 enable_thinking: bool = False) -> None:
        self.base_url = (base_url or os.environ.get("REPL_LLM_BASE_URL", "")).rstrip("/")
        if not self.base_url:
            raise RuntimeError("REPL_LLM_BASE_URL is not set — cannot serve the REPL agent")
        self.model = model or os.environ.get("REPL_LLM_MODEL", "")
        # 300s (not 120s): a first-run bug was Qwen 3.6 emitting 9-11k chars of
        # chain-of-thought at ~35 tok/s, timing out the client mid-answer.
        self.timeout = timeout
        self.max_tokens = max_tokens
        self.enable_thinking = enable_thinking
        # Populated after each complete(): {"finish_reason", "tokens"} so the
        # agent can record truthful response metadata (usage, truncation).
        self.last_meta: dict[str, Any] = {}

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
            "max_tokens": self.max_tokens,
            # vLLM passes chat_template_kwargs to the Qwen template; disabling
            # thinking removes the 9-11k-char CoT that blew the latency budget.
            "chat_template_kwargs": {"enable_thinking": self.enable_thinking},
        }
        req = urllib.request.Request(
            f"{self.base_url}/chat/completions", data=json.dumps(body).encode(),
            headers={"Content-Type": "application/json"}, method="POST",
        )
        with urllib.request.urlopen(req, timeout=self.timeout) as r:
            data = json.loads(r.read())
        choice = data["choices"][0]
        usage = data.get("usage") or {}
        details = usage.get("completion_tokens_details") or {}
        prompt_details = usage.get("prompt_tokens_details") or {}
        self.last_meta = {
            "finish_reason": choice.get("finish_reason", ""),
            "tokens": {
                "input": usage.get("prompt_tokens", 0),
                "output": usage.get("completion_tokens", 0),
                "reasoning": details.get("reasoning_tokens", 0),
                "cached": prompt_details.get("cached_tokens", 0),
            },
        }
        return choice["message"]["content"]


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


def strip_thinking(text: str) -> str:
    """Remove a Qwen ``<think>…</think>`` chain-of-thought before parsing.

    Keeps the text after the last ``</think>`` (the actual answer). If a
    ``<think>`` opened but never closed (truncated CoT), there is no answer —
    return "" so parsing falls through to the safe fallback.
    """
    if not text:
        return ""
    lower = text.lower()
    close = lower.rfind("</think>")
    if close != -1:
        return text[close + len("</think>"):].strip()
    if "<think>" in lower:
        return ""  # unclosed thinking block => no usable answer
    return text


_MOUSE_RE = re.compile(r"MOUSE\s*\(\s*(\d+)\s*,\s*(\d+)\s*\)", re.IGNORECASE)
_MOVE_RE = re.compile(r"^\s*(UP|DOWN|LEFT|RIGHT|SPACE|RESET)\s*$", re.IGNORECASE)


_PREDICT_RE = re.compile(
    r"PREDICT\s*:\s*(no[_ ]?change|changed|change)\b[\s:.\-]*(.*)", re.IGNORECASE)


def parse_prediction(text: str) -> dict[str, Any] | None:
    """Extract a ``PREDICT: changed|no_change — <reason>`` line, if present.

    Returns ``{"prediction": "changed"|"no_change", "hypothesis": <reason>}`` so
    the agent can score it against the observed transition next turn.
    """
    m = _PREDICT_RE.search(text or "")
    if not m:
        return None
    pred = "no_change" if m.group(1).lower().replace(" ", "_").startswith("no") \
        else "changed"
    reason = m.group(2).strip().lstrip("-—:.() ").strip()
    return {"prediction": pred, "hypothesis": reason[:200]}


def _bare_text_action(text: str) -> dict[str, Any] | None:
    """Accept the model's bare-text action ONLY from the LAST non-empty line.

    Codex v3 review: scanning all lines recovered a STALE action mentioned mid-
    reasoning (su15 t4 executed an incidental ``MOUSE(63,58)`` from an earlier
    explanatory line while the real final line was truncated). Per the action-
    LAST contract, only the final line counts — no incidental recovery.
    """
    lines = [ln for ln in text.splitlines() if ln.strip()]
    if not lines:
        return None
    line = lines[-1]
    m = _MOUSE_RE.search(line)
    if m:
        return {"action": "MOUSE", "row": int(m.group(1)), "col": int(m.group(2))}
    mv = _MOVE_RE.match(line)
    if mv:
        return {"action": mv.group(1).upper()}
    return None


def parse_model_output(raw: str) -> ParsedOutput:
    """Parse a reply into code / action(s) / macro / none (deterministic).

    Strips any ``<think>`` block first, then tries: a python code block, a JSON
    object (macro / plan / single action), and finally a BARE-TEXT action
    (``MOUSE(r, c)`` / ``UP`` / …) — the shape Qwen naturally emits.
    """
    raw = strip_thinking(raw)
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
    bare = _bare_text_action(raw or "")
    if bare is not None:
        return ParsedOutput(kind="actions", actions=[bare])
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
        render_images: bool = True,
        game_id: str = "",
        max_tool_rounds: int = 1,
    ) -> None:
        from admorphiq.adapter import AdmorphiqAdapter

        self._convert = AdmorphiqAdapter._convert_action
        self._llm = llm
        self.giveup = giveup
        self.render_images = render_images
        # Bounded tool loop: an inspection-only code block returns its stdout to
        # the model for up to this many extra rounds before an action is required
        # (Codex defect #1). 0 = no tool loop (the JSON-only arm).
        self.max_tool_rounds = max_tool_rounds
        self._recorder = recorder
        self._builder = TurnPacketBuilder(token_budget=token_budget)
        self.last_hypothesis: str | None = None
        self._game_id = game_id
        self._last_source = "none"
        self._last_outcome: dict[str, Any] = {}
        # Game-lifetime observability counters (read by the bench diagnostics).
        self.llm_calls = 0
        self.parse_failures = 0
        self.governor_rejections = 0
        self.sandbox_errors = 0
        self.llm_errors = 0
        self.truncations = 0
        self.inspections = 0
        self.predictions_made = 0
        self.predictions_correct = 0
        self._pending_prediction: dict[str, Any] | None = None
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

        decided = False
        if not self._queue:
            self._decide(obs, frame, scene)
            decided = True
        if not self._queue:
            self._queue = [self._fallback(obs, base_hash(frame), frame.shape)]
            self._last_source = "fallback"
        elif decided:
            self._last_source = getattr(self, "_decided_source", "llm")
        else:
            self._last_source = "macro"

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
        # Outcome of the PREVIOUS action, surfaced next turn in LAST_ACTION so the
        # model does not have to reverse-engineer what its action did.
        self._last_outcome = {
            "board_changed": changed,
            "level_completed": level_up,
            "game_over": state == "GAME_OVER",
        }
        act = (self._prev_action or {}).get("action", "?")
        events = [f"t{self._turn} {act}: {e['type']} {e.get('id', '')}".strip()
                  for e in scene.events]
        self._history.push(
            {"turn": self._turn, "action": self._prev_action,
             "source": self._last_source, "board_changed": changed}, events)
        self._score_prediction(changed)
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

    def _score_prediction(self, changed: bool) -> None:
        """Score the previous turn's PREDICT against the observed change and feed
        the falsifiable memory (so MEMORY evolves — the v3 static-memory gap)."""
        pred = self._pending_prediction
        if pred is None:
            return
        self._pending_prediction = None
        correct = (pred["prediction"] == "changed") == changed
        self.predictions_made += 1
        if correct:
            self.predictions_correct += 1
        act = (self._prev_action or {}).get("action", "?")
        text = pred.get("hypothesis") or f"{act} -> {pred['prediction']}"
        self._memory.record_prediction(text, pred["prediction"], correct)

    def _render_image(self, frame: np.ndarray) -> tuple[list[str] | None, list[str]]:
        """Render the current frame to a labeled PNG for the multimodal call.

        Returns ``(images, image_hashes)``. Disabled (``None``) for the JSON-only
        arm or if rendering fails (text packet still carries the scene).
        """
        if not self.render_images:
            return None, []
        try:
            import base64

            from admorphiq.vlm_policy import render_frame_png
            png = render_frame_png(np.asarray(frame))
            return [base64.b64encode(png).decode("ascii")], [image_hash(png)]
        except Exception:  # noqa: BLE001 — image is an aid; text packet suffices
            return None, []

    def _decide(self, obs: Any, frame: np.ndarray, scene: Any) -> None:
        legal = _legal_names(obs)
        hw = frame.shape
        state_hash = base_hash(frame)
        packet = self._builder.build(
            game=self._game_ctx(obs, legal), last_action=self._last_action_dict(),
            scene=scene, prev_scene=self._prev_scene, frame=frame,
            prev_frame=self._prev_frame, history=self._history, memory=self._memory)
        base_prompt = (_SYSTEM_PROMPT + "\n\n" + self._builder.to_yaml(packet)
                       + _legal_reminder(legal))
        images, img_hashes = self._render_image(frame)

        # Bounded tool loop: an inspection-only code block gets its stdout RETURNED
        # to the model (no env action) for another round, up to max_tool_rounds.
        # An action/macro (or exhausting the rounds) ends the loop.
        tool_context = ""
        for round_i in range(self.max_tool_rounds + 1):
            prompt = base_prompt + tool_context
            call_images = images if round_i == 0 else None  # frame is fixed mid-decision
            round_hashes = img_hashes if round_i == 0 else []

            t0 = time.time()
            try:
                raw = self._llm.complete(prompt, call_images)
            except Exception as exc:  # noqa: BLE001 — a slow/failed call must not end the game
                latency_ms = (time.time() - t0) * 1000.0
                self.llm_calls += 1
                self.llm_errors += 1
                self._record_turn(obs, prompt, "", parse_model_output(""), "",
                                  f"{type(exc).__name__}: {exc}", None, frame,
                                  latency_ms, image_hashes=round_hashes)
                return
            latency_ms = (time.time() - t0) * 1000.0
            self.llm_calls += 1
            meta = getattr(self._llm, "last_meta", {}) or {}
            finish_reason = str(meta.get("finish_reason", ""))
            if finish_reason == "length":
                self.truncations += 1

            parsed = parse_model_output(raw)
            if parsed.kind == "none":
                self.parse_failures += 1
            self._decided_source = {"code": "code", "macro": "macro",
                                    "actions": "llm"}.get(parsed.kind, "llm")
            prediction = parse_prediction(raw)
            sandbox_out = sandbox_err = ""
            inspected_only = False

            if parsed.kind == "code" and parsed.code:
                res = run_code(parsed.code, self._store)
                sandbox_out, sandbox_err = res.stdout, res.error
                if res.error:
                    self.sandbox_errors += 1
                if res.actions:
                    for req in res.actions:
                        d = self._govern_single(req, legal, hw, state_hash)
                        if d is not None:
                            self._queue.append(d)
                else:
                    inspected_only = True  # inspection round — NEVER an env action
                    self.inspections += 1
            elif parsed.kind == "macro":
                self._arm_macro(parsed.macro, legal, hw)
            elif parsed.kind == "actions":
                for a in parsed.actions:
                    d = self._govern_single(a, legal, hw, state_hash)
                    if d is not None:
                        self._queue.append(d)

            chosen = self._queue[0] if self._queue else None
            if not inspected_only:
                self._pending_prediction = prediction  # scored against the action
            self._record_turn(obs, prompt, raw, parsed, sandbox_out, sandbox_err,
                              chosen, frame, latency_ms,
                              finish_reason=finish_reason, tokens=meta.get("tokens"),
                              prediction=prediction, image_hashes=round_hashes)

            if self._queue or not inspected_only:
                return  # got an action / macro / no-usable-output -> done
            # inspection-only: return the bounded stdout to the model for one more
            # round; the fallback (choose_action) only fires after the rounds.
            tool_context = (
                f"\n\nTOOL OUTPUT (round {round_i}, inspection only — NO action "
                f"taken yet):\n{sandbox_out[:1500]}"
                + (f"\nERROR: {sandbox_err[:400]}" if sandbox_err else "")
                + "\nNow choose an action (or inspect once more)."
            )

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

    def _fallback(self, obs: Any, state_hash: str,
                  hw: tuple[int, int]) -> dict[str, Any]:
        """A GOVERNED fallback (Codex defect #4/#5): the fallback used to bypass
        the governor and could repeat the same action in the same state. Now it
        runs each candidate through the governor and returns the first accepted
        (legal + not a repeat) — so the fallback can't loop, and it is disclosed
        next turn via LAST_ACTION source=fallback.
        """
        legal = _legal_names(obs)
        candidates: list[dict[str, Any]] = [
            {"action": n} for n in ("UP", "DOWN", "LEFT", "RIGHT", "SPACE")
            if n in legal
        ]
        if "MOUSE" in legal:
            candidates.append({"action": "MOUSE", "row": hw[0] // 2, "col": hw[1] // 2})
        if "UNDO" in legal:
            candidates.append({"action": "UNDO"})
        if not candidates:
            return {"action": "RESET"}
        for c in candidates:
            req = ActionRequest(c["action"], c.get("row"), c.get("col"))
            if self._governor.check_single(req, legal=legal, board_hw=hw,
                                           state_hash=state_hash).accepted:
                return c
        return candidates[0]  # all repeat-rejected: still must act

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
        """Full LAST_ACTION for the packet: action + coords + source + outcome
        (v5 causal-feedback fix — v3 dropped coords, source, and outcome)."""
        if self._prev_action is None:
            return None
        d: dict[str, Any] = dict(self._prev_action)  # action + row/col
        d["source"] = self._last_source
        d.update(self._last_outcome)  # board_changed / level_completed / game_over
        return d

    def _record_turn(self, obs: Any, prompt: str, raw: str, parsed: ParsedOutput,
                     sandbox_out: str, sandbox_err: str,
                     chosen: dict[str, Any] | None, frame: np.ndarray,
                     latency_ms: float, *, finish_reason: str = "",
                     tokens: dict[str, int] | None = None,
                     image_hashes: list[str] | None = None,
                     prediction: dict[str, Any] | None = None) -> None:
        if self._recorder is None:
            return
        rec = TurnRecord(
            turn=self._turn, game_id=self._game_id, level=self._last_levels,
            total_actions=self._governor.total_actions,
            legal_actions=sorted(_legal_names(obs)),
            prompt_text=prompt, image_hashes=image_hashes or [], raw_output=raw,
            finish_reason=finish_reason, parsed_tool_calls=normalize_parse(raw),
            sandbox_stdout=sandbox_out, sandbox_error=sandbox_err,
            action=chosen, prediction=prediction,
            # The decision is made ON this frame -> it is the BEFORE hash. The
            # post-action frame is only observed next turn; the bench event
            # stream is authoritative for the transition's after-hash.
            frame_before_hash=base_hash(frame),
            memory_after=self._memory.to_dict(), latency_ms=latency_ms,
            tokens=tokens or {},
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
