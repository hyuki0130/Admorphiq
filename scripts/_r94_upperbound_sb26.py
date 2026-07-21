"""R94 sandbox self-reproduction preflight for the ``simdfs`` card on ``sb26``.

The parity gate proves the LIVE adapter still clears sb26 8/8 after the engine was
distilled out (``scripts/script25.py --games sb26``). This preflight proves the
COMPLEMENTARY invariant: the assembled ``source_card("simdfs")`` — the exact,
self-contained source the offline model would patch — can, run through the REAL
``run_code`` sandbox (the same execution path Kaggle-time code takes), reproduce
the adapter's clears WITHOUT the adapter. If the card cannot self-reproduce, the
distillation dropped load-bearing orchestration (the D3 lesson: lp85's
press-until-certify omission failed exactly this gate).

Structure mirrors ``scripts/probe_patch_loop.py``'s PATCH RUN path, but with the
ORIGINAL card (no LLM patch): drive sb26 offline; on each refill, exec
``card + "\\n\\nsimdfs_core(current_frame, transitions, act)\\n"`` through
``run_code`` with the per-level transitions serialized in; execute the queued
clicks; report levels cleared. Because a portal-sort board is static between
actions, the card re-plans from the current (partially-filled) board each refill,
so it converges across the run despite the sandbox's per-call action cap.

Usage (on the ceph-build CPU VM, offline Arcade — do NOT run locally, the Mac
crashes on parallel/large loads):
  ~/admorphiq/.venv/bin/python scripts/_r94_upperbound_sb26.py --budget 5000

Requires only the offline Arcade (no LLM / no GPU): the card is the un-patched
original, so no ``HARNESS_LLM_*`` env is needed.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts"))

import numpy as np  # noqa: E402

# The card name + game are fixed for this preflight (mirrors _r94_upperbound_lp85's
# shape, specialized to the simdfs/sb26 pair).
_CARD = "simdfs"
_CORE_FN = "simdfs_core"
_GAME = "sb26"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--budget", type=int, default=5000)
    ap.add_argument("--out", default=None, help="optional path to also write the JSON result")
    a = ap.parse_args()

    # The driver line references ``transitions``; the sandbox only injects it under
    # this gate (byte-identical default otherwise). Harmless here — the simdfs core
    # ignores transitions (static board) — but keeps the execution path identical.
    import os

    os.environ.setdefault("HARNESS_KERNEL_API", "1")

    import probe_patch_loop as ppl  # the shared offline driver + serialization

    from admorphiq.tools.code_agent import run_code
    from admorphiq.tools.solver_core import source_card

    card = source_card(_CARD)
    driver = card + f"\n\n{_CORE_FN}(current_frame, transitions, act)\n"

    print(f"[live] preflight card={_CARD!r} core={_CORE_FN!r} game={_GAME!r} "
          f"budget={a.budget}", flush=True)
    arcade, match = ppl._find_game(_GAME)
    env = arcade.make(match.game_id)

    level_transitions: list[dict[str, Any]] = []

    def refill(obs: Any, frame: np.ndarray) -> list[tuple[int, Any]]:
        trans = [
            (t["action"], t["xy"], t["before"], t["after"]) for t in level_transitions
        ]
        res = run_code(driver, frame, [], ["MOUSE"], transitions=trans)
        if res.error:
            print(f"[live] card execute error: {res.error}", file=sys.stderr, flush=True)
        return [ppl._to_step(name, xy) for name, xy in res.actions]

    def on_transition(prev: np.ndarray, step: Any, frame: np.ndarray, changed: bool) -> None:
        from admorphiq.kernels.simdfs import _SIMPLE_ACTION_NAMES

        aid, xy = step
        # The same UP/DOWN/.../SPACE naming _plan_progress matches plan steps
        # against (established convention shared with probe_patch_loop.py's own
        # _NAME map) -- a divergent naming scheme here would silently defeat the
        # core's in-flight-plan reconstruction during a real preflight run.
        name = "CLICK" if aid == 6 else _SIMPLE_ACTION_NAMES.get(aid, f"ACTION{aid}")
        level_transitions.append({
            "action": name,
            "xy": [int(xy[0]), int(xy[1])] if xy is not None else None,
            "before": prev, "after": frame,
        })

    def on_level_up() -> None:
        level_transitions.clear()

    t0 = time.time()
    obs, steps, levels = ppl._drive(
        env, a.budget, refill, on_transition, on_level_up, tag=_CARD
    )
    elapsed = round(time.time() - t0, 1)

    # sb26 parity target is 8/8 @0.846; the sandbox path reproduces the clears the
    # distilled card can express through the per-action before/after contract.
    result = {
        "card": _CARD, "core_fn": _CORE_FN, "game": _GAME, "budget": a.budget,
        "levels_cleared": int(levels), "actions": int(steps), "elapsed_s": elapsed,
        "target": "8/8 (adapter parity @0.846); this preflight measures sandbox "
                  "self-reproduction of that clear",
    }
    text = json.dumps(result, indent=2)
    if a.out:
        Path(a.out).write_text(text)
        print(f"[live] wrote {a.out}", flush=True)
    print(text)


if __name__ == "__main__":
    main()
