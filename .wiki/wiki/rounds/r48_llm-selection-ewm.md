---
title: R48 — LLM selection for executable world model (research)
type: round-log
round: R48
axis: llm-selection
keywords: [executable-world-model, llm-selection, qwen3-coder, glm-5.2, gemma-4, vllm, fp8, kaggle-budget]
verdict: primary = Qwen3-Coder-30B-A3B (pending local measured bench); GLM-5.2 hardware-excluded
commit: pending
date: 2026-07-06
description: LLM selection research for the executable-WM role — Qwen3-Coder-30B-A3B primary, GLM-5.2 hardware-excluded (744B > 96GB), measured-pick bench designed
---

# R48 — LLM selection for the executable-world-model role (deep comparison)

Role = WRITE/refine Python transition rules from observed transitions (arXiv 2605.05138 recipe;
GPT-5.4 32.58%, GPT-5.5 successor 58.12%). Core skill: code generation + iterative refinement.

## Verdict table (2026-07, cited in agent report)
- **Qwen3-Coder-30B-A3B-Instruct** 🥇: MoE 30.5B/3.3B-active; SWE-bench Verified ~51.9%; 4bit ~18GB /
  FP8 ~30GB (96GB에 대여유); Apache 2.0; Ollama `qwen3-coder:30b` — 로컬 개발 가능. 결정적:
  active-3.3B MoE + vLLM batching → 110게임×20콜×4k tok ≈ 8.8M tok가 9h 안에 들어옴 (~2.4h @1000tok/s).
- **GLM-5.2**: 오픈 코딩 최강 (SWE-bench Pro 62.1 > GPT-5.5 58.6; MIT) BUT **744B total → 4bit 372GB
  → 96GB 물리적 불가**; Ollama cloud-only → 로컬 벤치도 불가. **배포 제외** (상한 레퍼런스로만).
- DeepSeek-Coder-V3: 초대형, 96GB 불가. Gemma 4 26B MoE: 수학/추론 강하나 코딩 특화 아님 — 2순위
  후보(다양성). Qwen3-Coder-Next: 크기 확인 후 상위 대안 가능.
- 참고: 작은 모델 distill 가능성 (arXiv 2605.24375: Qwen2.5-3B distill이 GPT-4o 근접) — M2 fallback.

## Measured-pick benchmark (mandatory before final; scripts/llm_worldmodel_bench.py 제안)
KA59/SB26/SP80 transitions 15 few-shot / 10 held-out; diff-serialization (초기 프레임 1회 + changed
cells만 → 콜당 2-8k tok); K=3 refinement rounds (틀린 케이스 되먹임); score = code-validity,
cell-acc, exact-frame-acc(주지표), refinement-gain, tokens/latency. Pull: `qwen3-coder:30b`.

## Kaggle stack
vLLM offline V1 + FP8 (Blackwell native) 권장; read-only Kaggle Model mount; guided decoding으로
validity 확보; 게임당 max-calls(≤25)+max-tokens 하드캡 (논문 $34-620/game = 무제한 루프 경고).

**Related**: [[r36_graph-frontier-bfs]] (paradigm wall), [[r34_metric-reexamination]],
[[r49_ewm-bench-partial]] (the measured bench this page designed — 14b/8b results, 30b blocked).
