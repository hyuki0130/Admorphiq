"""Duck-style multimodal code-REPL agent (R55).

The offline-testable core of the code-REPL architecture from the R55 Codex
design consultation (``docs/r55_codex_design_consultation_20260714.md``): a
multimodal coding model with a stateless Python REPL infers an
environment-specific controller, with structured segmentation perception, a
compact transition ledger, a governed action executor, and a deterministic
transcript/replay system for scientific Kaggle iteration.

Round 1 (this package) is LLM-free and unit-tested: transcript/replay,
segmentation/tracking, turn-packet building, the Python sandbox + inspection
API, and the action governor. The model wiring + Kaggle vLLM bundle is Round 1's
second half (Kaggle infra).
"""

from __future__ import annotations
