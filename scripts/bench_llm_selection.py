"""Live-env LLM selection benchmark (Phase 8 / Task #11b).

Differs from ``bench_llm.py`` (cold-prompt / wiki-only) in one critical way:
for each game we actually instantiate the environment, run the GeneralAgent's
movement-probe discovery loop (up to DISCOVERY_BUDGET actions), then build the
compact symbolic state via ``build_symbolic_state`` and call ``hypothesize``.
The LLM therefore sees *real* frame observations, not wiki-guessed summaries.

Ground-truth labels are hand-coded below from game source inspection + wiki
frontmatter for 9 representative games spanning all major classes.

Outputs
-------
scripts/bench_llm_selection.json — per-model accuracy/latency, per-game detail
stdout                           — printed table

Run
---
    uv run python scripts/bench_llm_selection.py

Models benchmarked (must be already pulled in Ollama):
    qwen_3_8b_q4  (qwen3:8b)
    qwen_3_14b_q4 (qwen3:14b)
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np

# ── project imports ──────────────────────────────────────────────────────────
from admorphiq.general_agent import (
    canonical_layer,
    infer_direction_map,
)
from admorphiq.llm import load_candidate
from admorphiq.llm_reasoner import build_symbolic_state, hypothesize

# ── paths ────────────────────────────────────────────────────────────────────

REPO_ROOT = Path(__file__).resolve().parent.parent
OUT = REPO_ROOT / "scripts" / "bench_llm_selection.json"

# ── ground-truth labels ──────────────────────────────────────────────────────
# Source: game source files in environment_files/ + wiki frontmatter.
# game_class: concise human label for the mechanic type.
# goal: one short sentence describing the win condition.
# target_color_hint: expected LLM target_color if deterministic (None = varies).
#   We only use this for a fuzzy "is the LLM pointing at something plausible"
#   check; we do not require an exact int match.

GROUND_TRUTH: dict[str, dict] = {
    # AR25 — movement/navigation: player navigates a maze to an exit.
    "AR25": {
        "game_class": "movement",
        "goal": "Navigate the player sprite to the goal exit tile.",
        "target_color_hint": None,
    },
    # M0R0 — movement/navigation: player moves through a corridored grid.
    "M0R0": {
        "game_class": "movement",
        "goal": "Guide the player through the grid to reach the exit.",
        "target_color_hint": None,
    },
    # DC22 — movement/navigation: simple directional maze.
    "DC22": {
        "game_class": "movement",
        "goal": "Move the player to the goal position in the maze.",
        "target_color_hint": None,
    },
    # FT09 — toggle/lights-out: click cells to toggle neighbors until all match target.
    "FT09": {
        "game_class": "toggle",
        "goal": "Click cells to toggle their state and reach the target configuration.",
        "target_color_hint": None,
    },
    # CD82 — paint/click: select colors and paint a canvas to match a pattern.
    "CD82": {
        "game_class": "paint",
        "goal": "Select palette colors and paint the canvas to match the target pattern.",
        "target_color_hint": None,
    },
    # SU15 — merge puzzle: click-attract fruits of matching color so they merge.
    "SU15": {
        "game_class": "merge",
        "goal": "Attract same-colored fruits to merge and reach the target color in goal zones.",
        "target_color_hint": None,
    },
    # SB26 — sort puzzle: click-drag colored blocks into matching slots.
    "SB26": {
        "game_class": "sort",
        "goal": "Sort and place colored blocks into their designated target slots.",
        "target_color_hint": None,
    },
    # KA59 — push/sokoban: push boxes onto target cells.
    "KA59": {
        "game_class": "sokoban",
        "goal": "Push boxes onto the marked target cells.",
        "target_color_hint": None,
    },
    # SC25 — spell_cast/sequence: cast action sequences on objects to transform them.
    "SC25": {
        "game_class": "sequence",
        "goal": "Apply the correct sequence of actions to each object to transform it.",
        "target_color_hint": None,
    },
}

# Movement-only action ids (same as general_agent._MOVE_ACTION_IDS).
_MOVE_IDS = (1, 2, 3, 4, 5, 7)

# How many step actions to probe per game (small enough to be fast).
PROBE_BUDGET = 12


# ── discovery helper ─────────────────────────────────────────────────────────


def _run_discovery(env, game_id: str) -> dict:
    """Run up to PROBE_BUDGET movement probes against a fresh env.

    Returns a dict with:
        probes      list[{aid, before, after}]  raw probe records
        layer       np.ndarray                  canonical layer from final obs
        avail       list[int]                   available action ids
        dir_map     dict[int, (dx, dy)]          learned direction map
        player      int | None                   detected player colour
    """
    from arcengine import GameAction

    obs = env.observation_space
    avail = list(obs.available_actions)
    layer = canonical_layer(np.asarray(obs.frame))
    bg = int(np.unique(layer)[np.unique(layer, return_counts=True)[1].argmax()])
    move_targets = [a for a in _MOVE_IDS if a in avail]

    probes: list[dict] = []
    if not move_targets:
        # Click-only game — no movement probes possible; return the base frame.
        return {
            "probes": probes,
            "layer": layer,
            "avail": avail,
            "dir_map": {},
            "player": None,
        }

    probed: set[int] = set()
    step_count = 0

    for aid in move_targets:
        if step_count >= PROBE_BUDGET:
            break
        before = canonical_layer(np.asarray(env.observation_space.frame))
        try:
            obs = env.step(GameAction.from_id(aid))
        except Exception:
            break
        step_count += 1
        after = canonical_layer(np.asarray(obs.frame))
        probes.append({"aid": aid, "before": before, "after": after})
        probed.add(aid)

    layer = canonical_layer(np.asarray(obs.frame))
    dir_map, player_comp = infer_direction_map(probes, bg)
    player_color = player_comp["color"] if player_comp is not None else None
    return {
        "probes": probes,
        "layer": layer,
        "avail": avail,
        "dir_map": dir_map,
        "player": player_color,
    }


# ── scoring ──────────────────────────────────────────────────────────────────

# Keywords that map to each game_class label (match against LLM goal text).
_CLASS_KEYWORDS: dict[str, list[str]] = {
    "movement": ["navigate", "move", "player", "maze", "exit", "walk", "path"],
    "toggle": ["toggle", "light", "click", "state", "switch", "config"],
    "paint": ["paint", "color", "canvas", "palette", "pattern", "match"],
    "merge": ["merge", "fruit", "same", "attract", "vacuum", "combine"],
    "sort": ["sort", "slot", "place", "block", "target", "drag"],
    "sokoban": ["push", "box", "sokoban", "crate", "block", "goal cell"],
    "sequence": ["sequence", "spell", "cast", "order", "transform", "action"],
}


def _fuzzy_class_match(hyp: dict, truth: dict) -> bool:
    """Return True when the LLM goal text contains keywords consistent with truth.

    We score by keyword presence in goal + plan rather than requiring an exact
    game_class field (the hypothesize schema doesn't emit game_class — it emits
    goal/plan/target/action_meaning). A hit means the LLM reasoned about the
    right mechanic even without seeing the label taxonomy.
    """
    expected_class = truth["game_class"]
    keywords = _CLASS_KEYWORDS.get(expected_class, [])
    full_text = (hyp.get("goal", "") + " " + " ".join(hyp.get("plan", []))).lower()
    return any(kw in full_text for kw in keywords)


def _goal_nonempty(hyp: dict) -> bool:
    return bool(hyp.get("goal", "").strip())


def _plan_nonempty(hyp: dict) -> bool:
    return bool(hyp.get("plan"))


# ── per-candidate runner ─────────────────────────────────────────────────────


def run_candidate(candidate_id: str, arcade) -> dict:
    """Run the live-env bench for one LLM candidate.

    For each game: make a fresh env, probe movement actions, build symbolic
    state, call hypothesize, score. Returns a per-game detail dict and
    aggregate stats.
    """
    llm = load_candidate(candidate_id)
    per_game: list[dict] = []
    class_hits = 0
    latency_total = 0.0
    goal_nonempty = 0
    plan_nonempty = 0

    for game_id, truth in GROUND_TRUTH.items():
        print(f"    [{game_id}] probing ...", end="", flush=True)
        try:
            env = arcade.make(game_id.lower())
            disc = _run_discovery(env, game_id)

            state_text = build_symbolic_state(
                layer=disc["layer"],
                probes=disc["probes"],
                avail=disc["avail"],
                dir_map=disc["dir_map"] if disc["dir_map"] else None,
                player=disc["player"],
            )

            t0 = time.time()
            hyp = hypothesize(state_text, llm)
            latency_ms = (time.time() - t0) * 1000
            latency_total += latency_ms

            hit = _fuzzy_class_match(hyp, truth)
            class_hits += int(hit)
            gne = _goal_nonempty(hyp)
            pne = _plan_nonempty(hyp)
            goal_nonempty += int(gne)
            plan_nonempty += int(pne)

            per_game.append(
                {
                    "game": game_id,
                    "expected_class": truth["game_class"],
                    "expected_goal_hint": truth["goal"],
                    "predicted_goal": hyp.get("goal", ""),
                    "predicted_target_color": hyp.get("target_color"),
                    "predicted_plan": hyp.get("plan", [])[:2],
                    "class_hit": hit,
                    "goal_nonempty": gne,
                    "plan_nonempty": pne,
                    "latency_ms": round(latency_ms, 1),
                    "probes_collected": len(disc["probes"]),
                    "dir_map_learned": len(disc["dir_map"]),
                }
            )
            status = "HIT" if hit else "miss"
            print(f" {status} ({latency_ms:.0f}ms)", flush=True)

        except Exception as exc:
            per_game.append(
                {
                    "game": game_id,
                    "expected_class": truth["game_class"],
                    "error": str(exc),
                    "class_hit": False,
                    "goal_nonempty": False,
                    "plan_nonempty": False,
                    "latency_ms": 0.0,
                }
            )
            print(f" ERROR: {exc}", flush=True)

    n = len(GROUND_TRUTH)
    return {
        "candidate_id": candidate_id,
        "meta": {
            "display_name": llm.meta.display_name,
            "family": llm.meta.family,
            "expected_vram_gb": llm.meta.expected_vram_gb,
        },
        "total_games": n,
        "class_accuracy": round(class_hits / n, 3),
        "goal_coverage": round(goal_nonempty / n, 3),
        "plan_coverage": round(plan_nonempty / n, 3),
        "mean_latency_ms": round(latency_total / max(n, 1), 1),
        "per_game": per_game,
    }


# ── main ─────────────────────────────────────────────────────────────────────


def _composite_score(r: dict) -> float:
    """Higher is better. Balances accuracy vs latency."""
    if "error" in r and "class_accuracy" not in r:
        return -1.0
    acc = r.get("class_accuracy", 0.0)
    cov = r.get("goal_coverage", 0.0)
    lat_s = max(r.get("mean_latency_ms", 1.0) / 1000.0, 0.001)
    return (acc + cov) / 2.0 / (1.0 + lat_s / 10.0)


def _print_table(results: list[dict]) -> None:
    print("\n" + "=" * 72)
    print("  LLM SELECTION BENCH — RESULTS")
    print("=" * 72)
    hdr = f"{'Model':<24} {'ClassAcc':>8} {'GoalCov':>8} {'Lat(ms)':>9} {'Composite':>10}"
    print(hdr)
    print("-" * 72)
    for r in results:
        name = r.get("meta", {}).get("display_name", r["candidate_id"])[:24]
        ca = r.get("class_accuracy", 0.0)
        gc = r.get("goal_coverage", 0.0)
        lat = r.get("mean_latency_ms", 0.0)
        comp = _composite_score(r)
        print(f"{name:<24} {ca:>8.2%} {gc:>8.2%} {lat:>9.0f} {comp:>10.4f}")
    print("=" * 72)

    # Per-game breakdown for each model.
    for r in results:
        name = r.get("meta", {}).get("display_name", r["candidate_id"])
        print(f"\n  {name} — per-game detail:")
        print(f"  {'Game':<6} {'ExpClass':<10} {'Hit':>4} {'PredGoal (truncated)'}")
        print("  " + "-" * 66)
        for g in r.get("per_game", []):
            hit_s = "HIT" if g.get("class_hit") else "miss"
            goal_s = (g.get("predicted_goal", "") or "")[:50]
            print(f"  {g['game']:<6} {g['expected_class']:<10} {hit_s:>4}  {goal_s}")
    print()


def main() -> None:
    from arc_agi import Arcade, OperationMode

    # Only the two Qwen models that are already pulled in Ollama.
    candidates = ["qwen_3_8b_q4", "qwen_3_14b_q4"]

    print(f"Benchmarking {len(candidates)} candidate(s): {candidates}", flush=True)
    print(f"Games: {list(GROUND_TRUTH.keys())}", flush=True)
    print(f"Probes per game: {PROBE_BUDGET}\n", flush=True)

    arcade = Arcade(operation_mode=OperationMode.NORMAL)

    results: list[dict] = []
    overall_start = time.time()

    for cid in candidates:
        print(f"\n>>> {cid}", flush=True)
        t0 = time.time()
        try:
            r = run_candidate(cid, arcade)
            r["status"] = "ok"
            r["total_runtime_sec"] = round(time.time() - t0, 1)
        except Exception as exc:
            r = {
                "candidate_id": cid,
                "status": "error",
                "error": str(exc),
                "total_runtime_sec": round(time.time() - t0, 1),
            }
            print(f"  FAILED: {exc}", flush=True)
        results.append(r)
        # Write partial results after each candidate so a crash doesn't lose data.
        OUT.write_text(
            json.dumps(
                {
                    "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
                    "games": list(GROUND_TRUTH.keys()),
                    "results": results,
                },
                indent=2,
            )
        )

    total_sec = round(time.time() - overall_start, 1)

    # Rank and recommend.
    ok = [r for r in results if r.get("status") == "ok"]
    ranked = sorted(ok, key=_composite_score, reverse=True)
    primary = ranked[0]["candidate_id"] if ranked else None
    fallback = ranked[1]["candidate_id"] if len(ranked) > 1 else None

    # Check for any additional models that are already in Ollama (non-Qwen).
    try:
        import subprocess

        ollama_out = subprocess.run(
            ["ollama", "list"], capture_output=True, text=True, timeout=5
        ).stdout
        extra_models = [
            line.split()[0]
            for line in ollama_out.strip().splitlines()[1:]
            if line and not any(q in line for q in ("qwen3:8b", "qwen3:14b"))
        ]
        if extra_models:
            print(
                f"\nNote: additional Ollama models detected (not benchmarked): "
                f"{extra_models}. Pull size unknown — did not auto-pull.",
                flush=True,
            )
    except Exception:
        pass

    summary = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "total_runtime_sec": total_sec,
        "games": list(GROUND_TRUTH.keys()),
        "primary_pick": primary,
        "fallback_pick": fallback,
        "results": results,
    }
    OUT.write_text(json.dumps(summary, indent=2))

    _print_table([r for r in results if r.get("status") == "ok"])

    print(f"Primary recommendation: {primary}")
    print(f"Fallback:               {fallback}")
    print(f"Total runtime:          {total_sec}s")
    print(f"Output:                 {OUT}")


if __name__ == "__main__":
    main()
