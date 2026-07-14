---
type: lesson
date: 2026-07-15
keywords: [vllm, determinism, temperature-zero, greedy-decoding, matched-experiment, measurement-discipline, engagement-experiment, su15, r11l, floating-point-non-associativity]
description: Temperature=0.0 greedy decoding is NOT bit-reproducible across separate vLLM server instances — matched A/B arms must run inside one server session, not be compared across sessions started hours apart.
---

# vLLM cross-session non-determinism at temperature 0.0 (2026-07-15)

> A "control" arm that should replicate a prior run's control arm — same
> config, same prompt, same model name, same temperature=0.0 — silently
> stopped replicating because the vLLM server PROCESS itself had changed
> between sessions, not because anything in the experiment changed.

## Symptom

The R55 engagement experiment (`REPL_EXPERIMENT=engagement`, `scratchpad/replbench_out13`,
32 runs) scored **0 levels on every single run, including the `base`/control arms**
for su15 and r11l — the exact games whose equivalent control arm in the earlier
matched12 experiment (`scratchpad/replbench_out9`, same day, ~6.8h earlier) had
cleared level 1 reliably (su15 OFF 3/3 reps at 19 actions; r11l OFF 1/1 at 46-105
actions). Both experiments shared `run_manifest.json`'s `config_env`
(`REPL_LLM_BASE_URL`, `REPL_LLM_MODEL=qwen`, `REPL_LLM_TEMPERATURE=0.0`,
`REPL_SANDBOX_TIMEOUT`) and `versions` block (`vllm: 0.19.1`) byte-for-byte. The
natural hypothesis — "something in the dataset/config changed between sessions"
— was directly falsifiable and turned out to be wrong.

## Root Cause

Turn-by-turn replay of `su15_base_r0` (out13, 0 levels) against `su15_off_r0`
(out9, cleared L1) — see [[../rounds/r55_code-repl-agent]] for the full trace —
showed turns 0, 1, AND 2's **inputs** (`prompt_text`, `image_hash`,
`legal_actions`) were byte-identical between the two runs. The divergence is the
MODEL'S OWN chosen action at turn 2: out9 picks `MOUSE(51,14)` decisively; out13
picks `MOUSE(53,10)` after visible hesitation in its own reasoning text ("Let's
try clicking the center... or a different part... Wait... Actually..."). Both
transcripts show the model was near a tie between adjacent click points in the
same region. r11l shows the identical directional pattern (out9 control cleared
1 level, out13 control 0, same wall-clock terminal reason, no crash).

Given identical config/version strings but different greedy output, and given
that action counts are **self-consistent within out13 across reps** (not random
per-call noise) but **different from out9** (a separate session ~6.8h earlier),
the parsimonious explanation is that the vLLM server PROCESS differs between
sessions — a restart or reload between the two runs — and **temperature=0.0
greedy decoding is not guaranteed bit-reproducible across separate server
processes**, even with an identical version string and identical config. This is
a known class of vLLM/GPU-inference behavior: floating-point non-associativity in
batched/continuous-batching attention means the exact logits (and therefore the
argmax tie-break at a near-tie decision point) can differ between server
instances, even though decoding is fully deterministic WITHIN one instance's
lifetime.

## Prevention

**Matched A/B arms must run inside ONE server session**, launched together, not
compared across sessions started hours apart — even with identical
`config_env`/`versions` in the manifest. A manifest match is necessary but not
sufficient evidence of a valid cross-session control. If a new experiment reuses
a game as a "control"/"base" arm that a prior experiment already measured, treat
that prior measurement as informative context, never as ground truth to
replicate — replicate WITHIN the new session (e.g., interleave OFF/base
reps with the treatment reps in the same kernel run, as matched12 already does)
rather than importing a numeric baseline from a different session's server
instance.

## Recovery

Within-session comparisons remain valid even when the cross-session baseline
does not: all arms of a single experiment (base/afirst/rfb/both in out13) ran on
the SAME server instance, so the RELATIVE deltas among those arms are trustworthy
A/B evidence — only the ABSOLUTE base-arm numbers can't be checked against a
different session's numbers. Do not conclude "the treatment broke the baseline"
from a cross-session base-arm regression; first confirm turn-by-turn input
equality (prompt/image/legal_actions) as done here — if inputs match exactly
through several turns and only the model's own output diverges, that is
non-determinism, not a treatment or config defect.

## Falsification

This diagnosis would be wrong if: (a) the inputs at the divergence turn were
NOT actually byte-identical (a hidden field difference, e.g. `image_hashes`
plural, tool-availability flags, or a prompt field not checked) — re-verify with
a full-field diff, not just the fields this analysis checked; (b) action counts
turned out to vary ACROSS REPS within the same session (would point to per-call
sampling noise rather than a fixed cross-session server difference); (c) server
logs (not available for this analysis) showed the vLLM process was never
restarted between sessions, which would remove the "different process" causal
story and require a different explanation for the observed output drift.

## Related

- [[../rounds/r55_code-repl-agent]] — the round page recording the engagement
  experiment's within-session A/B verdict and this cross-session finding.
- Project memory `feedback_measurement_discipline` (not a wiki page — dev-time
  cross-session convention) already requires matched-arm reruns to be logged as
  one live SUMMARY per session; this finding sharpens that to a mechanism: two
  sessions of a "matched" experiment are not comparable AT ALL for absolute
  counts once the server process differs, only within-session deltas are.
