---
name: feedback_rl_not_abandoned
description: "One bad RL run is not a verdict on the method; validate multiple versions / checkpoints with keep-best before concluding, and don't blind-benchmark the top team"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: c7e91ecf-c8c0-4c3c-bd62-4722ff123df5
---

When the first RL fine-tune (`scripts/train_rl.py`, REINFORCE from BC init)
scored 1.54% < BC 3.41%, the first write-up called RL "rejected". The user
pushed back: a single run with one hyperparameter set does not prove the method
fails, and two versions should be compared/validated rather than one declared
dead.

**Why:** RL-from-BC is hyperparameter-sensitive (catastrophic forgetting, reward
shaping side-effects, too-few steps, keep-last overshoot). Auto-promote keeping
v6 was a correct *deployment* decision, not a research verdict. Conflating the
two discards a promising lever.

**How to apply:**
- **Tune before you discard.** A single unfavorable config does NOT kill a lever. If it shows
  ANY positive signal (even on a subset — e.g. R16/R18 object-prior got CD82/M0R0 to L2), run a
  SMALL parameter sweep (2–3 coeff/threshold/prob configs) on the reliable 3-seed metric BEFORE
  the verdict. Only a mechanism proven INERT (byte-identical to baseline, e.g. R14) is a one-shot
  discard. Record the sweep in the round page. Revisit prior single-config "discards" that hinted.
- Distinguish "deployment choice" (ship the best *verified* model now) from
  "method verdict" (needs a sweep + ablations).
- Score intermediate checkpoints (`scripts/_rl_curve.sh`) to see the trajectory;
  use **keep-best-by-eval**, not keep-last.
- Likely RL fixes: lower LR, stronger KL/BC anchor, drop +0.02/frame-change
  shaping (rewards wiggling), longer training.
- Don't blind-benchmark the top team — copy the *online test-time learning*
  idea, not the public-gold BC. See [[project_general_direction_worldmodel]],
  [[project_bc_transfer_ceiling]], [[feedback_verify_via_regression]].
