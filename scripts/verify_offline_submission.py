"""Verify the OFFLINE Kaggle submission path end-to-end, locally.

This is the submission-day de-risking check. It proves that the exact
mechanism the Kaggle notebook uses can, with **no internet**, run our
``KaggleBCAgent`` against the bundled ``environment_files/`` games and
produce a valid ``submission.json`` scorecard.

Why this exists: the previous notebook drove the games through
``agents.swarm.Swarm`` + ``Arcade.listen_and_serve``. That path is NOT
offline-safe: ``Swarm.__init__`` builds its own ``Arcade()`` in NORMAL
mode (which fetches an anonymous API key over HTTP) and runs the games
through that internal Arcade, never through the locally-served OFFLINE
one — so the ``on_scorecard_close`` callback that was supposed to write
``submission.json`` never fires. The robust offline mechanism is a
direct ``Arcade(OFFLINE).make()`` + ``agent.main()`` loop, then
``Arcade.close_scorecard()`` to materialise the scorecard. This script
exercises exactly that, and ``notebooks/kaggle_submission.py`` uses the
same ``run_offline_submission`` helper.

Run: uv run python scripts/verify_offline_submission.py
     uv run python scripts/verify_offline_submission.py --games ar25 dc22 --max-actions 12
"""

from __future__ import annotations

import argparse
import json
import os
import sys

# Keep local verification on CPU so it never contends with a concurrent
# GPU/MPS training job. On Kaggle the agent uses CUDA (the real path);
# here we only need to prove the wiring, so tiny CPU inference is enough.
os.environ.setdefault("CUDA_VISIBLE_DEVICES", "")
try:  # disable MPS pick in admorphiq.bc_agent._pick_device
    import torch

    torch.backends.mps.is_available = lambda: False  # type: ignore[assignment]
except Exception:  # noqa: BLE001 - torch always present, but stay defensive
    pass

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_ENVS_DIR = os.path.join(REPO_ROOT, "environment_files")


def _base_game_ids(env_infos: list, limit: int | None) -> list[str]:
    """Dedupe served envs to one version per base game, in scan order."""
    seen: set[str] = set()
    chosen: list[str] = []
    for e in env_infos:
        base = e.game_id.split("-")[0]
        if base in seen:
            continue
        seen.add(base)
        chosen.append(e.game_id)
        if limit is not None and len(chosen) >= limit:
            break
    return chosen


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--envs-dir",
        default=DEFAULT_ENVS_DIR,
        help="Directory of environment_files (default: repo environment_files/).",
    )
    ap.add_argument(
        "--games",
        nargs="*",
        default=None,
        help="Specific game ids/bases to play (default: first --num-games games).",
    )
    ap.add_argument("--num-games", type=int, default=2)
    ap.add_argument(
        "--max-actions",
        type=int,
        default=12,
        help="Per-game action cap (kept tiny for a fast wiring check).",
    )
    ap.add_argument(
        "--out",
        default=os.path.join(REPO_ROOT, "scripts", "offline_submission_sample.json"),
        help="Where to write the produced scorecard JSON.",
    )
    args = ap.parse_args()

    # Import after the CPU pin above so device selection picks CPU.
    from arc_agi import Arcade, OperationMode

    from admorphiq.kaggle_bc_agent import KaggleBCAgent

    # Force OFFLINE deterministically: the Arcade constructor lets an
    # OPERATION_MODE=competition env var override the constructor arg, and
    # competition mode needs the network. With internet disabled, offline
    # is the only correct mode, so we pin it here too.
    os.environ["OPERATION_MODE"] = "offline"

    arc = Arcade(
        operation_mode=OperationMode.OFFLINE,
        environments_dir=args.envs_dir,
    )
    env_infos = arc.get_environments()
    print(f"OFFLINE Arcade discovered {len(env_infos)} environment(s).")
    if not env_infos:
        print(f"ERROR: no environments under {args.envs_dir}", file=sys.stderr)
        return 1

    if args.games:
        # Accept either base ids ('ar25') or full ids ('ar25-0c556536').
        wanted = set(args.games)
        game_ids = [
            e.game_id
            for e in env_infos
            if e.game_id in wanted or e.game_id.split("-")[0] in wanted
        ]
        game_ids = _base_game_ids(
            [e for e in env_infos if e.game_id in game_ids], None
        )
    else:
        game_ids = _base_game_ids(env_infos, args.num_games)

    print(f"Playing {len(game_ids)} game(s): {game_ids}\n")

    card_id = arc.open_scorecard(tags=["admorphiq", "bc", "verify"])
    print(f"Opened scorecard: {card_id}")

    for gid in game_ids:
        env = arc.make(gid, scorecard_id=card_id)
        if env is None:
            print(f"  {gid}: make() returned None — skipping")
            continue
        agent = KaggleBCAgent(
            card_id=card_id,
            game_id=gid,
            agent_name="admorphiq",
            ROOT_URL="",
            record=False,
            arc_env=env,
            tags=["admorphiq", "bc", "verify"],
        )
        agent.MAX_ACTIONS = args.max_actions
        agent.main()
        last = agent.frames[-1]
        print(
            f"  {gid}: actions={agent.action_counter} "
            f"state={getattr(last.state, 'name', last.state)} "
            f"levels_completed={last.levels_completed}"
        )

    scorecard = arc.close_scorecard(card_id)
    if scorecard is None:
        print("ERROR: close_scorecard returned None", file=sys.stderr)
        return 1

    payload = scorecard.model_dump_json()
    with open(args.out, "w") as f:
        f.write(payload)

    data = json.loads(payload)
    print("\n=== SCORECARD (produced offline) ===")
    print(f"  card_id: {data.get('card_id')}")
    print(f"  score: {data.get('score')}")
    print(f"  total_environments: {data.get('total_environments')}")
    print(f"  total_levels_completed: {data.get('total_levels_completed')}")
    print(f"  total_actions: {data.get('total_actions')}")
    print(f"  environments tracked: {len(data.get('environments', []))}")
    print(f"\nWrote scorecard JSON to {args.out}")

    # The competition wants a non-empty, parseable scorecard with the
    # games we played registered. That is the contract we assert here.
    assert "card_id" in data, "scorecard missing card_id"
    assert data.get("environments"), "scorecard has no environments"
    print("\nOK: valid offline scorecard produced.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
