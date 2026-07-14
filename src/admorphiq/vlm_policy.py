"""VLMPolicyAgent — vision-LLM-as-policy for ARC-AGI-3 (R54).

A multimodal LLM plays the game directly: each decision boundary renders the
current 64x64 frame to a LABELED image (upscaled grid + coordinate ruler), hands
it to a vision model together with a compact state summary, the reflection
memory, the legal action set, and a dead-signature list, and asks for ONE JSON
action (or a short 1-4 action plan queue). This is the M1 #2/#3 recipe (Reki /
forge, Gemma-4-31B): render → pick-JSON action under legal constraints +
reflection memory + dead-signature avoidance + plan queue + JSON self-repair.

Design notes:
- **Model-agnostic**: the model name comes from ``VLM_MODEL`` (default the small
  local gemma4 vision proxy). Swapping to the 31B deploy model is config-only.
- **Generic**: no game ids. Frame -> image + coordinate labeling is game-agnostic;
  the coordinate convention (x = column, y = row, both 0-63) is stated to the LLM.
- **Offline-safe / testable**: the VLM callable is injected; it degrades to a
  simple exploratory fallback when the model is unreachable, so the harness never
  crashes on a network miss.

The agent exposes the harness contract (``is_done`` / ``choose_action``) and
returns official ``GameAction`` objects via ``AdmorphiqAdapter._convert_action``.
"""

from __future__ import annotations

import base64
import io
import json
import os
import re
import urllib.request
from typing import Any, Callable

import numpy as np

from admorphiq.graph_frontier_agent import (
    _availability,
    _frame_2d,
    _has_frame,
    _levels_completed,
    _state_name,
)

# ---------------------------------------------------------------------------
# ARC canonical 16-color palette (indices 0-15 -> RGB). Values 0-9 are the
# well-known ARC-AGI colors; 10-15 extend the range ARC-AGI-3 frames can use.
# ---------------------------------------------------------------------------
ARC_PALETTE: list[tuple[int, int, int]] = [
    (0, 0, 0),        # 0  black
    (0, 116, 217),    # 1  blue
    (255, 65, 54),    # 2  red
    (46, 204, 64),    # 3  green
    (255, 220, 0),    # 4  yellow
    (170, 170, 170),  # 5  grey
    (240, 18, 190),   # 6  magenta
    (255, 133, 27),   # 7  orange
    (127, 219, 255),  # 8  azure
    (135, 12, 37),    # 9  maroon
    (149, 82, 199),   # 10 purple
    (0, 128, 128),    # 11 teal
    (170, 255, 195),  # 12 mint
    (128, 128, 0),    # 13 olive
    (255, 255, 255),  # 14 white
    (60, 60, 60),     # 15 dark grey
]

VLM_MODEL_DEFAULT = "gemma4:26b-a4b-it-qat"
VLM_HOST_DEFAULT = "http://localhost:11434"

# ACTION1-5 movement / simple commands, 6 = click (needs x,y), 7 = cancel/undo.
_ACTION_HINT = {
    1: "ACTION1 (simple move/command, no coords)",
    2: "ACTION2 (simple move/command, no coords)",
    3: "ACTION3 (simple move/command, no coords)",
    4: "ACTION4 (simple move/command, no coords)",
    5: "ACTION5 (simple move/command, no coords)",
    6: "ACTION6 (click at x,y — REQUIRES integer x and y in 0-63)",
    7: "ACTION7 (cancel / undo / commit)",
}


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------
def _rgb_frame(grid: np.ndarray) -> np.ndarray:
    """Map a (H, W) index grid to an (H, W, 3) uint8 RGB image."""
    g = np.asarray(grid)
    if g.ndim >= 3:
        g = g[0]
    g = g.astype(np.int64)
    n = len(ARC_PALETTE)
    idx = np.clip(g, 0, n - 1)
    lut = np.array(ARC_PALETTE, dtype=np.uint8)
    return lut[idx]


def render_frame_png(
    grid: np.ndarray,
    *,
    cell: int = 12,
    ruler_step: int = 8,
    margin: int = 22,
) -> bytes:
    """Render an index grid to a labeled PNG (bytes).

    The grid is upscaled so each cell is ``cell`` px; light gridlines and
    coordinate ruler labels are drawn every ``ruler_step`` cells. The top ruler
    labels columns (x), the left ruler labels rows (y); both run 0-63. Returns
    the PNG file bytes.
    """
    from PIL import Image, ImageDraw

    rgb = _rgb_frame(grid)
    h, w = rgb.shape[:2]
    img_w, img_h = w * cell, h * cell

    canvas = Image.new("RGB", (img_w + margin, img_h + margin), (30, 30, 30))
    board = Image.fromarray(rgb, "RGB").resize((img_w, img_h), Image.NEAREST)
    canvas.paste(board, (margin, margin))

    draw = ImageDraw.Draw(canvas)
    grid_color = (90, 90, 90)
    label_color = (230, 230, 230)

    for c in range(0, w + 1, ruler_step):
        x = margin + c * cell
        draw.line([(x, margin), (x, margin + img_h)], fill=grid_color, width=1)
        if c < w:
            draw.text((x + 1, 4), str(c), fill=label_color)
    for r in range(0, h + 1, ruler_step):
        y = margin + r * cell
        draw.line([(margin, y), (margin + img_w, y)], fill=grid_color, width=1)
        if r < h:
            draw.text((2, y + 1), str(r), fill=label_color)

    buf = io.BytesIO()
    canvas.save(buf, format="PNG")
    return buf.getvalue()


def ascii_grid(grid: np.ndarray, *, step: int = 8) -> str:
    """Compact ASCII rendering of the index grid, with x/y ruler headers.

    Cells are single base-16 digits (0-9, a-f). Column/row headers mark every
    ``step`` cells so the LLM can cross-reference the labeled image.
    """
    g = np.asarray(grid)
    if g.ndim >= 3:
        g = g[0]
    g = g.astype(np.int64)
    h, w = g.shape
    digits = "0123456789abcdef"
    header = "    " + "".join(
        (str((c // step * step) % 100).ljust(step) if c % step == 0 else "")
        for c in range(w)
    )
    lines = [header[: 4 + w]]
    for r in range(h):
        marker = str(r).rjust(3) if r % step == 0 else "   "
        row = "".join(digits[min(int(v), 15)] for v in g[r])
        lines.append(f"{marker} {row}")
    return "\n".join(lines)


def _b64png(png_bytes: bytes) -> str:
    return base64.b64encode(png_bytes).decode("ascii")


# ---------------------------------------------------------------------------
# VLM call plumbing (ollama multimodal chat)
# ---------------------------------------------------------------------------
def ollama_vlm(
    model: str | None = None,
    host: str | None = None,
    *,
    num_ctx: int = 8192,
    num_predict: int = 512,
    timeout: float = 180.0,
) -> Callable[[str, list[str]], str]:
    """Return a ``vlm(prompt, images) -> str`` callable backed by ollama.

    ``images`` is a list of base64-encoded PNG strings attached to the user
    message. Offline only — no external network. The model name defaults to
    ``VLM_MODEL`` so the 31B deploy swap is config-only.
    """
    model = model or os.environ.get("VLM_MODEL", VLM_MODEL_DEFAULT)
    host = host or os.environ.get("VLM_HOST", VLM_HOST_DEFAULT)

    def _call(prompt: str, images: list[str]) -> str:
        msg: dict[str, Any] = {"role": "user", "content": prompt}
        if images:
            msg["images"] = images
        body = {
            "model": model,
            "stream": False,
            "think": False,
            "messages": [msg],
            "options": {
                "temperature": 0.0,
                "num_ctx": num_ctx,
                "num_predict": num_predict,
            },
        }
        req = urllib.request.Request(
            f"{host}/api/chat",
            data=json.dumps(body).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read())["message"]["content"]

    return _call


# ---------------------------------------------------------------------------
# JSON action parsing + self-repair
# ---------------------------------------------------------------------------
def _extract_json(text: str) -> dict[str, Any] | None:
    """Pull the first JSON object out of an LLM reply, tolerating code fences.

    Returns the parsed dict, or ``None`` when nothing parseable is found.
    """
    if not text:
        return None
    # Strip markdown fences if present.
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    candidates: list[str] = []
    if fenced:
        candidates.append(fenced.group(1))
    # Greedy brace match as a fallback.
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        candidates.append(text[start : end + 1])
    for cand in candidates:
        try:
            obj = json.loads(cand)
            if isinstance(obj, dict):
                return obj
        except (json.JSONDecodeError, ValueError):
            continue
    return None


def parse_plan(
    text: str,
    legal_ids: set[int],
    action6_ok: bool,
) -> tuple[list[tuple[int, int, int]], dict[str, Any]]:
    """Parse an LLM reply into a legal action plan + metadata.

    Returns ``(plan, meta)`` where ``plan`` is a list of ``(action_id, x, y)``
    tuples (each already masked to the legal set; illegal or malformed actions
    dropped), and ``meta`` carries the model's ``observation`` / ``hypothesis``
    strings when present. Self-repairs common shape errors (single-action dicts,
    string action ids like ``"ACTION6"``, missing coords).
    """
    obj = _extract_json(text)
    meta: dict[str, Any] = {}
    if not isinstance(obj, dict):
        return [], meta

    for key in ("observation", "hypothesis"):
        val = obj.get(key)
        if isinstance(val, str):
            meta[key] = val.strip()

    raw_plan = obj.get("plan")
    if raw_plan is None:
        # Single-action shape: {action, x, y} at top level.
        raw_plan = [obj]
    elif isinstance(raw_plan, dict):
        raw_plan = [raw_plan]
    if not isinstance(raw_plan, list):
        return [], meta

    plan: list[tuple[int, int, int]] = []
    for step in raw_plan[:4]:
        if not isinstance(step, dict):
            continue
        aid = _coerce_action_id(step.get("action", step.get("action_id")))
        if aid is None or aid not in legal_ids:
            continue
        if aid == 6:
            if not action6_ok:
                continue
            x = _coerce_coord(step.get("x"))
            y = _coerce_coord(step.get("y"))
            if x is None or y is None:
                continue
            plan.append((6, x, y))
        else:
            plan.append((aid, 0, 0))
    return plan, meta


def _coerce_action_id(val: Any) -> int | None:
    """Coerce a model-emitted action field to an integer id 1-7."""
    if isinstance(val, bool):
        return None
    if isinstance(val, (int, float)):
        v = int(val)
        return v if 1 <= v <= 7 else None
    if isinstance(val, str):
        m = re.search(r"([1-7])", val)
        if m:
            return int(m.group(1))
    return None


def _coerce_coord(val: Any) -> int | None:
    """Coerce a coordinate field to an int in 0-63, or ``None``."""
    if isinstance(val, bool):
        return None
    if isinstance(val, (int, float)):
        return int(np.clip(int(val), 0, 63))
    if isinstance(val, str):
        m = re.search(r"-?\d+", val)
        if m:
            return int(np.clip(int(m.group()), 0, 63))
    return None


# ---------------------------------------------------------------------------
# The policy loop
# ---------------------------------------------------------------------------
_SYSTEM = (
    "You are playing an unknown 2D grid puzzle game on a 64x64 board. Your goal "
    "is to COMPLETE LEVELS by discovering the rules through play. You see a "
    "labeled image of the current board (a coordinate ruler marks columns=x and "
    "rows=y, both 0-63) plus an ASCII grid of the same board (cells are base-16 "
    "color digits). Choose actions to change the board toward completing the "
    "level. Play EFFICIENTLY — few, purposeful actions, near how a human would.\n"
    "Coordinate convention: x is the column (0=left..63=right), y is the row "
    "(0=top..63=bottom). ACTION6 clicks the cell at (x, y).\n"
    "Reply with ONE JSON object and NOTHING else:\n"
    '{"observation": "<what changed / what you see>", '
    '"hypothesis": "<your current theory of the goal and rules>", '
    '"plan": [{"action": <id>, "x": <0-63>, "y": <0-63>}, ...]}\n'
    "The plan is 1 to 4 actions to execute in order. Include x and y ONLY for "
    "action 6; omit them otherwise. Use ONLY actions from the legal list. Do NOT "
    "repeat actions listed as having no effect (dead)."
)


class VLMPolicyAgent:
    """Vision-LLM-as-policy agent (harness contract).

    Per decision boundary (plan queue empty): render the current frame to a
    labeled image, prompt the vision model with the state summary + reflection
    memory + legal actions + dead-signature list, parse a 1-4 action JSON plan,
    and queue it. Queued actions run without further LLM calls (amortizing the
    per-call latency), and the loop re-plans when the queue empties. Learns
    online per game: dead-signature avoidance from observed no-change actions and
    a running reflection memory of what was tried and the current hypothesis.
    """

    restart_on_game_over = True

    def __init__(
        self,
        vlm: Callable[[str, list[str]], str] | None = None,
        *,
        giveup: int = 8000,
        reflect_every: int = 10,
    ) -> None:
        from admorphiq.adapter import AdmorphiqAdapter

        self._convert = AdmorphiqAdapter._convert_action
        self._vlm = vlm if vlm is not None else ollama_vlm()
        self.giveup = giveup
        self.reflect_every = reflect_every
        self.last_hypothesis: str | None = None
        self._reset_level()
        self._llm_ok = True

    def _reset_level(self) -> None:
        self._queue: list[tuple[int, int, int]] = []
        self._prev_frame: np.ndarray | None = None
        self._prev_action: tuple[int, int, int] | None = None
        self._dead: set[tuple[int, int, int]] = set()
        self._history: list[str] = []
        self._steps = 0
        self._last_levels = 0
        self._explore_i = 0

    # ----- harness contract ---------------------------------------------------

    def is_done(self, frames: list[Any], latest_frame: Any) -> bool:
        if _state_name(latest_frame) == "WIN":
            return True
        return self._steps >= self.giveup

    def choose_action(self, frames: list[Any], latest_frame: Any) -> Any:
        from admorphiq.types import GameAction

        obs = latest_frame
        state = _state_name(obs)

        levels = _levels_completed(obs)
        if levels > self._last_levels:
            self._reset_level()
            self._last_levels = levels

        if state in ("GAME_OVER", "NOT_PLAYED"):
            self._prev_frame = None
            self._prev_action = None
            self._queue.clear()
            return self._convert(GameAction.reset())
        if not _has_frame(obs):
            return self._convert(GameAction.reset())

        frame = _frame_2d(obs).astype(np.int16)
        self._record_transition(frame)

        simple_ids, action6_ok = _availability(obs)
        legal = set(simple_ids)
        if action6_ok:
            legal.add(6)
        if not legal:
            return self._convert(GameAction.reset())

        if not self._queue:
            self._queue = self._replan(frame, legal, action6_ok)
        if not self._queue:
            self._queue = [self._explore(legal, action6_ok)]

        aid, x, y = self._queue.pop(0)
        self._prev_frame = frame
        self._prev_action = (aid, x, y)
        self._steps += 1
        return self._to_action(aid, x, y)

    # ----- internals ----------------------------------------------------------

    def _record_transition(self, frame: np.ndarray) -> None:
        """Note whether the previous action changed the board; update dead set."""
        if self._prev_action is None or self._prev_frame is None:
            return
        changed = not np.array_equal(frame, self._prev_frame)
        aid, x, y = self._prev_action
        sig = (aid, x // 8, y // 8) if aid == 6 else (aid, -1, -1)
        if changed:
            self._dead.discard(sig)
        else:
            self._dead.add(sig)
        where = f" @({x},{y})" if aid == 6 else ""
        self._history.append(
            f"ACTION{aid}{where} -> {'changed' if changed else 'no effect'}"
        )
        self._history = self._history[-self.reflect_every :]

    def _replan(
        self, frame: np.ndarray, legal: set[int], action6_ok: bool
    ) -> list[tuple[int, int, int]]:
        """Ask the vision model for a 1-4 action plan; return [] on failure."""
        try:
            png = render_frame_png(frame)
            prompt = self._build_prompt(frame, legal, action6_ok)
            reply = self._vlm(prompt, [_b64png(png)])
        except Exception:
            self._llm_ok = False
            return []
        plan, meta = parse_plan(reply, legal, action6_ok)
        if meta.get("hypothesis"):
            self.last_hypothesis = meta["hypothesis"]
        # Drop leading actions we already know are inert so the model's plan
        # doesn't waste budget re-confirming dead signatures.
        plan = [step for step in plan if not self._is_dead(step)]
        return plan

    def _is_dead(self, step: tuple[int, int, int]) -> bool:
        aid, x, y = step
        sig = (aid, x // 8, y // 8) if aid == 6 else (aid, -1, -1)
        return sig in self._dead

    def _build_prompt(
        self, frame: np.ndarray, legal: set[int], action6_ok: bool
    ) -> str:
        legal_lines = "\n".join(
            f"  - {_ACTION_HINT[a]}" for a in sorted(legal) if a in _ACTION_HINT
        )
        dead_lines = self._describe_dead()
        history = "\n".join(self._history[-self.reflect_every :]) or "(none yet)"
        reflection = self.last_hypothesis or "(no hypothesis yet)"
        parts = [
            _SYSTEM,
            f"\nLegal actions this turn:\n{legal_lines}",
            f"\nActions observed to have NO EFFECT (avoid repeating):\n{dead_lines}",
            f"\nRecent action history:\n{history}",
            f"\nYour current running hypothesis:\n{reflection}",
            f"\nASCII board (base-16 color per cell):\n{ascii_grid(frame)}",
            "\nStudy the labeled image, then output the JSON plan.",
        ]
        return "\n".join(parts)

    def _describe_dead(self) -> str:
        if not self._dead:
            return "(none yet)"
        items: list[str] = []
        for aid, cx, cy in sorted(self._dead):
            if aid == 6:
                items.append(f"ACTION6 near ({cx * 8}-{cx * 8 + 7},{cy * 8}-{cy * 8 + 7})")
            else:
                items.append(f"ACTION{aid}")
        return "\n".join(f"  - {it}" for it in items[:16])

    def _explore(self, legal: set[int], action6_ok: bool) -> tuple[int, int, int]:
        """Fallback exploratory action when the model gives no usable plan.

        Cycles simple actions first; if only clicking is legal, scans coarse grid
        centers that are not yet known dead.
        """
        simple = sorted(a for a in legal if a != 6)
        if simple:
            aid = simple[self._explore_i % len(simple)]
            self._explore_i += 1
            if (aid, -1, -1) not in self._dead:
                return (aid, 0, 0)
        if action6_ok:
            for _ in range(64):
                cx = (self._explore_i % 8)
                cy = (self._explore_i // 8) % 8
                self._explore_i += 1
                if (6, cx, cy) not in self._dead:
                    return (6, cx * 8 + 4, cy * 8 + 4)
        if simple:
            return (simple[self._explore_i % len(simple)], 0, 0)
        return (6, 32, 32) if action6_ok else (sorted(legal)[0], 0, 0)

    def _to_action(self, aid: int, x: int, y: int) -> Any:
        from admorphiq.types import ActionType, GameAction

        if aid == 6:
            return self._convert(GameAction.coordinate(x, y))
        return self._convert(GameAction.simple(ActionType(aid)))
