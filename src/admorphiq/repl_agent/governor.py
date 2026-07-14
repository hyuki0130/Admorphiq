"""Action governor for the code-REPL agent (R55 module 5).

Sits between the model's requested actions and the environment. It enforces the
design doc's action discipline so the model cannot damage RHAE with reactive or
repeated moves:

- **Legal-action enforcement** — a requested action must be in the current legal
  set; MOUSE(row, col) must be in bounds (row = y, col = x, zero-based).
- **Repeated state-action prevention** — the same action in the same state
  (frame hash) is rejected (the design warns repeated experiments waste actions).
- **Macro gating** — a 2-8 step macro is admitted ONLY if every step states a
  precondition AND a predicted invariant; it executes step-by-step and ABORTS on
  surprise (unexpected change / unexpected no-change / level completion / game
  over / signature mismatch). Speculative batches without invariants are refused.
- **Undo accounting** — UNDO is itself a counted environment action; the governor
  tracks total and undo counts so a probe+undo is correctly charged two actions.

Deterministic and model-free, so the transcript replayer can re-derive every
decision. MOUSE convention: row = y, col = x, zero-based.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

_MOVE_NAMES = {"UP", "DOWN", "LEFT", "RIGHT", "SPACE", "UNDO", "MOUSE"}
_CHANGE_WORDS = ("change", "move", "recolor", "appear", "disappear", "shift", "fill")
_NOCHANGE_WORDS = ("no change", "no_change", "unchanged", "nochange", "no effect")


@dataclass
class ActionRequest:
    """A single requested action. MOUSE needs row/col (zero-based y, x)."""

    action: str
    row: int | None = None
    col: int | None = None

    def signature(self) -> str:
        if self.action == "MOUSE":
            return f"MOUSE:{self.row}:{self.col}"
        return self.action

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"action": self.action}
        if self.action == "MOUSE":
            d["row"] = self.row
            d["col"] = self.col
        return d


@dataclass
class MacroStep:
    """One macro step with its stated precondition + predicted invariant."""

    action: str
    precondition: str
    predicted_invariant: str
    row: int | None = None
    col: int | None = None

    def request(self) -> ActionRequest:
        return ActionRequest(self.action, self.row, self.col)


@dataclass
class GovernorDecision:
    """Outcome of a governor check."""

    accepted: bool
    kind: str                       # "single" | "macro_step" | "rejected"
    reason: str = ""
    action: dict[str, Any] | None = None


def _expects_change(invariant: str) -> bool | None:
    """Interpret a predicted invariant: True=expect change, False=expect none,
    None=not a change/no-change assertion (only terminal surprises apply)."""
    low = invariant.lower()
    if any(w in low for w in _NOCHANGE_WORDS):
        return False
    if any(w in low for w in _CHANGE_WORDS):
        return True
    return None


class ActionGovernor:
    """Enforces legality, no-repeat, macro invariants, and undo accounting."""

    def __init__(self, macro_min: int = 2, macro_max: int = 8) -> None:
        self.macro_min = macro_min
        self.macro_max = macro_max
        self.total_actions = 0
        self.undo_count = 0
        self._seen: set[tuple[str, str]] = set()
        self._macro: list[MacroStep] = []
        self._macro_i = 0
        self._armed = False

    # ----- per-level lifecycle ------------------------------------------------
    def reset_level(self) -> None:
        """Clear per-level repeated-state memory + any armed macro.

        Action counters persist — they are game-wide RHAE accounting.
        """
        self._seen.clear()
        self._abort_macro()

    # ----- single action ------------------------------------------------------
    def check_single(
        self,
        req: ActionRequest,
        *,
        legal: set[str],
        board_hw: tuple[int, int],
        state_hash: str,
    ) -> GovernorDecision:
        """Validate one requested action against legality + no-repeat."""
        err = self._illegal_reason(req, legal, board_hw)
        if err:
            return GovernorDecision(False, "rejected", err)
        if (state_hash, req.signature()) in self._seen:
            return GovernorDecision(False, "rejected", "repeated state-action")
        return GovernorDecision(True, "single", "ok", req.to_dict())

    def _illegal_reason(
        self, req: ActionRequest, legal: set[str], board_hw: tuple[int, int]
    ) -> str:
        if req.action not in legal:
            return f"illegal action {req.action!r} (legal: {sorted(legal)})"
        if req.action == "MOUSE":
            if req.row is None or req.col is None:
                return "MOUSE requires row and col"
            h, w = board_hw
            if not (0 <= req.row < h and 0 <= req.col < w):
                return f"MOUSE ({req.row},{req.col}) out of bounds {board_hw}"
        return ""

    # ----- macros -------------------------------------------------------------
    def submit_macro(
        self,
        steps: list[MacroStep],
        *,
        legal: set[str],
        board_hw: tuple[int, int],
    ) -> GovernorDecision:
        """Admit a 2-8 step macro only if every step is legal and states a
        precondition + predicted invariant; arm it and return the first step."""
        if not (self.macro_min <= len(steps) <= self.macro_max):
            return GovernorDecision(
                False, "rejected",
                f"macro length {len(steps)} outside [{self.macro_min},{self.macro_max}]")
        for i, s in enumerate(steps):
            if not s.precondition.strip() or not s.predicted_invariant.strip():
                return GovernorDecision(
                    False, "rejected",
                    f"macro step {i} missing precondition or predicted invariant")
            err = self._illegal_reason(s.request(), legal, board_hw)
            if err:
                return GovernorDecision(False, "rejected", f"macro step {i}: {err}")
        self._macro = list(steps)
        self._macro_i = 0
        self._armed = True
        return GovernorDecision(True, "macro_step", "macro armed",
                                steps[0].request().to_dict())

    def current_macro_step(self) -> MacroStep | None:
        if self._armed and self._macro_i < len(self._macro):
            return self._macro[self._macro_i]
        return None

    def observe_after(
        self,
        *,
        board_changed: bool,
        level_completed: bool = False,
        game_over: bool = False,
        signature_match: bool = True,
    ) -> str:
        """Feed the transition an executed macro step produced; enforce
        stop-on-surprise. Returns "idle" | "continue" | "macro_done" |
        "macro_aborted:<reason>"."""
        if not self._armed:
            return "idle"
        step = self._macro[self._macro_i]

        surprise = ""
        if game_over:
            surprise = "game_over"
        elif level_completed:
            surprise = "level_completed"
        elif not signature_match:
            surprise = "signature_mismatch"
        else:
            want = _expects_change(step.predicted_invariant)
            if want is True and not board_changed:
                surprise = "unexpected_no_change"
            elif want is False and board_changed:
                surprise = "unexpected_change"
        if surprise:
            self._abort_macro()
            return f"macro_aborted:{surprise}"

        self._macro_i += 1
        if self._macro_i >= len(self._macro):
            self._abort_macro()
            return "macro_done"
        return "continue"

    def _abort_macro(self) -> None:
        self._macro = []
        self._macro_i = 0
        self._armed = False

    # ----- accounting ---------------------------------------------------------
    def record_executed(self, action: dict[str, Any], state_hash: str) -> None:
        """Charge an executed action: bump counters + remember the state-action.

        UNDO counts as one environment action (a probe+undo is two).
        """
        self.total_actions += 1
        if action.get("action") == "UNDO":
            self.undo_count += 1
        sig = _dict_signature(action)
        self._seen.add((state_hash, sig))


def _dict_signature(action: dict[str, Any]) -> str:
    if action.get("action") == "MOUSE":
        return f"MOUSE:{action.get('row')}:{action.get('col')}"
    return str(action.get("action"))
