---
title: R50 — cloud EWM bench on Kaggle-identical hardware (K=3, 4 models)
type: round-log
round: R50
axis: llm-selection
keywords: [executable-world-model, cloud-bench, gcp, g4-standard-48, rtx-pro-6000, gemma4-31b, gpt-oss-120b, qwen3-coder, held-out-leakage, train-fit-selection]
verdict: gemma4-31b-q8 0.433/0.494 NEW LEADER > gpt-oss-120b 0.272 > gemma4-26b 0.239 > qwen3-coder-q8 0.061 (family eliminated); held-out leakage found in refinement loop — fixed, K=8 honest re-run launched
commit: aea406d
date: 2026-07-07
description: First bench on Kaggle-identical hardware (GCP g4-standard-48 spot, RTX PRO 6000 96GB) — gemma4-31b-q8 leads at 0.433/0.494; qwen3-coder eliminated even at q8; refinement-loop held-out leakage found and fixed
---

# R50 — cloud EWM bench on Kaggle-identical hardware

> First measurement on the EXACT eval machine class: GCP `g4-standard-48` spot VM
> (RTX PRO 6000 Blackwell 96GB — the machine type the competition overview names),
> asia-east1-a, ~$2/hr spot, free-trial credits. Ollama, flash-attention on,
> num_ctx 65536 (no truncation possible), max_tokens 8192, K=3, temp 0.

## Results (18 games, exact-frame keep-last / keep-best, rescored)

| model | precision | last | best | note |
|---|---|---|---|---|
| **gemma4:31b-it-q8_0** | q8 | **0.433** | **0.494** | NEW LEADER; lf52 1.00, half of held-out exact |
| gpt-oss:120b | native MXFP4 | 0.272 | 0.294 | +15% over local 20b (0.256) — scale gain modest |
| gemma4:26b-a4b-it-qat | qat4 | 0.239 | 0.244 | ≈ local run (0.244) — local qat numbers were faithful |
| qwen3-coder:30b-a3b-q8_0 | q8 | 0.061 | 0.072 | **family ELIMINATED** — q8 ≈ local Q3 ≈ 14b-class |

- Dense-31B > MoE everywhere here: gemma4-31b beats its own 26b-A4B sibling 2x and
  gpt-oss-120b (5.1B active) by 1.6x. **Active-parameter count, not total, predicts
  rule-induction quality** on this task; SWE-bench-style coding rank (qwen3-coder)
  does not transfer to it at all.
- R48's original primary (Qwen3-Coder-30B) is now measured-refuted at full precision:
  the R49 Q3 collapse was NOT (only) quant damage.
- 26b-a4b cloud ≈ local: QAT-4bit local benching is a trustworthy cheap proxy.

## Defect found: held-out leakage in the refinement loop (fixed in `aea406d`)

`run_model_game` fed `score_predictions(fn, held_out).mismatches` back into the
refinement prompt — up to 3 test answers/round. All post-R0 scores above are therefore
optimistic in absolute terms (RELATIVE ranking stands — equal leakage). Also explains
why post-hoc train-fit selection scored below keep-last (sel 0.317 < last 0.433 for
31b): later rounds were fitting the leaked held-out. Fixed: refinement mismatches now
come from TRAIN (few-shot) only — the only protocol realizable at Kaggle runtime —
with a no-leakage contract test. **R50b (K=8, top-2 models, fixed harness) re-measures
honestly**; treat R50 absolute numbers as upper bounds until R50b lands.

## Ops (reusable)

`scripts/rounds/R50/vm_setup.sh` (ollama + q8-preferred pulls + flash-attn override),
`vm_run.sh` (per-game ratchet, spot-preemption-safe), `rescore.py` (post-hoc). VM is
disposable; source of truth is this repo — fixes flow local-edit → commit → scp.
GCP free-trial path: upgrade account → `GPUS_ALL_REGIONS` 0→1 → spot VM ~$2/hr
(g4 quota needed no separate approval). gcloud ssh/scp; bench detached via nohup.

**Related**: [[r49_ewm-bench-partial]] (local 3-way + harness fixes this run inherited),
[[r48_llm-selection-ewm]] (candidate research — verdict now superseded by measurement).
