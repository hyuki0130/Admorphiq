---
round: r94
axis: agent25 — adapter-template patching (characteristics→solution game cards)
keywords: [agent25, adapter-template, game-cards, arrangement-core, lp85, s5i5, paired-holdout, upper-bound-gate, structural-delegation, oracle-routing, gptoss-ab]
verdict: CLOSED — gates all passed (upper-bound proof: simdfs card reproduces sb26 8/8 in 131a via the patch sandbox), but BOTH template-transfer arms are refuted on the sk48 holdout. D5 v3: the 75KB family card adapts (626s) into near-inertness (3st/7tr). D5-SKEL (size-controlled): the 8.2KB family SKELETON also adapts cleanly (208.7s, 2 attempts, 0 exec errors) yet stays near-inert (3st/55tr, noop 0.999) while the 6.6KB generic card replicates 71st/309tr a FOURTH deterministic time. FINAL law: on an out-of-family game neither engine size nor compact family mechanics transfers — the generic probe-first template wins; family knowledge helps only when the family actually matches (and sk48 was independently flagged schema-inexpressible by the R95 Codex review). Road forward = generic card + R95 hypothesis-DSL discriminative selection
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
delegates, card 71.5KB. **Parity: 8/8 @0.846 in 170 actions — exact.**

**Self-reproduction gate v1 FAILED — diagnosed in one trace pass (04:23).** Direct-call
trace: refill 1 works end-to-end (*"plan=9 steps (8 clicks)"*) but only 8 clicks execute
and L1 does not clear (**defect 1: a non-click 9th step is dropped** at the plan→act
seam); thereafter the core re-parses the PARTIALLY-SORTED mid-game board every refill and
rejects it forever (*"no plan (transient/unsupported board) → idle-settle"* ×5000)
(**defect 2: the adapter parses the pristine entry board once and runs open-loop; the
stateless core must reconstruct plan-in-flight from the transitions instead of
re-planning mid-flight**). Both are distillation-completeness defects (adapter-local
orchestration again — the D3 gate keeps catching exactly what it exists to catch), NOT
interface ineligibility: the game is static/action-boundary expressible. Fix round
running on the same executor.

## Gate ladder (sb26, chronological — each rung = trace-diagnosed targeted fix)

| rung | sandbox gate result | diagnosis (from instrumented trace) | fix |
|---|---|---|---|
| v1 | 0 levels (plan ran once, then idle forever) | 9th non-click plan step dropped at plan→act seam; mid-game re-parse rejected partially-sorted boards | emit non-click steps; plan-in-flight reconstruction (f09be60) |
| v2 | **L1 cleared** @step ~100, then L2 stall ×2400 steps | pristine L2 ENTRY board rejected ("transient/unsupported") — parse covered L1-style boards only | extract the adapter's real per-level parse acceptance (e099e53) |
| v3 | direct-call clears **L2→L3→L4** (settle→plan→LEVEL UP per level); card path first hit `id` NameError (fixed 46f1738), then stalls at L2 | **run_code's 8-action cap**: 15-step plan chunked at 8; in-flight detection missed the capped prefix → unsound mid-state re-plan → non-terminating 2-click cycle | v4 (in build): reconstruct the ORIGINAL plan deterministically from the level-start board (transitions[0].before), match executed prefix, emit next chunk; no-progress guard |

Adapter parity held 8/8 @0.846 EXACT at every rung (v1/v2/v3 — delegation never broke).
The direct-call multi-level clear proves the extracted ENGINE is complete; the residual
work is purely the stateless-continuation semantics under the sandbox contract.

| **v4** | **PASSED: 8/8 levels in 131 actions, 2.2s** (fewer than the adapter's 170 — the
open-loop plan chunks replay without the adapter's re-checks) | — | cap-proof continuation
(7229844): original-plan-from-level-start + prefix match + next chunk + no-progress guard |

**THE UPPER-BOUND GATE IS PROVEN (2026-07-22 05:56)** — the user's completion requirement
("우리가 클리어하는 게임을 주면 견본만으로 똑같이 완주해야") holds: a conquered-solution
template drives its own game to FULL conquest through the exact pipeline an LLM patch
runs in. Any failure in the D5 holdout is now attributable to the MODEL's adaptation,
not the template or the plumbing.

## D5 PRE-REGISTRATION (frozen 2026-07-22 05:53, before any gate-v4/holdout result)

- **Target**: sk48 (holdout; its adapter/card/constants/wiki/traces excluded from BOTH arms).
- **Arm A**: simdfs card (sb26 conquest template) — FAMILY-MATCHED (sk48 is a
  faithful-sim game; sk48's own partial adapter is sim+A*).
- **Arm B**: toggle card (the R93-proven generic-core template) — deliberately
  FAMILY-MISMATCHED for sk48. There is no matched generic card for the sim family;
  this asymmetry (family-specific reusable algorithmic structure vs generic machinery)
  IS the experiment's variable, per Codex ("sb26 contributes faithful-simulator + DFS
  machinery that the generic tools explicitly lack").
- Patcher: gemma4-31b-it, temp 0, num_predict 8192, one server session, identical budgets
  both arms. Oracle routing (no automatic retrieval in this run).
- Protocol: select-on-adaptation-replay, score once on a fresh instance; level clears
  dominate; exploration metrics tie-break only; PATCH_INVALID reported separately.
- Honest scope: one pair, one patcher — outcome feeds the R94 verdict as ONE experiment,
  not a general law.

## D5 holdout v1 (2026-07-22 09:17) — mismatch arm wins on tie-break; family arm KILLED BY CLIENT TIMEOUT

| arm | template baseline (sk48) | adaptation | fresh score |
|---|---|---|---|
| A simdfs (family-match, 75KB card) | inert (0lv/1st, noop 1.0) | **FAILED at generation — 300.1s = the client's default timeout** | inert (template selected) |
| B toggle (mismatch, 6.6KB card) | inert (0lv/1st) | OK, 114.6s | **0lv / 71st / 309tr** (adapted selected) |

- Surface verdict (frozen prereg, tie-break): **arm B**. Real finding: **TEMPLATE SIZE
  gates adaptability through the time budget** — the family card never received its
  patch (harness config artifact: openai_compat_llm's default timeout=300s), so this
  run does NOT measure family-template value. Per tune-before-discard: v2 with
  HARNESS_PATCH_TIMEOUT=900 (e2c75a9) is the honest re-run.
- Positive sub-finding: the patch loop turned an INERT mismatched template into a live
  explorer on an unseen-family game (1→71 states) — mechanism generality again.
- Deployment note either way: family cards must be SMALLER (a distilled family card ≪
  the full engine card) — a real R94 design input independent of the v2 outcome.
- Artifacts: `scripts/rounds/R94/r94_holdout_*_v1.json`.

## D5 v2 (2026-07-22 10:33) — toggle arm replicates exactly; simdfs arm hit a 3rd harness bug

toggle arm: identical to v1 (adapted 71st/309tr, deterministic ×2). simdfs arm: crashed
BEFORE its adaptation ask — `_card_prelude` called `fn.__name__` on the simdfs
registry's raw-source STRING entries (AttributeError ~20min in). Fixed b7b703f
(string-tolerant prelude; regression test pins prelude assembly for every registered
card). **The 900s-timeout question is still unmeasured** — v3 (pushed 10:36) is the run
that finally answers whether the family card adapts and beats the mismatch arm.

## D5 v3 FINAL (2026-07-22 11:57) — clean measurement; full-engine template REFUTED on this pair

| arm | adaptation | adapted performance (fresh score) | verdict |
|---|---|---|---|
| A simdfs (family-match, 75KB) | **SUCCEEDED, 626s** (< 900s — the v1 timeout diagnosis was right) | **3 states / 7 transitions / noop 1.0 — near-inert** | loses |
| B toggle (mismatch, 6.6KB) | 115s | 71 states / 309 transitions (×3 deterministic) | **WINS** |

- Both arms executed end-to-end with zero harness failures — the first clean D5
  measurement (after 2 harness-defect rounds: client timeout, prelude string entries).
- **Outcome (b) of the pre-registered scenarios: adapts + loses.** The 75KB of
  sb26-specific machinery, even when the model successfully edits it, produces
  near-inert behaviour on sk48 (its clicks land nowhere); the small generic card is
  vastly more adaptable. Family MATCH did not overcome template BULK/SPECIFICITY.
- **PRIMARY design law (supported by both the timeout episode and this clean result):
  template size/specificity dominates family match — family templates must be
  distilled SMALL** (a compact family skeleton: the mechanics idea + minimal scaffolding,
  not the full engine). This vindicates the user's 특징→해결법 game-CARD framing over
  full-adapter provision.
- Caveats per prereg: one pair, one patcher, single trajectory — one experiment, not a
  law. The natural next test: a ~5-10KB distilled simdfs SKELETON vs the same toggle
  control on sk48.
- Artifacts: `scripts/rounds/R94/r94_holdout_*_v3.json`.

## D5-SKEL PRE-REGISTRATION (frozen 2026-07-22 12:03, before any skeleton result)

D5 confounded SIZE with FAMILY (75KB family vs 6.6KB generic). The size-controlled
follow-up de-confounds:
- **Arm A′**: `simdfs_skel` — a COMPACT family skeleton card (target 5-10KB): the
  mechanics IDEA (minimal piece/slot parse → tiny move simulator → DFS toward a
  sorted/goal state) with minimal scaffolding. NOT required to reproduce sb26's
  conquest (it is deliberately minimal); required only to be sandbox-executable and
  produce SOME actions on a synthetic board (smoke gate).
- **Arm B**: toggle card (6.6KB, unchanged control — same as D5).
- Same everything else: sk48 target (holdout rules), gemma4 patcher, budgets, frozen
  selection/scoring. Claim under test: **at comparable template size, does family
  mechanics knowledge beat mismatched machinery?** Win condition per the same
  lexicographic rule; B's benchmark to beat = 71st/309tr.

## D5-SKEL FINAL (2026-07-22 13:51 collection) — family skeleton ALSO loses; round CLOSED

Kernel `admorphiq-r94-holdout-gemma4` v4 (launched 12:15, COMPLETE ~13:45; artifacts
`scripts/rounds/R94/r94_holdout_bench_skel.json` + per-arm JSONs). Both arms adapted
successfully — this is a clean capability measurement, not a harness failure:

| arm | card | adapt | replay = fresh (deterministic) | noop |
|---|---|---|---|---|
| A′ simdfs_skel (family skeleton) | 8.2KB | 208.7s, attempts=2, 0 exec errors | 0 levels, **3st/55tr** | **0.999** |
| B toggle (generic control) | 6.6KB | 114.6s, attempts=1 | 0 levels, **71st/309tr** | 0.684 |

Frozen-prereg verdict (levels tie 0-0 → exploration tie-break): **arm B — the
family skeleton LOSES the size-controlled comparison.** gemma4's adaptation was
real (raised `_SKEL_MOVABLE_MAX_SIZE` to 25, restructured move-learning with a
click-on-piece heuristic) and executed cleanly, but the skeleton's family
assumptions (piece/slot parse → click-to-move → DFS assignment) never engage
sk48's directional-snake mechanics: 1998 of 2000 actions were no-ops.

**Combined D5 + D5-SKEL law (final)**: on an out-of-family holdout, NEITHER the
full family engine (75KB) NOR its compact skeleton (8.2KB) transfers — the
generic probe-first template wins at every size. The earlier "size dominates"
read was incomplete: size explained the 75KB card's failure mode (inert
machinery), but the skeleton shows family MECHANICS content itself is dead
weight when the family does not match. Caveats per the R95 Codex review: sk48
exploration deltas are CONTROL evidence (0 levels everywhere), and sk48 was
independently flagged schema/family-inexpressible — so this refutes "hand any
family card to the model and it adapts across families", NOT "family cards
never help in-family" (untested here; in-family reproduction DID pass via the
sb26 upper-bound gate).

**Road forward** (already designed + Codex-consulted while this ran):
`docs/design_hypothesis_dsl_r95.md` v2.6 — generic card stays the template
baseline; the model's game-understanding channel moves to the hypothesis DSL
(R95a discriminative selection on ft09+sc25, oracle-first, both models), with
the 5-tier fallback ladder (self-extension → fork-and-patch → generic floor).

## Continuation (round CLOSED — successor round owns these)

The historical "in flight" items resolved before close: the D3/upper-bound gate
passed via the sb26 simdfs card (gate ladder above); the gpt-oss-120b A/B ran as
the R93 breadth bench (see [[r93_tool-fork-patch]] — 9/15 at reasoning-HIGH, no
nomination under the paired protocol). The s5i5 arrangement-pair holdout was
superseded by the D5/D5-SKEL sk48 measurements recorded above.

Successor: the R95 hypothesis-DSL round (`docs/design_hypothesis_dsl_r95.md`,
designed + twice Codex-consulted while D5-SKEL ran) — R95a discriminative
selection on ft09+sc25 with oracle + historically-falsified hard negatives,
5-tier fallback ladder, two-model comparison rule.

## Related

- [[r93_tool-fork-patch]] (the surviving thesis this builds on)
- [[r56_generic-kernels]] (kernel library) · `memory/project_r56_r58_state.md`
