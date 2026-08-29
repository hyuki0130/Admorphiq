"""Score ONE game with a render mutation applied to the agent's observation.

Companion to `scripts/rendergate.sh`; see `src/admorphiq/render_mutation.py` for what
the mutation is and why it is meaning-preserving.

⛔ IT REUSES ``score_efficiency.run_game`` RATHER THAN RE-IMPLEMENTING THE LOOP. Rule
7aj: a hand-rolled loop clears four bp35 boards where the scorer clears five, so any
number from a private loop is describing a different run. ``run_game`` already exposes
``adapter_factory`` for exactly this, so the stepping, the restart policy, the
BREAK-on-WIN and the scoring maths are the gate's own.

The output JSON is the same shape ``score_efficiency.py --out`` writes, so
`scripts/rounds/compare.py` reads it unchanged, plus a ``render_mutation`` block
carrying the verdict — ``applied`` / ``inert`` / ``invalid`` / ``control``.

    uv run python scripts/rendergate_run.py --titles bp35 --mutation cperm \
        --max-actions 4000 --out /tmp/bp35.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from arc_agi import Arcade, OperationMode  # noqa: E402
from score_efficiency import _make_agent, run_game, total_score  # noqa: E402

from admorphiq.render_mutation import MutantAgent, build  # noqa: E402


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--titles", required=True)
    p.add_argument("--mutation", required=True)
    p.add_argument("--agent", default="unified")
    p.add_argument("--max-actions", type=int, default=4000)
    p.add_argument("--out", required=True)
    args = p.parse_args()

    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    wanted = [t.strip().lower() for t in args.titles.split(",") if t.strip()]
    seen: set[str] = set()
    envs = []
    for e in arcade.get_environments():
        hay = f"{e.game_id} {e.title or ''}".lower()
        if any(w in hay for w in wanted) and e.game_id not in seen:
            seen.add(e.game_id)
            envs.append(e)
    if not envs:
        print(f"⛔ no environment matched {args.titles!r} — REFUSING", flush=True)
        return 1

    results: list[dict[str, Any]] = []
    scored: list[float] = []
    for env_info in envs:
        holder: dict[str, MutantAgent] = {}

        def factory() -> MutantAgent:
            wrapped = MutantAgent(_make_agent(args.agent, game_id=env_info.game_id),
                                  build(args.mutation))
            holder["agent"] = wrapped
            return wrapped

        result = run_game(arcade, env_info.game_id, env_info.baseline_actions,
                          agent_name=args.agent, max_actions=args.max_actions,
                          adapter_factory=factory)
        result["title"] = env_info.title or env_info.game_id
        result["render_mutation"] = holder["agent"].close()
        results.append(result)
        if result.get("has_baseline"):
            scored.append(result["game_score"])
        rm = result["render_mutation"]
        print(f"{env_info.game_id} score={result.get('game_score')} "
              f"levels={result.get('levels_completed')} "
              f"mutation={rm['verdict']} frames={rm['frames_seen']} "
              f"changed={rm['frames_changed']} cells={rm['cells_changed']} "
              f"clicks_mapped={rm['clicks_mapped']} "
              f"violations={rm['violations'][:2]}", flush=True)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({
        "agent": args.agent,
        "mutation": args.mutation,
        "n_games_run": len(envs),
        "n_games_scored": len(scored),
        "total_score": round(total_score(scored), 6),
        "games": results,
    }, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
