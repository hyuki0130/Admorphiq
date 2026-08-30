---
type: campaign
description: Where everything stood when the 2026-08-30 session was halted — what is committed, what is UNGATED in HEAD, what each per-game agent left behind, and the two things that must happen before any further work.
---

# Session end — 2026-08-30 16:35 KST

> Halted by the user. The watchdog cron is **cancelled**, all nine agents are dead, the box is clean,
> and the working tree is committed. This page is what a fresh session needs before it touches
> anything, because two of the facts below are dangerous if missed.

## ⛔ THE TWO THINGS TO KNOW BEFORE ANY WORK

**1. HEAD CONTAINS UNGATED CHANGES TO TWO SHIPPED TOOLS.** Commit `e165eba7`:

```
src/admorphiq/tools/crag.py      +179   copy-on-write search view, _MAX_EDITS, a _reanchor path
src/admorphiq/tools/fogscout.py  +119   cross-level mechanic carry (claims "worth a whole level")
```

⛔ **No full-25 gate has been run on either.** They were in the working tree when the session limit
killed all nine agents at once, and they are committed so the work is not lost at the next checkout
— **not because either is accepted**. The card as last measured is **0.9082**
(`scripts/rounds/R101SHIPPED`), and that number describes the tree WITHOUT them.

⚠️ fogscout's claim is the agent's own probe (`scripts/_ls20_carry.py`, six arms), and ls20's entire
remaining prize is **+0.0035** — a claim that large against a gap that small is exactly what rule
7aj exists to check. ⚠️ And `fogscout.reset` runs at every level-up and on every switch to the tool,
so cross-level carry touches every game it ever holds, not only ls20.

⭐ **The first action of the next session is to gate them, separately:**
```
bash scripts/snapgate.sh cragwip     scripts/rounds/R101SHIPPED 8 4000
bash scripts/snapgate.sh fogscoutwip scripts/rounds/R101SHIPPED 8 4000
```
If either regresses a game, revert that one. Thirteen repairs have been built, measured and reverted
in this campaign, and rule 7o's precedent is exact: `frame_2d` really did read a stale layer at 100%
of level transitions in all 21 games, and fixing that correct diagnosis cost **0.8962 → 0.6525
across fourteen games**.

**2. THE WATCHDOG CRON IS CANCELLED** (job `bbe6c06e`, user instruction 16:24). Rule **7co** says
every incomplete game has an agent on it at all times — **that rule cannot restart itself now.**
Whoever resumes must relaunch the per-game agents deliberately.

## The card, unchanged

| | |
|---|---|
| full 25, generic tools | **0.9082**, 19 at the 1.0 cap, cumulative regressions 0 |
| shipped wrapper (`AGENT=kaggle_unified`) | 0.9082, zero games differing |
| Kaggle server-side at HEAD | same levels on all 25; same TOTAL ACTIONS on all 21 it wins |
| hidden leaderboard | **0.18** (2026-08-26, detection dispatch — a DIFFERENT card) |

⛔ **The generic path at 0.9082 has never been submitted.** The build is committed and verified
(`bash kaggle/build_and_push.sh`, `--submit` never passed automatically). **Submission is the
user's call.**

## Per-game state and what each agent left

Six were incomplete at the halt; **lp85 closed during the session**.

```
bp35  0.2456  +0.0302   2 agents (dynamics + perception).  Rule 7cr written: crag learns
                        volatility only AFTER a stitch succeeds.  crag.py WIP is UNGATED.
                        Probes: _bp35_arms · _bp35_l6_place · _bp35_l6_stitch · _bp35_l6_solve
lf52  0.2727  +0.0291   2 agents.  ⭐ lf52 is ONE OF ONLY TWO games where routing recovers
                        anything (7cq: `hop` +0.0909 on the ablated board).  47 sweep results
                        banked in R101ABLATELF52WALL, UNINTERPRETED.
                        Probes: _lf52_l6_dump · _lf52_l6_hold · _lf52_l6_plan
s5i5  0.5833  +0.0167   2 agents.  telescope commits the rider set ONCE per level on the OPENING
                        frame (7cn) — if that commitment is wrong on L7, nothing later can fix it.
                        Probes: _s5i5_l7 · _s5i5_l7b · _s5i5c_joint · _s5i5c_ongrid
dc22  0.7143  +0.0114   2 agents.  ONE LEVEL FROM THE END — best prize-to-distance in the corpus.
                        Probes: _dc22_l6_dump · _dc22_l6_oracle · _dc22_l6live · _dc22_l6plan ·
                        _dc22_l6walk · _dc22_missing · _dc22_mixedtile
ls20  0.9121  +0.0035   1 agent.  fogscout WIP is UNGATED and claims a whole level.
                        Probes: _ls20_carry · _ls20_panel · _ls20_passive
lp85  0.9767  +0.0009   ⛔ CLOSED WITH A PROOF (7cm-era work, rule in R101LP85CAP): with a
                        converged model the level costs EIGHT actions — half the human baseline —
                        and the probes are positionally net-neutral, so it is never a planning
                        problem.  The confirmations cannot be cut AT ALL: plan_presses returns
                        None at every propose until press 10 is learned, so every re-press happens
                        BECAUSE there is no plan.  Two-action problem or nothing.
```

⚠️ Every probe above is committed as an INSTRUMENT (`28fe45cb`), not as a result. None of their
findings is accepted; a probe is evidence only once its numbers reproduce a banked count and both
controls are carried.

## What the day established about the 110

Full synthesis with boundaries per claim: [[WHAT_WE_KNOW_ABOUT_THE_110]]. The four that change what
to build next:

- ⭐ **Remove each game's owner and 0.9082 → 0.1932** (7cj). Quote the PAIR — `~0.0014` is the
  analogue of *no tool fits*, `0.1932` of *adjacent to something we implement*.
- ⭐ **CAPABILITY, not routing** (7cq, 1175 runs): a perfect oracle over surviving tools recovers
  **0.5%**. In 21 of 25 the best solo tool scores EXACTLY the ablated harness; on 10 of 25 nothing
  in the registry clears level 1 without the owner. **Ownership is EXCLUSIVE.**
- ⭐ **The failure is SILENT** (7cj): a frontier explorer always proposes and always reaches a new
  state, so it satisfies every signal the harness watches while clearing nothing. `_PRIMARY_CONF` is
  REFUTED as the cause; the latch belongs to the fallback POSITION.
- ⭐ **A live LLM on a GPU is byte-identical to no LLM** (7ch) — with controls proving the model
  served 38 completions and drew targets. ⚠️ It does not say an LLM is useless; it says **these 25
  cannot measure it**, because nineteen sit at the cap.

## The session's own numbers

202 commits, rules **7bt → 7cr** (95 numbered rules in the file), nine agents, ~20 round dirs. Three
instruments built and committed: `scripts/xfergate.sh`, `scripts/zordergate.sh`, `ablate_run.py`.

⛔ **And the honest half**: the card did not move today. 0.9082 at the start, 0.9082 at the halt.
What moved is the MAP — what transfers, what does not, and which questions the public 25 are
structurally unable to answer.

## Related

[[WHAT_WE_KNOW_ABOUT_THE_110]] · [[ACTIVE]] · [[r101_shipped-and-transfer]] · [[r101_owner-ablation]]
· [[r101_llm-on-a-gpu]] · [[r101_lost-signal]] · [[r101_visibility-identity-census]]
