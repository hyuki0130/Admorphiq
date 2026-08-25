---
type: lesson
keywords: [kaggle, submission, build, dataset, dir-mode, guard, provenance, diagnose-by-reading]
date: 2026-08-26
verdict: Four defects in one 40-line build script, all found by pushing the KERNEL ONLY. Three were checks that looked like they verified something and did not; the fourth was a flag I "cleaned up" by pattern instead of reading what it does.
---

# Four defects in one build script, and why pushing the kernel alone found them

The submission build was committed for the first time (the 0.20 card's never was —
[[submission_not_reproducible_20260825]]). Pushing the KERNEL without consuming a submission slot
turned up four defects, each invisible locally.

## 1. A wait that guarded nothing

```bash
if uv run kaggle datasets files jaehyukhyun/admorphiq-src | grep -q 'admorphiq'; then break; fi
```

Every previous dataset version also contains the string "admorphiq", so the loop passed on its
first attempt. The guard existed because this campaign had twice pushed a kernel against a stale
dataset — and it did not prevent that at all.

## 2. `--dir-mode zip` blamed for a failure it did not cause

The kernel died on `ModuleNotFoundError: No module named 'admorphiq'`. The notebook walks
`/kaggle/input` for a directory NAMED `admorphiq` holding `__init__.py`, so "the package arrived as
a zip" was a plausible story, and I dropped the flag.

## 3. The default `dir-mode` is **skip**

```
--dir-mode {skip,zip,tar}   "skip" - ignore
```

⛔ Dropping the flag did not preserve the tree — it **dropped the package entirely**. The dataset
then held `COMMIT.txt` and nothing else, and the kernel failed on an EMPTY mount: a worse failure
than the one being fixed.

`zip` was right all along, and the notebook's own path list said why:

```python
"/kaggle/input/admorphiq-src",  # CLI dataset (zip strips src/)
```

Kaggle EXTRACTS the archive and strips its top level, so staging the package under `src/` makes it
arrive as `admorphiq/`. One line of the CLI's `--help`, or one comment already in the repository,
would have settled it before the experiment.

## 4. `--quiet` still prints to stdout

```
stamp='Dataset URL: https://www.kaggle.com/...
License(s): unknown
f973bc5'
```

The capture redirected only stderr, so the stamp could never equal the commit and the fixed guard
would have spun its full 30 minutes and then refused to push — on a dataset that was already serving
the right version.

## What the four have in common

Three of them are **checks that look like they verify something and do not** — the same shape as the
instrument failures in [[instrument_validity_20260825]], now in the deployment path rather than the
measurement one. The fourth is the opposite mistake and the more expensive: **diagnosing by pattern
instead of by reading what the tool does.** The flag's own `--help` and a comment already in the
notebook both held the answer.

## The rules

1. **Push the kernel alone first.** Every one of these surfaced at zero cost, without consuming a
   daily submission slot. A local run cannot find them: they live in the dataset mount and the
   server's Python path.
2. **A guard must be tested against the state it rejects.** Run it once when it SHOULD fail. All
   three broken checks would have died instantly under that test.
3. **Read the tool before rewriting the call.** `--help` is cheaper than a push cycle, and cheaper
   still than a "fix" that makes the failure worse.

Related: [[submission_not_reproducible_20260825]], [[instrument_validity_20260825]],
[[../rounds/r99_detection-dispatch]].
