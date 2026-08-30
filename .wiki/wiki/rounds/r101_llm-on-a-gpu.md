---
round: R101LLMGPU
axis: does an offline model in the loop change anything at 0.9082 — measured on a real GPU, two arms, with controls proving the model was actually there
keywords: [llm, gpu, vllm, gemma4, target-draw, routing, signature-routing, kaggle-kernel, two-arm, controls, attribution, measured-inert, axis-closed]
verdict: MEASURED INERT ON THESE 25 — arm_llm 0.908187, arm_fallback 0.908187, ZERO games differing, with four independent controls proving the model served 38 completions, drew targets successfully for the first time in the campaign, and cost 104 seconds of real work. ⚠️ NOT a verdict on the LLM for the private 110, which is the case these games cannot express.
commit: b307e315
supersedes: the open statement of the axis in rule 7ca
---

# R101 — the LLM on a real GPU

> Rule 7ca found that the harness's LLM had never once been in the loop — 404 on ceph-build for an
> unpulled model name, connection refused on Kaggle — so every number this campaign has produced was
> an LLM-free number and nobody knew what a working one would do. This is the run that found out.

## Why it had never been measured, and the mistake that preceded it

The axis was invisible because the failure was silent: `loop.py:666` calls `self.draw_llm(...)` and
catches every exception, so a harness with no model behaves exactly like a harness whose model is
never useful. The two are indistinguishable from the score.

⛔ **And when I did open the axis, I measured it in the wrong place** (rule 7cc): I taught the gate
to forward `HARNESS_MODEL` and ran it on ceph-build, where `CLAUDE.md` and `registry.py`'s own
comment both already record that one 26B model takes ~37 cores. ollama hit **3665% CPU** and the
shared box reached **load 110 against a 60-core cap**. `OLLAMA_NUM_THREAD` could not restrain it —
the client puts it in the request's `options.num_thread` and the server had already spawned its
runner. **A cap that lives in the caller cannot bound a process the callee already started.**

⭐ **The instrument for this question already existed and I did not look for it** —
`kaggle_bench/build_and_run.sh` + `kaggle_bench/r101_llm_full25.py` boot vLLM offline from mounted
wheels on a Kaggle GPU kernel, and run all 25 games in two arms differing in one thing only. It costs
**no submission slot**. That is rule 7b's shape applied to instruments instead of assets: sweep for
the runner that already exists before building the measurement by hand.

## The measurement

```
=== arm llm (model=gemma4) ===         total 0.908187   over 25 games   382s
=== arm fallback (model=NONE) ===      total 0.908187   over 25 games   278s
games differing:                       ZERO
kernel fallback arm vs the repo card:  ZERO differing — it reproduces R101SHIPPED exactly
```

## The controls are the result

A "no difference" between two arms is worth nothing if both arms were LLM-free — the
fail-toward-nothing shape this campaign has caught nine instruments in. Four independent checks, and
the number was not accepted until all four agreed:

```
vLLM served                     38 x "POST /v1/chat/completions HTTP/1.1" 200 OK
target-draw FAILURES by arm     fallback 3 · llm ZERO      <- the draw SUCCEEDED, first time ever
harness re-decide picks by arm  llm 34 · fallback 34       <- both arms decided equally often
wall clock                      382s vs 278s              <- the model cost 104 SECONDS of real work
```

⛔ **So the model ran, answered, drew targets, and changed nothing** — not one game, not one action.
It also amends rule 7ca's headline: the target draw HAS now succeeded, and the result was identical
anyway. The 404-and-refused finding stands as the explanation of why nobody had ever seen it work.

## The attribution step, which reversed the first reading

⚠️ My first pass through the log said the draw had failed here too — three `Connection refused`
lines, exactly the 7ca signature. Splitting them by arm banner took one pass and reversed it:
**all three belong to the fallback arm, which has no model and is supposed to fail.** ⛔ A count that
spans two arms describes neither (rule 7aj). Had it gone unchecked, this round would have concluded
"the LLM still never runs" — the opposite of what happened.

## What this does NOT say

⛔ It does not say an offline model is useless for ARC-AGI-3. It says that **on these 25 games there
is nothing left for a model to add**: nineteen sit at the 1.0 cap and the signature router already
picks a tool that clears. The private 110 are the case where signature routing has **no tool that
fits**, and this measurement cannot see that case at all.

⚠️ Same caveat shape as [[r101_inert-actions]]'s: a class measured at ~zero on a corpus where
nineteen games are already perfect has been measured on the wrong corpus, not measured away. The
honest reading is **"the 25 cannot measure the LLM"**, and the ablation arm — removing the tool that
actually plays each game — is the closest thing to the case that could.

## Related

[[r101_shipped-and-transfer]] · [[r101_inert-actions]] · [[r101_tenure-end]] · [[r101_discarded-band]]
