---
type: lesson
topic: measurement-integrity
date: 2026-08-27
keywords: [wall-clock, search-budget, reproducibility, cross-machine, blastclock, determinism, r101]
---

# A tool that budgets by wall clock scores differently on every machine

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
