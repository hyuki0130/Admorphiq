---
type: lesson
keywords: [environment-files, metadata, game-id, loader, filesystem-order, measurement-integrity, cn04, s5i5]
provenance: r59s14/r59s15 loader-line audit, 2026-07-19; commits a83d82d (s5i5 R79 diagnosis) + the r59s15 correction run
---

# Duplicate game_id in stale env-dir metadata makes the loaded CONTENT filesystem-order-dependent

> 15 of 25 games kept a stale old-hash dir whose metadata.json claimed the NEW game_id; arc_agi resolves duplicate ids by rglob scan order, so APFS (Mac) and ext4 (ceph-build) silently loaded DIFFERENT game content under the SAME reported game_id.

## Symptom

The same adapter, budget, and reported game_id score differently across machines.
Concrete case: the full-25 card said `s5i5-18d95033 0/8` on ceph-build while the Mac
measured 1/8; historically `cn04` showed a "budget-conditional" 1/6 local vs 2/5 VM
split that never reproduced under budget sweeps.

## Root Cause

When the ARC API rotated game hashes, the downloader left the OLD hash directory in
place but its `metadata.json` carried (or was rewritten to) the NEW `game_id`. The
registry scan (`arc_agi/base.py:_scan_for_environments`, one entry per
`metadata.json` via `rglob`) then holds TWO entries with the SAME `game_id` and
different `local_dir`s. `_find_local_game`'s exact-version match returns the FIRST
entry in scan order — and `rglob` order is filesystem-dependent: APFS returned the
true dir, ext4 returned the stale one. On ceph-build, r59s14 loaded OLD content for
five games (cn04/s5i5/sc25/tn36/tu93) while reporting the new game_id in every row.

## Prevention

- The loader-hash rule is now a per-run AUDIT, not a spot check: after every full-25
  run, grep each game log's `Successfully loaded ... from <dir>` line and compare the
  dir hash to the row's game_id hash. A mismatch invalidates the row.
- After any env re-download, run the mismatch scan (dir hash vs metadata `game_id`
  hash over `environment_files/*/*/metadata.json`) on EVERY machine that measures.
- Stale dirs are archived to `environment_files_archive/<game>/<hash>` — never left
  in the scan path.

## Recovery

Archive every mismatched dir on all measuring machines, then re-run the full-25 as an
explicit ENV-CORRECTION run whose diff is EXPECTED to move the affected rows.
Applied 2026-07-19: r59s15 moved exactly cn04 (2/5 @ 0.2000 stale → 1/6 @ 0.0309
honest — the "budget-conditional cn04" anomaly was content divergence, closed) and
s5i5 (0/8 → 1/8 @ 0.0278 recovered); sc25/tn36/tu93 scored identically on current
content. Card 32.68% → 32.11%, an integrity correction, not a regression.

## Falsification

If a machine with the SAME env-file set and the SAME filesystem still loads different
content run-to-run, scan order is not the mechanism and this lesson's fix is
insufficient. If a mismatched-metadata dir reappears after a fresh download, the
downloader itself rewrites old metadata and needs a code-level fix, not archiving.

## Related

- [[false_claim_verification_20260715]] — the loader-hash rule this lesson hardens
- [[api_hash_rotation_20260421]] — the hash-rotation events that created the stale dirs
