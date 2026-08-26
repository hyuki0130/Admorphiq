---
name: project-leaderboard-2026-08-and-method
description: "LB re-checked 2026-08-25: top = 5.99 (cstl), 2nd 4.58 (Tufa), 12th 2.66 — the old '1.38-1.61 top band' is STALE by 4x. Ours 0.20. Goal: clear all games + chase within August. Measurement method = ceph-build 64c, ALL 25 games in parallel."
metadata:
  type: project
---

**Leaderboard, measured 2026-08-25** (`kaggle competitions leaderboard arc-prize-2026-arc-agi-3 -s`):

```
1  cstl            5.99      <- the target
2  Tufa Labs       4.58
3  Lord Han Solo   3.36
4  Tony G          3.17
5  Daniel Franzen  2.88
12 The AGI Boys    2.66      <- realistic first milestone
   Admorphiq       0.20      <- ours, unmoved since 2026-07-13
```

⛔ The band recorded in [[project_leaderboard_first_score]] ("top 1.38-1.61") is **STALE** — that was
2026-07-14. The field rose ~4x in six weeks. Never quote it again without re-checking; the LB is a
moving target and a six-week-old anchor is worse than none.

⚠️ **It moves DAILY, not weekly.** Re-checked 2026-08-26 09:03, seventeen hours after the table
above:

```
1  cstl           5.99  (unchanged)
2  Lord Han Solo  4.99  (was 3.36 — up 48% in one day)
3  Tufa Labs      4.67  (was 4.58)
4  Tong Hui Kang  3.39  (new to the top four)
```

Field size 2,533 teams, against 1,424 recorded in June (+78%). So a leaderboard figure is stale
within a DAY, and any target derived from one has to be re-read at the moment it is used.

**User goal (2026-08-25):** clear ALL games and chase the top band **within August**.

**Card as of 2026-08-25 evening — DETECTION DISPATCH, measured full-25 on ceph-build:**

```
previous card (--agent chained)    0.0566
detection dispatch (SHIPPED)       0.2772     4.9x, zero regressions
adapter ceiling                    0.3296
```

Nine adapters (ft09 ls20 m0r0 r11l re86 sb26 sk48 su15 tr87) now reach the card by recognising
their mechanic FROM THE FRAME instead of by `game_id`, so they can run on games whose id we have
never seen. Every port lands EXACTLY on its ceiling, and the shipped configuration scores what the
benched one does game for game (`scripts/benched_vs_shipped.py`, 0 differences).

⛔ **A detector ships only at a MEASURED 0/24 false positives** (`scripts/detector_falsepos.py`) —
the gate refused sb26 at 2/24, predicted an s5i5 regression, and the run produced exactly it. It
protects TRANSFER, not the proxy: on the public 25 the unsafe detector was strongly net-positive.

⚠️ Measure with `--agent kaggle_detect` (the shipped build), not `--agent detect` (the bench), and
include `ARC-AGI-3-Agents/` when syncing — without it every game errors `No module named 'agents'`
and the run reads 0.0000 like a broken card.

The submission BUILD now ships with the card (`kaggle/build_and_push.sh` + `kernel-metadata.json`);
`--submit` is a flag, never the default. Round page: `.wiki/wiki/rounds/r99_detection-dispatch.md`.

**Submitted 2026-08-25 16:19 UTC** (`55774529`, kernel v3 @ commit 20aa652). Still PENDING five
hours later, which is EXPECTED not stuck: the card burns ~5,920 actions per game, so 110 hidden
games project to ~213 minutes. Reading criteria were fixed BEFORE the score (round page): >0.20 the
ports earn on hidden games; ≈0.20 they never fire there and the card simply falls back (NOT a port
failure); <0.20 a detector fires and does worse than the fallback, the one thing the 0/24 gate
exists to prevent.

⚠️ **Per-game budget cut 100,000 -> 4,000 for the NEXT card** — MEASURED, same score:

```
no cap   25 games 48.4 min  mean 0.2772
cap 4000 25 games  3.3 min  mean 0.2772
cap 2000 25 games  3.0 min  mean 0.2772
```

RHAE squares efficiency, so anything cleared past ~700 actions is already worth ~0. ⛔ But a cap at
500 would destroy 1.0 of REAL score (re86 L7 clears at 588 cumulative actions) — the cliff had to be
located, not guessed. 4,000 over 2,000 because it costs sixteen SECONDS. This takes 110 games from
~213 minutes to ~26 and removes the 9-hour risk.

**What the card is MADE of** (measured, `TRUESHIP` at the deployed budget): ports 5.8330 = **84%**
(m0r0/ls20/ft09 1.0000, sb26 0.8460, re86 0.7273, su15 0.4368, tr87 0.2857, sk48 0.2778, r11l
0.2594) · probe 1.0972 = 16% (cd82 0.9463 plus six near-zero) · **harness 0.0000 = 0%**. The chain
only hands the harness games its WorldModelAgent probe gave up on, and those are exactly the ones
nobody scores — so three real harness defects found this session (deadsig inert on 5 of 8, stall
re-decision unreachable at ANY threshold, `toggle` 20x faster than `graph` on vc33) are all worth
~0 on this card. The remaining fifteen games together produce **0.1509**; that is all the headroom
there is.

⛔ **RUNTIME RISK on the submitted card.** Submission `55774529` is kernel v3 @ 20aa652, which
PREDATES the budget cut and runs `MAX_ACTIONS = 100,000`. At the measured 51 actions/sec, 110 games
project to 59.9 hours worst case. It passed 10 hours still PENDING. ⚠️ The 9-hour limit recorded in
CLAUDE.md is itself unverified for a CPU kernel — no way to check offline. `tests/test_adapter_
detection.py` now rejects any budget whose worst case exceeds the limit, and it rejects the one
that was submitted.

⚠️ Two traps this cost a tick each, both invisible locally: `os.environ.setdefault` means a runner
exporting `GF_GIVEUP` silently measures a DIFFERENT configuration than ships (now refused by
`--agent kaggle_detect`), and `MAX_ACTIONS` is per-game only because the notebook builds a fresh
agent per game — `score_efficiency.py` never touches that counter, so a run-total counter would have
appeared for the first time in a submission.

**Measurement method — MANDATORY from now on (user directive 2026-08-25):**
run every game **in parallel on ceph-build**, not serially on the Mac.

```
# sync the current tree (ceph-build's copy goes stale; it is BEHIND, never ahead)
tar czf /tmp/admorphiq_sync.tgz --exclude=.venv --exclude=.git --exclude='__pycache__' \
    src scripts tests notebooks pyproject.toml uv.lock environment_files
scp -i ~/VM/keys/nfw-dev.pem /tmp/admorphiq_sync.tgz ubuntu@ceph-build:~/
ssh -i ~/VM/keys/nfw-dev.pem ubuntu@ceph-build \
   'export PATH=$HOME/.local/bin:$PATH; cd ~/admorphiq && tar xzf ~/admorphiq_sync.tgz && uv sync -q'
# then launch ALL 25 at once (64 cores) with nohup + a LIVE SUMMARY
```

Notes that cost time when forgotten: `uv` is at `~/.local/bin` and is NOT on the default PATH over
ssh; ceph-build's `~/admorphiq` is a tarball extract, **not a git repo**; its `._*` files are macOS
tar artefacts, and comparing file lists across the two machines needs `LC_ALL=C sort` or the diff
is nonsense.

Related: [[project_cpu_dev_vm_ceph_build]], [[feedback_measurement_discipline]],
[[project_submission_not_reproducible]].


## Ports 10 and 11 (2026-08-26) — and the rule that unlocked them

**A park recorded against ONE FEATURE is not a park against the mechanic.** Both of these were
parked and both came free once the mechanic's own CONJUNCTION was measured instead of a threshold:

* **lp85 0.0022 -> 0.6992** — parked because no button-COUNT threshold separates it (3) from ft09
  (12) and s5i5 (2). True, and one feature. Its adapter already carried the conjunction:
  click-only AND >=1 control AND >=1 mover AND per colour class #movers == #destinations. The last
  term is the pair rule, and it makes detection and solvability the same question.
  ⛔ Measured negative: lp85 was the ONLY adapter carrying its own solvability predicate; the other
  fourteen have no `_detect`, so each conjunction must be written by hand.
* **sp80 0.0000 -> 0.1429** — the flow family R98 modelled. Its rule: satisfaction runs through a
  NOTCH, and the grounding already treats a region without one as an obstacle. Control scheme
  narrows to four (sp80 m0r0 cd82 cn04); read IN CELLS, sp80 has 2 notched regions and the rest 0.
  ⚠️ Reading in cells is load-bearing — the scale-free version of the same test fires on all four
  and separates nothing. **The loosening that looks like generalisation destroys the
  discrimination.** R98's modelling reached the card here for the first time.

Card ladder: 0.0566 -> 0.2772 (9 ports) -> 0.3051 (+lp85) -> 0.3108 (+sp80). Every port lands on
its adapter ceiling exactly, and each full-25 moves exactly the one game.

⛔ **A guard that fails OPEN reports success while protecting nothing.** The full-25 runner threw
`wait -n` at bash 3.2 (what macOS ships), where it is an invalid option, so the concurrency throttle
never blocked and all 25 games launched at once. Throttle with `xargs -P`; skip games that already
have a result so a killed run resumes.
## ⛔ The card is a PROXY and it is not tracking the score (2026-08-26)

```
card 0.0566 -> 0.3162   (5.6x, thirteen ports)
hidden       0.20 -> 0.18
```

Calibration point: card 0.2772 -> hidden 0.18 (ratio ~0.65), so 0.3162 lands near 0.205 — back to
v3. **A 5.6x proxy gain bought ~nothing on the leaderboard.** The 25 public games are dev-only; eval
is 110 PRIVATE games, and a ported adapter fires only when its mechanic is visible in the frame.

The ports' transfer evidence (7/7 archived hashes gain) is transfer across a re-render of the SAME
game — much weaker than transfer to a different one.

Remaining ports are worth +0.0134 card / ~+0.009 hidden. Multiplying the score needs a GENERAL agent
learning an unseen game at test time. Top 5.99, 12th 2.66, ours ~0.2 — 13x to 30x away, so catching
the top band inside August is NOT achievable; say so rather than encourage.

**Method note**: measurements belong on ceph-build (64 cores, 25 games in parallel), synced by
TARBALL — `~/admorphiq` there is not a git repo. Running full-25 locally choked the Mac and killed a
runner mid-round.

## Cheap levers CLOSED, and a wrong dispatch now bails (2026-08-26)

Measured in parallel on ceph-build, and all three are negatives worth not re-testing:

```
budget 4,000 -> 30,000  (public 25)    0.3162 = 0.3162, no game gains a level
budget 4,000 -> 100,000 (HIDDEN 110)   0.18   = 0.18
give-up 4,000 -> 100,000 (25x)         0 of 21 games change anything
```

Adapters that stop short cannot go further; they were never being cut off. Depth needs new
capability, not more budget or patience.

Hidden score says v3 (no dispatch) 0.20 vs dispatch 0.18. On the public 25 dispatch is better on 13
games and worse on none, so the -0.02 comes from PRIVATE games where a detector fires and its adapter
does worse than the generic fallback would have. The 0/24 gate only covers boards we can see.

Fix shipped: `DetectDispatchAgent` bails to the fallback after 1,000 actions with nothing cleared.
Threshold measured (slowest dispatched public first clear = sc25 461, all others <= 25; archived
re-renders identical 7/7, so a re-render costs nothing in time-to-first-clear). Verified no-op on the
public 25 (0.3162, 0 games differ).

## The generic path's loss is DEPTH, not efficiency (2026-08-26)

Generic path (plays every game no adapter claims — most of the private 110), all 25 games:

```
17/25 clear at least one level.  Mean 0.0566.
Level-1 actions vs human: MEDIAN 1.3x. Ten of seventeen <= 1.5x, seven scoring a perfect 1.0.
```

Near-human on level 1, then STOPS. ls20: L1 score 0.9149, game score 0.0327 — one level of seven is
1/(1+2+...+7) of the weight. Efficiency is a minority problem (6 games, lf52 11.8x .. vc33 522x).

**Target for an unseen game is level 2/3/4, not a faster level 1.** This is also what the thirteen
adapters bought — depth (ft09 6 vs 1, ls20 7 vs 1, m0r0 6 vs 1) — and why the public card multiplied
while hidden did not: private games mostly get the generic path, which reaches level 1 and stops.

⚠️ I got this WRONG first by reading total action counts and concluding "exhaustive search". Most of
those actions are spent AFTER the first clear, failing level 2. Before a measurement becomes a
direction, look at the breakdown that would refute it.
