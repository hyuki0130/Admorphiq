---
name: feedback_parallel_build
description: Tool development runs as one background agent per game, integrated centrally and kept only on a full-25 measurement
metadata:
  type: feedback
---

Never improve tools one at a time.

**Why**: the user's standing directive (2026-08-27) — serial tool work leaves a 64-core box idle
and spends a session on one game. Measured the same day: six or seven iterations went into ONE
level of ONE game before a full-25 run showed the change was a 20x net loss.

**How to apply**: fan out one background agent per GAME, all launched in a single message. Each
owns exactly two NEW files (`src/admorphiq/tools/<name>.py`, `scripts/<name>_probe.py`) and may not
touch `registry.py`, `loop.py`, `segment.py`, another agent's tool, or commit anything. Brief each
with what has already been paid for: read the game's source and level data first, thirteen games
declare a per-level action budget that ENDS the game, `detect` returns 0.0 without a plan,
segmentation comes from `tools/segment.py`, actions are swallowed during animations, an edge-pinned
counter is not board content.

Then integrate CENTRALLY — only the parent edits `registry.py` — one tool at a time, and run the
full 25 on ceph-build at PAR=25 (~2 minutes). Keep only if no game regressed. Selectivity is a
property of the tool SET, so no agent may decide whether its own work is kept. See
[[feedback_measure_full_25]] and [[project_stage1_tool_build]].
