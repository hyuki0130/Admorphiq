---
title: R49 — executable-WM measured bench (partial — 14b/8b; 30b blocked locally)
type: round-log
round: R49
axis: llm-selection
keywords: [executable-world-model, llm-bench, qwen3-14b, qwen3-8b, qwen3-coder, exact-frame-accuracy, refinement, memory-crash, ollama, 24gb-ram]
verdict: 14b exact=0.100 (sp80 0.30 via refinement), 8b exact=0.000; 30b UNMEASURED — 18GB model crashed the 24GB dev Mac
commit: a12e760
date: 2026-07-06
description: Measured executable-WM bench — 14b exact=0.100 (refinement +0.30 on sp80), 8b invalid; 30b blocked by 24GB-RAM crash (WindowServer death)
---

# R49 — executable-WM measured bench (partial)

Harness = `scripts/llm_worldmodel_bench.py` (commit `a12e760`, 14 unit tests): per model×game,
synthesize `predict_next_frame(frame, action, xy)` in pure Python from 15 diff-serialized few-shot
transitions, score on 10 held-out, K=3 refinement rounds with execution feedback. Headline =
exact-frame accuracy. Data = `data/transitions/train/{ka59,sb26,sp80}.npz`.

## Run 1 (17:54 KST) — CRASHED, 0 results

`qwen3-coder:30b` (18GB Q4 MoE) via Ollama on the 24GB M4 Pro dev Mac. Loading the model wired
~18GB → system free RAM fell to **89MB** (5,720×16KB pages, from the WindowServer stackshot) →
VM-compressor/swap thrash → **WindowServer watchdog timeout twice (17:57, 19:22 KST)** + JetsamEvent
18:02 → Ollama connection died → bench raised `RuntimeError: Ollama /api/chat failed … Remote end
closed connection`. Side casualty: the 2.4MB crash `.ips` pasted into the dev session pushed the
prompt to 1.84M tokens > 1M → the Claude session itself bricked (three `prompt is too long` 400s,
unrecoverable by /compact because the queued paste is re-delivered).

⛔ **DO-NOT-REPEAT: never load an ≥18GB Ollama model on this 24GB Mac** (Metal wires ~75% of RAM;
the rest of the OS thrashes). Local ceiling ≈ qwen3:14b (9.3GB). Also: never paste multi-MB crash
reports into a session — reference the file path instead.

## Run 2 (20:19–20:28 KST) — memory-safe models, MEASURED

| model | game | valid | cell | exact R0→RK | gain | tok | sec |
|---|---|---|---|---|---|---|---|
| qwen3:14b | ka59 | 1.00 | 0.996 | 0.00→0.00 | +0.00 | 13,478 | 125 |
| qwen3:14b | sb26 | 1.00 | 0.999 | 0.00→0.00 | +0.00 | 9,188 | 61 |
| qwen3:14b | sp80 | 1.00 | 0.996 | 0.00→**0.30** | **+0.30** | 16,479 | 197 |
| qwen3:8b | ka59 | 1.00 | 0.998 | 0.00→0.00 | +0.00 | 10,559 | 36 |
| qwen3:8b | sb26 | 0.00 | 0.000 | 0.00→0.00 | +0.00 | 10,542 | 46 |
| qwen3:8b | sp80 | 0.00 | 0.000 | 0.00→0.00 | +0.00 | 12,369 | 58 |

Means: **14b exact=0.100 / valid=1.00 / gain=+0.100**; **8b exact=0.000 / valid=0.33**.

## Read

- The refinement loop WORKS when the model is strong enough: 14b×sp80 went 0.00 → 0.30 purely
  from execution feedback — the paradigm's core bet (climb under refinement) shows signal.
- 8B-class cannot even keep code validity (2/3 games invalid) — consistent with the R5–R11
  routing-era finding that 8B is the floor, not a candidate.
- cell≈0.996 with exact=0.00 means the models learn "mostly nothing changes" but miss the
  actual dynamics — exact-frame is the right headline; cell-accuracy is nearly saturated noise.
- Go/no-go for [[r48_llm-selection-ewm]]'s pick (Qwen3-Coder-30B-A3B) is still OPEN: the primary
  candidate is exactly the size class this machine cannot host. Options: (a) smaller quant
  Q3_K_M ~13-14GB fits the ~16GB Metal budget, (b) measure on Kaggle 96GB GPU, (c) accept 14b
  numbers as lower bound. Decision pending user.

**Related**: [[r48_llm-selection-ewm]] (candidate research), [[r36_graph-frontier-bfs]] (the
paradigm wall this track answers), [[r35_forward-transfer]] (neural-WM transfer precedent).
