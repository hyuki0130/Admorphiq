---
name: feedback-measurement-discipline
description: "Timestamp every output; run measurements as background shells (rate-limit-proof); one live SUMMARY.txt per round; never discard partial results — analyze and advance"
metadata:
  node_type: memory
  type: feedback
  originSessionId: c7e91ecf-c8c0-4c3c-bd62-4722ff123df5
---

User directives (firm, repeated with frustration 2026-07-01) after I repeatedly lost results,
re-ran completed work, and reported "just started" without checking the clock:

**1. TIMESTAMP EVERY OUTPUT — INCLUDING CHAT REPLIES TO THE USER.** EVERY message you write to the
user MUST begin with `[YYYY-MM-DD HH:MM:SS KST]`, and the value MUST come from an ACTUAL
`date '+%Y-%m-%d %H:%M:%S %Z'` call made IN THAT SAME TURN — NEVER estimate/increment/reuse a prior
turn's time (estimating once produced a FUTURE-dated 11:01 header when it was really 10:59 — worse
than no timestamp). Not optional, every reply — the user demanded this explicitly and repeatedly
(2026-07-01). Logs, SUMMARYs, progress.txt entries, and records are always timestamped too (logs
are logs). Before saying "just ran" / "방금", CHECK the actual time and compare to the record's
mtime. Stale vs fresh confusion (R10 transcript hunt, mixing old/new runs) came from not
timestamping. When waiting, always report current time + elapsed since the run started.

**2. MEASUREMENTS RUN AS BACKGROUND SHELLS, never inside agents.** Agents write CODE only; the
measurement runs as a `run_in_background` shell. Why: online-RL measurement inside an agent burns
its session tokens and it dies mid-run (R10), and manual `setsid nohup` gets torn down by the Bash
sandbox. The harness-managed `run_in_background` survives session rate-limits (proven: R8 ran 3h to
completion) — rate-limit blocks only my LLM turns, not the running process. So **even at rate-limit,
the measurement keeps going.**

**3. ONE LIVE SUMMARY PER ROUND.** Fixed convention: `scripts/rounds/RN/run.sh` writes
`scripts/rounds/RN/SUMMARY.txt` (+ per-game jsons in `games/`, `run.log`). SUMMARY.txt is
regenerated LIVE after every run via `scripts/rounds/aggregate.py` — always readable mid-run, and a
valid partial if the run dies. On completion OR crash the answer is ALWAYS SUMMARY.txt. No transcript
grepping. Parallelize games (PAR=3 on this Mac; env.step is CPU-bound but the per-step online CNN
training is the real bottleneck, uniform ~530s/game @3000 — so Kaggle's GPU would speed training).

**3b. CONTEXT MEMORY IS A CACHE, NOT THE SOURCE OF TRUTH.** If a fact about a past round (what was
tried, the number, the verdict, whether it already failed) is not clearly in your working context,
LOOK IT UP in `.wiki/wiki/rounds/index.md` → the round page BEFORE acting/proposing — never
reconstruct from memory or guess. The round pages are the source of truth. (Round log is structured
Obsidian-style: per-round pages `rounds/rNN_slug.md` + keyword index `rounds/index.md` + backlinks,
so retrieval is a keyword lookup, not a full-file scan.)

**4. NEVER discard partial results; analyze and advance.** If a run dies at 27/42, do NOT re-run
the completed ones and do NOT restart the whole thing. Aggregate what exists, ANALYZE it (not "just
archive it"), draw the conclusion if signal is sufficient, and launch the NEXT round applying that
finding — in parallel. Keep rounds going continuously until the user intervenes.

**Don't be hasty.** Killing/restarting processes recklessly wasted hours. Think, check time, reuse
work. Relates to [[feedback-online-rl-is-the-spine]], [[feedback-never-stop]], [[feedback-dev-loop]].

**Kaggle dataset-version race (2026-07-22, r95b fill v2).** `kaggle datasets status` reports
the PREVIOUS version's "ready" while a new version is still processing — a kernel pushed
immediately after `datasets version` can mount STALE code (fill v2 ran pre-fix code and
reproduced an already-fixed crash). Rule: after `kaggle datasets version`, wait 60s+ AND/OR
verify the new version landed (kaggle datasets files/versions) BEFORE `kernels push`.

## ⛔ ceph-build parallelism is capped at 60 cores (user directive, 2026-08-26)

The box has 64. Saturating them locks out SSH — the round becomes unreachable while it runs and
cannot be checked on. Use at most **60**, leaving 4 for the shell.

The user has had to say this **twice**. It is now CLAMPED in `scripts/rounds/R99CARD/run.sh` (and
every round runner copied from it), which is where a rule I keep forgetting belongs — not in my
head, and not in a doc I have to remember to read.

Related, same session: measurements go on ceph-build, not the Mac (a local full-25 choked the
machine and killed a runner at 17 of 25), and the sync is a TARBALL because `~/admorphiq` there is
not a git repo. See [[project_cpu_dev_vm_ceph_build]] and
[[project_leaderboard_2026_08_and_method]].
