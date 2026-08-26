---
name: feedback_measure_full_25
description: Measure the full 25 games before keeping any tool change; score a tool by net card effect, never by its own game
metadata:
  type: feedback
---

Never keep a tool change on the evidence of a single-game probe.

**Why**: on 2026-08-27 a ring-reader was loosened over six iterations so it could see a new board,
each iteration looking like progress under a single-game probe. The full 25 showed
`ft09 0.4762 -> 0.0476, mean 0.0211 -> 0.0037` — a 20x net loss — while the loosened tool remained
perfect on its own game. In a shared harness a tool's mistake is not its own failure; it takes the
turn from the tool that would have solved the board.

**How to apply**: after any change to a tool, the registry or the harness loop, sync to ceph-build
and run the full 25 (`scripts/rounds/*/run.sh`, `PAR=25`, ~2 minutes) BEFORE keeping it. Compare
per game, not just the mean. Score the tool by its net effect on the card. And a Kaggle submission
is never the measurement — the user's standing directive (2026-08-27) is no submission until the
sample games are cleared.
