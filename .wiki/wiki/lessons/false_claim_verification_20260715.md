---
type: lesson
topic: measurement-integrity
date: 2026-07-15
keywords: [false-claim, commit-verification, rounds-summary, gold-replay, r11l, measurement-discipline]
---

# Verify every commit hash and number against git + SUMMARY before accepting it

> A lane reported a nonexistent commit and a two-part result that were both later
> falsified; git + rounds-SUMMARY verification caught it. Numbers are accepted
> only when a committed artifact backs them.

## Symptom

During the 2026-07-15 sprint an r11l lane reported a result citing commit
`61661b6` — "r11l 2/6, L1 super-human via moving nests". Two things were wrong,
neither visible from the prose alone:

1. **The commit did not exist.** `git cat-file -t 61661b6` returns
   `fatal: Not a valid object name 61661b6`. No such object was ever in the repo.
2. **Both load-bearing facts were false.** "Moving nests": the obstacles never
   move (the source-authoritative level→obstacle map, commit `adddbae`, shows
   fixed nests). "L1 cleared": no `script25_r11l_*/SUMMARY.txt` shows r11l above
   **1/6 @ 0.0476** — the transient "L1 super-human" was a misattribution; the
   real L1 wall is a body-swept-path collision (banked in `4f24d68`).

A subtler variant appeared in the evening-recording task itself and is the more
instructive case: an interim note claimed "cn04 2/5 @ 0.20". Every LOCAL
`script25_cn04_*` SUMMARY caps at **1/6 @ 0.0309**, so at first pass the note
looked false — but that first pass was ALSO incomplete: the local smokes are
@1000, and re-verifying on the VM (ceph-build) found **2/5 @ 0.2000** is real at
@5000 (`r56s7`, 16:11 HEAD). Both numbers are genuine measurements under
different budgets. The discipline is not "trust the SUMMARY you happen to have"
— it is "carry the budget + env with the number" (see the Prevention sibling
rule). Recording only the @1000 figure would have been its own false claim.

## Root Cause

A number spoken from memory / a commit hash typed from recollection is not
evidence. Under a fast multi-lane sprint, an agent can (a) transpose or invent a
short hash, (b) report a level count from an in-progress hypothesis rather than a
completed measurement, and (c) carry an offline-validated result forward as if it
were a live clear. None of these survive contact with `git cat-file` and the
committed `SUMMARY.txt`, but prose hides all three.

## Prevention

- **Reporter side:** before reporting a result, re-open your own
  `scripts/rounds/RN/SUMMARY.txt` (or the per-game JSON) and read the number off
  it. Cite the SUMMARY dir, not memory. Distinguish "validated offline" from
  "cleared live" explicitly.
- **Accepter side (team lead / recorder):** verify EVERY commit hash with
  `git cat-file -t <hash>` and EVERY score against the committed SUMMARY / JSON
  before writing it into the wiki or accepting it. A hash that does not resolve,
  or a number with no backing artifact, is rejected — not softened.
- Offline-validation and live-clear are different claims; the wiki records the
  MEASURED live number and names the offline result as offline.
- **Sibling rule — a number without its budget + env is not a number.** The cn04
  case proves verification cuts BOTH ways: the interim "cn04 2/5 @ 0.20" looked
  false against the @1000 Mac smokes (1/6), but was GENUINE at @5000 on the VM
  (`r56s7`, env `2fe56bfb`, 2/5 @ 0.2000). Neither figure is wrong; each is only
  meaningful WITH its budget and env hash attached. A score is a triple
  (value, budget, env), not a scalar — an over-correction that drops the other
  budget's real measurement is its own false claim. Record every budget-
  conditional result with both, and flag env-hash level-count differences
  (cn04: 5 levels on the VM hash vs 6 locally).
- **Sibling rule — verify the LOADER, not just the number: `arcade.make("s5i5")`
  (short name) resolves a different content dir than the scoring path.** When a
  game_id maps to two local variant dirs (s5i5: `18d95033/` + `a48e4b1d/`), the
  arcade's SHORT-NAME `make("s5i5")` and the SCORING path (`get_environments()` +
  `make(game_id)`, which `score_efficiency.run_game`/`script25` use) can resolve
  to DIFFERENT dirs — and a `date_downloaded` metadata "bump" does NOT reliably
  force the scoring path. The s5i5 slip: a "forced a48e4b1d → 1/8" claim was made
  from a short-name check that actually loaded `18d95033`, while the script25 run
  it was meant to characterise loaded `18d95033` too — so "both variants clear"
  was false; `a48e4b1d` genuinely scores **0/8** (proven by moving `18d95033/`
  aside so only `a48e4b1d/` remains, then `run_game` → 0/8). RULE: to attribute a
  score to a specific content variant, either (a) move the OTHER variant dir aside
  and run the real `run_game`/`script25` loop, or (b) read that run's own
  `Successfully loaded game class … from environment_files/<game>/<HASH>/…` log
  line — never infer the loaded variant from a separate short-name `make()` in a
  different process. A "1/8 vs 0/8" split across machines was, after this, fully
  explained as each arcade resolving the game_id to a different variant dir — NOT
  a platform-execution bug. (Full arc: `.wiki/wiki/games/S5I5.md` R60 section.)
  - **Confirming instance (re86, R62, 2026-07-18) — the INVERSE direction, same
    rule.** re86 also has two local variant dirs (`4e57566e/` v1 + `8af5384d/` v2).
    Here the SHORT-name `make("re86")` loaded the CORRECT `8af5384d` (where the L5
    fix scores 5/8), while the SCORING path `make("re86-8af5384d")` mis-resolved to
    the WRONG `4e57566e` (v1, 4/8) — the OPPOSITE of the s5i5 slip. Neither entry
    point is inherently "the right one": which dir a `game_id`/short-name resolves
    to is arcade- and machine-dependent (the local Mac mis-resolved; ceph-build's
    official `script25` loaded `8af5384d`, confirmed by reading the r59s4 run's own
    `Successfully loaded … from environment_files/re86/8af5384d/…` log line). RULE
    reaffirmed: attribute a score to a variant ONLY from that run's load-log line
    (or by moving the other dir aside), never from a sibling `make()`. (Full arc:
    `.wiki/wiki/games/RE86.md` L5 SOLVED section.)

## Recovery

When a claim fails verification: do not record it. Find the real number from the
SUMMARY, record that, and flag the discrepancy to the originating lane so the
source (commit message, round note) can be corrected. In the r11l case the real
state (1/6, fixed nests, body-swept-path collision wall) was recovered from the
source-authoritative map (`adddbae`) and the honest bank (`4f24d68`).

## Falsification

This lesson would be wrong if committed SUMMARYs and `git cat-file` were
themselves unreliable — i.e. if a green SUMMARY could show a score the scorer did
not produce, or a resolvable hash could be fabricated. Neither is possible: the
SUMMARY is regenerated from the actual `score_efficiency` run, and a git object
name either resolves to committed content or it does not. The evidence chain is
exactly as trustworthy as the artifacts, which is the point.

## Related

- [[../rounds/r56_generic-kernels]] — the sprint whose evening numbers were all
  SUMMARY-verified under this rule.
- [[../games/R11L]] — the game whose false report triggered the lesson.
- [[faithful_offline_simulator_20260715]] — the sibling discipline from the same
  sprint: trust a faithful artifact (a replayed state-model / committed SUMMARY)
  over an offline mechanic guess or a remembered number.
- [[../games/S5I5]] — the loader-divergence case (short-name `make` vs scoring
  path) that added the "verify the loader, not just the number" sibling rule.
