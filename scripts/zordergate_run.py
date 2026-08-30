"""Score ONE game with a PAINT-ORDER mutation installed on the engine's camera.

Companion to `scripts/zordergate.sh`; see `src/admorphiq/zorder_mutation.py` for what
the mutation is and the argument that it is render-only.

⛔ IT REUSES ``score_efficiency.run_game`` RATHER THAN RE-IMPLEMENTING THE LOOP. Rule
7aj: a hand-rolled loop clears four bp35 boards where the scorer clears five, so any
number from a private loop is describing a different run. The stepping, the restart
policy, the BREAK-on-WIN and the scoring maths are the gate's own.

⛔ AND THE PATCH IS INSTALLED AROUND ``run_game``, NOT AROUND THE PROCESS. It is a
monkeypatch of ``arcengine.camera.Camera.render``; leaving it installed would leak into
any later game in the same process and the accounting would then mix two boards. One
game per process is the driver's shape, and the patch is still scoped and removed.

The output JSON is the same shape ``score_efficiency.py --out`` writes, so
`scripts/rounds/compare.py` reads it unchanged, plus a ``zorder_mutation`` block
carrying the verdict — ``applied`` / ``inert`` / ``partial`` / ``invalid`` / ``control``.

    uv run python scripts/zordergate_run.py --titles s5i5 --mutation zrev \
        --max-actions 4000 --out /tmp/s5i5.json
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
from score_efficiency import run_game, total_score  # noqa: E402

from admorphiq.zorder_mutation import ZOrderPatch, build  # noqa: E402


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
        patch = ZOrderPatch(build(args.mutation)).install()
        try:
            result = run_game(arcade, env_info.game_id, env_info.baseline_actions,
                              agent_name=args.agent, max_actions=args.max_actions)
        finally:
            report = patch.close()
        result["title"] = env_info.title or env_info.game_id
        result["zorder_mutation"] = report
        results.append(result)
        if result.get("has_baseline"):
            scored.append(result["game_score"])
        print(f"{env_info.game_id} score={result.get('game_score')} "
              f"levels={result.get('levels_completed')} "
              f"mutation={report['verdict']} frames={report['frames_seen']} "
              f"changed={report['frames_changed']} cells={report['cells_changed']} "
              f"layers={report['layers_seen']} "
              f"internal={report['internal_render_calls']} "
              f"violations={report['violations'][:2]}", flush=True)

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
