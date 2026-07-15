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

The same class of gap appeared again in the evening-recording task itself: an
interim note claimed "cn04 2/5 @ 0.20", but every `script25_cn04_*` SUMMARY caps
at **1/6 @ 0.0309** (cn04 has 6 levels; no run reached 2). Recording the SUMMARY
number instead of the note is the whole discipline.

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
