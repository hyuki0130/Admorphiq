"""script25 — kernel-expressiveness scoreboard (R56).

Runs each QUARANTINED per-game adapter under ``src/admorphiq/adapters25/``
through the SAME env-stepping loop ``scripts/score_efficiency.py`` uses
(imports ``run_game``/``total_score`` directly via ``adapter_factory``
rather than re-implementing the loop) and reports per-game + total RHAE.

This measures whether the namespace-safe kernel library
(``src/admorphiq/kernels/``) is EXPRESSIVE ENOUGH for a thin, hand-written
script to compose a solution -- it is NEVER a measurement of LLM/agent
capability. See ``docs/r56_codex_toolbase_verdict_20260715.md``,
"Sequencing and experiments": script25 = kernel expressiveness,
agent25 = LLM competence, and public improvement on script25 alone does
NOT promote anything -- only agent25 non-inferiority + hidden transfer do.

Usage:
  uv run python scripts/script25.py --games m0r0 --max-actions 300 \\
      --out scripts/rounds/script25_smoke
  uv run python scripts/script25.py --games all --out scripts/rounds/script25
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

# Allow running from repo root without installing the package (mirrors
# scripts/score_efficiency.py's own path setup).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from arc_agi import Arcade, OperationMode  # noqa: E402
from score_efficiency import run_game, total_score  # noqa: E402  (sibling, same dir)

from admorphiq.adapters25 import discover_adapters  # noqa: E402


def _select_adapters(games_arg: str, discovered: dict[str, type]) -> dict[str, type]:
    """Filter the discovered {GAME_ID: Adapter} map by --games.

    "all" keeps every discovered adapter. Otherwise ``games_arg`` is a
    comma list matched by EXACT GAME_ID (case-insensitive) -- adapters are
    a small, explicit set, so exact match (not score_efficiency's broader
    substring match against the whole env catalog) keeps a typo from
    silently selecting nothing or the wrong adapter.
    """
    if games_arg.strip().lower() == "all":
        return dict(discovered)
    wanted = {g.strip().lower() for g in games_arg.split(",") if g.strip()}
    selected = {gid: cls for gid, cls in discovered.items() if gid in wanted}
    missing = wanted - set(selected)
    for m in sorted(missing):
        print(f"  (no script25 adapter registered for '{m}' -- skipped)", flush=True)
    return selected


def _matching_envs(envs: list[Any], game_id_substr: str) -> list[Any]:
    """Every live environment whose id/title contains ``game_id_substr``.

    Mirrors scripts/score_efficiency.py's own --titles substring-matching
    convention against the full env catalog (a GAME_ID like "m0r0" can
    match more than one live hash-version env, e.g. "m0r0-dadda488" and
    "m0r0-492f87ba").
    """
    out = []
    seen: set[str] = set()
    for e in envs:
        hay = f"{e.game_id} {e.title or ''}".lower()
        if game_id_substr in hay and e.game_id not in seen:
            seen.add(e.game_id)
            out.append(e)
    return out


def _write_summary(out_dir: Path, results: list[dict[str, Any]]) -> None:
    """Regenerate SUMMARY.txt from every per-game result gathered SO FAR.

    Called after every game completes so SUMMARY.txt is always live —
    readable mid-run, and a valid partial record on crash (repo measurement
    discipline: one LIVE SUMMARY.txt per round, never discard partials).
    """
    scored = [r["game_score"] for r in results if r.get("has_baseline") and "error" not in r]
    tscore = total_score(scored)

    lines = [
        "script25 SUMMARY (LIVE — regenerated after every game)",
        "kernel-expressiveness scoreboard — NEVER reported as agent capability "
        "(see docs/r56_codex_toolbase_verdict_20260715.md)",
        f"games run: {len(results)}   scored: {len(scored)}   "
        f"total_score: {tscore:.4f} ({tscore * 100:.2f}%)",
        "",
        f"{'game_id':<22}{'adapter':<10}{'levels':<10}{'actions':<10}{'game_score':<12}status",
    ]
    for r in results:
        if "error" in r:
            lines.append(f"{r['game_id']:<22}{r.get('adapter', '?'):<10}{'-':<10}{'-':<10}{'-':<12}ERROR: {r['error']}")
            continue
        levels = f"{r['levels_completed']}/{r['win_levels']}"
        gs = r.get("game_score")
        gs_str = f"{gs:.4f}" if gs is not None else "n/a"
        status = "ok" if r.get("has_baseline") else "no_baseline"
        lines.append(
            f"{r['game_id']:<22}{r.get('adapter', '?'):<10}{levels:<10}"
            f"{r['total_actions']:<10}{gs_str:<12}{status}"
        )

    (out_dir / "SUMMARY.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument(
        "--games",
        default="all",
        help="Comma-separated adapter GAME_IDs to run, or 'all' (default: all discovered adapters).",
    )
    p.add_argument("--max-actions", type=int, default=5000, help="Per-game action budget (default: 5000).")
    p.add_argument(
        "--out",
        default="scripts/rounds/script25",
        help="Output directory (default: scripts/rounds/script25). "
        "Writes <out>/games/<game_id>.json per game + <out>/SUMMARY.txt.",
    )
    return p


def main() -> None:
    args = _build_parser().parse_args()

    out_dir = Path(args.out)
    games_dir = out_dir / "games"
    games_dir.mkdir(parents=True, exist_ok=True)

    discovered = discover_adapters()
    selected = _select_adapters(args.games, discovered)
    if not selected:
        print("No adapters selected -- nothing to run.", flush=True)
        return

    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    envs = arcade.get_environments()

    jobs: list[tuple[str, type, Any]] = []  # (game_id_substr, AdapterClass, env_info)
    for game_id_substr, adapter_cls in sorted(selected.items()):
        matches = _matching_envs(envs, game_id_substr)
        if not matches:
            print(f"  (no live environment matches adapter '{game_id_substr}' -- skipped)", flush=True)
            continue
        for env_info in matches:
            jobs.append((game_id_substr, adapter_cls, env_info))

    print(f"Running {len(jobs)} script25 job(s) ({len(selected)} adapter(s)) …", flush=True)

    results: list[dict[str, Any]] = []
    for i, (game_id_substr, adapter_cls, env_info) in enumerate(jobs):
        env_game_id = env_info.game_id
        title = env_info.title or env_game_id
        baseline = env_info.baseline_actions
        print(f"  [{i + 1}/{len(jobs)}] {env_game_id} ({title}) via adapter '{game_id_substr}' …", flush=True)

        start = time.time()
        try:
            result = run_game(
                arcade,
                env_game_id,
                baseline,
                agent_name=f"script25:{game_id_substr}",
                max_actions=args.max_actions,
                adapter_factory=adapter_cls,
            )
        except Exception as exc:  # noqa: BLE001 — record and keep going
            result = {"game_id": env_game_id, "error": str(exc)}
        elapsed = time.time() - start

        result["title"] = title
        result["adapter"] = game_id_substr
        result.setdefault("elapsed_s", round(elapsed, 2))
        results.append(result)

        (games_dir / f"{env_game_id}.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
        _write_summary(out_dir, results)  # LIVE regeneration after every game

        if "error" in result:
            print(f"    ERROR: {result['error']}", flush=True)
        else:
            gs = result.get("game_score")
            print(
                f"    levels={result['levels_completed']}/{result['win_levels']}  "
                f"actions={result['total_actions']}  "
                f"game_score={gs if gs is None else round(gs, 4)}",
                flush=True,
            )

    scored = [r["game_score"] for r in results if r.get("has_baseline") and "error" not in r]
    tscore = total_score(scored)
    print(
        f"\nscript25 total_score: {tscore:.4f} ({tscore * 100:.2f}%) "
        f"[{len(scored)}/{len(results)} games scored]",
        flush=True,
    )
    print(f"Output written to: {out_dir}", flush=True)


if __name__ == "__main__":
    main()
