---
round: R101SHIPPED / R101XFER10
axis: measure the CARD AS SHIPPED, and measure how much of it survives a board that is rendered differently
keywords: [shipped, kaggle_unified, submission-path, snapgate, AGENT, transfer, re-render, archived-hash, xfergate, brittleness, generalisation, duplicate-game-id, instrument-gap]
verdict: BOTH MEASURED CLEAN — the shipped wrapper scores 0.9082 with ZERO games differing from the bench member, and 24 of 25 games are action-for-action IDENTICAL on an archived re-render (ratio 0.9989, only s5i5 L4 moving 39 -> 61 actions). Two instrument gaps closed: the gate could not take an agent argument, and the transfer procedure had never been recorded.
commit: 61864302, f407fa04
supersedes: the "gains reach the submission path" note in [[r101_conquest-wave]], which measured 0.9069 through an ad-hoc invocation rather than the gate
---

# R101 — the card as shipped, and what survives a re-render

> Two numbers that the campaign had been quoting without ever measuring properly. The first is
> whether the thing that SHIPS scores what the bench scores. The second is whether the tools read
> mechanics or pixels. Both came back clean — and both had been blocked not by the work but by
> instruments that could not express the question.

## Why neither had been measured

⛔ **CLAUDE.md has carried the instruction "measure the card AS SHIPPED (`--agent kaggle_unified`),
not as benched (`--agent unified`) — they are different configurations" for days, and
`scripts/snapgate.sh` hardcoded `--agent unified`.** The rule was correct, load-bearing, and named
a flag the runner would not accept. That is the same failure shape as the guards in
[[r101_conquest-wave]]: written discipline the commands do not support gets skipped, and afterwards
it looks like carelessness. `AGENT=` now overrides it (rule **7bv**).

⛔ **The transfer number had been measured at least three times** — `R101XFER9` recorded ratio
0.9981, 13 of 14 identical — **and the procedure was never recorded.** The round dirs hold `games/`
and no `run.sh`, so every re-measurement rebuilt the substitution by hand. That is precisely the
failure that made the 0.20 card unrebuildable and had to be recovered by grepping a round page.
`scripts/xfergate.sh` is the procedure, committed (rule **7by**).

## The card as shipped

```
AGENT=kaggle_unified bash scripts/snapgate.sh shipped scripts/rounds/R101LF52PART 12 4000

MEAN new = 0.9082 over 25      MEAN old = 0.9082 over 25      no game regressed
canaries hold at 1.0000: re86, sc25, tu93, sb26
19 of 25 at the cap.  bp35 0.2456 · lf52 0.2727 · s5i5 0.5833 · dc22 0.7143 · ls20 0.9121 · lp85 0.9767
```

⭐ **The wrapper has not drifted from the bench member it mirrors, and every gain of this campaign
is in the notebook.** `notebooks/kaggle_submission.py` registers `KaggleUnifiedAgent` (commit
`f1067554`).

⚠️ **And CLAUDE.md said otherwise in two places, for days** — "ships `KaggleDetectAgent` — grep it
for `UnifiedAgent` and you get ZERO", and "the submission path is … `KaggleChainedAgent`". A fresh
session reading either would have re-done a switch that was already made, and one of them framed it
as an open user decision. Both corrected. **A document that describes the code is an instrument, and
it fails toward the past.**

## What survives a re-render

`bash scripts/xfergate.sh xfer10 scripts/rounds/R101SHIPPED 12 4000` substitutes all fifteen
archived version hashes — the same games re-rendered with different sprite tags and coordinates —
into a private snapshot and scores the full 25.

```
MEAN archived 0.9072      MEAN live 0.9082      ratio 0.9989

ONE game differs in the whole set:   s5i5   0.5833 -> 0.5593
  and inside it, ONE level:          L4     39 -> 61 actions   (still CLEARS, 1.0 -> 0.7837)
  L1 13 · L2 30 · L3 47 · L5 32 · L6 31   identical, as is every level of every other game
```

⭐ **Twenty-four of twenty-five games score identically, action for action, on a differently
rendered board.** The ten games with no archived hash run live in both arms — they are the
instrument's own determinism control, and they are identical too. This is the best transfer number
the repository has recorded.

⚠️ **Stated plainly so it is not oversold: a re-render is the SAME GAME.** It proves the tools read
MECHANICS rather than memorised pixels — a floor on brittleness — and it does not predict a game we
have never seen, which is what all 110 private games are. ⛔ Do not quote 0.9989 as a transfer
coefficient for the leaderboard; the hidden score of the generic path remains UNMEASURED.

## Three instrument traps, all in one direction

⛔ **`game_id` IS NOT PROVENANCE.** Both s5i5 arms declare `s5i5-18d95033` although the content
differs, and `score_efficiency.py`'s `--titles` filter dedupes on exactly that field — so the
artefact cannot tell you which board it scored. Only the procedure can, which is the argument for
committing the procedure.

⛔ **The duplicate-`game_id` hazard from `r59s15` HAD RECURRED** (rule **7bu**): ceph-build's
`environment_files/sk48` held two version dirs, 44925 vs 44840 bytes, both declaring
`sk48-d8078629`, where the Mac holds one. The loader keeps whichever `rglob` yields first. ⭐ **And
it was INERT** — both arms score 1.0000 with the SAME action count on all eight levels
(14·30·34·27·41·56·41·27), so no gate was corrupted. Archived anyway; both machines back to 25.
**The rule is the order: a discrepancy is not yet a defect — run the arm that prices it before
writing it down.** Recording "the box loads a different sk48, the number is suspect" the moment the
md5s diverged would have thrown unmeasured doubt over every gate this week.

⛔ **`compare.py` says "REGRESSED" and it is the wrong word in a transfer run.** Its language is a
GATE's: refuse a CODE change that costs a game. Here the code is fixed and the BOARD changed, so a
lower score means *failed to transfer*, not *regressed* — and the two call for opposite responses
(investigate the tool's board-reading vs revert). `xfergate.sh` prints the correction under the
verdict. **An instrument borrowed from another question answers the question it was built for.**

⚠️ A fourth, smaller: four suite failures on the box were the ptest snapshot missing `.wiki` and
`kaggle`, not breakage. **A directory omitted from the archive is indistinguishable from a directory
deleted from the repo** — the third time in this campaign, after `data/traces` twice.

## What is open

- **s5i5 L4 is the only render-dependent thing in the whole 25.** 22 extra actions on a re-rendered
  board of the same level. It is worth 0.0240 of dev score and far more as a defect class: the eval
  is 110 games rendered differently from anything here. Under investigation.
- **Ten games have NO archived hash** — bp35, cd82, ft09, g50t, lf52, lp85, ls20, sb26, tr87, wa30 —
  so they have zero transfer evidence of any kind, and four are among the six still short of the
  cap. A render-mutation instrument that manufactures the re-render (AST identifier rename, colour
  permutation, board offset) is being built; ⛔ its hard part is not the mutation but proving the
  mutation preserves the MECHANIC, because a broken mutation is indistinguishable from a transfer
  failure.
- **The hidden score of the generic path.** ⭐ **CLOSED ON THE PROXY SIDE, 2026-08-30** (rule
  **7bz**): kernel version 5 ran server-side at HEAD, logged `Registered agent 'admorphiq' ->
  KaggleUnifiedAgent`, and reproduced the local card on **all 25 games — same levels, and the same
  TOTAL ACTION COUNT on every one of the 21 it wins**. The four it does not win reach the same level
  and differ only in how much larger budget they spend afterwards. So the chain local gate → shipped
  wrapper → Kaggle's own machine is closed end to end, each link measured. ⚠️ It says NOTHING about
  the hidden 110. ⛔ The submission itself is the user's call and no `--submit` is passed
  automatically. Artefacts: `scripts/rounds/R101KAGGLE/`.
- ⛔ **The kernel log also corrects the sk48 cleanup above**: Kaggle serves
  `environment_files/sk48/d8078629`, which is the directory archived off ceph-build as "the
  duplicate". Harmless — 270 actions there and 270 locally, a third confirmation of equivalence —
  but the local layout names directories by DOWNLOAD id and Kaggle names them by GAME hash, so check
  the kernel log before deciding which of two version dirs is stale.

## Related

Three pages this round's subject makes reachable again — each had NO inbound link and was therefore
invisible to the retriever's backlink walk, which is the same as not existing at runtime:
[[card_portability]] (what "the card travels" means and how it was measured),
[[generic_tools_are_shippable_20260828]] (the lesson this round's shipped-gate confirms), and
[[probe_cost_vs_human_baseline]] (why an action spent probing is an action spent against the human
denominator).


[[r101_conquest-wave]] · [[r101_tenure-end]] · [[r101_tool-development]] · [[r101_silent-specialists]]
· [[r101_discarded-band]] · [[r101_inert-actions]] · [[r101_allowance-ledger]] · [[campaign/ACTIVE]]
· [[r101_llm-on-a-gpu]] — the other half of "does the shipped path have anything left in it":
the model in the loop is measured INERT on these 25, so this round's 0.9082 is tools and
signature routing alone.

⭐ [[r101_render-mutation-transfer]] extends this measurement to the games with no archive by
MANUFACTURING the re-render (rule 7ce), and corrects one number here: the archive covers
**fourteen** games, not fifteen — `environment_files_archive/sk48` is the same version hash as
the live tree, byte-identical, so substituting it substitutes a game for itself.
