---
round: r94
axis: agent25 — adapter-template patching (characteristics→solution game cards)
keywords: [agent25, adapter-template, game-cards, arrangement-core, lp85, s5i5, paired-holdout, upper-bound-gate, structural-delegation, oracle-routing, gptoss-ab]
verdict: IN PROGRESS — D1 parity gate PASSED (delegated lp85 reproduces 8/8 @0.6992 exactly); D3 sandbox upper-bound + gpt-oss A/B running
commit: 07c81eb
---

# R94 — adapter-template patching: give the LLM our conquests as editable guides

> R93 proved the model can repair OUR code when given the source + failure evidence
> (paint×cd82 PATCH_WINS ×2). R94 tests the user's escalation: hand it not just generic
> tool cores but the CONQUERED per-game solutions — "어댑터는 힌트/가이드; 게임별 특징과
> 해결법을 제시하고, 필요한 건 수정하거나 추가해서 해결하라" — matched by observable
> characteristics, never by game id.

## Design authority

- **User directives (2026-07-22 00:19–00:32)**: (1) adapters as patch templates; (2) per-game
  guide cards = 특징(observable characteristics)→해결법(solution method: which tools/kernels,
  how) — id-blind, matching runs on features; (3) upper-bound completion check — given the
  verbatim conquered solution, the pipeline must complete that game; (4) helper library note:
  curated per-family helper sets (R92 measured that a full catalog DROPS usage 23→2).
- **Codex review (2026-07-22 01:09, gpt-5.6-sol) — approved MINIMUM, ranked**:
  1. ONE clean paired holdout experiment: adapter-family template vs generic-core template,
     everything else identical. "Without this, R94 answers nothing."
  2. ONE structurally-delegated family core (live-score parity alone insufficient — R93's
     probe-order drift proved it; refactor only the family entering the experiment).
  3. FULL verbatim upper-bound gate (exact conquest reproduction, not a fraction).
  4. Minimal card/signature; ORACLE routing first, automatic routing a separate condition.
     Target's card/adapter/constants/wiki/traces held out.
  5. Tiny Stage A shakedown (pipeline check, not evidence).
  - CUT: patch iteration 2 (cost+confounding), 4-6 family catalog, 25 polished cards.
  - Selection: level clears dominate; select on adaptation replay, score once on a fresh
    locked instance; generic baseline gets identical budgets.

## Family pair (decided by wiki mechanism scan)

**Source: lp85** (8/8 @0.6992 conquest — learn per-button marker-movement effects →
permutation planning). **Holdout target: s5i5** (click-only slider: slide a track's goal
marker ±1 along an axis to its target — same constrained-1D-arrangement family; currently
1/8, headroom real). Rejected ft09→vc33: the generic toggle core is already a GF(2) solver,
so the template-vs-generic differentiation would be weak.

## D1 — arrangement family core (commit 07c81eb) + parity gate PASSED

- `src/admorphiq/kernels/arrangement.py`: lp85's load-bearing engine extracted
  (button-effect learning `arrangement_learn_button`, permutation planning
  `arrangement_plan`, full-pipeline `arrangement_core`) as sandbox-runnable fns; the lp85
  adapter now structurally DELEGATES its learning + mp/cb planning to them (byte-equivalent
  extraction). `source_card("arrangement")` = 34KB real source incl. stdlib-only kernel
  primitives; GAME-SPECIFIC PRIORS emitted under a RE-DERIVE header (`_CARD_CONST_HEADERS`
  — name=value emission drops source comments). Sandbox builtins += frozenset/repr.
- **Parity gate (ceph-build, script25 driver, 2026-07-22 02:04)**:
  `levels=8/8 actions=300 game_score=0.6992` — the delegated adapter reproduces the
  conquest EXACTLY (to four decimals). Artifacts: `scripts/rounds/R94/lp85_parity/` on
  ceph-build. (First launch used `--agent graph_frontier` by mistake — that is the generic
  agent, NOT the adapter path; its 1/8 is meaningless for this gate. script25.py is the
  adapter driver, and its `--out` takes a DIRECTORY.)

## D3 upper-bound gate — FAILING as designed to catch (2026-07-22 03:05 interim)

The verbatim `source_card("arrangement")` driven through the run_code sandbox on lp85 is
at **0 levels by step 750+** (the delegated adapter: 8/8 in 300). Root cause read from
the core: it does SINGLE-press learning + "probe next unpressed control", but the
conquest's load-bearing orchestration is **press-until-certify / adaptive-K** (press the
SAME button repeatedly until its ring's effect map certifies) — and that stayed
ADAPTER-LOCAL. The bare core is a token-slice template; Codex's exact D3 rationale
("if the supplied source solution cannot reproduce its own conquest, STOP") fired
correctly on the first try. The paired experiment is BLOCKED until the core carries the
certify orchestration — extension build in flight (extract the adapter's real
press-until-certify policy into the core, preserve 8/8 adapter parity by construction,
re-run D3). Note the meta-lesson: D1's live-score parity PASSED while D3 caught the
slice — the two gates test different things (adapter parity ≠ template drivability),
Codex's layering was right.

## Certify-orchestration extraction (97be189) — adapter parity v2 PASSED

The D3-fail fix: press-until-certify (per-button evidence accumulation across ALL its
presses, series learning, certify gate with the adapter's adaptive press cap, re-press
least-pressed uncertified control) extracted INTO the core; adapter delegates to the same
functions. **Parity v2: 8/8 @0.6992 exact** — extraction preserved behaviour. Card now 47.5KB.

**Upper-bound gate v2 FAILED (03:53)**: verbatim certified card via the sandbox on lp85
@2000 = 0 levels / 13 states / **noop 0.97** (exec clean — the code runs, its clicks land
nowhere). Worse exploration than v1 (50 states): the certify loop re-presses what it
believes are controls, but they are no-ops. Since the SAME functions clear 8/8 inside the
adapter, the defect is at the I/O seam — and the direct-call trace diagnostic (core
invoked OUTSIDE the sandbox on the same dict input; same result → NOT sandbox mechanics)
pinned it structurally:

1. **Button detection drifts on an animating game** — the tracked "control" key slides
   (0,32)→(0,34)→(0,36)→(0,39)→(0,42) across refills: a MOVING marker is re-detected as a
   button each frame, and the certify loop chases it with no-op clicks (noop 0.97).
2. **`learned 0 effect-map(s)` permanently** — lp85's conquest learner is TIME-SERIES
   based (frames sampled DURING press runs, `_extract_frames_at`); the sandbox contract
   provides per-action before/after pairs, which animation contaminates → nothing learns.

**Conclusion: interface-capability mismatch, not extraction quality.** lp85 (an animating,
time-series-dependent conquest) was the wrong SOURCE pick for the per-action
before/after sandbox contract.

**Codex re-pair verdict (FROZEN 2026-07-22 04:00, before any further outcomes):**
- **Pair = sb26 (source, 8/8 @0.846 portal-sort, faithful-simulator+DFS engine) →
  sk48 (holdout, same faithful-sim family, currently 3/8 — real headroom).**
- lp85 recorded as **PAIR-INELIGIBLE** (not an extraction failure): its decisive
  information lives in intra-action time series; adapter parity tested a strictly
  stronger interface. **Eligibility rule (frozen): the source conquest must be
  expressible through action-boundary observations.**
- Sandbox contract UNTOUCHED (enriching it mid-experiment would confound template
  quality with contract change); frame-series support = separate follow-up experiment.
- Differentiation is cleaner than lp85's: generic tools have NO simulator+DFS machinery.
- Source self-reproduction preflight (sandbox path) required before the holdout gate.

## sb26 simdfs distillation (2b85b6b) — parity PASSED; self-reproduction gate running

Eligibility pre-check passed (portal-sort static between actions). Engine extracted to
`kernels/simdfs.py` (frame→board parse → faithful simulator → DFS → click plan), adapter
delegates, card 71.5KB. **Parity: 8/8 @0.846 in 170 actions — exact.** Sandbox
self-reproduction gate (the one lp85 failed twice) in flight.

## In flight

- **D3 upper-bound gate**: verbatim arrangement card driven through the run_code sandbox
  (exact patch-arm path) on lp85 @2000 — conquest must reproduce through the pipeline an
  LLM patch would use.
- **gpt-oss-120b A/B** (`admorphiq-r93-patchloop-gptoss` v1): the R93 2-case bench on the
  120B reasoner, offline harmony vocab verified. Key read: does it avoid gemma4's WRONG
  toggle diagnosis (row/column diffs mistaken for stencils)? If yes, reasoning capability
  is the patch-quality bottleneck and the bigger model earns a place as the patcher.

## Next

1. D3 result → if the conquest reproduces, build the D2 minimal arrangement card
   (characteristics/signature + solution method) with s5i5 artifacts held out.
2. D5 paired holdout: s5i5 ×2 arms (arrangement-template vs generic-core template), oracle
   routing, identical budgets; level clears decide.
3. gpt-oss verdict → patcher-model choice for the paired experiment.

## Related

- [[r93_tool-fork-patch]] (the surviving thesis this builds on)
- [[r56_generic-kernels]] (kernel library) · `memory/project_r56_r58_state.md`
