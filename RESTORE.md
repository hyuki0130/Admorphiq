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

⚠️ It is NOT pushed to git because the repo is **PUBLIC** and this is Kaggle competition data.
Redistributing it publicly is a rules question, not a technical one. Keep it in private storage —
the natural home is a **private Kaggle dataset**, using the flow this repo already has for source
(`kaggle datasets version`, see `kaggle/build_and_push.sh`).

## 2. THE BACKUP BUNDLE

Created 2026-08-31 15:41 at `~/Desktop/admorphiq_backup_20260831_1541/`:

```
environment_files_archive.tgz   436K   ⛔ irreplaceable
environment_files.tgz           984K
data.tgz                        2.4M   traces + transitions
scratchpad.tgz                  429K
omc_state.tgz                   157K   session state; not needed to continue
```

⛔ **Copy that directory off this machine before formatting.** Total ~4.4MB. `models/` (2.3G) is
deliberately excluded — see §4.

Restore by unpacking each at the repo root:
```
tar xzf environment_files_archive.tgz -C /path/to/Admorphiq
tar xzf environment_files.tgz         -C /path/to/Admorphiq
tar xzf data.tgz                      -C /path/to/Admorphiq
```

## 3. VERIFY THE RESTORE

```
git clone https://github.com/hyuki0130/Admorphiq.git && cd Admorphiq && uv sync
# unpack the bundle (§2), then:
ls environment_files | wc -l                 # expect 25
ls environment_files_archive | wc -l         # expect 15 dirs (14 usable — sk48's duplicates the live tree, rule 7ce)
uv run pytest tests/test_wiki_lint.py -q     # cheap smoke
```
⛔ **Everything heavier runs on a box, not on the laptop** — `scripts/ptest.sh`, `scripts/pfan.sh`,
`scripts/snapgate.sh`. All three hardcode `ubuntu@ceph-build` and `~/VM/keys/nfw-dev.pem`; **that
host no longer exists**, so a new box must be provisioned and those three edited. Until then there
is no way to gate anything (rule 7m: a PreToolUse hook refuses local game runs, and that hook exists
because three concurrent local suites made the laptop unusable).

## 4. WHAT YOU DO NOT NEED

`models/` — 2.3G of behaviour-cloned CNN weights (`bc_policy.pt` v6 and the RL checkpoints).
**Grepped 2026-08-31: neither `notebooks/kaggle_submission.py` nor `kaggle_unified_agent.py` nor
anything under `harness/` or `tools/` references `models/`.** The shipped card is
`KaggleUnifiedAgent` → generic tools, which carry no weights. The BC track was superseded after its
held-out transfer measured **0.00%**. Keep a copy only if you want the history.

## 5. STATE AT THE MOMENT OF THE FORMAT

```
card, full 25 (generic tools)         0.9082   19 games at the 1.0 cap, cumulative regressions 0
shipped wrapper (kaggle_unified)      0.9082   zero games differing
Kaggle server-side at HEAD            all 25 same levels; same TOTAL ACTIONS on all 21 it wins
hidden leaderboard                    0.18     from a DIFFERENT card (detection dispatch, 2026-08-26)
```

⛔ **HEAD carries UNGATED changes to two shipped tools** (`e165eba7`: `crag.py` +179,
`fogscout.py` +119). **The 0.9082 above describes the tree WITHOUT them.** Gating them, separately,
is the first action on a new box:
```
bash scripts/snapgate.sh cragwip     scripts/rounds/R101SHIPPED 8 4000
bash scripts/snapgate.sh fogscoutwip scripts/rounds/R101SHIPPED 8 4000
```

⛔ **The watchdog cron is cancelled**, so rule **7co** ("every incomplete game has an agent on it, at
all times") does not restart itself. Relaunch the per-game agents deliberately.

**Where to read next**, in this order: `CLAUDE.md`'s top block →
[`.wiki/wiki/campaign/SESSION_END_20260830.md`](.wiki/wiki/campaign/SESSION_END_20260830.md) →
[`.wiki/wiki/campaign/ACTIVE.md`](.wiki/wiki/campaign/ACTIVE.md) →
[`.wiki/wiki/campaign/WHAT_WE_KNOW_ABOUT_THE_110.md`](.wiki/wiki/campaign/WHAT_WE_KNOW_ABOUT_THE_110.md)
→ `OPERATING_RULES.md`'s INDEX BY SITUATION (95 rules; nobody reads it front to back).
