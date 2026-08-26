---
name: project_kaggle_hardware
description: "ARC-AGI-3 2026 Kaggle eval hardware is g4-standard-48 (96GB VRAM), NOT T4 16GB — corrects a foundational CLAUDE.md assumption"
metadata: 
  node_type: memory
  type: project
  originSessionId: c7e91ecf-c8c0-4c3c-bd62-4722ff123df5
---

The ARC Prize 2026 / ARC-AGI-3 Kaggle evaluation machine is **`g4-standard-48`**, confirmed 2026-06-25 from the competition overview:

- **GPU: 1× NVIDIA RTX PRO 6000 Blackwell, 96GB GDDR7 VRAM** (verified via the GCP g4-standard-48 spec — 48 vCPU, 180GB RAM).
- **Runtime ~9h** (not 6h), **disk ~32GB** (per the overview — user-reported, exact numbers worth re-confirming).

This **invalidates the long-standing "T4 16GB VRAM / 6h" assumption** baked into CLAUDE.md and `configs/llm.yaml`, which drove every model-selection decision (favoring Qwen 8B/14B, ruling out Gemma 4 26B MoE as "17GB > 16GB").

**How to apply:** VRAM is no longer the binding constraint — ~32GB disk (model weight size) and ~9h runtime are. Gemma 4 26B MoE Q4 (~13-17GB) fits VRAM with ~79GB to spare and disk comfortably; even Q5/Q8 of ~26-32B models fit. Re-enabled `gemma_4_26b_moe_q4` in configs/llm.yaml. Model selection is reopened as round R17 (bench the strongest model that fits ~32GB disk + 9h, no longer capped at 14B). The deeper "T4"-based math throughout CLAUDE.md's LLM Selection section is stale and tracked for R17. Relates to [[project_llm_selection]] (now partially obsolete) and the round-16 wiki/retrieval work.
