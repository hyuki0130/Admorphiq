---
name: Phase 8 restart — three-layer agent architecture (2026-04-21)
description: Linear Phase 8 plan replaced by agentic loop with Cognition/Memory/Action separation and dev/Kaggle time boundaries
type: project
originSessionId: eba5cc76-48c0-4391-bce2-39b48288934e
---
Phase 8 plan restart on 2026-04-21. The pre-restart plan (Wiki seed → frame-only solvers → LLM inference → cleanup) was a linear pipeline. Live-env WikiAgent first run (`memory/project_wiki_agent_first_run.md`) capped at 15/40 envs, classification 45%, exposing four structural gaps: thin LLM input (5 features), thin LLM output (17/74 strategies), no failure feedback, no regression gate.

**Why:** the user reframed the system as an agent — LLM = 두뇌(cognition), Wiki = 기억(memory), 함수 = 액션(action). Improvement must flow as a loop: run → reflect → propose → apply → gate → commit.

**How to apply:**
- Binding architecture doc at `.wiki/wiki/architecture.md` — load-bearing, any contradicting change updates the doc first.
- Dev-time loop: Qwen proposes JSON (wiki edits, new features, new strategies), Claude Code (me) implements. 8B-class models are reliable proposers but unreliable code editors on an 8000-line module — that split is intentional.
- Kaggle-time loop: frozen assets + session dict. No disk writes to code paths. Mid-run LLM refinement optional (only if token budget allows).
- R1–R6 restart order:
  1. R1 architecture doc (done this commit)
  2. R2 feature-rich DiscoveryReport (>5 features)
  3. R3 universal strategy dispatcher (74 strategies exposed via ctx)
  4. R4 reflection module (`scripts/reflect_wiki_agent.py`)
  5. R5 regression gate (don't break working envs)
  6. R6 live-env bench (8B vs 14B with full feature set)
- **Do not** try to make Qwen self-edit strategy .py files directly. Proposer/implementer split is load-bearing for quality and safety.
- **Do not** confuse cold-prompt bench (`scripts/bench_llm.py`, name-only) with live-env bench (R6) — they measure different things.
- Kaggle submission = frozen snapshot the dev loop has hardened. Each submission is one iteration of the dev loop promoted to production.
