"""Post-hoc rescore of R49 game JSONs with the fixed extract_code fallback.

The bench stores every round's generated code verbatim, so a scoring-layer fix
(unterminated-fence extraction) can be re-applied deterministically without any
LLM call: re-extract -> compile -> score against the SAME held-out split
(seed=0, few=15, hold=10, max_diff_cells=80 — the defaults every run used).

Emits keep-last (the bench headline) and keep-best-round aggregations.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from llm_worldmodel_bench import (  # noqa: E402
    compile_predict,
    extract_code,
    load_game_data,
    score_predictions,
    select_transitions,
)

ROUND_DIR = Path(__file__).resolve().parent
DATA_DIR = REPO_ROOT / "data" / "transitions" / "train"


def main() -> None:
    rows = []
    for path in sorted((ROUND_DIR / "games").glob("*.json")):
        record = json.loads(path.read_text())
        model, game = record["model"], record["game"]
        _, hold = select_transitions(
            load_game_data(game, DATA_DIR), n_few=15, n_hold=10, seed=0,
            max_diff_cells=80,
        )
        per_round = []
        for rnd in record["rounds"]:
            code = extract_code(rnd["code"])
            try:
                fn = compile_predict(code)
            except Exception:
                fn = None
            score = score_predictions(fn, hold)
            per_round.append(
                (score.exact_frame_accuracy, score.cell_accuracy, score.code_validity)
            )
        last = per_round[-1]
        best = max(per_round, key=lambda t: (t[0], t[1]))
        rows.append((model, game, last, best, [r[0] for r in per_round]))

    lines = [
        "R49 rescore (fixed fence extraction; same held-out split)",
        f"{'model':<50} {'game':<5} {'last-ex':>8} {'best-ex':>8}  per-round exact",
    ]
    for model, game, last, best, curve in rows:
        lines.append(
            f"{model:<50} {game:<5} {last[0]:>8.2f} {best[0]:>8.2f}  "
            + " ".join(f"{e:.2f}" for e in curve)
        )
    lines.append("")
    for model in sorted({r[0] for r in rows}):
        sub = [r for r in rows if r[0] == model]
        mean_last = sum(r[2][0] for r in sub) / len(sub)
        mean_best = sum(r[3][0] for r in sub) / len(sub)
        lines.append(
            f"{model:<50} mean last-exact={mean_last:.3f} best-exact={mean_best:.3f} (n={len(sub)})"
        )
    out = "\n".join(lines) + "\n"
    (ROUND_DIR / "RESCORE.txt").write_text(out)
    print(out)


if __name__ == "__main__":
    main()
