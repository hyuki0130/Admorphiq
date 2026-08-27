---
type: round
round: R101-LLM
axis: runtime-model routing
date: 2026-08-27
keywords: [llm, kaggle, gpu, vllm, gemma4, routing, fallback, tool-selection, r101]
verdict: "CLOSED — the model first routed 24 of 25 games identically to the LLM-free fallback and lost cn04 (0.6333 vs 0.6733). Cause found in the PROMPT, not the model: a 0.60 claim threshold the fallback does not have. After the fix, kernel v3 measures 25 of 25 IDENTICAL, ZERO routing losses, 0.7288 both, and the LLM arm fell from 2817s to 228s."
---

# R101-LLM — the shipped path, measured on a GPU for the first time

> Every generic-path number in R101 came from the LLM-FREE fallback. The path that actually
> ships asks a model to name the tool, and on all 25 games it agrees with the fallback 24
> times, disagrees once, and is wrong the one time it disagrees.

## Why it had never been measured

`harness/loop.py` drops to signature routing whenever the llm call raises, and the ceph round
runners set no model — so the fallback is what every round measured. ceph-build has no GPU and
one 26B model on its shared CPUs takes about 37 cores, so the real path stayed unmeasured for
the whole round.

## How

`notebooks/r101_llm_full25.py`, pushed as a Kaggle GPU kernel (`kaggle_bench/`). vLLM serves
gemma4-31b-it offline from a mounted Kaggle Model; the 25 games and the official framework come
from the competition mount; both arms run through the SAME `score_efficiency` subprocess and
differ in exactly one thing — whether `HARNESS_LLM_MODEL` names a served model.

⛔ This is a kernel run, not a submission. `kaggle kernels push` does not consume the daily
slot, and the standing directive is that nothing is submitted until the sample games clear.
`kaggle_bench/build_and_run.sh` has no `--submit` path at all.

## Result

```
              llm     fallback
mean       0.6333       0.6733     over 25 games
wall-clock   2817s         157s     18x
routing losses: 1   —  CN04  1.0000 -> 0.0000
```

**Twenty-four of twenty-five games score IDENTICALLY.** The entire difference is cn04, where
the model picks a tool that scores zero over one that scores 1.0000. The arithmetic closes
exactly: 0.6733 - 1.0/25 = 0.6333.

The fallback arm returned **0.6733**, equal to the ceph-build baseline to four decimals on a
different machine, a different OS and a different Python build. That cross-machine agreement is
the strongest instrument check this round has had.

## What it means

The model is not adding routing skill on this set — the signature default already picks what it
would pick, 24 times out of 25 — and it is subtracting one game. That is a much narrower gap
than "the LLM path is unmeasured and might be anything", and it makes the work concrete:
**one board, one wrong pick.**

⛔ It does NOT mean the model is useless for the hidden 110. The signature fallback is tuned by
us against these 25; a game whose signature we have never seen has no tuned default to fall
back on, which is the case the model exists for. What this measures is that on boards where
the fallback is already right, the model does not improve on it and can break it.

## Closed by kernel v3 (same day)

The cause was in the PROMPT, and the kernel log said so rather than any inference of mine: on
cn04 the model picked `code` at step 0 and `graph` at step 11. It was obeying the instruction.
cn04's two best fits are 0.45 (tied), the CLAIMS line only fires at 0.60, so the model was shown
no claim — and the text then licensed both the general searcher and writing code. The fallback
has no 0.60 threshold anywhere, so the two paths could only ever diverge in the band
0 < fit < 0.60, and that is exactly where they did. The threshold also contradicted this repo's
own rule that a tool with no plan must bid ZERO: under that rule the line sits at zero, not 0.60.

Two changes, prompt-side only, so the LLM-free path is untouched:

* **a partial claim is still a claim** — a PARTIAL CLAIM line now names the highest fit when
  nothing reaches 0.60, and the general searcher and code are reserved for boards where EVERY
  fit is 0.00 (measured: no board of the 25 is in that state);
* **ties break by registration order, not the alphabet** — see [[../concepts/tool_claim_breadth]].

```
kernel v3        llm      fallback
mean          0.7288       0.7288      25 of 25 IDENTICAL
routing losses    0
wall-clock     228s          151s      was 2817s vs 157s
```

The 18x wall-clock gap collapsed to 1.5x as a side effect: the model no longer takes the code
branch, which was where the time went.

⛔ Equal is the CEILING of this measurement, not a success criterion for the model. On these 25
the signature default is already right everywhere, so parity is the best any router can do here.
The question this cannot answer is whether the model helps on a board whose signature we have
never tuned against — which is the entire private set.

## Open work

- Find what the model picks on cn04 and why. The prompt already lists tools RANKED by their own
  `detect` with a `CLAIMS THIS BOARD` line, and the instruction to follow that line is binding
  — so cn04 is either a board where nothing claims it, or one where the model overrides a claim.
- The 18x wall-clock matters at 110 games inside a 9-hour cap; measure how many LLM calls a game
  actually issues before treating it as a cost of doing business.

## Related

- [[r101_tool-development]] — the round whose fallback numbers this is the counterpart to.
- [[../lessons/llm_path_anchor_bias_20260827]] — the three hardcoded layers that had to come off
  before the model could name the right tool at all.
- [[../lessons/wrong_env_var_name_20260827]] — the first GPU run scored 0/0 games and looked healthy.
