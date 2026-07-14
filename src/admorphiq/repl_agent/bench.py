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

# The matched 12-game audit OFF/ON experiment (Codex v8 ruling): 5 carryovers +
# 2 positive controls, spanning click/paint, transform, hidden-mechanic movement,
# mixed movement, and maze navigation.
MATCHED_12_GAMES = [
    "su15", "ls20", "bp35", "dc22", "g50t", "r11l",
    "sp80", "ft09", "ar25", "sb26", "tr87", "tu93",
]


def matched_run_plan(games: list[str], replicate_game: str = "su15",
                     replicates: int = 3) -> list[dict[str, Any]]:
    """Interleaved OFF/ON run plan for the matched experiment.

    Each game gets an adjacent OFF then ON run (controls for time drift within a
    pair); ``replicate_game`` gets ``replicates`` OFF/ON pairs. Returns ordered
    ``{game, arm, rep}`` entries (arm in {"off","on"}).
    """
    plan: list[dict[str, Any]] = []
    for game in games:
        reps = replicates if game == replicate_game else 1
        for rep in range(reps):
            plan.append({"game": game, "arm": "off", "rep": rep})
            plan.append({"game": game, "arm": "on", "rep": rep})
    return plan


@dataclass
class GameDiagnostics:
    """Per-game observability record (serialized to diagnostics/{game}.json)."""

    game_id: str
    levels: int = 0
    actions: int = 0
    wall_s: float = 0.0
    llm_calls: int = 0
    llm_errors: int = 0
    parse_failures: int = 0
    truncations: int = 0
    inspections: int = 0
    audits_triggered: int = 0
    predictions_made: int = 0
    predictions_correct: int = 0
    governor_rejections: int = 0
    sandbox_errors: int = 0
    sandbox_infra_errors: int = 0
    sandbox_code_errors: int = 0
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


def _obs_hash(obs: Any) -> str:
    """Stable hash of the observation's frame (or "" when unavailable)."""
    import hashlib

    fr = getattr(obs, "frame", None)
    if fr is None:
        return ""
    try:
        import numpy as np
        arr = np.asarray(fr)
        return hashlib.md5(np.ascontiguousarray(arr).tobytes()).hexdigest()[:12]
    except Exception:  # noqa: BLE001 — hashing is best-effort telemetry
        return ""


def _action_repr(action: Any) -> Any:
    """A JSON-able tag for an action object (dict passthrough or type name)."""
    if isinstance(action, dict):
        return action
    return getattr(getattr(action, "action_type", None), "name", str(action))


def run_game(
    env: Any,
    agent: Any,
    *,
    max_actions: int = 150,
    wall_s: float = 600.0,
    reset_action: Any = None,
    clock: Any = time.monotonic,
    events: Any = None,
) -> GameDiagnostics:
    """Play one game to a level clear, budget, or soft deadline.

    ``env`` exposes ``observation_space`` (the current obs) and ``step(action)``;
    ``agent`` is the harness contract (``is_done`` / ``choose_action``, optional
    ``restart_on_game_over`` + counters). ``reset_action`` is the env's RESET
    command used to revive after GAME_OVER when the agent restarts. ``clock`` is
    injectable so tests can drive the wall-clock deadline deterministically.
    ``events`` is an optional :class:`EventStream`; when given, each executed
    action + its transition are emitted (linked by ``action_id``) so a killed
    kernel still leaves a truthful per-event record.
    """
    diag = GameDiagnostics(game_id=str(getattr(env, "game_id", "") or ""))

    def emit(etype: str, **f: Any) -> None:
        if events is not None:
            events.emit(etype, **f)

    start = clock()
    obs = getattr(env, "observation_space", None)
    prev_levels = _levels(obs)
    restart = bool(getattr(agent, "restart_on_game_over", False))
    action_id = 0
    emit("game_start", game_id=diag.game_id, level=prev_levels)

    try:
        while diag.actions < max_actions:
            if clock() - start > wall_s:
                diag.terminal_reason = "wall"
                break
            if agent.is_done([], obs):
                diag.terminal_reason = "done"
                break
            pre_hash = _obs_hash(obs)
            action = agent.choose_action([], obs)
            emit("action_executed", action_id=action_id,
                 action=_action_repr(action), pre_hash=pre_hash)
            obs = _step(env, action)
            if obs is None:
                diag.terminal_reason = "env_none"
                break
            diag.actions += 1
            cur = _levels(obs)
            post_hash = _obs_hash(obs)
            emit("transition", action_id=action_id, post_hash=post_hash,
                 changed=(pre_hash != post_hash), level=cur, state=_state(obs))
            action_id += 1
            if cur > prev_levels:
                emit("level_up", level=cur)
                prev_levels = cur
            if _state(obs) == "WIN":
                diag.terminal_reason = "win"
                break
            if _state(obs) == "GAME_OVER":
                if not restart or reset_action is None:
                    diag.terminal_reason = "game_over"
                    break
                emit("reset", reason="game_over")
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
        emit("exception", error=diag.error)

    diag.wall_s = round(clock() - start, 3)
    diag.levels = _levels(obs) if obs is not None else prev_levels
    diag.llm_calls = int(getattr(agent, "llm_calls", 0))
    diag.llm_errors = int(getattr(agent, "llm_errors", 0))
    diag.parse_failures = int(getattr(agent, "parse_failures", 0))
    diag.truncations = int(getattr(agent, "truncations", 0))
    diag.inspections = int(getattr(agent, "inspections", 0))
    diag.audits_triggered = int(getattr(agent, "audits_triggered", 0))
    diag.predictions_made = int(getattr(agent, "predictions_made", 0))
    diag.predictions_correct = int(getattr(agent, "predictions_correct", 0))
    diag.governor_rejections = int(getattr(agent, "governor_rejections", 0))
    diag.sandbox_errors = int(getattr(agent, "sandbox_errors", 0))
    diag.sandbox_infra_errors = int(getattr(agent, "sandbox_infra_errors", 0))
    diag.sandbox_code_errors = int(getattr(agent, "sandbox_code_errors", 0))
    emit("terminal", reason=diag.terminal_reason, levels=diag.levels,
         actions=diag.actions, wall_s=diag.wall_s)
    return diag
