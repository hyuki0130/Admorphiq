"""R50 post-hoc rescore: apply train-fit round selection to the cloud K=3 run.

The cloud run predates the train-fit selection harness (commit 1c847f5), but
every round's code is stored, so the deploy policy is recomputable offline:
score each round's code on the FEW-SHOT (train) split and on held-out, then
selected = argmax(train_exact, tie -> later round). Reports last / selected /
best per model x game plus per-model means.
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
        few, hold = select_transitions(
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
            hold_s = score_predictions(fn, hold)
            train_s = score_predictions(fn, few)
            per_round.append(
                (train_s.exact_frame_accuracy, hold_s.exact_frame_accuracy)
            )
        last = per_round[-1][1]
        sel = max(enumerate(per_round), key=lambda t: (t[1][0], t[0]))[1][1]
        best = max(h for _, h in per_round)
        rows.append((model, game, last, sel, best))

    lines = [
        "R50 rescore — cloud K=3, post-hoc train-fit selection",
        f"{'model':<28} {'game':<5} {'last':>6} {'sel':>6} {'best':>6}",
    ]
    for model, game, last, sel, best in rows:
        lines.append(f"{model:<28} {game:<5} {last:>6.2f} {sel:>6.2f} {best:>6.2f}")
    lines.append("")
    for model in sorted({r[0] for r in rows}):
        sub = [r for r in rows if r[0] == model]
        m = [sum(r[i] for r in sub) / len(sub) for i in (2, 3, 4)]
        lines.append(
            f"{model:<28} mean last={m[0]:.3f} sel={m[1]:.3f} best={m[2]:.3f} (n={len(sub)})"
        )
    out = "\n".join(lines) + "\n"
    (ROUND_DIR / "RESCORE.txt").write_text(out)
    print(out)


if __name__ == "__main__":
    main()
