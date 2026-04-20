"""Wiki-driven hypothesis agent (Phase 8 Step 3, Task #9).

The agent's contract mirrors the Karpathy LLM-Wiki pattern:

  observe(live_env)  ──┐
                       ├─> prompt ─> LLMBackend.generate ─> JSON ─> dispatch
  load_wiki_context ──┘

It is intentionally thin — no state dump, no bundled weights, no agent-side
learning. All knowledge lives in `.wiki/` and is composed on demand from a
small, deterministic retrieval recipe (see `wiki_retrieval_recipe.md`).

The agent is **LLM-agnostic**: it calls `LLMBackend.generate(prompt)` and
does not care which model answers. Choose the candidate via `configs/llm.yaml`.

Deployment assumption: Kaggle T4, internet disabled. All wiki pages and
weights must be pre-staged. This module does no network I/O.
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from ..llm import LLMBackend

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
WIKI_DIR = REPO_ROOT / ".wiki" / "wiki"


@dataclass
class DiscoveryReport:
    """What we observed in the first ~N frames of a game. Used to prime the LLM."""

    game_title: str
    available_actions: list[int]
    layer_count: int
    dominant_colors: list[tuple[int, int]]  # [(color, count), ...]
    probe_diffs: dict[int, int]  # action_id -> pixel count changed vs reset
    reset_levels: int
    frame_shape: tuple[int, int]


@dataclass
class Hypothesis:
    """Parsed LLM response."""

    game_type: str
    primary_strategy: str
    fallback_stack: list[str] = field(default_factory=list)
    rationale: str = ""
    raw: str = ""


_PROMPT_TEMPLATE = """You are the Admorphiq Phase 8 Hypothesis Engine.

The wiki context below describes game types and strategies. Read it, then
observe the live-game discovery report and output ONE JSON object:

  {{"game_type":        "one of: movement | click | programming_puzzle | merge_puzzle |
                         sokoban | platformer | transform | delivery | slider_puzzle |
                         rotation | sort_puzzle | spell_cast | sequence | hybrid | unknown",
    "primary_strategy": "frame_only strategy name (see selector.md)",
    "fallback_stack":   ["strategy_name", ...] (up to 3),
    "rationale":        "1-2 sentences"}}

No prose outside the JSON.

=== Wiki Context ===
{context}

=== Live Discovery ===
Game title: {title}
Available actions: {avail}
Layer count: {layers}
Dominant colors (color:count): {colors}
Probe diffs (action: pixels changed vs reset): {probes}
Starting level: {lvl}
"""


_DEFAULT_PAGES = [
    "reasoning/discovery_phase.md",
    "reasoning/frame_to_strategy_chain.md",
    "reasoning/hypothesis_check.md",
    "selector.md",
    "lessons/v2_hash_obfuscation.md",
    "lessons/brittle_tells.md",
    "strategies/frame_only/bfs_state_space.md",
]


def _read_wiki(pages: list[str], budget_chars: int = 8000) -> str:
    """Concatenate requested wiki pages, trimming to `budget_chars` total."""
    parts: list[str] = []
    total = 0
    for p in pages:
        path = WIKI_DIR / p
        if not path.exists():
            continue
        body = path.read_text()
        header = f"--- {p} ---\n"
        chunk = header + body
        if total + len(chunk) > budget_chars:
            chunk = chunk[: max(0, budget_chars - total)]
        parts.append(chunk)
        total += len(chunk)
        if total >= budget_chars:
            break
    return "\n\n".join(parts)


def _parse_json_lenient(raw: str) -> dict[str, Any]:
    """Extract the first JSON object from an LLM response. Tolerates fences + prose."""
    if not raw:
        return {}
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, re.DOTALL)
    if m:
        raw = m.group(1)
    else:
        m = re.search(r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}", raw, re.DOTALL)
        if m:
            raw = m.group(0)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {}


def discover(env: Any, probe_actions: list[int] | None = None) -> DiscoveryReport:
    """Reset the env, snapshot the opening frame, then probe each action once.

    The probe diffs are the single most useful signal for classifying a game —
    they tell the LLM which actions cause movement, which are no-ops, and which
    cause large scene changes (level transition, click-spawn, etc.).
    """
    import numpy as np

    # Lazy import to keep this module importable without arcengine.
    from arcengine import GameAction

    obs = env.step(GameAction.RESET)
    if obs is None:
        raise RuntimeError("env.reset returned None")
    frame0 = np.array(obs.frame[0], dtype=np.int32)
    layers = len(obs.frame)
    avail = [int(a) for a in (obs.available_actions or []) if int(a) != 0]
    unique, counts = np.unique(frame0, return_counts=True)
    colors = sorted(
        ((int(c), int(n)) for c, n in zip(unique, counts) if c != 0),
        key=lambda t: -t[1],
    )[:6]

    if probe_actions is None:
        probe_actions = [a for a in avail if a != 6][:4]

    probes: dict[int, int] = {}
    for aid in probe_actions:
        obs_r = env.step(GameAction.RESET)
        if obs_r is None:
            continue
        f_before = np.array(obs_r.frame[0], dtype=np.int32)
        if aid == 6:
            obs_a = env.step(GameAction.ACTION6, data={"x": 32, "y": 32})
        else:
            obs_a = env.step(GameAction.from_id(aid))
        if obs_a is None:
            continue
        f_after = np.array(obs_a.frame[0], dtype=np.int32)
        probes[aid] = int(np.count_nonzero(f_before - f_after))

    env.step(GameAction.RESET)

    title = getattr(env, "title", None) or getattr(env, "_game_id", "UNKNOWN")
    return DiscoveryReport(
        game_title=str(title),
        available_actions=avail,
        layer_count=layers,
        dominant_colors=colors,
        probe_diffs=probes,
        reset_levels=int(obs.levels_completed),
        frame_shape=tuple(frame0.shape),
    )


class WikiAgent:
    """Reads `.wiki/` + a live discovery report, asks an LLM what to run, then dispatches.

    Parameters
    ----------
    llm: LLMBackend — any backend from `admorphiq.llm` that satisfies the protocol.
    strategy_registry: dict[str, Callable] — maps strategy names (as they appear in
        `selector.md`) to callables that take `(env, budget)` and return `(levels, name, used)`.
    extra_context_pages: list[str] — wiki pages to append after the default set.
    context_chars: int — soft cap on prompt wiki length (default 8000, tuned for T4 budget).
    """

    def __init__(
        self,
        llm: LLMBackend,
        strategy_registry: dict[str, Callable[..., tuple[int, str, int]]],
        extra_context_pages: list[str] | None = None,
        context_chars: int = 8000,
    ) -> None:
        self.llm = llm
        self.strategies = strategy_registry
        self.extra_pages = extra_context_pages or []
        self.context_chars = context_chars

    def build_prompt(self, report: DiscoveryReport) -> str:
        pages = list(_DEFAULT_PAGES) + list(self.extra_pages)
        context = _read_wiki(pages, self.context_chars)
        return _PROMPT_TEMPLATE.format(
            context=context,
            title=report.game_title,
            avail=report.available_actions,
            layers=report.layer_count,
            colors=report.dominant_colors,
            probes=report.probe_diffs,
            lvl=report.reset_levels,
        )

    def classify(self, report: DiscoveryReport, max_tokens: int = 512) -> Hypothesis:
        prompt = self.build_prompt(report)
        raw = self.llm.generate(prompt, max_tokens=max_tokens)
        parsed = _parse_json_lenient(raw)
        return Hypothesis(
            game_type=str(parsed.get("game_type", "unknown")),
            primary_strategy=str(parsed.get("primary_strategy", "")),
            fallback_stack=[str(s) for s in parsed.get("fallback_stack", [])][:3],
            rationale=str(parsed.get("rationale", "")),
            raw=raw,
        )

    def run(self, env: Any, budget_per_strategy: int = 5000) -> dict[str, Any]:
        """Full loop: discover → classify → dispatch primary → fallbacks on failure.

        Returns a trace suitable for JSON logging. Does not raise — strategy
        failures are captured as `{"status": "error", ...}`.
        """
        t_start = time.time()
        try:
            report = discover(env)
        except Exception as exc:  # noqa: BLE001 - top-level guard for the inference loop
            return {"status": "error", "stage": "discover", "error": str(exc)}

        hyp = self.classify(report)
        trace: dict[str, Any] = {
            "game_title": report.game_title,
            "discovery": {
                "available_actions": report.available_actions,
                "layer_count": report.layer_count,
                "dominant_colors": report.dominant_colors,
                "probe_diffs": report.probe_diffs,
            },
            "hypothesis": {
                "game_type": hyp.game_type,
                "primary_strategy": hyp.primary_strategy,
                "fallback_stack": hyp.fallback_stack,
                "rationale": hyp.rationale,
            },
            "executions": [],
            "best_levels": report.reset_levels,
        }

        best = report.reset_levels
        for sname in [hyp.primary_strategy, *hyp.fallback_stack]:
            if not sname or sname not in self.strategies:
                trace["executions"].append({"strategy": sname, "status": "unknown_strategy"})
                continue
            strat = self.strategies[sname]
            t0 = time.time()
            try:
                lvls, winning, used = strat(env, budget_per_strategy)
            except Exception as exc:  # noqa: BLE001 - isolate strategy crashes
                trace["executions"].append(
                    {"strategy": sname, "status": "error", "error": str(exc)}
                )
                continue
            trace["executions"].append(
                {
                    "strategy": sname,
                    "winning_label": winning,
                    "levels": int(lvls),
                    "actions": int(used),
                    "elapsed_s": round(time.time() - t0, 2),
                    "status": "ok",
                }
            )
            if lvls > best:
                best = int(lvls)
            if best > report.reset_levels:
                break  # primary or first successful fallback wins — stop

        trace["best_levels"] = best
        trace["total_elapsed_s"] = round(time.time() - t_start, 2)
        trace["status"] = "ok"
        return trace
