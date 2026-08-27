---
type: lesson
topic: measurement-integrity
date: 2026-08-27
keywords: [environments-dir, kaggle, gpu, zero-games, silent-success, instrument-validity, r101, r98]
---

# A recorded fix that names the wrong variable costs the same as no fix

> A GPU session booted a healthy model server, scored 0.00% over ZERO games in two
> seconds, and printed nothing that looks like a failure — because the variable our own
> record names as the fix is read by no code in this repository.

## Symptom

A run — typically on Kaggle, where the working directory is not the repository — reports:

```
Scoring 0 game(s) with agent 'unified' …
Total score: 0.0000 (0.00%)  [0/0 games scored, 0 excluded]
```

Everything upstream looks correct and *is* correct: the model server is healthy, a
preflight request returns 200, the environment directory is found and its 25 entries are
counted and printed. The arms complete in seconds. A mean over the results is `0.0000`,
which is indistinguishable from an agent that genuinely solved nothing.

## Root cause

`arc_agi`'s `Arcade` resolves its environments directory as **constructor arg > the
`ENVIRONMENTS_DIR` environment variable > the cwd-relative default `environment_files`**.

`scripts/score_efficiency.py` builds `Arcade(operation_mode=OFFLINE)` with no directory
argument, so it depends entirely on `ENVIRONMENTS_DIR` or on being run from the repository
root.

`ARC_ENVIRONMENTS_DIR` is a **different variable with a different owner**: it is a
convention of the R97/R98 probe scripts, each of which reads it *itself* and then passes
`environments_dir=` to the `Arcade` explicitly. Nothing inside `arc_agi` or `arcengine`
reads that name. Setting it for a runner that does not read it either has no effect at all.

The trap fired twice because it was written down wrong. The record in `CLAUDE.md` listed
"ARC_ENVIRONMENTS_DIR unread" among the permanently-fixed operational traps — true for the
probes that motivated the entry, false for every other entry point, and stated generally.
The second session dutifully set the name the record gave and got the identical failure.

## Prevention

- **Set `ENVIRONMENTS_DIR`.** Set `ARC_ENVIRONMENTS_DIR` too if probe scripts are in the
  path; they are not alternatives and one does not imply the other.
- **Set `RECORDINGS_DIR` to a writable path** whenever the environments live on a read-only
  mount.
- **A zero-game run must RAISE, not report.** `0/0 games scored` is not a measurement. Any
  harness that aggregates arm results should refuse to accept an arm with an empty `games`
  list, because that value averages into a verdict and looks like a score.
- **When recording a fix, record the identifier the CONSUMER reads**, not the one the
  calling script happened to use. The two differ exactly when a wrapper does the reading,
  which is the case that makes the bug subtle enough to be worth writing down.

## Recovery

Reproduce it locally in one command — run the runner from a foreign working directory:

```
cd /tmp && uv run --project <repo> python <repo>/scripts/score_efficiency.py \
    --agent unified --titles vc33 --max-actions 300 --out a.json
```

Unset it scores 0 games. With `ENVIRONMENTS_DIR=<repo>/environment_files` the same command
scores `1.0000` on the same game in 199 actions. Both directions were measured before the
kernel was pushed again.

## Falsification

This lesson is wrong if `grep -rn ENVIRONMENTS_DIR` inside the installed `arc_agi` package
stops showing `os.getenv("ENVIRONMENTS_DIR", ...)` in `base.py`, or if
`score_efficiency.py` starts passing `environments_dir=` explicitly — in which case the
runner no longer depends on the variable and the failure mode disappears.

## Related

- [[instrument_validity_20260825]] — the general rule this is an instance of: a field means
  what it RECORDS, not what its name suggests, and a checker is an instrument too.
- [[../rounds/r101_tool-development]] — the round whose LLM-on-GPU measurement this blocked.
- [[../rounds/r98_flow-deflection]] — where the mis-stated trap was first recorded.
