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

## 6. Submissions are the user's decision

Prepare the candidate, measure it as SHIPPED (`--agent kaggle_detect`, not `--agent detect`), report,
and wait. Never push one unasked.
