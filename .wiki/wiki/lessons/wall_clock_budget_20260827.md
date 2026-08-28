---
type: lesson
topic: measurement-integrity
date: 2026-08-27
keywords: [wall-clock, search-budget, reproducibility, cross-machine, blastclock, determinism, r101]
---

# A tool that budgets by wall clock scores differently on every machine

⛔ **THE CAUSAL CLAIM BELOW IS WITHDRAWN (2026-08-28). The symptom is real and reproduces; the
cause named here was never measured — see "The retraction" at the foot of the page. The general
rule (budget by work, not by time) still holds as a rule; it is not what produced these numbers.**

> ka59 measured **1.0000 on the laptop and 0.7500 on ceph-build** from byte-identical code, the
> same engine, the same numpy and the same game file. The cause was one line: the tool's search
> stops at `time.monotonic() + limit`, so a slower or busier machine gets a worse plan.

## Symptom

```
                       blastclock.py     ka59
laptop  (frozen copy)  d33922ec2452      1.0000   7/7   294 actions
ceph-build             d33922ec2452      0.7500   6/7   700 actions
```

Every tool and harness file hashed identical between the two trees. `arcengine 0.9.3`,
`arc-agi 0.9.6`, `numpy 2.4.4` on both. `ka59.py` identical. **Each machine was internally
deterministic** — five runs on one, three on the other, same answer every time — which is what
made it look like a code difference rather than a timing one.

The elimination order that got there, each step ruling out a real candidate:

1. **stale tree** — real, and it mattered elsewhere (+0.1631 on s5i5), but the hashes matched here;
2. **the LLM path** — ollama was up on the laptop and absent on the box. Unplugged with
   `HARNESS_HOST=http://127.0.0.1:9`, the laptop still scored **1.0000**;
3. **engine / numpy / game data** — identical;
4. **`PYTHONHASHSEED`** — 1.0000 at seeds 0 and 1;
5. **the tool's own clock** — `stop = time.monotonic() + limit`, checked every 2048 pops.

## Why this is worse than an ordinary bug

⛔ **It makes the score a property of the machine, not of the agent.** The card is measured on
ceph-build and the competition runs on Kaggle hardware, so a wall-clock-budgeted tool will produce
a third number there — and nothing in the repository would show why. It also makes a *parallel*
run differ from a *serial* one: the full-25 runs 20 games at once, so every wall-clock tool gets
less real CPU exactly when the round is being measured.

⚠️ And it defeats repetition, which is the usual defence. Repeating on one machine returns the
same answer because that machine's speed is stable. **Determinism within a machine is not
reproducibility**, and it reads exactly like it.

## The fix

**Budget by work done, not by time elapsed** — nodes expanded, states popped, candidates tested.
Those are properties of the search and they travel. `blastclock` already counts `popped`; the
clock check rides alongside a counter that would serve on its own.

Present in `blastclock` (8 uses), `spill`, `sluice`, `slotlaunch`. ⚠️ The harness's own
`_GAME_SECONDS` cap in `loop.py:219` is the same hazard one level up; it exists to stop a game
hanging, and it should be justified as a hang-stopper rather than relied on as a bound — if it
ever fires during a scored run, that run's number is machine-dependent too.

## Falsification

Run the same frozen tree on two machines of different speed, or the same machine at
`PAR=1` and `PAR=20`. If a game's score moves, a wall-clock budget is deciding it. If every score
holds, this lesson does not apply to that tool.

## Related

- [[instrument_validity_20260825]] — the fifth entry there is the tree-divergence half of the same
  investigation; this is what remained after the trees were made identical.
- [[../concepts/guard_about_the_model]] — a guard whose answer depends on something other than the
  board.
- [[../rounds/r101_tool-development]] — the round.


## The retraction (2026-08-28)

**None of the clock bounds this page blames actually fire.** With the searches instrumented to
report at every exit, ka59 was run on both machines:

* `stop = time.monotonic() + limit` in `plan_blast` / `plan_stage` — **never reached**, on either
  machine. The node cap (`_NODE_CAP = 400_000`) is not reached either; every search finds its
  answer first;
* the cumulative `_PLAN_BUDGET = 600.0` guard (`left <= 0.5 -> return None`) — **never refuses**,
  on either machine;
* the tool CHOICE is identical: `[harness] step=0 pick=blastclock` with a byte-identical
  signature line on both.

So the divergence is inside `blastclock` and none of its time bounds explain it. **The cause is
still unknown.** What is measured and stands: the same file hash scores 1.0000 here and 0.7500 on
ceph-build, deterministically on each side.

⚠️ **And the first two rounds of that instrumentation were themselves invalid, which is the part
worth carrying.** The instrumented copy was placed on a path and selected with `PYTHONPATH` —
but `scripts/score_efficiency.py:35` does `sys.path.insert(0, <its own repo>/src)`, which wins.
Both "the clock never fires on ceph" readings were therefore readings of ceph's *uninstrumented*
code. It was caught only by adding an unconditional `INSTR-ATTACHED` marker and noticing it never
printed — the check that [[instrument_validity_20260825]] already prescribes and that had not been
applied here.

⛔ **The same defect was in `scripts/measure_frozen.sh`, written the day before to prevent exactly
this.** It set `PYTHONPATH` at a snapshot and ran the LIVE runner, so it printed a snapshot
fingerprint beside a number measured from the live tree. It had been "validated" by importing
`admorphiq` under `PYTHONPATH` rather than by running the runner: **the mechanism was tested and
the path the tool actually uses was not.** Fixed by snapshotting `scripts/` too and running the
snapshot's own runner, and re-validated through the real runner in both directions.

**So this page's own conclusion was reached with an unattached instrument, and the tool built to
stop that was unattached in the same way.** The rule that survives is not about clocks: **prove
the instrument is attached before reading it, by making it say something it could not say if it
were not.**

## What it actually was (2026-08-28, measured)

A 2×2, each cell run through the snapshot's own runner so the code is named rather than assumed:

```
blastclock.py            this machine        ceph-build
d33922ec (git HEAD)      1.0000 / 294 a      0.7500 / 700 a    <-- diverges
393762f2 (uncommitted)   1.0000 / 290 a      1.0000 / 290 a    <-- portable
```

**The cross-machine divergence exists only in the committed version, and an UNCOMMITTED edit
removes it.** The same file that had been reported as a regression and nearly reverted is the one
that makes ka59 machine-independent — same 290 actions, same answer, both machines.

⛔ So the day's headline was backwards twice over: the tool was not budgeting by wall clock in any
path that fires, and the "regression" was the fix.

### The three instrument failures crossed to get here, all one shape

1. **`PYTHONPATH` does not select the code the runner runs.** `scripts/score_efficiency.py:35`
   does `sys.path.insert(0, <its own repo>/src)`, which precedes it. Two readings of "the clock
   never fires on ceph" were readings of ceph's **uninstrumented** code. Caught only by an
   unconditional `INSTR-ATTACHED` marker that never printed.
2. **`measure_frozen.sh` carried the identical defect** — written the day before to prevent exactly
   this, "validated" by importing `admorphiq` under `PYTHONPATH` instead of by running the runner.
   It printed snapshot fingerprints beside live-tree numbers. Fixed by snapshotting `scripts/` too
   and running the snapshot's own runner.
3. **A file-list diff without `LC_ALL=C`** buried the one real difference under dozens of ordering
   artefacts — a trap already written down in `CLAUDE.md`. With the locale fixed, the entire
   difference between the two trees was **one file**.

**The rule that survives is not about clocks.** It is: *prove the instrument is attached before
reading it, by making it say something it could not say if it were not* — and, for a comparison,
*name the code by hash on both sides before attributing anything to the machine.*
