# Operating rules — read FIRST, every session

⛔ These are the rules that have actually been broken, each one more than once, each one after being
stated. They live here because a rule that exists only in a chat message or in machine-local memory is
a rule that dies at the next context compaction or the next machine.

## 1. ceph-build runs at MAXIMUM parallelism, capped at 60 cores

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

## 6. Use the daily submission slot; use GPU quota when the work needs it

**Standing directive, 2026-08-26**: the Kaggle submission slot is one per day, resetting 00:00 UTC,
and **leaving it unused is waste** — put the best measured candidate in it rather than holding for a
better one. GPU kernel runs are separate: `kaggle kernels push` does NOT consume a submission, only
`kaggle competitions submit` does, so run GPU work whenever weekly quota remains.

⚠️ This supersedes the earlier "never push one unasked" reading. What survives from it: the candidate
must be measured AS SHIPPED (`--agent kaggle_detect`, not `--agent detect`) before it goes, and a
submission whose build is not committed is not reproducible — kernel source, `kernel-metadata.json`,
the push command and the dataset-version-to-commit mapping all go in with it.

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

## 7. The watchdog contract — what to do when a tick fires

⛔ **The wiki and this file are the single source of truth. The cron prompt must stay a POINTER**, not
a copy: the moment it carries rules of its own there are two sources and they drift. If a rule needs
changing, change it HERE and both the cron agent and the session pick it up.

A tick firing means work had already stopped. **The cron is a watchdog, not a work queue** — finish a
step and start the next one without waiting for it.

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
