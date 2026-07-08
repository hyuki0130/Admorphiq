"""R49: measured LLM-selection benchmark for the executable-world-model track.

Purpose
-------
For each candidate LLM, measure how well it *synthesizes* a pure-Python

    def predict_next_frame(frame, action, xy=None)

transition function from a handful of observed transitions of an UNKNOWN game,
and how much that function improves under K rounds of execution feedback. This
is the pivotal go/no-go for the executable-world-model paradigm (R48 research,
``.wiki/wiki/rounds/r48_llm-selection-ewm.md``): a WRITE/refine-code LLM is only
worth deploying if it can reach useful exact-frame accuracy AND climb under
refinement.

The bench never trusts model-generated code — every synthesized function runs in
a restricted namespace with a per-prediction timeout, so a broken or malicious
generation degrades to "invalid", never a crash.

Data
----
Reuses ``scripts/collect_transitions.py`` output (``<game>.npz`` with
``frames`` / ``actions`` / ``next_frames``). Per game we take a deterministic
15 few-shot / 10 held-out split (changed transitions preferred so the examples
and the held-out targets actually exercise the game's dynamics).

Serialization (token economy)
-----------------------------
The first few-shot frame is emitted ONCE as a compact hex grid (one char/cell,
values 0-15). Every transition is then a diff — ``{"action", "changed"}`` where
``changed`` is ``[[row, col, old, new], ...]``. Prompts stay well under ~8k
tokens.

Scores (per model x game)
-------------------------
- ``code_validity``        fraction of held-out cases that ran + returned a grid
- ``cell_accuracy``        mean per-cell match over held-out
- ``exact_frame_accuracy`` fraction of held-out frames predicted 100% (headline)
- ``refinement_gain``      exact-frame delta R0 -> R{K}
- tokens / latency         per LLM call

Run (I run this; do NOT run it from an agent — the LLM call is live)
--------------------------------------------------------------------
    uv run python scripts/llm_worldmodel_bench.py \
        --models qwen3-coder:30b,qwen3:30b-a3b,qwen3:14b \
        --games ka59,sb26,sp80 --rounds 3 --out scripts/rounds/R49
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable

import numpy as np

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))


# Core primitives shared with the runtime agent (extracted in R52 / US-1).
# The trailing block re-exports names the test suite exercises through this
# module's namespace — keep them even though this file no longer calls them.
from admorphiq.ewm.core import (  # noqa: E402, F401
    ChatFn,
    OllamaChat,
    SandboxError,
    Transition,
    _run_with_timeout,
    _validate_grid,
    action_call_args,
    action_label,
    apply_diff,
    build_observations_block,
    build_prompt,
    build_refinement_prompt,
    compile_predict,
    diff_cells,
    extract_code,
    parse_grid,
    score_predictions,
    serialize_grid,
)


def select_transitions(
    data: dict[str, np.ndarray],
    n_few: int = 15,
    n_hold: int = 10,
    seed: int = 0,
    max_diff_cells: int = 80,
) -> tuple[list[Transition], list[Transition]]:
    """Deterministically split transitions into (few-shot, held-out) lists.

    Changed transitions with a serialization-friendly diff (``<= max_diff_cells``
    changed cells) are preferred so few-shot examples stay compact and held-out
    targets actually test the dynamics. If too few qualify, the pool is topped up
    with remaining changed then unchanged transitions. The shuffle is seeded, so
    the same (data, seed) always yields the same split.
    """
    frames = data["frames"]
    actions = data["actions"]
    next_frames = data["next_frames"]
    n = int(actions.shape[0])

    changed_counts = np.array(
        [int((frames[i] != next_frames[i]).sum()) for i in range(n)]
    )
    changed = changed_counts > 0

    small = [i for i in range(n) if changed[i] and changed_counts[i] <= max_diff_cells]
    big = [i for i in range(n) if changed[i] and changed_counts[i] > max_diff_cells]
    unchanged = [i for i in range(n) if not changed[i]]

    rng = np.random.RandomState(seed)
    rng.shuffle(small)
    rng.shuffle(big)
    rng.shuffle(unchanged)

    need = n_few + n_hold
    ordered = small + big + unchanged
    picked = ordered[:need]

    def make(i: int) -> Transition:
        return Transition(
            frame=np.asarray(frames[i], dtype=np.int16),
            action_idx=int(actions[i]),
            next_frame=np.asarray(next_frames[i], dtype=np.int16),
        )

    few = [make(i) for i in picked[:n_few]]
    hold = [make(i) for i in picked[n_few : n_few + n_hold]]
    return few, hold


# ─────────────────────────────────────────────────────────────────────────────
# Per model x game refinement run
# ─────────────────────────────────────────────────────────────────────────────
def run_model_game(
    chat: ChatFn,
    model: str,
    game: str,
    few_shot: list[Transition],
    held_out: list[Transition],
    rounds: int,
    max_tokens: int = 2048,
    timeout: float = 2.0,
    mechanics_prior: bool = False,
) -> dict[str, Any]:
    """Run round-0 synthesis + ``rounds`` refinement rounds for one model×game.

    Returns a JSON-serializable record with per-round scores, the refinement
    gain (R0 -> R{rounds} exact-frame delta), and token/latency totals.
    """
    messages = build_prompt(few_shot, mechanics_prior=mechanics_prior)
    round_records: list[dict[str, Any]] = []
    calls: list[dict[str, Any]] = []
    code = ""
    last_mismatches: list[dict[str, Any]] = []

    for r in range(rounds + 1):
        if r > 0:
            messages = messages + [
                {"role": "assistant", "content": f"```python\n{code}\n```"},
                {"role": "user",
                 "content": build_refinement_prompt(code, last_mismatches)},
            ]
        text, meta = chat(messages, model, max_tokens)
        calls.append(meta)
        code = extract_code(text)
        try:
            fn: Callable[..., Any] | None = compile_predict(code, timeout)
            compile_error = ""
        except SandboxError as exc:
            fn = None
            compile_error = str(exc)[:200]
        score = score_predictions(fn, held_out, timeout)
        # Train-fit on the few-shot transitions the model actually saw: the
        # leakage-free selection signal (usable identically at Kaggle runtime,
        # where held-out labels don't exist).
        train_score = score_predictions(fn, few_shot, timeout)
        # Refinement feedback comes from TRAIN mismatches only. Feeding
        # held-out mismatches (the pre-R50b behaviour) leaks up to 3 test
        # answers per round into the prompt and inflates every post-R0 score;
        # at Kaggle runtime no held-out labels exist at all.
        last_mismatches = train_score.mismatches
        round_records.append(
            {
                "round": r,
                "code_validity": round(score.code_validity, 4),
                "cell_accuracy": round(score.cell_accuracy, 4),
                "exact_frame_accuracy": round(score.exact_frame_accuracy, 4),
                "train_exact": round(train_score.exact_frame_accuracy, 4),
                "compile_error": compile_error,
                "prompt_tokens": meta.get("prompt_tokens", 0),
                "eval_tokens": meta.get("eval_tokens", 0),
                "latency_s": meta.get("latency_s", 0.0),
                "code": code,
            }
        )

    # Deploy policy: pick the round with the best train-fit (ties -> later
    # round). Guards against late-round regressions (gemma4 su15 0.60->0.00)
    # and invalid final generations (qwen tu93 empty r3) without touching
    # held-out labels.
    selected = max(round_records, key=lambda rec: (rec["train_exact"], rec["round"]))
    r0 = round_records[0]["exact_frame_accuracy"]
    rk = round_records[-1]["exact_frame_accuracy"]
    return {
        "model": model,
        "game": game,
        "n_few": len(few_shot),
        "n_hold": len(held_out),
        "rounds": round_records,
        "final": round_records[-1],
        "selected": selected,
        "refinement_gain": round(rk - r0, 4),
        "total_prompt_tokens": sum(c.get("prompt_tokens", 0) for c in calls),
        "total_eval_tokens": sum(c.get("eval_tokens", 0) for c in calls),
        "total_latency_s": round(sum(c.get("latency_s", 0.0) for c in calls), 3),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Data loading + IO
# ─────────────────────────────────────────────────────────────────────────────
def load_game_data(game: str, data_dir: Path) -> dict[str, np.ndarray]:
    """Load a game's ``.npz``, collecting it via the CLI if missing."""
    path = data_dir / f"{game.lower()}.npz"
    if not path.exists():
        print(f"[{game}] transitions missing; collecting via collect_transitions.py …",
              flush=True)
        data_dir.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            [sys.executable, str(REPO_ROOT / "scripts" / "collect_transitions.py"),
             "--titles", game, "--out", str(data_dir)],
            check=True,
        )
    npz = np.load(path, allow_pickle=True)
    return {"frames": npz["frames"], "actions": npz["actions"],
            "next_frames": npz["next_frames"]}


def write_summary(round_dir: Path) -> None:
    """Regenerate SUMMARY.txt from every per-model×game json (live, partial-safe)."""
    games_dir = round_dir / "games"
    records = []
    for f in sorted(games_dir.glob("*.json")):
        try:
            records.append(json.loads(f.read_text()))
        except (json.JSONDecodeError, OSError):
            continue

    lines = ["R49 — executable-world-model LLM selection", "=" * 60, ""]
    header = (
        f"{'model':<22}{'game':<7}{'valid':>6}{'cell':>7}"
        f"{'exR0':>7}{'exRK':>7}{'exSel':>7}{'exBest':>8}{'gain':>7}{'tok':>8}{'sec':>8}"
    )
    lines.append(header)
    lines.append("-" * len(header))

    per_model: dict[str, list[dict[str, Any]]] = {}
    for rec in records:
        per_model.setdefault(rec["model"], []).append(rec)
        r0 = rec["rounds"][0]["exact_frame_accuracy"] if rec["rounds"] else 0.0
        best = max(
            (r["exact_frame_accuracy"] for r in rec["rounds"]), default=0.0
        )
        rec["_best_exact"] = best
        sel = rec.get("selected", rec["final"])["exact_frame_accuracy"]
        rec["_sel_exact"] = sel
        fin = rec["final"]
        lines.append(
            f"{rec['model']:<22}{rec['game']:<7}"
            f"{fin['code_validity']:>6.2f}{fin['cell_accuracy']:>7.3f}"
            f"{r0:>7.2f}{fin['exact_frame_accuracy']:>7.2f}{sel:>7.2f}{best:>8.2f}"
            f"{rec['refinement_gain']:>+7.2f}"
            f"{rec['total_prompt_tokens'] + rec['total_eval_tokens']:>8}"
            f"{rec['total_latency_s']:>8.1f}"
        )

    lines.append("")
    lines.append("Per-model means (headline = exact-frame-accuracy @ final round):")
    for model, recs in sorted(per_model.items()):
        mean_exact = float(np.mean([r["final"]["exact_frame_accuracy"] for r in recs]))
        mean_cell = float(np.mean([r["final"]["cell_accuracy"] for r in recs]))
        mean_gain = float(np.mean([r["refinement_gain"] for r in recs]))
        mean_valid = float(np.mean([r["final"]["code_validity"] for r in recs]))
        mean_best = float(np.mean([r["_best_exact"] for r in recs]))
        mean_sel = float(np.mean([r["_sel_exact"] for r in recs]))
        lines.append(
            f"  {model:<22} exact={mean_exact:.3f} sel-exact={mean_sel:.3f} "
            f"best-exact={mean_best:.3f} cell={mean_cell:.3f} valid={mean_valid:.2f} "
            f"gain={mean_gain:+.3f} (n={len(recs)})"
        )
    lines.append("")
    (round_dir / "SUMMARY.txt").write_text("\n".join(lines))


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────
def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--models", default="qwen3-coder:30b,qwen3:30b-a3b,qwen3:14b",
                   help="Comma-separated Ollama model tags.")
    p.add_argument("--games", default="ka59,sb26,sp80",
                   help="Comma-separated game titles.")
    p.add_argument("--rounds", type=int, default=3, help="Refinement rounds (K).")
    p.add_argument("--out", default="scripts/rounds/R49", help="Round output dir.")
    p.add_argument("--data-dir", default="data/transitions/train",
                   help="Directory of <game>.npz transition files.")
    p.add_argument("--host", default="http://localhost:11434", help="Ollama host.")
    p.add_argument("--few", type=int, default=15, help="Few-shot transitions/game.")
    p.add_argument("--hold", type=int, default=10, help="Held-out transitions/game.")
    p.add_argument("--seed", type=int, default=0, help="Split seed.")
    p.add_argument("--max-tokens", type=int, default=2048, help="Generation cap.")
    p.add_argument("--num-ctx", type=int, default=16384,
                   help="Ollama context window (default 4096 truncates few-shot prompts).")
    p.add_argument("--mechanics-prior", action="store_true",
                   help="Prepend the game-agnostic mechanic vocabulary to the "
                        "system prompt (R51 axis B).")
    p.add_argument("--pred-timeout", type=float, default=2.0,
                   help="Per-prediction sandbox timeout (s).")
    p.add_argument("--max-diff-cells", type=int, default=80,
                   help="Max changed cells for a few-shot-eligible transition.")
    return p


def main() -> None:
    args = _build_parser().parse_args()
    models = [m.strip() for m in args.models.split(",") if m.strip()]
    games = [g.strip() for g in args.games.split(",") if g.strip()]
    round_dir = REPO_ROOT / args.out
    (round_dir / "games").mkdir(parents=True, exist_ok=True)
    data_dir = REPO_ROOT / args.data_dir

    chat = OllamaChat(host=args.host, num_ctx=args.num_ctx)

    splits: dict[str, tuple[list[Transition], list[Transition]]] = {}
    for game in games:
        data = load_game_data(game, data_dir)
        splits[game] = select_transitions(
            data, n_few=args.few, n_hold=args.hold, seed=args.seed,
            max_diff_cells=args.max_diff_cells,
        )

    for model in models:
        for game in games:
            few, hold = splits[game]
            print(f"[{model} × {game}] running {args.rounds} refinement rounds …",
                  flush=True)
            record = run_model_game(
                chat, model, game, few, hold, rounds=args.rounds,
                max_tokens=args.max_tokens, timeout=args.pred_timeout,
                mechanics_prior=args.mechanics_prior,
            )
            safe_model = model.replace(":", "_").replace("/", "_")
            out_path = round_dir / "games" / f"{safe_model}__{game}.json"
            out_path.write_text(json.dumps(record, indent=2))
            write_summary(round_dir)  # live-append per model×game
            fin = record["final"]
            print(f"    exact={fin['exact_frame_accuracy']:.2f} "
                  f"cell={fin['cell_accuracy']:.3f} "
                  f"gain={record['refinement_gain']:+.2f}", flush=True)

    print(f"Done. See {round_dir / 'SUMMARY.txt'}", flush=True)


if __name__ == "__main__":
    main()
