# Operating rules — read FIRST, every session

⛔ These are the rules that have actually been broken, each one more than once, each one after being
stated. They live here because a rule that exists only in a chat message or in machine-local memory is
a rule that dies at the next context compaction or the next machine.

## 1. ceph-build runs at MAXIMUM parallelism, capped at 60 cores

⛔ **ceph-build is SHARED, and the load average is NOT all yours.** Measured 2026-08-27 while
chasing a load of 96: the top consumers were an `ollama runner` at 3743% CPU (my own 26B model)
AND a `freqtrade` process 91 days old, postgres, rabbitmq and docker/runc — other people's
workloads. Read `ps -eo pid,etimes,pcpu,args --sort=-pcpu | head` before concluding the load is
yours, and set the parallelism against the load you FIND, not against 64 cores.

⛔ **Do not run LLM inference here.** There is no GPU, and one 26B model on CPU takes ~37 cores by
itself — more than half the cap, for one process. LLM-in-the-loop verification belongs on a GPU
(Kaggle's free quota, or GCP with the user's awareness that it now costs money). See rule 5.

⛔ **`pkill -f <pattern>` matches YOUR OWN ssh command line.** Killing a run by a pattern that
appears in the command that issues the kill silently kills the kill. Put the kill in a script file
on the box, or split the pattern (`"score_effici""ency.py"`).

The box has 64. Saturating them locks out SSH; leave 4 for the shell. **The cap is not a target to
approach cautiously — it is a ceiling to work up against.** An idle measurement box is wasted time,
and this has been said on 2026-08-26 morning, again that afternoon, and again that evening.

⛔ **THE CAP IS LOAD AVERAGE, NOT JOB COUNT — and I got this wrong within an hour of writing it.**
`xargs -P 55` bounds concurrent JOBS. Each job here is `uv run python ...`, which is a wrapper plus a
python process, so 55 slots produced 80 python processes and a load average of **60.97 — over the
cap**. The rule as first written said "use `xargs -P 55`", which is exactly what overshot.

Clamped in `scripts/rounds/R99CARD/run.sh` and every runner copied from it. For ad-hoc sweeps start at
**`-P 30`** and MEASURE: `uptime` a minute after launch, then again — the 1-minute average lags, so a
reading of 40 while jobs are still starting means it is heading past 60. Raise only if the settled
load sits well under 60. SSH answering is necessary but not sufficient: it answered fine at 60.97.

⛔ Never run a full-25 serially on the Mac. It choked the machine and killed a runner at 17 of 25.

## 2. Everything that runs on a box comes BACK into the repo

`~/admorphiq` on ceph-build is a tarball extract — not a git repo, no backup. On 2026-08-26 it held
47 run scripts spanning Jul 19 to Aug 26, six full-25 DETECT rounds, and four diagnostic logs that
existed only in `/tmp` — one of which carried the sharpest finding available. All uncommitted. 208K
in total, so size was never the reason.

Run `scripts/ceph_pull.sh` at the end of any session that touched the box, then commit. **Work that
lives only on that box is work that does not exist.**

## 3. Memory files do NOT carry continuity — the repo does

Claude Code memory lives at `~/.claude/projects/<slug>/memory/` on ONE machine. Move the project and
it is gone while the code and wiki travel fine. Mirror with `scripts/memory_mirror.sh`; the copy under
`.wiki/wiki/memory/` is the one that matters, and anything load-bearing also belongs in `.wiki/` or
`CLAUDE.md`.

## 4. Read `.wiki/wiki/rounds/index.md` BEFORE choosing a direction

Not after. On 2026-08-26 a full day went into an axis that the index's own R93 entry describes as
superseded by the user's counter-design, and the doctrine conflict was found only when the user asked.
The index is the retrieval mechanism; writing to a round page while never reading the index is
half the discipline.

## 5. Three environments, three jobs

| where | what it is | what it does |
| --- | --- | --- |
| `ceph-build` | 64 cores, NO GPU, tarball sync | parallel game measurement, tool sweeps |
| Kaggle GPU kernels | `notebooks/r9*_bench.py`, vLLM, offline | model stages, two-model rule (run twice) |
| GCP `ewm-bench` | `g4-standard-48`, RTX PRO 6000 96GB, SPOT, ollama with gemma4:31b-it-q8_0 + gpt-oss:120b | Kaggle-identical box; `gcloud compute instances start ewm-bench --zone=asia-east1-a`, STOP when idle; disk persists |

⚠️ GCP credits were recorded exhausted and the instance deleted; the procedure is kept because the
disk-persists property means a restart restores the models. Kaggle GPU kernel pushes do NOT consume a
submission slot — only `kaggle competitions submit` does, one per day, resetting 00:00 UTC.

⛔ Two GPU traps already paid for: `ARC_ENVIRONMENTS_DIR` is UNREAD (a GPU session booted a healthy
server and found zero games), and dataset versions must be verified by FILE SIZE, never by
`datasets status`.

⛔ **NO KAGGLE SUBMISSION UNTIL THE SAMPLE GAMES ARE CLEARED (user directive, 2026-08-27).**
This overrides rule 6 below for now. The daily slot is not to be spent while stage one is
unfinished: the generic tools clear 3 games of 25, the submission's score would not move, and
preparing one costs attention that belongs on the tools. Build tools, measure the full 25, record.
Ask again when the sample set is cleared.

## 6. Use the daily submission slot; use GPU quota when the work needs it

**Standing directive, 2026-08-26**: the Kaggle submission slot is one per day, resetting 00:00 UTC,
and **leaving it unused is waste** — put the best measured candidate in it rather than holding for a
better one. GPU kernel runs are separate: `kaggle kernels push` does NOT consume a submission, only
`kaggle competitions submit` does, so run GPU work whenever weekly quota remains.

⚠️ This supersedes the earlier "never push one unasked" reading. What survives from it: the candidate
must be measured AS SHIPPED (`--agent kaggle_detect`, not `--agent detect`) before it goes, and a
submission whose build is not committed is not reproducible — kernel source, `kernel-metadata.json`,
the push command and the dataset-version-to-commit mapping all go in with it.

⛔ **READ THE GAME'S SOURCE FIRST. It is in `environment_files/` and rule 0 already said so.**
Added 2026-08-27 after a session spent probing sample games as black boxes: twenty measurements on
ONE game, ten of them correcting an earlier reading, while `g50t`'s entire control scheme, its
loss condition and the reason its probes contradicted each other sat in forty lines of its own
`step()`. `uv run python scripts/read_sample_games.py [game...]` prints the action dispatch, the
win predicate and the lose predicate for any of the 25 in seconds. Findings live in
`.wiki/wiki/sample_games_mechanics.md`.

The line: this is DEV-TIME understanding of WHICH MECHANIC to implement. The tools stay
frame-only — a tool that reads internals is an adapter, and the eval is 110 games whose source we
will never see.

## 0. What the project is actually building — read before choosing any axis

⛔ Recorded here because it was lost twice on 2026-08-26 and both times the plan was sitting in the
repo unread (`.wiki/wiki/architecture_self_improving_agent.md`, `.wiki/wiki/memory/project_unified_harness_r53.md`).

**Two stages, in order:**

1. **Strengthen the generic TOOLS until they clear all 25 sample games.** `"Goal: 25/25 generic
   clears"` / `"iterate toward 25/25"` / `"continuation = per-tool strengthening"`. This is done by
   intervening game by game — measure where a tool stops, develop it past that, re-measure.
2. **Then the LLM patches and combines those tools on HIDDEN games, through the harness.** Stage two
   is the only part that generalises, because a game never seen cannot have a tool hand-written for
   it — and it needs stage one as its foundation, since a model patching tools that clear nothing has
   nothing to patch from.

**Current distance to stage one** (measured 2026-08-26, `scripts/rounds/ALTFULL`, every tool forced
alone at budget 3000): twenty of twenty-five games sit at 0 or 1 level under every generic tool.
Fifteen score zero under all of them.

**The working loop, in the order the user set it (2026-08-26):**

```
1. UNDERSTAND each sample game and BUILD the tools — done here, game by game, by me.
   Diagnose why a tool stops (scripts/tool_stall_diag.py names it: states opened,
   transitions taken, whether a goal was ever drawn), then develop past that.
2. PUSH the tools to ceph-build and check IN PARALLEL whether the sample games clear.
   That box is for verification at width, not for authoring.
3. THEN cut the harness down and put it on a Kaggle GPU kernel to measure how much
   of the HIDDEN set it completes.
```

⛔ **Before improving any existing tool, decide whether it is the RIGHT tool.** Added 2026-08-26 after
a measurement made the question unavoidable: `dead_signature` had learned **0 keys after 599 actions
on ft09**, and nothing in the repository calls its `is_dead()` / `live_actions()`. The cause is not a
bug — `loop.py:458` calls `observe` on the ACTIVE tool only, and this harness runs one tool at a time,
while `dead_signature` is the kind of tool that must learn in the BACKGROUND while another works. The
structure and the tool disagree. Wiring it up would make a possibly-wrong tool run better.

So stage 1 begins by reading the sample games and deriving what tools they need, then judging the
current six against that — is one-tool-at-a-time right, is anything missing — and only then writing
code. The order is: understand the games → derive the tool set → judge the existing one → develop.

⛔ Steps 1 and 2 are different activities on different machines and must not be confused: authoring is
local and per-game, verification is parallel and on ceph. Step 3 only starts when step 2 says the
tools carry the sample set.

⛔ **Two things that are NOT the plan**, both of which consumed a day: porting hand-written per-game
adapters into the shipped card (no LLM in that path, and it conflicts with the non-negotiable
dual-scoreboard doctrine), and treating "the tools cannot clear these" as a verdict rather than as
stage one's work list.

⛔ **`registry.py` is the ONE file both the parent and the agents touch, and it must never be
committed from a `git add` that was not preceded by a diff.** Measured 2026-08-27: the `reforge`
commit silently carried an agent's swap of `LedgeTool` for `ShaftTool` — the parent had named
explicit paths, not `git add -A`, and `registry.py` was one of them. The committed tree then
disagreed with every measurement in the round for two hours.

It was caught only because a later `git checkout --` produced a registry with `ledge` missing.
Two cheap habits prevent it:
* `git diff src/admorphiq/harness/registry.py` immediately BEFORE staging it, every time;
* after integrating, `uv run python scripts/harness_probe.py <a game the change should not
  touch>` and check it still reports the number the round measured. bp35 at 3 levels is what
  exposed this one.

The measurements themselves survived — the box had the correct registry, and both rounds
reported bp35 at 3 levels, which is `ledge`'s result and not `shaft`'s. That is luck, not a
safeguard: the box is synced from the same working tree.

## 8. FAN OUT, THEN INTEGRATE — the parallel build protocol (user directive, 2026-08-27)

⛔ **Do not improve tools one at a time.** The user's words: *"언제까지 하나씩 개선할거야? 그러니깐
ceph 인스턴스 최대로 활용을 못하잖아."* Serial tool work leaves a 64-core box idle and spends a
session on one game. It was measured: six or seven iterations went into ONE level of ONE game
before the full-25 run revealed the change was a net loss.

**The protocol, in order.**

1. **FAN OUT.** One background agent per GAME, launched together in a single message so they run
   concurrently. Each agent owns exactly two NEW files — `src/admorphiq/tools/<name>.py` and
   `scripts/<name>_probe.py` — and is forbidden to touch `registry.py`, `loop.py`, `segment.py` or
   another agent's tool. That ownership rule is what makes the fan-out conflict-free; without it
   the merges cost more than the parallelism saves.
2. **BRIEF EACH ONE with what has already been paid for**, or they will re-learn it: read the
   game's own source and level data FIRST (`scripts/read_sample_games.py`,
   `scripts/dump_sample_levels.py`); thirteen of the twenty-five games declare a per-level ACTION
   BUDGET and END when it is exceeded, so plan rather than explore; `detect` returns **0.0** when
   the tool has no plan; segmentation comes from `tools/segment.py` and is never re-invented;
   actions are SWALLOWED during animations; an edge-pinned counter is not board content.
3. **INTEGRATE CENTRALLY.** Only the parent edits `registry.py`. Take one tool at a time, register
   it, and run the **full 25** on ceph-build at `PAR=25` — about two minutes — comparing per game
   against the previous round.
4. **KEEP OR REVERT ON THE MEASUREMENT, never on the agent's own report.** A tool that clears its
   game and steals another's turn is a loss. A tool is kept only when no game regressed.
5. **RECORD** the outcome in the round page and pull every artefact back off the box (rule 2).

⛔ **FREEZE A SNAPSHOT, THEN VARY ONLY THE REGISTRY.** Measured 2026-08-27: six bisect runs
chased a "regression" that did not exist. The baseline it was measured against came from a tarball
taken while that game's own tool was mid-edit by its agent, and the intermediate version no longer
exists — so the committed code was never the measured code, and three innocent tools were nearly
reverted. Sync ONE snapshot to the box, then produce every variant by editing `registry.py` THERE.
A comparison is only like-for-like when the tool FILES are identical and the registry is the only
difference.

⛔ **While agents are running, NEVER `git add -A`.** Commit explicit paths only. Measured
2026-08-27: a docs commit about one game swept in 393 lines of an agent's in-progress tool and its
driver, under a message that mentions neither. The agents are writing into the same working tree,
so a blanket add is a commit of other people's half-finished work — and if one of them is mid-edit,
of broken code under a green-looking message.

**Why integration stays central**: selectivity is a property of the TOOL SET, not of any one tool.
No agent can see the cost its `detect` imposes on the other twenty-four games, so no agent may
decide whether its own work is kept.

## 7a. THE CURRENT AXIS — what a tick should find you doing (2026-08-27, user-set)

**Clear the sample games.** Nothing else. Not the leaderboard, not a submission, not the card.

**Where it stands (re-measured 2026-08-27 at commit d1f0e3c, full 25 on ceph-build,
`--agent unified` @4000 — generic tools ALONE, zero adapters):**

```
mean 0.8602 over ALL 25   FIFTEEN at 1.0000   SEVENTEEN clear EVERY level   25/25 clear one
1.0000  ar25 cd82 cn04 ft09 m0r0 r11l sb26 sc25 sk48 sp80 su15 tn36 tr87 tu93 vc33
0.9908 re86 8/8 · 0.8919 lp85 8/8 · 0.8000 wa30 8/9
0.7500 g50t 6/7, ka59 6/7, ls20 6/7 · 0.7143 dc22 5/6
0.4204 s5i5 6/8 · 0.2727 lf52 5/10 · 0.1648 bp35 5/9
```

✅ **TRANSFER 0.9981, 13 of 14 re-rendered games IDENTICAL** (`scripts/rounds/R101XFER8`),
held across the day's last three conquests AND across tightening the no-progress bail.
Re-run it whenever the card moves.

⚠️ **A GUARD CALIBRATED AGAINST A MEASUREMENT DECAYS ON ITS OWN, AND THE DIRECTION IS NOT
KNOWABLE WITHOUT RE-MEASURING.** Three checked on 2026-08-27 evening: the no-progress bail's
stated 10x margin had become 4.7x because the worst level ever CLEARED went 120 -> 255 in a
day (recalibrated to 500, a deliberate 2.0x — full 25 IDENTICAL at 300, 500 and 1200, so the
choice is wall-clock against margin and nothing was measured lost); the wall-clock cap's
stated 4x had become 10x, drifting the SAFE way; and `claim breadth` went from 29 specialists
to 38 with the clean split intact. Re-read every constant whose comment cites a number
whenever the tools underneath it change.

⛔ **AND GIVE IT ONE HOME.** The recalibrated bail was measured, committed and written up — and
NEVER RAN, because `score_efficiency.py` passed an explicit `no_progress=1200` that overrode
`UnifiedAgent`'s new 500. Caught only when a run came back at 1520 actions where 820 was
expected. A constant with two homes has one that is wrong, and the wrong one wins whenever it is
the explicit argument.

⛔ **"THE RATIOS WILL HOLD" IS UNSAFE FOR ANYTHING ORDERED IN TIME.** Told a tool author that
halving the bail would shrink their counts and leave the ratios intact. Measured, on lf52 level
6: `none` collapsed 510 -> 3 while the working tiers merely halved, because the idle phase is a
TAIL rather than something spread through the level — so truncating cuts almost pure idle. Their
conclusions survived because they rested on the working tiers, but the reasoning I gave them was
wrong.

⛔ **A LEVEL LOST AND RETRIED IS INVISIBLE IN THE SCORE.** The engine restores the board and hands
back a fresh allowance while the score carries the actions already paid, so a level cleared on the
third try reads exactly like one cleared slowly — and the two want OPPOSITE work.
`scripts/attempt_probe.py where <game>` splits a run into levels and attempts and prices them;
its last column is what the game would score if only its winning attempts were paid for. That
measurement moved re86 from 0.8349 to 0.9908 and refuted two of my own diagnoses on the way.
Only **bp35 (+0.1283)** still has attempt headroom.

⛔ **THE THIRTEEN ADAPTERS NOW COST THE SHIPPED CARD.** Measured the same day, same tree:
`--agent kaggle_detect` (as shipped) **0.5422** against `--agent unified` **0.8602** — a gap of
**+0.3180**. The adapters lose on 22 of 25 games (sc25 0.0427 against a generic 1.0000, ar25
0.0833 against 1.0000, sp80 0.1429 against 1.0000, wa30 0.0222 against 0.8000), tie on two,
and **only `ls20` still beats the generic path**. The gap widens on its own every time a
generic tool lands. Nothing broke: the FALLBACK moved
out from under them and both routing guards were calibrated when it scored 0.0566. Full
measurement and the two guard defects:
[`.wiki/wiki/lessons/adapters_now_cost_the_card_20260827.md`](.wiki/wiki/lessons/adapters_now_cost_the_card_20260827.md).
**Dropping twelve adapters is worth ~+0.31 of card and is SUBMISSION-AFFECTING, so it is the
user's call, not mine.**

⛔ **A report that gives only the LEVEL COUNT cannot be acted on.** Measured on bp35 the same
day: one tool cleared five levels where the incumbent cleared three and scored 0.1344 against
0.1333 — two extra levels worth **+0.0011**, because RHAE prices a level at `(human/ours)^2` and
the incumbent's three sat at human parity. The same tool then kept the SAME five levels, made
them cheaper, and gained **+0.0304**. Ask every agent for the per-level costs, not the depth.

✅ **Transfer is essentially CLEAN: ratio 0.9981, 13 of 14 re-rendered games IDENTICAL**
(`scripts/rounds/R101XFER6`). Re-run it whenever the card moves — the ratio went 0.91 -> 0.88
-> 0.92 -> 0.93 -> 0.94 -> 0.9981 while the card went 0.6733 -> 0.8540, and NONE of the
fixes that recovered it moved the card by a digit.

⚠️ **The card is not the property that matters, and one gain today proved it.** Re-run the
archive transfer measurement (`scripts/rounds/R101XFER2`) whenever the card moves: `telescope`
lifted s5i5 from 0.0833 to 0.4167 on the live board and scores **0.0000** on the re-render,
because its detector keyed on an exact colour census that a two-cell difference destroys. See
[`.wiki/wiki/lessons/generic_transfer_20260827.md`](.wiki/wiki/lessons/generic_transfer_20260827.md).

⛔ The figures this block carried until 2026-08-27 — *"0.0230, 16 of 25 clear nothing"* — were
from the morning of the day the axis was set and were **30x stale by that evening**. An axis
statement is read by every new session as the current position; when it goes stale it sends
work at a problem that is already solved. Re-measure it whenever a round closes.

⛔ **A round directory is not a baseline just because it is the newest.** `R101FAN6` reports
ar25 at 0.0 — it is a FAN-OUT round carrying an agent's experimental registry. HEAD measures
ar25 at 1.0000 in 268 actions. And the per-round aggregator prints LEVELS, not scores; reading
its column as a score is the "a field means what it RECORDS" trap. Compute from `games/*.json`.

**The work left is DEPTH, not efficiency** (measured, and got wrong once in the other
direction): the weak games clear level 1 at or faster than the human count and then stop.

**How the work runs now (user directive, "하나씩 개선할거야?"):** tool development goes in
PARALLEL — one background agent per game, each owning its own new file under `src/admorphiq/tools/`
and `scripts/`, never touching `registry.py`, `loop.py` or another tool. The parent integrates,
runs the full 25 on ceph-build at PAR=25 (two minutes), and keeps the change only if no game
regressed. Building one tool at a time leaves ceph idle and is not the plan.

**Per tool, in order:** read the game's own source and level data first
(`scripts/read_sample_games.py`, `scripts/dump_sample_levels.py`) → design against the mechanic and
the DECLARED action budget → write a frame-only tool whose `detect` returns 0.0 without a plan →
verify on that game → hand to the parent → full 25 → keep or revert.

## 7. The watchdog contract — what to do when a tick fires

⛔ **The wiki and this file are the single source of truth. The cron prompt must stay a POINTER**, not
a copy: the moment it carries rules of its own there are two sources and they drift. If a rule needs
changing, change it HERE and both the cron agent and the session pick it up.

⛔ **THE CRON IS A WATCHDOG. IT DOES NOT HAND OUT WORK.** A tick firing is a FAULT REPORT: it means
work had already stopped when it should not have. The correct number of ticks in a productive session
is ZERO.

**Never end a turn by announcing the next step.** If the next step is known, DO IT — in the same turn,
without pausing, without asking, without waiting for a tick. "Next I will measure X" is only ever
written after X has been measured and something else is next. Chain steps until the work genuinely
blocks on a decision only the user can make, or on a long-running job whose result nothing can proceed
without.

This was violated on nearly every turn of 2026-08-26 despite the rule being in this file: a step would
finish, the finding would be written up, and the turn would end on "next I will…" — which is exactly
the stop the watchdog exists to catch.

**On every tick, in order:**

1. Read this file.
2. `tail -40 .wiki/wiki/rounds/index.md` — the most recent round is the current axis. Read that
   round page's "Open work".
3. Check what is running: local background tasks, and
   `ssh -i ~/VM/keys/nfw-dev.pem ubuntu@ceph-build 'uptime; pgrep -cf python'`.

**Before taking an open item as the task, MEASURE that it is still open.** On 2026-08-26 all three of
R98's open items turned out stale — "the sink shortlist comes back empty" (the walk clears that level
in 22 actions), "multi-piece placement" (the compiler already plans over every piece jointly), and "a
fourth target the schema cannot express" (the round itself corrected it). Each took one replay to
check. An open list is a claim about the present.

⛔ **Do not chase a visible residual instead of the list.** Five ticks went into idx3's three leftover
cells while `CLAUDE.md` already said *"17 distinct events say the engine always steps off, so there is
no step-off rule to find here"*. A conclusion already in the record is not progress when re-derived.

⛔ **Do not invent a sweep to keep ceph busy.** That produced a full detour onto another axis the same
day. An idle box is better than a misdirected one — but a box idle while the current axis has parallel
work is waste, so check which case it is.

When every open item is measured closed, open the next round and register it in `index.md`. Rounds are
meant to be finished; nothing here is tied to any particular one.

After a change: `uv run ruff check` on files you wrote, the related tests, and the round's own gates.
Commit progress to the round page, and bring the MEASUREMENTS back too — `scripts/ceph_pull.sh`,
`scripts/memory_mirror.sh` — because the instance and the memory directory both vanish with the
machine.
