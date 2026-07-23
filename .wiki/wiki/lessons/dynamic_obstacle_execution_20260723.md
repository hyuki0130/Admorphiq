---
type: lesson
keywords: [dynamic-obstacle, transient-evidence, invalidation, observation-trumps-inference, ttl, flip-flop, time-expanded-bfs, behavioural-orbit, invisible-mover, execution-fidelity]
date: 2026-07-23
provenance: R96 idx1 15-defect ladder (commits 01a4fa0..b9011cc, gates v5-v15)
---

# Dynamic obstacles under online world-model execution

> A moving obstacle poisons EVERY static inference layer in turn — wall
> learning, the static parse, transient memory, even the never-learn guard —
> and each layer needs its own observation-lifetime rule; when the mover is
> floor-coloured it is perception-invisible and only behavioural sensing
> (block events) observes it at all.

## Symptom

Plan-execute-confirm loops on a board with a moving obstacle fail in a
CHAIN of distinct modes, each 3/3-deterministic: hammering loops (nothing
learned), learn→unlearn churn, mirror-locked oscillations through fictional
walls, maps that close into false UNSATISFIABLE, and static learners whose
caps fill with the mover's transient positions.

## Root Cause

A static world model treats every block observation as evidence about
FOREVER. A mover makes block evidence time-local. Six specific poisonings
measured in R96 (m0r0 idx1):

1. A mover sitting on a cell at PARSE time is baked into the static
   occupancy as a permanent wall (the plan then routes "desyncs" through
   pure fiction).
2. A mover blocking an entry once becomes a learned wall that later
   contradicts an actor standing on that very cell.
3. A never-learn guard (added against #2) turns a toggled cell into an
   UNWALLABLE fictional floor — the plan hammers it to the cap.
4. A transient block set cleared only by observation SELF-SEALS: forbidden
   cells can never be re-observed, so temporary fiction accumulates until
   the map is unroutable.
5. Greedy reactive avoidance with instant-clear memory CHASES a periodic
   mover across a corridor fork forever (flip-flop).
6. A floor-coloured mover (colour N blob on colour-N floor) produces ZERO
   frame diff — perception cannot see it even in principle; only failed
   moves (block events) sense it.

## Prevention

Layered rules, each matching evidence to its true lifetime:

- **Observation trumps inference, at EVERY layer**: an actor observed ON a
  wall (learned OR grounded/parsed) invalidates it immediately.
- **Static learning requires persistence evidence**: retry-once before
  learning; learn only when no mover is visible at the target (when a
  perception channel exists).
- **Transient evidence gets a TTL**: block-now sets decay after a few
  recompiles unless re-confirmed; on UNSATISFIABLE, flush to
  freshest-evidence-only and retry once before surfacing.
- **Flip-flop detection → commit-and-wait**: when a bounce pair alternates,
  stop switching branches; re-attempt in place (each re-emission samples
  the mover one phase later).
- **Model the mover explicitly when reactive threading saturates**:
  time-expanded joint BFS over (positions, t mod P) with orbit phases from
  (a) frame-diff perception for visible movers, (b) behavioural sparse
  phase-consistency (blocked = positive sample, passed = negative) for
  invisible ones.

## Recovery

When a new board shows the symptom chain, apply the ladder in order (each
rung is cheap and the cause-logged recompile stream tells you which rung
you are on): invalidate-occupied → settle → wait → hazard-learn →
wall-candidates (retry-once, never churn/transient) → ambiguous. Escalate
to the time-expanded planner only when the reactive residual meter shows
chasing/accumulation.

## Falsification

- If a board's blocks never contradict (no learn→unlearn events), the
  obstacle is static and none of this machinery activates (idx0 stayed
  byte-identical through all 15 R96 gates — the P=1 degeneracy).
- The behavioural period fit is honest: a monotonic climb toward the pmax
  ceiling without stabilizing falsifies "small-period mover" (m0r0 idx1
  measured 2→10 at pmax=12 — long-period, multi-mover, or
  position-dependent; the discriminator is a tick-shift counterfactual,
  not more replays).

## Related

- [[../rounds/r96_controlled-grid-dynamics]] — the full 15-defect ladder
  with per-gate artifacts.
- [[../lessons/faithful_offline_simulator_20260715]] — the static
  counterpart: learn an operator/state-model, then plan.
- [[../lessons/env_metadata_duplicate_game_id_20260719]] — another case
  where a stale layer silently poisoned downstream conclusions.
