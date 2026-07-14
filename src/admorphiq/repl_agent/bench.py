"""Bench driver for the code-REPL agent (R55 Round-1 second half).

`run_game` plays one game with a harness-contract agent under BOTH an action cap
and a wall-clock soft deadline, isolates per-game crashes (one game never kills
the run), and collects the observability diagnostics the Kaggle repl-bench kernel
writes: levels, actions, wall time, and — read off the agent — LLM calls, parse
failures, governor rejections, sandbox errors, plus the terminal reason.

Kept separate from the Kaggle kernel script so the loop logic (caps, terminal
reasons, diagnostics assembly) is unit-testable off-Kaggle with a fake env/agent.
"""

from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class GameDiagnostics:
    """Per-game observability record (serialized to diagnostics/{game}.json)."""

    game_id: str
    levels: int = 0
    actions: int = 0
    wall_s: float = 0.0
    llm_calls: int = 0
    parse_failures: int = 0
    governor_rejections: int = 0
    sandbox_errors: int = 0
    terminal_reason: str = ""     # win | budget | wall | game_over | env_none | error | done
    error: str = ""
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _state(obs: Any) -> str:
    st = getattr(obs, "state", None)
    return getattr(st, "name", str(st) if st is not None else "")


def _levels(obs: Any) -> int:
    v = getattr(obs, "levels_completed", None)
    if v is None:
        score = getattr(obs, "score", None)
        if isinstance(score, dict):
            v = score.get("levels_completed")
    try:
        return int(v)
    except (TypeError, ValueError):
        return 0


def _step(env: Any, action: Any) -> Any:
    """Step the env, passing coordinate data for complex (ACTION6) actions."""
    if hasattr(action, "is_complex") and action.is_complex():
        data = action.action_data.model_dump() if hasattr(action, "action_data") else None
        return env.step(action, data=data)
    return env.step(action)


def run_game(
    env: Any,
    agent: Any,
    *,
    max_actions: int = 150,
    wall_s: float = 600.0,
    reset_action: Any = None,
    clock: Any = time.monotonic,
) -> GameDiagnostics:
    """Play one game to a level clear, budget, or soft deadline.

    ``env`` exposes ``observation_space`` (the current obs) and ``step(action)``;
    ``agent`` is the harness contract (``is_done`` / ``choose_action``, optional
    ``restart_on_game_over`` + counters). ``reset_action`` is the env's RESET
    command used to revive after GAME_OVER when the agent restarts. ``clock`` is
    injectable so tests can drive the wall-clock deadline deterministically.
    """
    diag = GameDiagnostics(game_id=str(getattr(env, "game_id", "") or ""))
    start = clock()
    obs = getattr(env, "observation_space", None)
    prev_levels = _levels(obs)
    restart = bool(getattr(agent, "restart_on_game_over", False))

    try:
        while diag.actions < max_actions:
            if clock() - start > wall_s:
                diag.terminal_reason = "wall"
                break
            if agent.is_done([], obs):
                diag.terminal_reason = "done"
                break
            action = agent.choose_action([], obs)
            obs = _step(env, action)
            if obs is None:
                diag.terminal_reason = "env_none"
                break
            diag.actions += 1
            cur = _levels(obs)
            if cur > prev_levels:
                prev_levels = cur
            if _state(obs) == "WIN":
                diag.terminal_reason = "win"
                break
            if _state(obs) == "GAME_OVER":
                if not restart or reset_action is None:
                    diag.terminal_reason = "game_over"
                    break
                obs = _step(env, reset_action)
                diag.actions += 1
                if obs is None:
                    diag.terminal_reason = "env_none"
                    break
        else:
            diag.terminal_reason = "budget"
    except Exception as exc:  # noqa: BLE001 — one game must never kill the run
        diag.terminal_reason = "error"
        diag.error = f"{type(exc).__name__}: {exc}"

    diag.wall_s = round(clock() - start, 3)
    diag.levels = _levels(obs) if obs is not None else prev_levels
    diag.llm_calls = int(getattr(agent, "llm_calls", 0))
    diag.parse_failures = int(getattr(agent, "parse_failures", 0))
    diag.governor_rejections = int(getattr(agent, "governor_rejections", 0))
    diag.sandbox_errors = int(getattr(agent, "sandbox_errors", 0))
    return diag
