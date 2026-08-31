# RESTORE — bringing this repo back up on a new machine

> Written 2026-08-31 because the development Mac was about to be formatted and **ceph-build was
> already gone**. A `git clone` gets you the code, the rules and every measurement. It does **not**
> get you five things, and one of them is **not re-obtainable**. Read §1 before anything.

## 1. ⛔ WHAT A CLONE DOES NOT GIVE YOU

`.gitignore` is tracked, so the exclusions below are reproducible — but the *contents* are not in
git, deliberately. Sizes are the compressed backup.

| path | size | in git? | can it be re-obtained? |
|---|---|---|---|
| `environment_files_archive/` | 436K | no (`.gitignore:63`) | ⛔ **NO — the ARC Prize API rotated every version hash. These archived hashes cannot be downloaded again.** |
| `environment_files/` | 984K | no (`.gitignore:40`) | ✅ yes — Kaggle competition data (`arc-prize-2026-arc-agi-3`) |
| `data/traces/` + `data/transitions/` | 2.4M | no (`.gitignore:57`) | ⚠️ regenerable but expensive; **11 tests fail without `data/traces`** |
| `scratchpad/` (195 untracked probes) | 429K | partly | ⚠️ one-off probes; the durable ones are under `scripts/` |
| `models/` | 2.3G | no | ✅ retrainable — **and the shipped card does not use it** (see §4) |

⛔ **`environment_files_archive/` IS THE ONE THAT MATTERS.** It holds 14 usable archived version
hashes — the same games re-rendered with different sprite tags and coordinates — and it is the
corpus for the entire transfer axis (`scripts/xfergate.sh`, rules 7by / 7cd / 7ce / 7ck / 7cp). The
API has since rotated; **if this directory is lost, every transfer measurement in this repository
becomes unreproducible forever.**

✅ **RESOLVED 2026-08-31: it is in a PRIVATE Kaggle dataset**, `jaehyukhyun/admorphiq-envdata` —
see §2 for the one-line restore and the verification. Not on GitHub, and it must not be: this repo is
PUBLIC and that is competition data.

## 2. WHERE THE IRREPLACEABLE DATA LIVES

⭐ **A PRIVATE KAGGLE DATASET, uploaded 2026-08-31 — this is the durable copy and the one to use.**

```
git clone https://github.com/hyuki0130/Admorphiq.git && cd Admorphiq && uv sync
uv run kaggle datasets download -d jaehyukhyun/admorphiq-envdata --unzip
```

That restores `environment_files_archive/` (30 files, **15 archived version hashes**),
`environment_files/` (52) and `data/` (54) — everything `.gitignore` excludes and a clone cannot
carry. It needs `~/.kaggle/kaggle.json` (your API token) present.

⛔ **VERIFIED, not assumed** — a dataset that exists is not a dataset that contains what you think:

```
file counts per prefix    archive 30 · environment_files 52 · data 54
archive game list         ar25 cn04 dc22 ka59 m0r0 r11l re86 s5i5 sc25 sk48 sp80 su15 tn36 tu93 vc33
private?                  anonymous curl to the dataset URL returns HTTP 404
```

⚠️ **The 2.9MB total is NOT a red flag even though it equals the archive's uncompressed size** — that
coincidence made this look like a partial upload until the file counts were read. **Count the
entries; never infer contents from a total.**

⛔ **It is NOT on GitHub and must not be.** This repo is PUBLIC (the competition requires
open-sourcing the notebook) and that is Kaggle competition data; a private dataset on the competition
platform, in your own account, is the right home.

### Secondary copies

A USB bundle was made at `~/Desktop/admorphiq_backup_20260831_1541/` before the format (five
tarballs, ~4.4MB, SHA-256 and gzip verified) and copied to `/Volumes/SY/`. The replacement host at
`62.210.150.230` also holds the data with matching hashes. ⚠️ Both are machines and machines vanish —
`ceph-build` did, on the day this was written. **Prefer the Kaggle dataset.**

`models/` (2.3G) is in none of them, deliberately — see §4.

## 3. VERIFY THE RESTORE

```
git clone https://github.com/hyuki0130/Admorphiq.git && cd Admorphiq && uv sync
uv run kaggle datasets download -d jaehyukhyun/admorphiq-envdata --unzip   # §2
ls environment_files | wc -l                 # expect 25
ls environment_files_archive | wc -l         # expect 15 dirs (14 usable — sk48's duplicates the live tree, rule 7ce)
uv run pytest tests/test_wiki_lint.py -q     # cheap smoke
```
⛔ **`ceph-build` NO LONGER EXISTS**, and `ptest.sh` / `pfan.sh` / `snapgate.sh` / `xfergate.sh` /
`ceph_sweep.sh` all defaulted to it. They now take `ADMORPHIQ_REMOTE=user@host` and
`ADMORPHIQ_KEY=~/.ssh/key`, so pointing them at a new box is one environment variable, not an edit.

⭐ **And you can gate WITHOUT a box: `bash scripts/gate_local.sh NAME baseline 2 4000`** — the full
25 on one machine, keeping every refusal the remote gate had (already-used round dir, shadowed
snapshot, fewer than 25 results) plus a **load guard that refuses above the core count**. Verified
end to end 2026-08-31; it is what produced the current card.

⚠️ **PAR 1-2 on the dev host, and that is measured, not cautious.** It is an 8-core M2 and someone
else's `clang` build already held load 11-13, so the guard correctly REFUSED a gate there. On a
64-core box pass 12. ⛔ A gate killed half-way produces a mean over a subset, which this repository
has twice reported as if it were a result.

## 4. WHAT YOU DO NOT NEED

`models/` — 2.3G of behaviour-cloned CNN weights (`bc_policy.pt` v6 and the RL checkpoints).
**Grepped 2026-08-31: neither `notebooks/kaggle_submission.py` nor `kaggle_unified_agent.py` nor
anything under `harness/` or `tools/` references `models/`.** The shipped card is
`KaggleUnifiedAgent` → generic tools, which carry no weights. The BC track was superseded after its
held-out transfer measured **0.00%**. Keep a copy only if you want the history.

## 5. STATE AT THE MOMENT OF THE FORMAT

```
card, full 25 (generic tools)         0.9135   NINETEEN at the 1.0 cap, cumulative regressions 0
shipped wrapper (kaggle_unified)      0.9082   zero games differing  (measured before the bp35 gain)
Kaggle server-side                    all 25 same levels; same TOTAL ACTIONS on all 21 it wins
hidden leaderboard                    0.18     from a DIFFERENT card (detection dispatch, 2026-08-26)
```

⭐ **The two ungated tool edits are now RESOLVED, and the gate split them exactly** — this was
RESTORE.md's "first action on a new box" and it is done:

```
crag.py      KEPT      bp35 0.2456 -> 0.3771, reaching LEVEL 6; card 0.9082 -> 0.9135
fogscout.py  REVERTED  ls20 0.9121 -> 0.7500 — its own docstring claimed "worth a whole level"
```

⛔ Two plausible changes, one working tree, opposite signs, and **nothing but the full-25 gate could
tell them apart**. The losing one carried the confident claim.

⚠️ **STILL OPEN: re-measure the SHIPPED wrapper.** The 0.9082 in the table above is
`AGENT=kaggle_unified` from BEFORE the bp35 gain. `crag` is in the shipped path, so the shipped
number should now be 0.9135 too — but that is an inference, and this repository's own rule is that a
mirror drifts. One command:
```
AGENT=kaggle_unified bash scripts/gate_local.sh shipped2 scripts/rounds/R101CRAGONLY 2 4000
# expect 0.9135 with zero games differing. ⛔ If it differs, the wrapper has drifted from
# _make_agent("unified") — which is exactly how a card once moved 0.20 -> 0.18 unattributably.
```

⛔ **The watchdog cron is cancelled**, so rule **7co** ("every incomplete game has an agent on it, at
all times") does not restart itself. Relaunch the per-game agents deliberately.

**Where to read next**, in this order: `CLAUDE.md`'s top block →
[`.wiki/wiki/campaign/SESSION_END_20260830.md`](.wiki/wiki/campaign/SESSION_END_20260830.md) →
[`.wiki/wiki/campaign/ACTIVE.md`](.wiki/wiki/campaign/ACTIVE.md) →
[`.wiki/wiki/campaign/WHAT_WE_KNOW_ABOUT_THE_110.md`](.wiki/wiki/campaign/WHAT_WE_KNOW_ABOUT_THE_110.md)
→ `OPERATING_RULES.md`'s INDEX BY SITUATION (95 rules; nobody reads it front to back).
