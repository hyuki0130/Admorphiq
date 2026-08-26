---
name: project_r56_r58_state
description: "R56-R58 state (2026-07-15 dawn): generic kernel library + script25 adapters (ft09 3/6 super-human, sb26 first live clear), win-condition typology + GoalLedger, explanation-layer protocol; Codex verdicts list; VM/engagement runs in flight"
metadata: 
  node_type: memory
  type: project
  originSessionId: 3f835f42-61d8-4a15-811f-a74e74370d28
---

**R56-R58 sprint state as of 2026-07-15 ~03:30 KST** (one overnight session; consult
`.wiki/wiki/rounds/r56_generic-kernels.md`, `r57_win-condition-typology.md`,
`r58_explanation-layer.md` for full provenance — they are kept current).

**Architecture (Codex-ruled, docs/r56_codex_toolbase_verdict_20260715.md):** solver-card
25/25 rejected (transfer 13%); instead: namespace-safe generic KERNEL library
(`src/admorphiq/kernels/`, 9 modules/45 exports/134 tests) + quarantined per-game adapters
(`src/admorphiq/adapters25/`, model-NEVER-visible, import-whitelist AST+import-smoke lint)
composing ONLY kernels = **script25 expressiveness scoreboard** (`scripts/script25.py`,
reuses score_efficiency's RHAE loop via adapter_factory). agent25 (LLM with same kernels)
is the promotion metric; script25 never reported as agent capability.

**script25 results (as of ~04:50 KST):** **ft09 6/6 = 100% game_score, 88 total actions,
every level at the 1.0 cap** (95c27c4) — the first fully-conquered game: GLYPH DECODE (win
condition READ from frame: ring center glyph = 3x3 compass target map; ink0=equal marker,
ink2=NOT-equal, ink3=no-cell, ALL covering glyphs' full 8-reach simultaneously; measured
colour cycles; control glyphs with ink-stencil cross-toggles solved via GF(2); L5's 21
actions exactly match the Codex-predicted click count). **tr87 3/6 at ALL-1.0** (362c672,
was the 0/6 wall): frame-only grammar pipeline + dial executor, flagged L4-L6 fail safely.
sb26 3/8 (0.1446; L4 icon-behavior discriminator falsified, banked). vc33 1/7 (NEW
mechanic: escalating click-counter with decoy penalty — commit-beats-round-robin). dc22
0/6 (walk/stuck/probe/learn loop, primitives live-verified; seesaw re-click iteration in
flight). su15 0/9 (6 falsification iterations; near-merge 1.9px). ka59 0/7 (push WORKS —
measured wall-crossing — but joint planning gap; banked). **Late-night updates:** lp85 1/8 at NEAR-HUMAN efficiency (18a vs 17 human, 2.48% —
granularity root cause: functionally distinct pixels inside one region, centroid was
never one of them; round-robin base ordering + local-focus, f4e8b11). m0r0 1/6 (joint-
state configuration_path planner with sticky plan buffering — desync-capable; b9b35cd).
tu93 2/9@3000 baseline (slide-until-CORRIDOR-BEND mechanic; corridor prediction plateaus
21% — connectivity-graph bug is the reopen pointer; 9e7f474). dc22 BANKED 0/6 (proactive
state-gated win check outside reactive walk-stuck-probe — divergence table recorded;
b36fd8a). sp80: move+TRANSFORM mechanic (action5 recolors = clears L0); position
hypothesis falsified, count hypothesis probing. su15 perception bugs found (fragmented
bowtie sprites + scatter-colour contamination silently deleting real tiles) — gap-
parameter fix in flight. **Full-budget verdicts (VM): su15 0/9@4121 (mechanic-level,
not budget), old-ft09/m0r0/lp85 0s superseded by the above.** VM `r56-cpu` (e2-standard-8
spot, asia-east1-a — ewm-bench VM was DELETED; recreate CPU spots as needed, ~2h/game
at 10k). Gold-replay divergence analysis = the night's master diagnostic method.

**R57:** win-condition typology docs/r57_win_condition_typology_20260715.md — 8 types,
24 frame-verified games, 67 level-up events (data/traces/*.npz; data/transitions lacks
level labels — unusable for this).

**R58 (explanation layer, docs/r58_codex_explanation_layer_20260715.md):** protocol
compiler NOT bigger wiki — SELECT->FILL->auto-COMPUTE->CONSUME->VERIFY enforced state
machine (`src/admorphiq/explanation/protocol.py`, Navigation Slice v0 committed),
playbook/schema/packet token budgets, GoalLedger (goal_ledger.py) with three measured
tuning rounds (TOPK 57->76%, zero coverage regressions) and a Codex redesign verdict
(docs/r58_codex_ledger_ranking_20260715.md): evidence TIERS (predicate/behavioral/
affordance) + footprint dependency relations, replace pattern_match with canvas/lattice
detector, TOP1 demoted — rebuild in flight.

**R56 OFFICIAL closing measurement (r56s4, VM, HEAD code, 5000a full budget, 2026-07-15
~12:00 KST):** ft09 6/6=1.0000 (88a — Mac smoke reproduced exactly), tr87 3/6=0.2857
(503a), sb26 3/8=0.1446, lp85 1/8=0.0248, m0r0 1/6=0.0057, vc33 1/7=0.0006, tu93
2/9=0.0002, dc22/ka59/su15 0. **10-game mean 14.62%; on the 25-game card scale the
adapter-covered sum = 1.4616/25 ≈ 5.85% — the quarantined kernel-composition scoreboard
alone now matches the entire deployed LLM-free card's proxy (5.83), with 14 games still
adapter-less.** All smoke numbers reproduce at full budget (deterministic adapters).
Remember: script25 is an EXPRESSIVENESS metric, never agent capability; promotion still
goes through agent25 + hidden transfer per the Codex verdict.

**R56 EXPANSION SPRINT (2026-07-15 afternoon, parallel teammates): 25/25 ADAPTER COVERAGE
COMPLETE.** 12 new adapters in ~70 min: ar25 2/8 (mirror-reflection coverage), ls20 1/7
(shape/color/rotation-match maze), sp80 1/6 (water-routing), cn04 1/6 (rigid connector
arrangement), r11l 1/6 (click-drag assembly), re86 **1/8 first-ever generic clear** on the
highest-value game (brittle ceiling 6/8; key insight: never disturb a covered movable —
cycle ACTION5 selection), plus honest 0-banks with decoded mechanics: sk48 (snake
template-match), wa30 (pick-carry-drop), g50t (reactive sokoban), bp35 (gravity platformer,
determinism confirmed within-step), tn36 (bit-panel ENCODING MAP fully decoded: binary bit
row y=44, play button, multi-frame program, deadline wall), lf52 (cursor+click-to-connect;
2 layers byte-identical). **LEARNED-OPERATOR + configuration_path PATTERN = 2/2 super-human
levels**: reflection kernel (ar25 835→23a, beats human 32) + flow kernel (sp80 337→10a,
beats human 39), both in kernels/motion.py. Uniform depth thesis: blind explorers clear
single-goal reachability, never chained/precise multi-subgoal plans — the operator kernels
are the lever (queued: delivery #47/wa30, tn36 opcode planner, lf52 link, bp35 gravity,
sk48 body). Three reusable explorer patterns: pure-move, pure-click alphabet, hybrid
move+click Label. Base gap task #46: available_action_ids drops ACTION7 (re-measure
ar25/sk48 after fix). Measurement env: **ceph-build (free, 64c) reproduces GCP numbers
byte-exactly, 10-game parallel run** — official bench env now.

**R56 DEPTH PHASE (2026-07-15 ~15:00 KST): planner pattern 6 clears; TRUE 25/25 (cd82 was
missing).** **cd82 6/6 @97a game_score 0.9800** (2c1ed0f — second fully-conquered game;
ring-paint, replan-one-op) and **dc22 first generic clear** 1/6 @78a (df0eb6f — wall-SET
layer model beats parity; new kernel plan_gated_path = gated-maze shortest path). Also:
r11l L0 4a vs human 22 (964ce9d, points_with_centroid kernel), sc25 1/6→3/6 @0.0427
(3a4db6f, template_occupancy kernel — read the DISPLAYED target, ft09-move), s5i5 1/8
first frame-only (757e4b2, 8-connectivity fix), wa30 1/9 @30a vs human 71 (098e2f4,
plan_carry_delivery). Kernel-planner set now 6: plan_delivery/carry/push/gated_path +
slide_endpoint/chain. Full-25 scoreboard (r56s6 + late commits) ≈ **10.7-11%** vs deployed
5.83. New wall classes recorded: hidden-control (tn36/bp35/lf52 — frame doesn't expose the
win-gating control), level-entry transient masquerade (r11l L1), cross-life state-key
instability (sc25 cast animation), global-CSP stub assignment (cn04 L2). Method loop that
works: validate-first probe → gold-replay divergence → planner build → stop-rule bank.
ceph-build parallel: full 23-game measurement finished in ~15 min.

**R56 NIGHT BUILDS (2026-07-15 ~21:00, all verified vs SUMMARY+git):** ls20 1/7→**4/7 @
0.3571** (offline maze reconstruction 57eb823 — byte-exact parse, L1 606a→13a, L2 = the
45a oracle exactly — then push-wall transition model e2b1794 clears L3+L4; ALL FOUR
super-human; L5+ = moving changer/multi-goal/Fog banked), sp80 1/6→**2/6 @ 0.1429**
(401a6e1 — multi-piece flow: select-probe 8↔9 classification, 180° render rotation +
4px/cell scale, plan_flow_coverage_multi kernel; both levels super-human; NOTE dev
probes must pass data= to env.step for ACTION6 — runner already correct). Official card
r56s7 = **14.98%** (2f14a6e recorded); post-snapshot landings (sk48 .1667, lp85 .1637,
ls20 .3571, sp80 .1429, tu93 .0028) → HEAD arithmetic ≈ **17.4%**; r56s8 (16:11 HEAD)
running, next full-25 (r56s9, night HEAD) will make ~17.4% official.
**R56 ROUND CLOSED — FINAL official card = 18.02%** (r56s9, e2b1794 HEAD, @5000,
ceph-build, landed 2026-07-16 03:32 KST; recorded commit a4a20d6). Sequence r56s7 14.98%
→ r56s8 16.21% → r56s9 **18.02%**, each matching its arithmetic prediction EXACTLY
(deterministic adapters). Day arc 5.85% → 18.02% = 3.09x in one day. Top games: ft09 1.0,
cd82 0.98, sb26 0.846, ls20 0.357, tr87 0.286, cn04 0.20, sk48 0.167, lp85 0.164,
sp80 0.143, su15 0.104. Next-round levers: hidden-control park (tn36/bp35/lf52/g50t),
dynamic-extension queue (ls20 L5+, su15 L3+, wa30 L1, r11l L3), sc25 nav one-bug,
agent25 A/B prep. Expressiveness only — promotion via agent25 + hidden transfer.

**R59 DEPTH WAVE (2026-07-16 day, 6 parallel lanes) — official card 21.56%** (r59s1,
9b8e2e8 HEAD, @5000, ceph-build, landed 20:04 KST; supersedes r56s9 18.02%; all 25 games
matched lane predictions exactly). Landings: m0r0 1/6→**5/6 @0.7143 ALL levels 1.000**
(L5 momentary pressure-plate gates = pure function of player positions, joint BFS no extra
bits; L5 48a vs human 500), bp35 0/9→**1/9 first generic clear** (faithful sim + visited-
aware frontier explore; gem=colour 7, cam_y=py*6-36), sk48 3/8→4/8 + **L4 CLOSED
single-control-unsolvable** (lockstep-faithful + exhaustive 94,921-state reachability),
wa30 2/9 @0.0667, re86 L2. Post-HEAD (in next full-25): su15 3/9→**4/9 @0.1923**
(enemy-in-sim; euclidean-vs-Chebyshev fruit-match fix INVERTED the lure_base=20-starves
belief; L4 single-lure class airtight-negative, joint side-parallel plan designed), re86
2/8→**3/8 @0.1162** (separate_by_motion + max_coverage_offset kernels) → HEAD arithmetic
≈**22.25%**. Ready-spec parks: re86 L4 changer/recolour (live-validated 10→12), m0r0 L6
block-pin×gate×mirror-desync joint search, ls20 L5 moving-changer (decoded, 43a plan),
lp85 L4 σ/σ² ordering. Full detail: `.wiki/wiki/rounds/r59_depth-wave.md`. NOTE lp85
@5000 ≈ 3.7h wall — the long pole of every full-25 run.

**🚀 agent25 KAGGLE BENCH running (2026-07-21, commit f238417, R92).** User said "run it
on Kaggle even if slow." Kernel `jaehyukhyun/admorphiq-agent25-kernel-bench` v1 pushed +
running (GPU, offline; model michaelpoluektov/qwen3-6-27b-fp8/Transformers/default/1,
kernel_source philipvonderlind/vllm-deps, dataset jaehyukhyun/admorphiq-src). It boots a
vLLM api_server (served-name "qwen", the R55 offline config: TRITON_ATTN, enforce-eager,
--max-model-len 131072), then runs UnifiedAgent over a 4-game subset (ls20/vc33/m0r0/cd82)
in MATCHED bridge OFF vs ON arms (both HARNESS_CODE_ESC=1), scoring via run_game (RHAE),
telemetry-wrapping the llm (code-prompt / K.-usage / latency counts), preflighting the
sandbox bridge, and FAILING if the ON arm never issues a code prompt. Wiring (commit
f238417): registry.openai_compat_llm (vLLM /chat/completions, enable_thinking:false, hard
fail on missing base_url/model); score_efficiency --agent unified backend switch by
HARNESS_LLM_BACKEND=openai (ollama default byte-identical); K injection GATED on
HARNESS_KERNEL_API. Notebook notebooks/agent25_kernel_bench.py. GOTCHAS captured for reruns:
(1) served-model-name is "qwen" not the weights dir; (2) model_sources needs the FULL
instance path `owner/slug/Transformers/default/1`; (3) dataset --dir-mode zip strips the
zipped dir → stage `src/` containing admorphiq/ + scripts/. **RESULT (kernel v3 COMPLETE, 2026-07-21)**: pipeline PROVEN end-to-end on RTX PRO 6000 —
vLLM served qwen, LLM calls landed (20-34s latency), code escalation fired, kernel-bridge
preflight passed, RHAE scoring + telemetry worked, BRIDGE-INERT guard did NOT trip (ON arm
sent toolbox cards: vc33 5, ls20 10). **0 clears in BOTH arms** (m0r0/vc33/cd82/ls20 @300a).
LOAD-BEARING FINDING: model got the kernel vocabulary but produced **ZERO K.-using replies**
(kernel_replies=0 everywhere) — cards alone don't get qwen to call kernels. Uninformative on
ceiling (qwen not gemma4, small budget, weak code-path, only perception/geometry kernels
exposed — high-value transition kernels DEFERRED). NEXT LEVER: add a worked few-shot K.-using
example to the code prompt, re-run matched smoke, watch kernel_replies climb before a full-25.

**QWEN vs GEMMA4 COMPARISON (2026-07-21, kernels admorphiq-agent25-kernel-bench v4 qwen +
admorphiq-agent25-gemma4 v1)**: model-agnostic notebook, same 4 games / few-shot / matched
OFF-ON. ON-arm kernel_replies: qwen(+few-shot)=1 vs **gemma4-31b-it=23** (m0r0 10/10, cd82
10/10, ls20 3/10). gemma4 wrote a python block every turn in BOTH arms; qwen mostly none.
BOTH still 0 clears. CONCLUSIONS: (a) MODEL is the kernel-uptake variable — gemma4 engages
the bridge ~23× more; tuning to qwen would have misled (user's caution validated); (b) vLLM
0.19.1 serves gemma4-31b-it fine (arch-support risk RESOLVED; gemma4 = runtime model to
carry forward); (c) the agent25 gap is no longer "model uses kernels" but "composed
solutions don't SOLVE" → **Phase-2 sandbox enrichment is the critical path**: expose the
DEFERRED transition kernels (frame_diff/track_objects/learn_cyclic_successor/
reachable_frontier/configuration_path) by giving the code sandbox previous_frame + a bounded
(state,action)->state record + a capped successors harness. Files:
.wiki/wiki/rounds/r92_agent25_bench_{v4_fewshot,gemma4}.json.

**PHASE-2 RESULT (2026-07-21, gemma4 v2 = transitions + 8 transition kernels exposed,
Codex-reviewed)**: STILL 0 clears; adding transition kernels REDUCED gemma4 K.-engagement
23→2 (prompt bloat). Three configs all 0-clear (qwen K.=1 / gemma4-perception K.=23 /
gemma4+transition K.=2). **VIABILITY VERDICT**: the agent25 code-agent path (LLM writes
python composing kernels; stall-triggered escalation; 300a budget; ≤10 blocks) does NOT
produce clears at smoke scale — consistent with R53 "orchestrating tools plateaus". Piling
on kernels is NOT the lever and can hurt. Infra all PROVEN (bridge fires, gemma4 engages,
vLLM serves both). CHEAPEST NEXT DIAGNOSTIC (before more agent25 investment): does the
unified harness clear what its OWN graph tool clears in script25 (m0r0/vc33/ls20)? If
harness=0 where bare tool clears → bottleneck is harness orchestration/budget, not the
bridge. ⛔ do NOT keep adding kernels hoping for clears. The proven lever remains dev-time
kernel composition (32.96% card). Result: r92_agent25_bench_gemma4_phase2.json. Phase-2
follow-up if ever resumed: click-xy in transitions (needed for permute-class, deferred).

**DEEP-DEBUG + CODEX VERDICT (2026-07-21, transcript-capturing run, output cap 4096 /
ctx 131072 / auto-max-from-config wired)**: CONTEXT + OUTPUT both RULED OUT — prompts
~few-K tokens ≪ ctx; max model output 1376-2374 CHARS ≪ 4096-token cap (never approached).
REAL WALL (from captured code): gemma4 writes PLAUSIBLE GUESS/EXPLORATORY code ("assume red
block is player, try RIGHT to see if it moves") not goal-directed plans; calls K.find_regions
(perception) but doesn't use transitions to learn-then-plan. gpt-oss-120b CANNOT boot offline
on Kaggle (openai_harmony HarmonyError: vocab file needs network download; internet disabled)
— dead unless harmony vocab pre-bundled. Codex: diagnosis sound (caveat: code path runs
late/rarely via a tool-selection JSON gate, so "kernels not LIMITING" not fully proven).
VERDICT: **shelve agent25 as PRIMARY performance direction, keep as infra; proven lever =
dev-time kernel composition 32.96%.** Fund ONE scoped falsification: a mandatory EARLY
plan-probe-verify scaffold (infer entities+dynamics from transitions → 1 discriminating probe
→ predict → compare → update → bounded kernel program), bypass the JSON gate. If disciplined
kernel use rises but still 0 clears → shelve runtime-composition thesis confidently. ⛔ NOT
levers: bigger budget, force-code-first-alone, different model, 256K context. Files:
r92_agent25_gemma4_{debug,transcripts}.json.
Two boot gotchas now standard: machine_shape=NvidiaRtxPro6000 (else P100 can't fp8);
score_efficiency resolved by walk. Result JSON: .wiki/wiki/rounds/r92_agent25_bench_v3.json.

**🌉 agent25 KERNEL BRIDGE landed (2026-07-21, commit f14f323, R92).** User wants LLM
integration (agent25) developed/tested on GPU (Kaggle or NHN 2×V100) IN PARALLEL with my
dev-time kernel work — but chose "GPU 대기, 준비 코드만" for now. Prep done:
tools/kernel_api.py exposes curated PURE r59 kernels to the code-agent sandbox as `K.<name>`,
gated behind HARNESS_KERNEL_API (default OFF = deployed prompt byte-identical). Codex review
(gpt-5.6-sol, APPROVE-WITH-CHANGES). **KEY FINDING**: the code sandbox only gives the model
current_frame + shallow history — so the HIGH-value transition-dependent kernels (motion/
permute/config-path that made lp85/r11l/m0r0 clear) are DEFERRED; unlocking them = Phase-2
sandbox enrichment (previous_frame + (state,action)->state triples + capped successors
harness). NEXT (needs GPU): flip HARNESS_KERNEL_API=1, measure agent25 above the ~18/25
plateau; then Phase-2. NHN GPU sizing: 2×V100 (64GB, ₩7,898/h) fits gemma4-31b-q8 (~35-40GB)
for correctness; final 9h-throughput check must be on Kaggle (RTX PRO 6000 96GB). Codex CLI:
ChatGPT account only serves model `gpt-5.6-sol` (all -codex/o3 rejected). Round page:
`rounds/r92_agent25-kernel-bridge`.

**⏸ RESUME POINT (2026-07-20 — teammate weekly limit, resets Jul 21 20:00 KST).** User
directive: pause lanes now, resume when the limit resets; meanwhile Kaggle notebook re-push
+ validation test was run. State to resume from:
- **Two lanes died mid-task at the limit** (both have complete banks/handoffs):
  1. **r11l-l5** (task #116, r11l L5 collect-match): controller SHIPPED floor-safe
     (commits d901501..12f6989; detection/subset-solver/closed-loop collect all in;
     mechanic = teleport-absorption, 60a budget, no strike). GRANTED next pass =
     **learned placeability** (click→move fired/refused → is_free for
     points_with_centroid; seed probes at level start; then post-absorption collector
     re-detect by position continuity). Wall = frame hazard under-covers the octagon
     arena wall (R59/R88 pattern). Banks: rounds/r91_r11l-l5-collect-match.md + R11L.md.
  2. **sp80-l2** (task #117, sp80 L2): Pass 1 decode DONE — L2 is MULTI-SOURCE COVERAGE
     (NOT angled deflectors as R84 assumed); real wall = perception merge +
     simulate_flow unfaithful; Pass 2 = faithful-oracle channeling build (see task #117
     subject + any SP80.md bank the lane landed).
- **Respawn recipe**: fresh lanes with the standard brief (floor sacred, frame-only,
  det ×2, loader-hash, explicit-path commits, honest-bank; R92+ numbering) pointing at
  the banks above. Full-25 only on an actual clear; diff vs scratchpad r59s17 rows.
- **Kaggle validation (2026-07-20)**: kernel `admorphiq-arc-agi-3-chained-llm-free` v12
  FAILED (ModuleNotFoundError: admorphiq) — root cause: my dataset restage stripped the
  package dir (`--dir-mode zip` strips the zipped dir itself → stage `src/admorphiq`,
  NOT `admorphiq`, in the dataset dir). Fixed in the next dataset version + kernel v13
  re-pushed. LESSON: kaggle datasets version with dir-mode zip = contents of each
  top-level dir land at dataset root. Also fixed: broken NODE_OPTIONS preload
  (cmux temp file /var/folders/.../cmux-claude-node-options/restore-node-options.cjs
  deleted by temp cleanup → every OMC hook died with cjs/loader:1424; restored a no-op
  stub — if hook errors recur after reboot, recreate that stub).

**CURRENT official card: 32.96% (r59s17, 2026-07-19 10:04)** — r11l 3/6→**4/6 @0.2594**:
L3 cleared (ba4b39e) via colour-blind connectivity detection (2+2+3 legs) + NESTED
colour-set discriminator (target ⊆ body or body ⊆ target; decoys carry foreign colours —
resolves the 4-way overlap tie) + speculative-trial net. L3 clears at 172a (0.023): both
efficiency levers ⛔ measured-dead (pad regresses/thrashes; deterministic leg-tracking
strike-loops) — the stochastic re-detect churn is LOAD-BEARING because frame hazard
under-covers the engine obstacle mask; efficiency reopen = faithful obstacle mask
(perception research). L5 = NEW collect-and-colour-set-match hybrid (R89 spec) —
COMMITTED as the first post-R84 multi-session build (lane r11l-l1, task #116; weight 5/21
is the largest live single-level weight). Bounded frontier now closed EVERYWHERE (R84 +
r11l): remaining lift = multi-session only. Loader audits 25/25 clean on r59s16+r59s17.

**PREVIOUS: 32.94% (r59s16, 2026-07-19 07:57)** — r11l 1/6→**3/6 @0.2551**
via strike-aware drag-assembly planner (9c5afc0): R60c bank falsified (camera IDENTITY, no
transform; wall-edge infeasibility never real) — FIFTH re-measurement-killed wall of the
sprint; true mechanic = body recentres to legs' mean + engine strike-and-revert on obstacle
overlap → config-space A* with body-centroid hazard avoidance + leg-sep ≥10. First full-25
loader-line audit: 25/25 clean. R84 scan: bounded frontier otherwise EXHAUSTED (3 ⛔
settled tr87/sk48/sc25; 6 multi-session parks dc22/wa30/ar25/vc33/bp35/sp80). r11l L3:
plans verified (~14a), leg-grouping solved (2+2+3), wall = target-ring assignment
(multi-colour shared bodies); ring-geometry detection round R87 in flight (lane r11l-l1).

**PREVIOUS: 32.11% (r59s15 ENV-CORRECTION, 2026-07-19 06:21)** — the
measurement-integrity correction: 15/25 games had stale old-hash env dirs whose
metadata.json claimed the NEW game_id → duplicate registry ids → arc_agi picks by rglob
FILESYSTEM order (APFS≠ext4) → ceph-build loaded OLD content for cn04/s5i5/sc25/tn36/tu93
while reporting new ids. All 15 dirs archived to environment_files_archive/ on both
machines. r59s15 diff: cn04 0.2000→0.0309 (stale inflation removed; "budget-conditional
cn04" anomaly CLOSED as content divergence), s5i5 0→0.0278 (R79 recovery); sc25/tn36/tu93
identical. Loader-line audit after every full-25 is now mandatory. Lesson:
env_metadata_duplicate_game_id_20260719.

**PREVIOUS: 32.68% (r59s14, 2026-07-19 05:54)** — **lp85 FULLY CONQUERED
8/8 @ 0.6992 (SIXTH conquest)** via L8 open-chain geometric repair (3e5ca3a): the colour
bijection's own cycle decomposition IS the ring separator (R77 insight, 09ea45b — no spatial
separator needed); gate = complete-vs-incomplete PERMUTATION (heads/tails), floor-safe by
construction, measured no-op on all L1-L7 maps; R77's "fixed-point" trigger found INERT at
build time (fragmentation = chain heads/tails, never self-loops) — gate-check-first caught
it pre-splice. L8 SUPER-HUMAN 47a vs human 159 = 1.0. lp85 ladder R70-R78: 3/8 → 8/8.
Same night: su15 idx6 PARKED at the sub-pixel-perception wall (pin ORACLE-VALIDATED but 4
frame-only routes falsified — oracle merge click is 1px-UNPLACEABLE on the integer frame;
SU15.md §R75-R75d ⛔); g50t L2 parked at ghost-reachability (colour-11 premise
self-falsified pre-build, R76b). Seventeen consecutive single-diff runs. Conquests (6):
ft09 · m0r0 · ls20 · cd82 · sb26 · lp85. Remaining parks: tn36 L2, g50t L2, su15 idx6
sub-pixel, re86 L8 (provably unwinnable).

**PREVIOUS: 31.79% (r59s13, 2026-07-19 04:06)** — lp85 L7 CLEARED 6/8→7/8
@ 0.4769 (a26a20f): failure-triggered coupled retry — L7 frame-count-identical to L3, so
the coupled path arms ONLY when the single-press planner returns None; L2/L3/L5 byte-identical
(never reach the retry), L7 49a=0.282. Named principle: prefer failure-triggered fallback over
prophylactic probing when the failure is observable and cheap. L8 attempted+REVERTED (a7b1cc8):
adaptive-K reached 44/45 cells perfect reconciliation, GT 18-press solution exists, but the 3
coupled rings (14/16/15) are spatially INTERLEAVED + colour-duplicated — separation is the
wall; multi-session bank, clean 7/8, zero dead code. THIRD stale-frame park refuted by
settled-frame verification. Sixteen consecutive single-diff-verified runs. Remaining parks:
lp85 L8 (multi-session), tn36 L2, g50t L2, su15 idx6 lag-predictor (lane active), re86 L8
(provably unwinnable).

**PREVIOUS: 31.57% (r59s12, 2026-07-19 03:44)** — lp85 L6 CLEARED 5/8→6/8
@ 0.4222 (e5913ad): 36 rings = 7 coupled press-cells; the 2 map errors were exactly the
goal-occluded cells → temporal-mask learning + inject each goal's OWN visible motion as the
authoritative edge for its occluded cell; class-aware joint 3-token BFS, 70/80 budget.
L7 banked (9cba20a §R72): same coupling class, needs a RUNTIME coupling probe as gate
discriminator (frame-count-identical to L3 — static gate would regress L2/L3 from 1.0).
Fifteen consecutive single-diff-verified runs. Remaining parks: lp85 L7 (probe spec ready),
tn36 L2, g50t L2, su15 lag-predictor, re86 L8 (provably unwinnable).

**PREVIOUS: 31.08% (r59s11, 2026-07-19 02:25)** — lp85 L5 CLEARED 4/8→5/8
@ 0.2997 (5551b78; root cause = RENDER SCALE breaking all fixed pixel thresholds at once —
L5's 27×32 grid renders ~4×; fix = derived tile unit u + relative thresholds equal to old
constants at u=4; L1 also improved 0.892→1.0, disclosed deviation KEPT). New lesson:
scale_relative_thresholds_20260719 (fixed pixel thresholds = scale debt). lp85 ladder:
L6 dedicated wall (27+ rings), L7 likely cheap post-L6, L8 = L6 class. Fourteen consecutive
single-diff-verified runs. Remaining parks: lp85 L6, tn36 L2, g50t L2, su15 lag-predictor,
re86 L8 (provably unwinnable as modelled).

**PREVIOUS: 30.61% (r59s10, 2026-07-19 02:03)** — lp85 L4 σ² conflict RESOLVED
3/8→4/8 @ 0.1814 (0a8b08a): the conflict was REAL under-determination; fix = full colour
TIME-SERIES learning over K presses (new kernel learn_successor_from_series; certify K≥8 —
single-press can yield self-consistent-but-WRONG cycles). su15 idx6 CLOSED 6/9 (winnable in
8 clicks by oracle; both oracle-free routes fail on ONE ±1-step root cause — sim drift or
frame read-lag; reopen = lag-compensating predictor). lp85 L5 = corner-target detection at
render scale (queued #91). Thirteen consecutive single-diff-verified runs.

**PREVIOUS: 30.53% (r59s9, 2026-07-19 00:42) — FIRST 30% CROSSING** — ls20 L7
Fog CLEARED → **ls20 7/7 @ 1.0 FULLY CONQUERED (5th)** (1e5cb6f; refill-chained observation
post; the "no reachable cell sees the whole track" wall from TWO prior passes was WRONG —
posts (49,15)/(49,20) see all 6 track cells; real blocker = push-wall-aware navigation to
reach the column; ⛔ mover does NOT freeze through life-loss; fixed-count loiter over-burns).
SECOND game in two days whose terminal wall was a prior-pass measurement artifact (after
g50t) → the verify-don't-trust-parks doctrine is now standing. Full-conquest roster: ft09,
m0r0, ls20 @1.0; cd82 0.98; sb26 0.846. Twelve consecutive single-diff-verified runs.

**PREVIOUS: 29.53% (r59s8, 2026-07-18 22:05)** — g50t L1 first clear 1/7→2/7
@ 0.1071 (87c48bb). The 8-lane g50t saga resolved by ONE perception root-cause: TWO colour-9
blobs (moving player + static goal); prior diagnostics' min()-selection tracked the GOAL →
fake camera-lock, fake lag-2, fake offset-instability, fake "no reachable plate" (all
⛔-superseded in G50T.md; real model = fixed camera, lag-1, frame-readable maze, REACTIVE
barrier gating — barrier state IS frame-observable colour 5/8). N-ghost architecture landed;
g50t L2 = genuine ghost-path-pressing decode (parked, measured with correct tracking).
LESSON CLASS: when EVERY approach to a game mysteriously fails, suspect ONE shared perception
bug before exotic mechanics (two same-colour blobs here; goal-tracking made every diagnostic
lie consistently). Eleven consecutive single-diff-verified runs.

**re86 CLOSED at 7/8 @ 0.7273 (2026-07-18 20:51)** — L8 provably unwinnable as modelled
(6a747a0, DOUBLE falsification from source: win predicate REQUIRES colour match @1916;
thread-the-gap fatal — threading the dense 14-station band needs width ≤6, targets need ≥7,
no below-band obstacle to re-widen). The sk48-L4 honourable-close standard. Remaining parks
(all multi-session, complete specs): g50t L1 SLAM, tn36 L2 selector, ls20 L7 life-gated fog,
lp85 σ² conflict, s5i5 rotation, su15 idx6, re86 L8 (needs an undecoded new mechanic).

**CURRENT official card: 29.25% (r59s7, 2026-07-18 20:31, ceph-build @5000)** — re86 L7
SOLVED 6/8→7/8 @ 0.7273 (d1c5e1c) — PAST the brittle 6/8 ceiling, frame-only. Method: faithful
offline sim of the engine cross-collision handler + BFS'd pushes (22/22 live-validated);
occlusion-vs-flood identity breakthrough (cycle-index identity; NEVER ACTION5 on marker=None —
it's occlusion, re-issue the move); width-aware recolour (mis-aligned recolour = GAME_OVER trap).
L8 decoded (a64eda5, SIMPLER: two outlines no crosses) — build in flight for 8/8 = 5th conquest.

**PREVIOUS: 28.47% (r59s6, 2026-07-18 18:31)** — re86 L6
SOLVED 5/8→6/8 @ 0.5329 (c5247ec; per-piece mechanic split: outline=perimeter-conserving
reshape vs cross=bar-shift in fixed frame; corridor bar-control placer; 68a vs human 139 =
1.0 cap at weight 6). re86 = 6/8 = brittle ceiling, frame-only. L7 decoded (1caf774) as
recolour+reshape+place HYBRID — all subsystems exist, orchestration queued (task #88,
+0.46pp). 9 consecutive exact arithmetic matches.

**PREVIOUS: 27.80% (r59s5, 2026-07-18 17:03)** — re86 L5
SOLVED 4/8→5/8 @ 0.3662 (d63c823; flood-drive discovery: a move DURING a recolour flood
drives the piece — use ACTION5 as flood-wait; push-into-corner never re-floods; rightward
centre-waypoint ascent). 8th consecutive exact arithmetic match. Loader lesson strengthened:
re86 = inverse confirming instance of the s5i5 divergence (attribute scores ONLY from the
run's own "Successfully loaded … from <HASH>" log; Mac make("re86-8af5384d") mis-resolves
to 4e57566e while the VM loads 8af5384d). re86 L6 = next frontier (brittle reached 6/8);
L7/L8 never cleared by anything.

**2026-07-18 day-after state:** card HOLDS at 27.25% (r59s4; r59s5 skipped — no card-moving
commits since). API instability killed 7 teammate lanes on 07-17 afternoon-night (connection
errors within first minutes); recovered by 07-18 ~15:00. Post-recovery lane (g50t-v6, 5 rounds):
g50t L1 ROOT CAUSE = CAMERA-LOCK SCROLLING view (player pinned at screen (3,4), world scrolls —
every anchoring scheme was structurally doomed; the "offset instability" was never instability;
reopen = scrolling-camera SLAM: dead-reckon via floor_symdiff>0⟺moved + stitched world map +
the engine-verified two-ghost plan; 107f3f9). re86 L5 taken to ONE geometric residual (win-check
= all-movables SNAPSHOT decoded; feasibility PROVEN unique 1:1; assignment/selection/routing/
single-station recolour→cover all SOLVED, 1/3 pieces places live; residual = 22px body cannot
thread the ~25px station-9/station-14 left-edge gap — reopen shape: overlap station-9 from
below/right, exit rightward; 231696a). ALL remaining queue items are multi-session parks with
complete specs: g50t SLAM, re86 L5 geometry, tn36 L2 selector, ls20 L7 life-gated fog, lp85 σ²
conflict, s5i5 rotation control, su15 idx6 constructive downgrade.

**FINAL overnight number: 27.25% official (r59s4, 02:14 KST)** — post-milestone landings
tn36 2/7 @0.1071 (L0+L1 both 1.0; L2 parked on the unfindable tozzsf frame-selector) and
re86 4/8 @0.2273 (L4 multi-piece recolour-routing FSM; L5 parked: 3-movable set-cover +
mid-edge station). Remaining parked-with-spec queue: g50t L1 (#77, learned-passability
driver — generic online-WM value), tn36 L2 (#78 multi-session), re86 L5, ls20 L7
(life-gated fog), lp85 σ² conflict, s5i5 rotation control, su15 idx6 constructive
downgrade, m0r0 DONE 6/6, sk48 L4 unsolvable-closed, cn04 closed 2/5.

**R59-R60 OVERNIGHT WAVE (2026-07-16 night → 07-17 00:52) — official card 26.38%** (r59s3,
@5000, ceph-build; sequence r59s1 21.56% → r59s2 22.25% → r59s3 **26.38%**, all exact
arithmetic matches). **MILESTONE: ALL 25 GAMES CLEAR ≥1 LEVEL** (tn36 fell last, 00:41,
opcode-panel program synthesis e536f65; post-r59s3 arithmetic ≈26.52%). Day arc 18.02→26.38
(+8.4pp). Landings: m0r0 **6/6 @1.0 CONQUERED** (12bda52), ls20 5/7→**6/7 @0.75** L1-L6 all
1.0 (e698ed8+02fe3d8; L7 fog = proximity radius-20 partial-obs, build granted), su15 6/9
@0.4368 (spare-sacrifice 0abeb0d), ar25 2/8 @0.0833 (geared-copy kernel 2bdea69 — new
learn/render/plan_geared family in kernels/motion.py), g50t 1/7 first clear (ACTION5
ghost-on-plate 9647858; L1 = nested 2-circuit two-ghost, granted), lf52 1st clear (peg
solitaire f677aed; L1 = conveyor transport bank), bp35 1/9 first generic clear (a1701f9).
FIVE parks overturned by re-measurement (ka59 walk→launch, vc33 counter→sequence, g50t
infeasible→ghost-maze, lf52 animation→peg-solitaire, tn36 unfindable→opcode-panel) — the
park-verification-first doctrine is now standing. Honest closes: sk48 L4 topologically
unsolvable (94,921-state exhaustive), cn04 2/5 (set_level+render-kick artifact invalidated
the old "L3 proven" spec — new probe-validity lesson), s5i5 a48e4b1d rotation-walled
(perception fix built+reverted card-neutral), tu93 at probing ceiling, dc22 L1 engine-mode
flip. lp85 stall give-up (7ac5a00) cut full-25 wall time 3.7h→~15min. Queued: tn36 L1 6-bit
parse (#76), ls20 L7 fog build, g50t L1 nested ghosts, re86 L4 changer-routing spec.

**Local Mac ollama models DELETED (2026-07-15, user decision):** gemma4-26b/gpt-oss-20b/
qwen3-14b removed (36GB freed; disk was at 20GB free). Local LLM benches are retired —
LLM runs happen on GPU VMs only (GCP g4 / NHN 2xV100 under evaluation). Re-pull via
ollama if a local proxy is ever needed again.

**R56 EVENING DEPTH SPRINT (2026-07-15 night, verified per rounds SUMMARYs + git):**
sk48 0→3/8 @0.1667 (faithful sim+A*, ALL super-human 14/61 31/177 36/101; L3+ banked:
paired controls lack sys_click = not selectable), lp85 1/8→3/8 @0.1637 (kernels/permute.py
ring planner, tour+vote cycle reconstruction; L4 dense-ring bank), su15 0→3/9 @0.1035
(vacuum-pull merge-deliver; the "player" of 9 failed iterations was the vacuum-RING
animation artifact; L3 enemy-downgrade arithmetic bank), dc22 1/6 @0.0272 (5 efficiency
configs measured, all fail → stuck-gated-discovery root cause, eager-discovery = only
remaining lever, withdrawn on diminishing returns), tu93 11.6x (goal-directed frontier,
0.0002→0.0028, graph ceiling), ka59 1/7 (L1 invisible colour-15 walk, blind-transit
unvalidatable → depth stopped), cn04 budget-conditional 1/6@1000/2/5@5000, ls20 banked
with a VALIDATED 45-action super-human L2 plan (replays to live win; wall = per-step
re-keying, open-loop-legs round in flight), ar25 L1 = parallel multi-mirror (translation
subgroup, no single axis — banked). **Full-25 card ≈15%+ (r56s7 final pending; deployed
5.83).** ⚠️ FALSE-CLAIM INCIDENT: a teammate lane reported nonexistent commit 61661b6
("r11l 2/6, moving nests") — caught by git cat-file + SUMMARY check; BOTH claim elements
later source-falsified. New doctrine (wiki lessons pages, commit 65a8b96/796c4f7): verify
every reported hash+number against git/SUMMARY; a score is a (value, budget, env) TRIPLE.
⚠️ codex-cli UNAVAILABLE on this account ("not supported with ChatGPT account") — Codex
review gate substituted by empirical floor-gate + critic agent (slow under contention);
user decision pending. NHN Cloud GPU (2xV100 ₩7,898/h) under evaluation for LLM benches
(no single-96GB Kaggle-identical instance exists there). CLAUDE.md synced (523efee).

**R55 engagement experiment (landed 06:02 KST after 2 NULL runs — dual-default dispatch
bug fixed 127240f + stale dataset fixed v17):** within-session A/B verdict = ACTION_FIRST
ADOPTED (parse failures 8->1, ft09 governor rejections 63.5->1; cost: ~halved action
throughput), REPEAT_FEEDBACK DROPPED (worsens rejections 63.5->89). All 32 runs 0 levels
incl. base guards — diagnosed NOT config (byte-identical prompts through turn 2) but
**vLLM cross-session non-determinism at temperature 0.0** (greedy tie-breaks differ across
server instances; fp non-associativity): NEW MEASUREMENT RULE — matched arms must run
within ONE server session; cross-session absolute clear-counts are not comparable. Also
found+fixed: sandbox _scene_payload vs turn_packet topology.holes schema mismatch (7
verbatim KeyErrors). **basenav: PUSH-READY, HELD pending user GPU-quota decision**
(engagement consumed ~4.6h GPU).

**Process that works:** adapter iterations = falsification chains with measured claims;
stuck formulas -> self-contained brief -> `codex exec` (solved ft09 L3 outright);
teammates commit verified work directly; wiki round pages kept current per measurement
discipline. **Why:** this is the "tools clear publics + explain to weak LLM" plan the
user set on 2026-07-15. **How to apply:** continue adapter depth (ft09 6/6 integration,
ka59 select fix, sb26 second-frame kernel), then agent25 A/B per R58 §7 once
engagement/basenav land. Related: [[project_unified_harness_r53]],
[[project_kaggle_eval_and_metric]], [[feedback_codex_review_gate]].

**R92 agent25 verdict (2026-07-21, commit a9ebe5e) — SHELVED as performance direction, kept
as infra.** The runtime "offline LLM composes kernels" thesis was tested to its cheap end.
Native vLLM tool-calling (v6: staged `select_strategy`→`write_solver_code`, rich per-param
schemas, `--tool-call-parser gemma4`, max-model-len 200000) FIXED the interface — the thin
regex-parse the user rightly criticised — giving `route_valid==route_calls` 100% on all 4
games (m0r0/vc33/cd82/ls20), diverse routing, code path reached (≤120 blocks). But STILL 0
clears both arms; verbatim `write_solver_code` shows blind guess-probes ("no clear cursor,
try RIGHT/DOWN/SPACE"), and across 120+10 ON-arm blocks the model used `K.*` ZERO times and
`transitions` ZERO times. This was Codex's requested falsification experiment: routing
validity rose to 100%, kernel discipline did NOT, clears stayed 0 → per Codex's own criterion
the runtime-composition thesis is shelved for the gemma4/qwen tier. Prior R92 arms already
ruled out context (prompts ≪131072), output (≪4096-tok cap), and kernel exposure (23→2 K.
usage when transition kernels added — MORE kernels HURT). Dual-scoreboard clincher: m0r0 is a
script25 CONQUEST (1.0, offline reconstruction) — kernels CAN solve it; the LLM cannot compose
them to. ⛔ DO-NOT-REPEAT: more prompt tuning / bigger budget / more-kernels / different
mid-tier model. **The ONE remaining open lever the user named = gpt-oss-120b** (larger
reasoner) — offline-blocked by harmony vocab network-fetch; needs a pre-bundled tiktoken
encoding dataset (o200k_base+cl100k_base + TIKTOKEN_ENCODINGS_BASE + HF_HUB_OFFLINE/
TRANSFORMERS_OFFLINE + preflight load_harmony_encoding). If a 120B reasoner also guess-codes,
agent25-as-performance is closed and the private-110 lever is dev-time kernel generality, not
runtime LLM composition. Round page: `.wiki/wiki/rounds/r92_agent25-kernel-bridge.md`.

**R93 verdict (2026-07-22 01:04, commit 3628083) — the USER'S tool-fork-and-patch thesis
SURVIVED falsification: first positive agent25 outcome ever.** Design (user, three directives):
runtime agent works like a coding agent — run OUR tool first; on stall READ its real source
(source_card = inspect-assembled, parity-tested, the card IS the production code); patch;
matched parent-vs-patch replay from RESET; lexicographic progress metric (levels > distinct
states > distinct transitions). v3 paint×cd82 = **PATCH_WINS**: gemma4 diagnosed the
repeated-click deadlock from the instrumented trace and its next-largest-region patch DOUBLED
transition diversity (128 vs 64) on a fair driver (verbatim-core control reached vc33 L2 via
the sandbox path). Contrast R92: same model, from-scratch = guess-code; given OUR code +
failure evidence = correct causal debugging (6/6 patch outputs across v1-v3 diagnosed right).
Honest bounds: third-tier win (exploration diversity, not level clears), temp 0. FINAL
scoreboard (v4, 196d5de): paint win REPLICATED ×2 (deterministic); toggle×vc33 =
PARENT_HOLDS on a fully-executed patch (0lv/127st vs 2lv/834st) — the first genuine
model-attributed loss: a plausible-but-WRONG diagnosis (1024-cap "stencils" that were
really movement diffs) produced a worse solver. Deployment rule derived: matched-replay
gating with keep-parent-on-loss is mandatory.
HARNESS LESSON (measured, 6 defect chain): click-xy dropped from transitions → future-import
omission → num_predict=1024 truncation → card helpers not provisioned → centroid probe-order
drift (Codex's distillation-drift warning came true) → patch's own future import mid-file.
All regression-pinned (17 tests in test_probe_patch_loop.py). NEXT: convert exploration-win
into clears — hypothesis DSL (#121), no-repeat rule (#122), patch iteration ≥2, gpt-oss A/B
(pre-staged), and **R94 (#123, user-directed): characteristics→solution GAME CARDS + conquered
adapter cores as patch templates** ("특징→해결법" cards, id-blind; upper-bound harness half
already proven by the verbatim-core control). Round page: `.wiki/wiki/rounds/r93_tool-fork-patch.md`.

**R94 gates ALL PASSED (2026-07-22 05:56, commits 2b85b6b→9e0bc29) — the user's upper-bound
requirement PROVEN.** "우리가 클리어하는 게임을 주면 견본만으로 완주해야": the sb26 simdfs
card (distilled conquest engine, structural delegation, adapter parity 8/8 @0.846 exact ×4)
reproduces the FULL 8-level conquest through the exact LLM patch sandbox in 131 actions (vs
adapter 170). Getting there = a 4-rung trace-diagnosed fix ladder (dropped non-click plan
step → stateless plan-in-flight → L2+ entry-parse acceptance → cap-proof continuation under
run_code's 8-action chunking) — every rung found by instrumented traces, never guessed.
lp85 was ruled PAIR-INELIGIBLE first (frozen eligibility rule: the source conquest must be
expressible through action-boundary observations; lp85's time-series learner is not). D5
paired holdout pre-registered + runner built (probe_template_holdout.py + r94_holdout_bench
notebook): sk48 holdout, simdfs (family-match) vs toggle (mismatch control), gemma4 patcher,
select-on-adaptation-replay + score-once-fresh. Same night the model-comparison discipline
was hardened: gpt-oss one-shot verdict RETRACTED (2-game sample + reasoning channel off —
user caught both), breadth bench 10 games × 2 families × 2 models under a PRE-REGISTERED
scoring protocol (f53a82e: 4 compatible-case primary, McNemar, no-winner-without-holdout;
tuning-ladder rule in [[feedback_codex_review_gate]]). Round page:
`.wiki/wiki/rounds/r94_adapter-template.md`.

**Breadth bench SCORED (2026-07-22 08:46, 63a8ec2) — NO MODEL NOMINATED; the MECHANISM
wins.** Per the f53a82e pre-registration: gemma4 12/18 scored wins, gptoss-HIGH 9/15;
primary set IDENTICAL 3/4 both (both lose only toggle×vc33); paired discordants D=2 vs 1,
exact McNemar p=1.000 → statistically indistinguishable at proper configs — the earlier
"gpt-oss loses" one-shot verdict is now DOUBLY measured-wrong (reasoning-channel-off 0/2 →
reasoning-HIGH 9/15). gemma4 keeps default-patcher status only on secondary grounds (fewer
harness errors 2 vs 5, smaller to serve) — NOT on capability. THE substantive result: the
tool-fork-and-patch mechanism beat the parent tool on **11 of 20 breadth cases** — the R93
thesis holds at scale. Artifacts scripts/rounds/R93/r93_breadth_{gemma4,gptoss_high}.json.

**D5 v3 FINAL (2026-07-22 11:57, beba072) — full-engine family template REFUTED on the
sb26→sk48 pair; the design law is "distill family cards SMALL".** First clean measurement
(v1 killed by the 300s client timeout, v2 by a prelude string-entry bug — both fixed +
regression-pinned): the 75KB simdfs family card's adaptation SUCCEEDED (626s < 900s) but
produced a near-inert solver on sk48 (3st/7tr, noop 1.0), while the 6.6KB mismatched
toggle card adapted into a real explorer (71st/309tr, ×3 deterministic) and WINS per the
frozen prereg. Template SIZE/SPECIFICITY dominates family match — the user's compact
특징→해결법 game-CARD framing beats full-adapter provision. One pair/one patcher caveat
recorded. Natural next: ~5-10KB distilled simdfs SKELETON vs the same control; hypothesis
DSL (#121) is exactly the "compact structured template" version of this lesson. Round
page: `.wiki/wiki/rounds/r94_adapter-template.md` (final verdict in frontmatter).

**D5-SKEL FINAL (2026-07-22 13:51 collection) — family skeleton ALSO loses; R94 CLOSED.**
Size-controlled arm: the 8.2KB simdfs_skel family-skeleton card adapted cleanly (208.7s,
attempts=2, 0 exec errors — gemma4 raised movable-size cap, restructured move-learning)
yet stayed near-inert on sk48 (0 levels, 3st/55tr, noop 0.999); the 6.6KB generic toggle
card replicated **71st/309tr a FOURTH deterministic time** and wins the frozen prereg.
Combined law: on an out-of-family holdout NEITHER engine size (75KB) nor compact family
mechanics (8.2KB) transfers — generic probe-first wins at every size; family knowledge is
dead weight when the family doesn't match (in-family reproduction DID pass: sb26 gate).
Caveat: sk48 flagged schema-inexpressible by the R95 Codex review; exploration deltas are
control evidence (0 levels everywhere). ROAD: `docs/design_hypothesis_dsl_r95.md` v2.6
(commits aa8bdfa→7e456dd) — generic card baseline + hypothesis-DSL channel; R95a =
discriminative selection on ft09+sc25 (oracle + historically-falsified hard negatives,
data feasibility verified), 5-tier fallback ladder (probes → DSL self-extension
[EWM-measured basis] → fork-and-patch FINAL → generic floor), two-model rule (gemma4 +
gpt-oss-120b, paired protocol). Tasks: #121 (R95a build next), #122 (tier-1 probes,
design done), #124 (self-extension test). Artifacts scripts/rounds/R94/*_skel*.json.

**R95a IN FLIGHT (2026-07-22 14:48) — collection state for the next context.** Part-2 LLM
selection bench RUNNING on Kaggle: kernel `admorphiq-r95a-select-gemma4` v1 (launched 14:45,
wakeup armed 15:31; boot ~25min + 2 games x 3 asks). gptoss twin FULLY STAGED at scratchpad
`r95a_gptoss_push/` (launch AFTER gemma4 — GPU session limit). Scoring per the FROZEN prereg
(82199cf): PASS = choice in equivalence class; ft09 primary (random 0.4), sc25 weak (random
0.6); audit evidence fields. Teammate agent `r95a-build` idle-standing-by (context: built parts
1+2, knows the gptoss wiring). Commits today through 97ae07f (CLAUDE.md agent25 arc block).
After both models land: paired verdict -> r95 round page + memory + task #121 update; then
branch = R95b family compiler (if model shows selection skill) vs #124 self-extension seed test.

**R95a gemma4 RESULT (2026-07-22 15:31) — hypothesis-selection thesis SUPPORTED on the
primary case.** ft09: 3/3 PASS picking the EXACT ORACLE (not just the tied class), confidence
high, evidence citing the true discriminators (215/359 single-cell clicks refuting the stencil;
relational completion language). sc25: 0/3 — model picked neighbour_stencil, and its inference
is CORRECT GIVEN THE OBSERVATIONS (click CURSOR shows as a 2nd changed region → multi-cell
histogram); this exact failure was PREDICTED pre-run by the build agent → sc25 FAIL =
observation-layer defect (cursor/HUD masking, the Codex finding-6 binding-layer gap), first
concrete binding-backlog entry, NOT a model failure. gpt-oss twin launched (admorphiq-r95a-
select-gptoss v1) for the paired verdict. Artifacts scripts/rounds/R95/. Round page r95 updated.

**R95a PAIRED VERDICT (2026-07-22 16:18) — hypothesis-selection thesis CONFIRMED across
models; R95b gate OPENS.** gpt-oss-120b (reasoning=high) = IDENTICAL to gemma4: ft09 3/3
exact-oracle PASS (attempts=1, true-discriminator evidence), sc25 3/3 same-cursor-artifact
FAIL. Conclusions: (1) first measured proof the offline models SELECT the correct mechanic
hypothesis from strong falsified distractors given honest observations; (2) sc25 = observation-
layer defect CONFIRMED across model families → binding-backlog #1 = mask transient cursor
regions before click histograms; (3) no model-capability difference (consistent with R93
NO-NOMINATION); (4) R95b family-compiler build gate OPEN per prereg. Artifacts
scripts/rounds/R95/r95a_select_bench_{gemma4,gptoss}.json. Round page r95 verdict final.

**#125 CLOSED for gemma4 (2026-07-22 16:54) — first closed defect chain through the hypothesis
channel.** Diagnosis CORRECTED during build (verify-don't-trust): sc25 artifact = right-edge
click-budget BAR leaking past the col-63 HUD mask (edge-touch 0.86 vs ft09 0.06), NOT a
relocating cursor. Generic HUD-edge rule + generic cursor guard (inert here, synthetic-proven)
landed in the observation layer only (b3bdcf5); part-1 frozen numbers untouched. Masked rerun
(gemma4 v2): **sc25 0/3 -> 3/3 PASS picking the exact oracle**; ft09 replicated 3/3
byte-identical. R95b under way per Codex CONDITIONAL GO plan v1 (28d36ca): contract FROZEN
(34553c5), schema+oracles+mutant-verdict-table BUILT (3c1b142, model_selected = exactly 4
semantic slots). Next: gptoss v2 paired closure (kernel RUNNING) -> step iii grounding service
(Codex: 60% of residual risk). Artifacts scripts/rounds/R95/r95a_select_bench_gemma4_v2_masked.json.

**gpt-oss v2 masked rerun (2026-07-22 17:14) — FIRST MODEL DIFFERENCE in R95; #125 COMPLETED.**
ft09 3/3 exact-oracle replicated. sc25 STILL 0/3 but failure MODE changed (= masking worked):
rep0 anchored on the honest 13-cell level-transition example; reps1/2 read dynamics correctly
but misread completion as absolute-preview. gemma4 recovers fully with the same observations →
paired divergence recorded (NOT a nomination — one bench config, tuning-ladder rule). Residual
root cause = sc25 evidence THINNESS (9 clicks/4 wins); honest lever = richer trace recapture.
#125 completed (chrome fix validated: mode 2->1, ft09 byte-identical, gemma4 closure).
R95b progress: (i) contract 34553c5, (ii) schema 3c1b142, (iii) grounding 925d26f (adapter-free
parse lift, honest cycle-UNKNOWN + L3 12->8 anomaly under investigation), (iv) verifier in build.

**R95b LIVE MILESTONE (2026-07-22 17:52) — FIRST LIVE LEVEL CLEARS through the hypothesis
channel.** The compiled ORACLE hypothesis (schema instance -> grounding -> compiler, zero
adapter code) cleared ft09 idx0 **3/3 fresh-reset runs at EXACTLY 4 actions each (= human
baseline), fully deterministic**; discovery closes the colour cycle in 15 actions every run
(responsiveness-adaptive bidirectional probing — blind fixed-cell probing measured inert).
Gate (idx0+idx1) = FAIL honestly: idx1 decoy->reveal under-modelled by the single-phase oracle
(3/3 DIVERGED, plan-DONE-without-clear never counted as cleared); sc25 live pattern read
diverges at start. Both walls assigned (phase/guard reveal-trigger extension; live-read
diagnosis). Steps built today: contract(34553c5) schema(3c1b142) grounding(925d26f)
verifier(05b5b0c, matrix 8/8) compiler(25a129a, 4-click fixture) driver(d8f3421).
Artifacts scripts/rounds/R95/r95b_gate_ft09.json. Remaining: re-gate -> (vii) canned-instance
selection -> (viii) slot filling, both models, Kaggle.

**ft09 ORACLE GATE PASS (2026-07-22 18:21) — R95b step vi closed for the primary game.**
Re-gate after the reveal-phase fix (8f637de): **3/3 fresh-reset runs clear idx0+idx1 at 4+8
actions each** (discovery 19a, one decoy->reveal rebind per run) — fully deterministic,
human-baseline efficiency, zero adapter code. sc25: start-divergence fixed (base-snapshot
diagnosis); post-cast EXIT-NAV phase discovered but OUTSIDE the frozen contract (navigation
excluded) -> banked; driver criterion aligning to contract (cast+handover), then sc25 re-gate.
Next: (vii) canned-instance selection + (viii) slot filling, both models, Kaggle. Artifacts
scripts/rounds/R95/r95b_gate_ft09_v2.json.

**R95b STEP VI COMPLETE — BOTH ORACLE GATES PASS (2026-07-22 18:27).** sc25 re-gate under the
contract-aligned criterion (c6f82ed): 3/3 CAST_HANDOVER (genuine flips + cast colour + guard
on committed grid; levels honestly 0, exit-nav banked). With ft09 3/3 idx0+idx1 (6fc6f6e),
the full oracle pipeline schema->grounding->verify->compile->live is proven on both family
variants. Next: (vii) canned-instance model selection -> live execution (both models, Kaggle,
>=2/3 rule) -> (viii) slot filling. Artifacts scripts/rounds/R95/r95b_gate_{ft09,sc25}_v2.json.

**🏆 R95b MODEL STAGE 6/6 (2026-07-22 19:28) — FIRST FULLY AUTONOMOUS agent25 CLEARS through
the hypothesis channel (gemma4).** Every fresh run: model selected the EXACT ORACLE from live
grounding evidence (ft09 I3 x3 citing the 1-cell footprint vs the stencil mutant; sc25 I1 x3)
-> verifier PASS -> compiled plan cleared ft09 idx0+idx1 at 4+8 actions (human baseline) /
sc25 cast+handover — 3/3 each vs the >=2/3 contract bar. Zero adapter code, zero game ids in
the runtime path. gptoss twin launched (admorphiq-r95b-model-gptoss v1). Remaining: (viii)
slot filling; then family expansion per the 15-game backlog. Artifacts
scripts/rounds/R95/r95b_model_bench_gemma4.json. THE dev thesis of the day is proven end to
end: model hypothesizes (multiple choice), harness grounds/verifies/compiles/executes.

**R95b PAIRED VERDICT: CONFIRMED (2026-07-22 20:11) — both models pass the model stage.**
gpt-oss: ft09 2/3 (runs 1-2 exact-oracle -> 2 levels each; run 0 picked the STENCIL mutant and
the VERIFIER CONTRADICTED it -> never executed, zero actions wasted — first live proof of the
safety layer working in the model loop), sc25 3/3 cast+handover BUT picked the absolute-preview
MUTANT x3 (execution-equivalent on idx0: uniform base makes absolute==XOR — the R95a thin-
evidence signature at the execution layer; gemma4 was 6/6 exact-oracle; second soft divergence,
NOT a nomination). CONTRACT VERDICT: CONFIRMED — the hypothesis channel is end-to-end real on
the cell-state family for BOTH models. Artifacts scripts/rounds/R95/r95b_model_bench_{gemma4,
gptoss}.json. NEXT-ROUND OPTIONS (user decision): (a) step viii slot filling (variant-first,
the last contract substage), (b) family expansion per the 15-game inexpressible backlog,
(c) #124 self-extension seed test, (d) sc25 exit-nav follow-up. Recommendation: (a) then (b) —
finish the contract, then scale families.

**fill v3 (2026-07-22 23:13) — both games FAIL but FULLY ATTRIBUTED; the generation result is
real.** ft09: model generated the CORRECT full semantics for the first time (glyph_relational +
all_covering + ink 0=equal/2=differ = oracle-identical) -> idx0 CLEARED 3/3; idx1 DIVERGED on
the guard slot ([[],[level_advanced]] vs the needed layout_replaced) = the PRE-DECLARED
epistemic gap (reveal guard unobservable pre-solve). sc25: REGRESSION from v1 3/3 — the new
click-style evidence line ("paints a temporary selection colour, then commits") was read as a
multi-cell signal -> empirical_effect_matrix pick -> typed UNSUPPORTED_COMBINATION (guard
worked; no crash). Two final adjustments assigned: (1) reveal-trigger made guard-name-agnostic
(all-satisfied-but-not-won fires the trigger regardless of the phase-2 guard label — same
unobservability doctrine as transition auto-pairing), (2) evidence line re-worded to per-cell
("paints THAT ONE CELL"). v2 was a STALE-DATASET race (745d010; lesson in
feedback_measurement_discipline). Artifacts r95b_fill_bench_gemma4_{v2_stale,v3}.json.

**🏁 R95 ROUND CLOSED — CONTRACT COMPLETE (2026-07-23 04:17).** Fill v8: sc25 3/3 (prose fix)
+ ft09 3/3 (4th consecutive round) → gemma4 fulfils the frozen contract in BOTH substages
(select 6/6 + fill 6/6); select mode was already CONFIRMED paired with gpt-oss. The fill
v3-v8 defect ladder each removed a DISTINCT defect; the final root cause was captured
VERBATIM from the model's own reply via the v7 echoing_llm wrapper: gemma4 misparses
'Ncell(s)->Mclick(s)' notation (key/value swap) → fixed by prose rendering. PERMANENT LESSON
(.wiki/wiki/lessons/prompt_notation_misparse_20260723.md): model-facing evidence must be
unambiguous PROSE naming both quantities inline, never compact arrow notation; gain
observability (ask/reply echo) BEFORE iterating on evidence content. Artifacts
scripts/rounds/R95/r95b_fill_bench_gemma4_v3..v8.json. NEXT ROUND (recommendation): FAMILY
EXPANSION per the 15-game inexpressible backlog (movement/push families first) — the
private-110 coverage lever; optional completeness item = gptoss fill twin.

**R96 ControlledGridDynamics (movement family, m0r0) — 2026-07-23 06:30 status.** Codex reshaped
v0 decisively (family/oracle mismatch was 65% of drawn risk): scope = CoupledActorMerge on m0r0
idx0+idx1 ONLY; dc22 = near-OOD control (a SECOND transition family); risk re-estimate 55% =
grounding/occupancy. Contract frozen 727b34b. Pipeline replicated: schema (b191834, mirror-delta
oracle + 6 mutants 4C/2U) -> two-actor grounding GREEN (9e54634; action<->axis mapping is
HASH-VARIABLE -> verifier judges STRUCTURE; frame-based actor id robust to replay epoch churn) ->
verifier matrix EXACT (bfd6848) -> compiler joint-BFS plan length 15 = gold (eb4d3cf) ->
**idx0 CLEARED LIVE 3/3 @15a = gold, deterministic** (87aed80). idx1 execution defect ladder (5
removed, each instrumented): per-level fresh re-grounding (fc9140b) -> confirmed-edge-subset
planning (648124f) -> actor-colour PERSISTENCE gate (0582f12; vanishing colour-0 transient
out-scored real actors; my rebind hypothesis FALSIFIED) -> settle absorption of the FIRST
post-transition plan action (01a4fa0; idx1's first gold action also moves nothing) -> online
occupancy learning via compile_movement_hypothesis(extra_walls=...) (01a4fa0; learned 10 real
walls live, routed 5->15, honest UNSATISFIABLE). DEEPER ROOT (the contract's PRE-DECLARED 55%
outcome; falsification clause -> pivot to GROUNDING): movement_occupancy under-detects idx1 edge
walls (45 parsed, >=10 missing, rows 5-7/cols 9-11, likely background-coloured boundary cells vs
center-pixel parse; idx0 89 walls unaffected). Occupancy-perception round IN BUILD (r95a-build):
pixel diagnosis at the 10 learned-wall cells -> generic fix + idx0 89-wall regression pin -> v5
re-gate. Step (vii) model-stage assignment pre-drafted (scratchpad r96_step7_assignment.md; NO
auto-pairing for movement v0). Round page: rounds/r96_controlled-grid-dynamics.md.

**R97 tier-2 self-extension design v1 (2026-07-23 06:29, fb78a64) — Codex CONDITIONAL GO.** Two
v0 validity traps: (1) compiler has NO extension node -> authored code could pass live WITHOUT
causal use -> AuthoredCellUpdate plan node + causal-use proof required; (2) existing verifier is
footprint-only, cannot discriminate flip-vs-cycle -> new EXACT colour-transition verifier
required. binary_flip IS ordered_cycle(k=2) -> sc25+ft09 = ONE capability, verdict capped at
SEED-PASS; sc25 becomes the NO-HOLE equivalence control. Exclusive output union
select/extend/abstain (mixed pick+flag INVALID); controls: no-hole (extension = false positive
even if correct), evidence-blind (success = leakage), insufficient-evidence (expect abstain),
hand-authored oracle path, mutant definitions. Dedicated AST sandbox (R49 loader insufficient).
Scoring: >=2/3 hole recall AND >=2/3 no-hole specificity per model, detection separate from
authoring. Build queued AFTER the R96 gate. Doc: docs/design_r97_self_extension.md.

**R96 idx1 defect ladder UPDATE (2026-07-23 08:24) — 14 rungs, orbit escalation in build.** After
the occupancy pivot: clean-block learning -> hazard learning (joint-teleport) -> transient/dynamic
obstacle discovery ((6,9) blocked-then-passable) -> observation-trumps-inference unlearn (learned
AND grounded walls; the patroller was BAKED into the static parse at (3,7)) -> merge semantics
corrected (engine merges ONLY by simultaneous same-empty-cell entry; walk-onto/swap blocked;
adjacent gap = parity-impossible without desync) -> blocked_at block-evidence sensor -> flip-flop
commit-and-wait -> TTL decay (transient evidence lifetime) -> REACTIVE CEILING (static learner
poisoned by patroller positions) -> defect 14: patroller = COLOUR-10 MIRROR PAIR, period ~4-6,
VISIBLE in frame diffs (colour detector only ran at discovery, frozen); (A) frame-diff transient
perception + no-mover-visible learning gate BUILT (5008cb1, learner un-poisoned) but v14 still
UNSAT 3/3 -> **(B) APPROVED + IN BUILD: orbit inference (set-sequence autocorrelation P in 2..12)
+ time-expanded joint BFS (pos_a, pos_b, t mod P), reactive layer as fallback, P=1 degeneracy
pins idx0 byte-identical**. idx0 3/3 @15a=gold STABLE through all 14 gates. Every gate 3/3
deterministic; artifacts scripts/rounds/R96/r96_gate_m0r0_v5..v14.json; full ladder in
rounds/r96_controlled-grid-dynamics.md. Step (vii) model-stage assignment pre-drafted.

**R96 VERDICT (2026-07-23 08:57, Codex-consulted, 36ea122): ORACLE PARTIAL / GROUNDING PIVOT;
MODEL CRITERION OPEN.** idx0 FULL PASS (3/3 @15a = gold through 15 gates, oracle-proven). idx1
PARKED at the pre-declared grounding-class wall: an INVISIBLE floor-coloured (colour-5-on-colour-5)
dynamic obstacle whose policy has NO stable period <=12 (behavioural fit engages 12x/run but climbs
2->10 monotonically; long-period / multi-obstacle / position-dependent — mirror-pair simultaneous
blocks observed). NOT a schema/model failure (schema plans idx1 perfectly given correct walls);
banked with control/merge/static-wall/hazard mechanics decoded, hidden-obstacle dynamics
unresolved. The 15-defect ladder = GENERALISATION ASSETS (not private-110 proof until evaluated
there). Step (vii) model stage DISPATCHED on idx0 (select: oracle + 6 mutants, no auto-pairing;
fill: relation/collision/hazard slots; both models, Kaggle, prompt review before first push) +
ONE pre-registered position-dependence discriminator (tick-shift counterfactual; park regardless).

**R96 discriminator DECISIVE (2026-07-23 09:43, 3397ec3): the idx1 invisible obstacle is
POSITION-DRIVEN** — K=6 net-zero prepad shifts 61/61 block events by exactly +6 (raw
intersection 1/61): a guard/chaser = f(actor joint config), NOT time-periodic (explains the
frame-diff invisibility AND the unstable time-orbit fit). Future idx1 build model class =
StateDependentOccupancy (existing schema arm): learn (actor config -> obstacle cell) online,
plan joint (actor_a, actor_b, obstacle). M0R0_PREPAD_K gated diagnostic kept (default OFF).
idx1 stays PARKED. Step (vii) Kaggle chain (gemma4-first) in flight; R97 oracle-certification
gate build in flight (r97-build lane).

**R96 (vii) + R97 progress (2026-07-23 10:23).** R96 model stage: build 6168252 (SELECT
equivalence-class scoring {oracle, hazard_as_wall}; FILL schema-faithful 3 frozen slots incl.
actors role-binding with symmetric-equivalence under same_cell — a fork's silent narrowing of
the frozen surface was caught); kernel 1/4 gemma4 SELECT = **m0r0 PASS 3/3 EXACT-ORACLE**
(f001b2c; riders: sc25 PASS, ft09 FAIL 3/3 = Kaggle-env-specific no-op-dominated evidence, NOT
a code regression — verifier CONTRADICTED the wrong pick every run with zero executed actions);
kernels 2 (fill-gemma4) + 3 (select-gptoss) running in parallel (GPU 2-cap), 4 (fill-gptoss) on
auto-retry. R97: oracle-certification gate PASS + committed (42bc851) with the LOAD-BEARING
finding **ft09 = per-level 2-state toggle; genuine k=3 cycle first at idx4 (8,12,9)** → contract
amended (325f097, hole evidence = k>=3 level, idx0 = no-hole control); hand-authored oracle
clears LIVE [4,8] through the AuthoredCellUpdate causal-use node; 6/6 definition mutants fail;
model-bench scaffolding built+reviewed+committed (86542a0 + ac75dc8 no-hole scoring lock:
{binary_flip, ordered_cycle} both pass, extend = FP, abstain = miss). R97 Kaggle runs queue
AFTER the R96 chain frees the GPU slots (dataset needs scripts/probe_r97_model_bench.py added).
Round pages: rounds/r96_controlled-grid-dynamics.md, rounds/r97_self-extension.md.

**R96 (vii) v2 re-runs BOTH PASS (2026-07-23 11:04, 6e14294/f8b18e2).** Two m0r0 harness defects
shared ONE root (the evidence-gathering solve MERGES the actors; downstream reads mishandled the
coalesced state): (1) feed() never ran the merge detector -> merge_observed False -> same_cell
CONTRADICTED even for the oracle (fix 4cc38eb: _movement_merge_seen = named event OR coalesced
single cell); (2) movement_actors() read ONE coalesced cell -> n_actors=1 while prose named two
roles (fix ad77e52: n_actors = bound actor ROLES from the delta table). v2 validation: gemma4
FILL m0r0 PASS 3/3 (verifier PASS -> executed -> idx0 @15a each run); gptoss SELECT m0r0 PASS 3/3
(hazard_as_wall every run = the pre-declared criterion-level equivalence-class member). Tally:
gemma4 select+fill PASS, gptoss select PASS; LAST substage = gptoss fill via fresh slug
admorphiq-r96-vii-fillgptoss (original slug = Kaggle limbo record, 404 regardless of slots).
>=2/3 there => R96 (vii) CONFIRMED both models. ft09 rider stays env-sensitive (R95 lane).

**🏁 R96 ROUND COMPLETE (2026-07-23 11:19, e1f9a9c): MODEL STAGE CONFIRMED both models.** Final
substage gptoss FILL (fresh slug admorphiq-r96-vii-fillgptoss; old slug = Kaggle limbo record)
= m0r0 PASS 3/3 (idx0 @15a each run). ALL FOUR substages PASS 3/3 on the idx0 criterion: gemma4
select (exact-oracle I7) + gemma4 fill + gptoss select (hazard_as_wall equivalence-class) +
gptoss fill. The SECOND family (ControlledGridDynamics/CoupledActorMerge) is measured end-to-end
— schema -> grounding -> verifier -> compiler -> live oracle gate -> model select+fill — on both
models, matching R95's cell-state precedent. idx1 parked (position-driven invisible guard;
StateDependentOccupancy = future model class). NEXT: R97 paired Kaggle bench (scaffolding +
certified gate ready; kernels admorphiq-r97-ext-{gemma4,gptoss}; dataset already carries the
driver), then family expansion #3 per the 15-game inexpressible backlog.

**R97 paired bench MEASURED (2026-07-23 11:35, 02a8761/ba91afa/21075f7).** gptoss = SEED-PASS
(hole recall 2/3 — extend chosen 3/3, two authored cyclic_palette definitions pass
TRAIN+held-out; no-hole specificity 3/3; blind=abstain NO leakage; insufficient=abstain).
gemma4 = NOT SEED-PASS (0/3) but the failure is a HARNESS defect: detection PERFECT (extend
3/3), authored rule SEMANTICALLY EXACT-ORACLE ({8:12,12:9,9:8} + .get) — rejected only by the
AST sandbox's attribute-access ban, never stated in the prompt. R97b sub-round IN FLIGHT
(allowed-syntax sentence added to the contract prompt, all 4 cases identically; gemma4-only
re-run; gptoss verdict stands). Tier-2 takeaway so far: BOTH models detect the hole and author
semantically-correct rules — the residual gap is syntax-surface communication, not capability.

**🏁 R97 ROUND COMPLETE (2026-07-23 11:54, dda8fa3): CONFIRMED SEED-PASS BOTH MODELS.** gemma4
v2 (R97b syntax-contract fix df6a443) = PERFECT: hole recall 3/3 (extend cyclic_three_state,
exact cyclic-successor via if/elif/else, identical source hash every run, TRAIN+held-out exact)
+ no-hole 3/3 + controls abstain. gptoss standing SEED-PASS (2/3 + 3/3). TIER-2 THESIS
MEASURED-REAL at seed scope: both offline models detect a vocabulary hole from prose transitions
alone, refuse to force an offered rule, author a working definition under the fixed contract,
and pass exact held-out verification. v1 gemma4 0/3 = un-communicated AST constraint (the
R95b notation-misparse lesson replicated in the authoring channel). NEXT ROUND: family
expansion #3 per the 15-game inexpressible backlog (push/delivery families are the Codex-ranked
candidates — R96's grid grounding/occupancy/path-search assets are their prerequisites).

**R98 family #3 OPENED + PIVOTED (2026-07-23 12:26, 7844bd4 -> b8e4e63, Codex CONDITIONAL GO).**
v0 proposed PushDynamics (sokoban-class) — Codex found the dominant defect: the 15-game backlog
has NO clean classic-sokoban row and none of the candidate oracles certifies one-cell contact
push (ka59 = SELECTED-MOVER MOMENTUM LAUNCH per adapters25/ka59.py:216; ls20 = STATIC CONTACT
LAUNCHER; sk48 = body topology, excluded) — a ka59 clear would have certified the WRONG
transition model. **PIVot: R98 = FlowDeflectionDynamics, oracle sp80 idx0** (readiness-ranked #1:
coherent backlog family, learned flow operators + simulation + coverage planning exist from R56
#45/#65, super-human live idx0; change->spill two-phase must be explicit). Runners-up recorded:
re86 RecolourOnContact, wa30 CarryDelivery idx0, OneCellContactPush deferred. 7 corrections
bound: one-variant-only / compiler-claims-match-reality (plan_push is ONE-box) / full transition
semantics in schema / mutants pre-certified with honest UNKNOWN / oracle 3/3 vs model >=2/3
split / CRITERION LEVEL ONLY (no mechanical idx0+idx1 copy) / near-OOD = confusable negative
(wa30), far-OOD tu93. Risk post-pivot: 40% grounding, 25% compiler/search, 20% verifier, 10%
model, 5% live; + asymmetric mobility classification + position-multiset identity + PROBE
DESTRUCTIVENESS (reset-separated probe episodes). NEXT: v1.1 FlowDeflection schema draft (sp80
decoded mechanics + task #117 L2 perception-merge findings) -> schema-only Codex consult ->
contract freeze -> build (r95a-build standing by). Task #127.
