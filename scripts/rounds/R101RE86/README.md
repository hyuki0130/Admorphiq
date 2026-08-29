# R101RE86 — re86 level 2, 46 actions against a human 42

`fan_before.jsonl` — the 18-way fan of `scripts/_re86_l2.py` on ceph-build BEFORE the change
(modes: trace / ground / attempts / fallback / repeat, three repeats each). It is what established
that all 46 actions were effective, that level 2 is never lost and retried, that the count is
deterministic, and that one of the 46 came from the harness probe rather than from the tool.
⚠️ Mode 3 (`optimal`, an exhaustive placement search checked against the engine's own win
predicate) never returned inside 1800s and is not represented here; the optimum was computed
arithmetically instead from the ground truth and the trace — 34 moves for the placement the tool
itself chooses, plus 2 presses of the cyclic select control.

`re86_after.json` — the official score after the change: **1.0000, 8/8, 696 actions**, level 2 at
42 against a human 42.

`cn04_after.json` / `sc25_after.json` / `cd82_after.json` — three of the five other games
`cover_targets` bids on, unchanged at 1.0000. dc22 and lf52 are the two the full-25 gate must
still cover.
