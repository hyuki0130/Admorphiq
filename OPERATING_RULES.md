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

## 7b. HOW TO WORK THIS AXIS — measured 2026-08-28/29, each line paid for

**⛔ SWEEP FOR UNUSED ASSETS FIRST. DIG SECOND.** Every gain on 2026-08-28 came from something
already present that was not being used, and each cost minutes:

```
ls20 +0.0942   fogscout.py was committed and never added to default_tools() — an UNREGISTERED
               TOOL MEASURES EXACTLY LIKE AN ABSENT ONE, so the run that called it "inert" was a
               measurement of nothing. Pinned now by tests/test_every_tool_is_registered.py.
bp35 +0.0431   _reveals was used as a BOOLEAN where the board needed its MAGNITUDE.
lp85 +0.0179   confirmation presses were unbounded; bounding them by the plan they protect.
bp35 +0.0142   a ranking term in the right position (reach above blocks-spent).
```

The same evening, a deep dive into ONE parked board cost hours, produced six measured repairs that
all scored **identically**, and moved the total by **zero**. Diagnosis is not score.

**⛔ THE BOX IS FOR PARALLEL WORK AND IT WAS LEFT IDLE FOR HOURS.** One game at a time locally while
ceph-build's 64 cores sat empty. Sweeps go on the box, one process per game, all at once.

⛔ **AND NEVER `pkill` BY A PATTERN A GATE ALSO MATCHES.** Clearing a sweep with
`pkill -f "score_efficiency.py --agent unified --titles"` also killed the running gate's own s5i5
process. The gate waits for 25 result files and simply never finishes — it has no way to notice a
game died, so it hangs instead of failing. Kill by the sweep's OWN path
(`pkill -f "v[1-4]/scripts/"`), and if a gate is running, check
`ls <round>/games/*.json | wc -l` before and after so a stall is visible immediately.

⚠️ **But a GATE must not share the box with a sweep.** Launching eight variant runs beside a
running full-25 put 33 processes on it and made both crawl — and the gate is the measurement whose
number gets banked, so loading it is worse than idling. Gate alone; sweep while nothing is being
gated. (The 60-core cap in rule 5 bounds one job, not the sum of two.)

**⛔ CONTRAST WITH THE LEVEL THAT CLEARS, ALWAYS.** Four readings of s5i5 were wrong and each died
the moment the clearing level was measured the same way: "the control map is empty" and "three
controls are unknown" are both TRUE of the level that clears. A property of the stuck level is not
a cause until the clearing level lacks it.

**⛔ WHEN A PARK SAYS "IT NEEDS INFORMATION X", HAND IT X AND LOOK.** s5i5 was parked with a proof —
the tool cannot see 291 hidden cells. An oracle probe injected them exactly; the score did not move.
One run overturned an evening of reasoning. A difference that correlates perfectly with success is
not thereby the cause.

**⛔ ATTRIBUTION BY PROXIMITY IS BANNED, AND IT IS NOW AN EXCEPTION.** Assigning trace events to the
most recent level line produced three withdrawn findings in one session (ten read failures reported
as "499 of 500 actions"; level 6's model reported as level 7's). Print the level from inside the
code that fires the marker and group with `scripts/trace_attribute.py`, which REFUSES events with no
`lvl=` field. ⚠️ And never hardcode the level into a marker — a literal is not a measurement.

**⛔ PROVE THE INSTRUMENT IS ATTACHED BEFORE READING IT.** Make it say something it could not say if
it were not. Failures this session: a marker replacing the FIRST match of a string that occurs
twice; a marker calling a name the module does not import, so `propose` threw on every call, the
harness swallowed it, and the game scored 0.0000 while looking like a measurement.

**⛔ MEASURE A FROZEN COPY**: `bash scripts/measure_frozen.sh` — `PYTHONPATH` does NOT select the
code the runner runs, because `scripts/score_efficiency.py:35` inserts its own repo's `src` ahead of
it. And hash the tools on both machines before any cross-machine comparison; `LC_ALL=C sort` or the
diff is nonsense.

**⛔ KEEP NOTHING THAT DOES NOT MOVE THE SCORE.** Six read repairs were measured on dc22 and exactly
one was banked (full-25 neutral, and it made the board readable for the first time). The rule
applies to your own work hardest.

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

### 7c — the waste a stalled tool spends is the HARNESS's, and `observe`'s flag cannot see it (2026-08-29)

Two traps, both measured on lf52, both generic, both of which cost a session each:

**The fallback presses the lowest-numbered key.** `UnifiedAgent._probe` returned `simple_ids[0]`
whenever the active tool proposed nothing. On lf52's sixth level that is ACTION1, which the engine
refuses **117 times against 21 that move anything**, and **83 of those presses come from here, not
from any tool**. The whole of the previous session read this as a tool defect and named a tool-side
lever for it; the tool's own plan emits 34. ⛔ Before attributing wasted actions to a tool, check
who ISSUED them — the loop tags nothing, so add the tag rather than assume.

**`observe`'s `changed` flag is `(prev != frame).any()`** — and a board with an action counter at
the frame's edge makes that TRUE for every action, refusals included. A refusal counter built on it
recorded `fail={}` across **227 transitions on the very level whose waste it was written to find**,
and the guard it fed was inert while looking exactly like a measured negative. Only
`tools.segment.board_changed` (which ignores the outer band) can see a refusal, and it needs the
NEXT frame, which `observe` is not given — settle it at the following `propose`.

**And the negative that matters more than either**: removing the waste did NOT open a level. lf52
clears 5 at 500 actions and 5 at 1000. ⛔ A level that stalls with actions to spare is not
budget-starved, so "N wasted actions" is never by itself a diagnosis of why it stalls.

### 7d — the Mac's disk fills with OUR OWN sync tarballs (2026-08-29)

A Stop hook failed with `cannot create temp file for here document: No space left on device`, and
the volume was at **100% with 117Mi free**. Nothing in the repository caused it: the round's own
sync tarballs — `tar czf /tmp/<name>.tgz src scripts`, one per push to ceph-build, kept from three
days of rounds — had accumulated to **283MB**, and every one is regenerable in seconds.

```
rm -f /tmp/*.tgz        117Mi -> 412Mi free, hook green again
```

⚠️ The bulk of the disk was NOT ours: 9.4GB sat in one other project's session scratch under
`/private/tmp/claude-501/`, with 390 files touched that day — an ACTIVE session, and not something
to delete on another session's behalf. Check `du -sh /private/tmp/claude-501/*` before assuming the
space is yours to reclaim, and clear only what this round created.

⛔ A full disk does not announce itself as a disk problem. It arrives as a hook failing on a
here-document, and the next thing it breaks is a measurement that will look like a tool regression.

### 7e — a probe that prints NOTHING and exits 0 has usually lost its entrypoint (2026-08-29)

Twice in one day a probe ran, exited cleanly, and produced an empty log. Both times the cause was the
same: an edit that REPLACED THE TAIL of the file took `if __name__ == "__main__": main()` with it. The
module then defines its work and never calls it, which is indistinguishable from a measurement that
came back empty — and the second occurrence cost half an hour of chasing ssh, nohup and buffering.

```
grep -c "__main__" scripts/_probe.py        # 1, or the probe does nothing
```

⛔ **Prefer inserting over replacing a tail.** When a tail must be replaced, re-append the entrypoint
in the same edit, and check the count before running anything remote.

⚠️ Related, same day: a long probe writes NOTHING until its setup finishes (reaching a late level can
take 400+ actions), so an empty log early is not evidence of failure. Print progress from the first
action, and run remote work by `nohup`-ing a SCRIPT the box owns — an `ssh ... cmd &` dies with the
connection, which is how the same probe was lost twice more.

### 7f — "the level number changed" is not "we won" (2026-08-29)

A dc22 probe reported `LEVEL CLEARED ... by a click at (26,8)` and it was the opposite: the click
restarted the game and the run FELL BACK to level 0. The test was `levels_completed != 5`, which is
true when the level advances and equally true when the run collapses. Three commits and two probes
were built on the wrong side of it before anything forced the direction to be named.

```
if lvl != start:      ⛔ says nothing about which way
if lvl > start:       ✅ and print the number when it moves
```

⚠️ **The tools in `src/admorphiq/` already do this correctly** — every level comparison there is
`lvl > self._levels_completed`, and there is not one `!=` among them. The defect was in the probe,
which is the code nobody reviews.

⛔ A collapse and a clear look IDENTICAL to a boolean, and the favourable reading is the one that
gets written down. Name the direction in the probe, and print the resulting level, so the record
cannot be read two ways later.

### 7g — the source says what is POSSIBLE; only the run says what HAPPENS (2026-08-29)

Three retractions in one round, all the same shape: a fact read out of a game's source was treated as
a description of the game's behaviour, without checking that the code path executes.

- **wa30**: level 9 declares `StepCounter: 70` and the source has `elif not current_steps:
  self.lose()`. Concluded "the level is lost on its budget". MEASURED: one unbroken 507-action
  attempt, no restart, 506 actions moving the board — **the branch never fires**. The budget does not
  bite, and the whole "efficiency not mechanic" reading went with it.
- **dc22**: a click was reported as clearing level 6 on `levels_completed != 5`. It had FALLEN BACK
  to level 0 (see rule 7f).
- **bp35 / ls20**: mechanics recovered correctly from source — a crumbling platform, a fuel budget —
  and both turned out not to be what stops the tool.

⛔ **Reading the source is still the cheapest way to find a mechanic** — it has ended questions in one
read that frame probing could not settle in a session. But a mechanic FOUND is not a mechanic that
BINDS. Before building for it, run the game and show the branch executing: the counter reaching zero,
the tile being consumed, the level actually ending.

⚠️ The failure is seductive because the source reading is usually CORRECT. wa30 really does declare
70 and really does contain a lose(); it simply never reaches it in play.

### 7h — ROOT CAUSE of working one-at-a-time: hypotheses are generated one at a time (2026-08-29)

The user asked three times for parallel work on ceph-build, the watchdog tick asks for it every nine
minutes, two scripts now exist for it (`ceph_sweep.sh`, `pfan.sh`) — and I still worked serially.
Adding a third script would not have fixed it either, because the tooling was never the bottleneck.

**The bottleneck is that I form ONE hypothesis at a time.** The loop is: measure, get a surprising
result, derive the single next question from it, write a probe for that question, run it. Question
N+1 depends on answer N, so there is nothing to parallelise — not because the box is unavailable, but
because at any moment I am holding exactly one question.

Measured cost of this pattern on 2026-08-29: **76 commits, ZERO surviving source changes, 14 of them
retractions**, box at load 9 of 64.

⛔ **THE RULE: before writing any probe, enumerate every hypothesis that could explain the
observation, and test them all at once.** Not seeds of one question — DIFFERENT questions, run
together. If the list has one entry, that is the tell that the enumeration was skipped.

⚠️ This also explains the retractions. A single hypothesis, once formed, is the only one being
tested, so the first result that is consistent with it gets accepted — "wa30 declares 70 and spends
508, therefore budget" — and the alternatives that would have refuted it were never on the list.
Enumerating first is the same discipline that prevents both failures.

### 7i — ONE tree on the box; the conflict is the SYNC, not the tree (2026-08-29)

With eight agents running at once I concluded the box's single `~/admorphiq` checkout was a shared
resource that needed per-worker copies, and built `ceph_worktree.sh` to give each one its own. That
was over-engineering a non-problem, and it is deleted.

**One tree is correct.** Game logic is read-only, and every process constructs its own engine
instance, so N processes reading the same source do not conflict. What conflicts is the **SYNC** —
overwriting the tree while something is measuring against it. So the rule is about timing, not
topology:

- sync ONCE, then let everything read it;
- never sync while a measurement is in flight — that is exactly what `gate_tool.sh`'s tree-hash check
  is protecting, and it is the right guard;
- a gate re-syncs by design, so a gate must not overlap another gate or a sweep.

**The 60-core cap is a TOTAL, not a per-worker budget.** Stated repeatedly and still broken: each
agent fanned out 60-way and the box reached **129 processes at load 64.6**, above which SSH stops
answering and the round cannot be checked on. `ceph_idle_alarm.sh` now reports the overload into
every turn, because a ceiling in a document is one nobody sees at the moment they exceed it.

### 7j — nobody owns the TOTAL, so the box has to own it (2026-08-29)

Eight agents, each honouring its own `-P`, still took ceph-build to **133 processes at load 55.7**.
Their individual settings were fine — one used `-P 6`, another `-P 12` — and the SUM was nobody's
responsibility. A cap that every participant must voluntarily divide among themselves is not a cap.

`~/bin/cap.sh` now runs on the box and holds the total at 56: it `SIGSTOP`s the newest processes over
the line and `SIGCONT`s them when there is room, so no work is lost, only deferred. The daemon is the
only thing that sees the total.

⛔ This is the same shape as the other process failures today. The 60-core limit was in
`OPERATING_RULES.md`, in `CLAUDE.md`, in the watchdog tick and in four messages from the user — and
it was still breached, because every one of those places asks a PARTICIPANT to remember it at the
moment they are thinking about something else. The version that works is enforced by something that
is not a participant.

### 7k — measurements were running on the MAC, and nobody noticed until the user asked (2026-08-29)

Rule 0 has always said the Mac is edit/lint/pytest only and measurements run on ceph-build. With
eight agents active it was breached anyway: `_bp35_l6_replay.py` was burning **91.9% CPU on the Mac**
with a 30,000,000-step argument, a `score_efficiency.py` run was going beside it, and Mac load was
20.2 — on the machine the session itself runs on.

`.claude/hooks/local_measurement_alarm.sh` now reports any local game measurement into every turn.

⚠️ Its first version matched `python.*scripts/_` against the full process list and counted the
`ssh` and `zsh` WRAPPERS that launch work on the box — three false alarms in a row. Match the
interpreter that is actually executing here (`.venv/bin/python`, `python3`), not the command that
mentions the script's name.

⛔ Same shape as 7i and 7j: a rule that has been true and written down for months, breached the
moment work went parallel, because every statement of it asks a participant to remember it. The
version that holds is checked by something that is not a participant.

### 7l — a measurement must not WRITE to a shared path; snapshot it (2026-08-29)

⛔ The gate was the contamination. `scripts/rounds/gate_tool.sh` syncs `~/admorphiq` on ceph-build,
and that path is SHARED by eight agents who edit `src/` continuously. Its own header documents two
traps that are both this one cause — trap 4 (a gate ships every agent's work-in-progress, so a
"single tool" verdict is jointly attributed and nobody notices) and trap 5 (the tree moved under the
measurement; `blastclock` was `d33922ec` locally and `ef0dafdf` on the box, so five ka59 runs
returned 0.7500 five times while the real tree scored 1.0000).

Neither trap has a fix at the level they were written. Trap 4 explicitly "cannot REFUSE — in-flight
edits are the normal state of a fan-out round", and trap 5's hash check can only VOID a verdict
after the machine time has been spent. Both were paid again on 2026-08-29: the ls20 gate refused its
own verdict because `cover_targets.py` moved mid-run, and an hour later `integrate.sh` would have
gated a peer's uncommitted `cyclepress.py` and attributed it to the re86 agent.

**The fix is that the measurement never writes to the shared path at all.** `scripts/snapgate.sh`:

```
bash scripts/snapgate.sh re86 scripts/rounds/R101REACH 6 4000
```

`git archive HEAD` → a private `~/snap_<name>` on the box → run the 25 out of THAT copy → compare
per-game. `~/admorphiq` is read for its venv and its `environment_files` and is never written.
Consequences, all of them the point:

- **Two gates can run at once.** Verified: the re86 gate ran to completion beside the lp85 agent's
  50-run A/B, neither disturbing the other.
- **A rider cannot ride.** The snapshot is the COMMITTED tree, so a peer's uncommitted edit is
  excluded by construction rather than by anyone remembering to look. The verdict names a commit.
- **The tree cannot move under it.** There is nothing to move; the snapshot was taken once.

⚠️ Two load-bearing details, both silent when wrong. `scripts/score_efficiency.py:35` inserts ITS
OWN repo's `src` ahead of `PYTHONPATH` — that is what makes invoking the copy inside the snapshot
actually select the snapshot's code, and it is why `PYTHONPATH` does not work here (already
recorded, under `measure_frozen.sh`). And the run needs `cwd=~/admorphiq` to find the environment
files, because `score_efficiency.py` sets neither `ENVIRONMENTS_DIR` nor passes `environments_dir=`.

⛔ CREDIT, because the method was not mine: the **lp85 agent** built it independently on 2026-08-29
to A/B two `cyclepress.py` arms — `~/lp85gA` / `~/lp85gB`, private snapshots, shared tree untouched —
while a peer's gate was in flight, and both measurements stood. I went looking for whoever had put
42 scoring processes on the box in order to stop them, and found the answer to a problem three rules
had failed to solve. **Look at what a parallel worker is doing before stopping it; the deviation may
be the fix.**

### 7m — the Mac rule SAID "pytest" and that is what melted the laptop (2026-08-29)

The user, twice within a minute: *"아직도 로컬에서 돌아가는것들 있어! 정리해서 ceph 인스턴스 사용하도록해!
랩탑이 너무 느려"* / *"에이전트들에게 확실히 인스턴스 사용하도록 지시를 하라고!"*

I went looking for a game measurement and there wasn't one. The local load was **three concurrent
`pytest tests -q` runs** at 57% / 56% / 55% CPU, laptop load 27, on the machine the session itself
runs on. `local_measurement_alarm.sh` reported nothing because it matches `score_efficiency` and
`scripts/_`, and the suite is neither.

⛔ **NOBODY BROKE A RULE. THE RULE WAS WRONG.** Rule 0 has always read *"the Mac is edit/lint/**pytest**
only"*, so every agent running the suite locally was obeying it exactly. That sentence was written
when there was one worker. With eight, ~1700 tests is a minute of a core times eight agents times
every edit — the laptop's entire capacity, spent beside 64 idle cores one ssh away.

**Tests run on the box, out of a private snapshot, like every other measurement:**

```
bash scripts/ptest.sh tests/test_crag.py        # just yours — PREFER THIS
bash scripts/ptest.sh                           # whole suite, when you truly need it
bash scripts/ptest.sh --dirty tests/test_x.py   # include uncommitted edits (red-green loop)
```

Default is HEAD and it NAMES the uncommitted files it excluded; `--dirty` ships the working tree,
because a red-green loop testing HEAD is testing the wrong thing. `-p no:randomly` is forced so two
runs are comparable. The snapshot is deleted on exit.

**The Mac now runs an editor, `grep`, and `ruff`. Nothing else.** Not pytest, not a solver, not a
replay, not a "quick" offline enumeration — that last one was argued for explicitly ("plain python,
no engine") while the user was complaining about laptop speed. ⚠️ **If you are unsure whether
something counts, it counts.**

⛔ This is the FOURTH rule in a row with the same shape (7i, 7j, 7k, and now this) and the sharpest
version of it: the previous three were rules that participants forgot, and this one is a rule that
participants FOLLOWED. A correctly-obeyed rule can be the defect. When a limit is breached, read
what the rule actually licenses before looking for who ignored it.

⛔ **AND THE RULE DID NOT HOLD BY BEING WRITTEN.** Within minutes of the three suites being killed
and every agent being told in writing, **two more respawned** — `pytest tests -q` at 95.5% CPU and a
`-k "tool or registry or harness"` run at 50.9% — and a peer agent found and killed them. So the
enforcement is now a hook, `.claude/hooks/block_local_pytest.sh` (PreToolUse on Bash), which REFUSES
a local `pytest` or game run and prints the box command to use instead. Anything routed through
`ssh` / `pfan.sh` / `snapgate.sh` / `ptest.sh` passes untouched.

⚠️ A blocked run costs one re-run and nothing else. A rule that is merely written costs a laptop.

### 7n — `ptest.sh` was measuring the BOX'S code, not the snapshot's (2026-08-29, same hour)

The remote test runner shipped with a defect of exactly the kind it exists to prevent, and it was
found by an agent, not by me. The linked venv installs admorphiq **editable**:
`_editable_impl_admorphiq.pth` carries the absolute path `/home/ubuntu/admorphiq/src`, baked in at
install time. Nothing set `PYTHONPATH`, so the snapshot's own `src/` was SHADOWED and pytest
imported the shared tree's copy — the very thing the snapshot exists to escape.

Proved in both directions on the box, because "it passes now" is not proof:

```
WITHOUT PYTHONPATH: /home/ubuntu/admorphiq/src/admorphiq/__init__.py    <- the shared tree
WITH    PYTHONPATH: /tmp/shadowtest/src/admorphiq/__init__.py           <- the snapshot
```

⛔ **The loud half is the cheap half.** A NEW symbol fails with a traceback naming a file that
plainly contains it (`cannot import name '_rail_reach' from .../railpeg.py`) — confusing, but it
stops you. A CHANGED function **PASSES, against the old code**, and `--dirty` then reports green on a
tree it never shipped. Every `src/` edit validated with `ptest.sh` before this fix must be re-run.

The fix is one line plus a REFUSAL: the runner now imports `admorphiq` and checks the file it got is
inside the snapshot, and reports nothing at all if it is not. A guard that only fixes the common case
leaves the silent case silent.

⚠️ `snapgate.sh` was never affected, for a reason worth knowing: `score_efficiency.py:35`
`sys.path.insert(0, ...)`s its own repo's `src` at position 0, ahead of anything site-packages adds.
The gate is immune by accident of the runner's design, not by anything the gate does.
