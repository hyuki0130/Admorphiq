---
name: project_unified_harness_r53
description: R53 unified self-improving harness — 6 from-scratch generic tools + retry loop; graph clears 3/9 legacy games; continuation = per-tool strengthening
metadata: 
  node_type: memory
  type: project
  originSessionId: 3f835f42-61d8-4a15-811f-a74e74370d28
---

**🌙 NIGHT STATE 2026-07-14→15 (newest — read first):** audit KILLED by matched12 (OFF arm
cleared su15 3/3 @19a AND r11l; audit = trajectory-divergence cost, confound resolved: v7's
clear was the 430d000 sandbox fixes). Wall map: 7/10 nav (shortest_path called 0× despite
correct declared goals), 1 truncation (sb26, finish_reason=length before action), 1 repeat
(ft09, 55/100 governor rejections). RUNNING overnight: engagement experiment (32 runs:
{base,+ACTION_FIRST,+REPEAT_FEEDBACK,+both} × sb26/ft09 targets + su15/r11l guards, kernel v10,
lands ~04:00; analyzer scripts/repl_engagement_verdict.py). PUSH-READY next: basenav (Base vs
NAV 18 runs on ls20/g50t/tu93, Codex-ruled after PLAN exposure-gate failure; trigger = goal-
declaration-eligible unconditional, spec d421beb wired 11164ed, replay gate passed base=0/nav=4;
analyzer repl_plannav_verdict.py; flip REPL_EXPERIMENT=basenav in push copy). Then winner→full25
→ submission candidate ONLY if >5.83 proxy (user decides submissions; NO auto-submit). Codex
review gate mandatory for all analyses (5 verdicts in docs/r55_codex_*.md; always </dev/null on
backgrounded codex). GPU quota ~7h left this week after tonight.

**🔁 R55 BENCH-CYCLE STATE (2026-07-14 PM — KEEP CURRENT):** repl_agent iterating on Kaggle
RTX Pro 6000 (kernel jaehyukhyun/admorphiq-repl-bench, `--accelerator NvidiaRtxPro6000`;
dataset jaehyukhyun/admorphiq-src; vLLM recipe: TRITON_ATTN, NO fp8-KV [forces broken
flashinfer JIT], 131k ctx, api_server subprocess). Cycle log: v2 thinking-mode timeouts →
v3 fixes (no-think/300s/bare-parse) but REPL dark + illegal-MOUSE storms → v4 legality binding
works (illegal→0) + models WANT to inspect (93/107 turns) but stdout discarded → v5 big-four
(image wiring, causal feedback, governed fallback, bounded tool loop) — **P0: sandbox dead on
Kaggle (subprocess PYTHONPATH not propagated) → v5 REPL results INVALID**; su15 rediagnosis
(Codex): wrong JOINT mechanic/goal model + memory SELF-CONFIRMS false stories → v6 = P0-only
rerun (in flight); v7 batch built flag-gated (REPL_AUDIT: 12/24/48 falsification audit,
EFFECT vs PROGRESS predict split, real worker smoke test w/ hard abort, turn_in_level fix,
PNG dumps). All analyses Codex-reviewed (user standing order; docs/r55_codex_*_20260714.md ×4).
Comparison harness: scripts/repl_bench_compare.py --a <new> --b <old>. Guards untouched
throughout (10-guard set + cd82 6/6). v10 submission (proxy 5.8307) hidden score PENDING;
public scorecard shows completed=1 (cd82 WIN) — full-game completion is the score lever.

**🧭 R55 CODE-REPL PIVOT (2026-07-14 AM — newest direction):** Codex consultation
(docs/r55_codex_design_consultation_20260714.md, binding spec) recommends Duck-style multimodal
code-REPL + persistent controller memory; existing solvers = zero-action shadow proposers.
KEY CORRECTION: Qwen 3.6 27B is MULTIMODAL (first-choice deploy model; Kaggle mirror
michaelpoluektov/qwen3-6-27b-fp8; vLLM ≥0.19). LB research banked in
.wiki/wiki/lessons/lb_top_team_research_20260714.md (M1 top-3 = offline LLM brains; hidden set
intentionally OOD; two leaderboards — we're on the community/code track, top band 1.38-1.61).
Built (additive, offline-tested): src/admorphiq/repl_agent/ 6 modules 46 tests (transcript/replay
FIRST, scene tracker stable-IDs, turn-packet YAML + falsifiable-hypothesis memory, subprocess
sandbox + Inspector API, action governor MOUSE(row,col), ReplAgent loop with injected LLMClient
— Kaggle wiring = client swap); also R54 vlm_policy.py (JSON-policy arm for the R2 2×2 ablation).
⚠️ Mac local inference/heavy runs BANNED by user (26b vision call ≈26s/turn, machine lag);
normal CLI kernels = P100 16GB (27B can't load) — v11 env-probe kernel determines the submission
kernel's real GPU. v10 submitted (proxy 5.8307, cd82 6/6 @97.49 server-verified) — hidden score
pending; v6 transfer ratio ~13% ([[project_leaderboard_first_score]]).

**🚀 NIGHT SESSION 2026-07-13→14 (newest state — supersedes cards below):**
- **cd82 FULLY SOLVED 1/6→6/6 @0.9463, 108 actions (~1900×)** — frame-only ring-paint
  solver `src/admorphiq/ring_paint.py` (WMA paint phase): empirical launch-physics
  table (8-pos ring → half/diag regions + arrow variant), BFS over (ring_pos,colour)
  launches, ⚠️ win check ignores the two main diagonals. Unlocks: settle-aware first
  read + component size-floor 40→8 (thin bands). Commits 043794c/d5b9979/84261aa.
- **sb26 1/8→2/8 @0.0796** — frame-only portal-graph SORT solver in sort_match.py
  (70084f1): "internal-only" verdict was a STALE-LAYER bug (read canonical frame[-1],
  not frame[0]; transition stacks ~16-118 transient layers, settle 1 step); box/pipe
  morphological split gives the portal link; top-display legend = target DFS order.
- **su15 2/9→3/9 @152** — reset-then-retry on merge-goal switch (317d4b3); deliberate
  mid-level RESET preserves levels_completed (verified).
- Also landed: GAME_OVER cycling guard (3 death-cycles → give up level), direction-map
  majority vote + non-cardinal drop, occupancy floor-colour (player footprint), mobility
  player-selection (span-fraction HUD exclusion), toggle-solve GAME_OVER state recovery,
  wa30 delivery calibration (object-permanence player colour), merge_drag stall detection
  (tile-position snapshot, not full-frame). 778 tests. **GUARD SET (10): su15 3/9@152,
  s5i5 1/8@169, re86 2/8@264, wa30 1/9@100, ft09 1/6@93, tn36 1/7@110, lp85 1/8@311,
  ls20 1/7@89, sb26 2/8@288, cd82 6/6@108@0.9463.**
- Re-opened (banked, feature-scale): tr87 = production/REWRITE-GRAMMAR win rule (visible
  rule table); s5i5 L2 = permutation puzzle; ft09 L2 = glyph-clue decoding (non-ring
  3×5 grid, execution-lethal); wa30 L2 = efficiency+closed-loop (budget ~68/level,
  frame-occupied≠solid); re86 L3 = 2-sprite multi-placement (scored hash = v2 8af5384d).
- **Kaggle: v6 hidden publicScore 0.14 (transfer ~13%); v8 proxy 1.7091; v10
  (sb26+cd82, projected proxy ~5+) = the 2026-07-14 09:00 KST submission.** LB top
  band 1.38–1.61. See [[project_leaderboard_first_score]].

**R53 (2026-07-08/09): the runtime general agent = a self-improving retry loop
over 6 Claude-authored generic tools.** Full detail: `.wiki/wiki/rounds/r53_unified-harness.md`
(read it before touching this axis). Commits b533ca4 → 089f3b3.

**Built (all committed + tested, 655+ tests):**
- `src/admorphiq/tools/` — 6 tools RE-IMPLEMENTED from scratch on a shared
  `base.Tool` contract (detect/reset/observe/propose + generic frame utils):
  `graph`, `world_model`, `dealias`, `deadsig`, `paint`, `llm_goal`. All
  grep-clean of game ids. (User directive: re-implement generically, do NOT
  reuse the legacy brittle sprite-tag solvers — graph_frontier_agent.py is
  itself generic but the user chose to re-author, option (a) 2026-07-09.)
- `src/admorphiq/harness/` — `loop.py:UnifiedAgent` (the retry loop: observable
  Signature → minimal wiki slice via `context.py` (HARNESS_CTX char cap) → LLM
  picks a tool OR writes code → feed transition to every tool → re-decide on
  stall), `registry.py` (6 tools + ollama llm). `--agent unified` in
  score_efficiency.py. Env: HARNESS_MODEL/HARNESS_CTX/HARNESS_STALL/GF_GIVEUP.
- Diagnostics: `scripts/probe_tool_direct.py` (drive ONE tool, no LLM — isolates
  tool strength from routing), `scripts/harness_ctx_sweep.py`.

**6 measured bug fixes (the loop only works with all of them):**
1. `restart_on_game_over=True` — else the game ends at the first death (~50 acts).
2. LLM called only at decision boundaries (first/stall), not every empty queue
   (gemma SWA breaks prompt caching → per-action LLM is untenable).
3. Progress = reaching a NOVEL frame-hash, not "frame changed" (paint wandered).
4. Swap-on-failure: a stalled tool is retired for the level, next pick excludes it.
5. HUD masking in graph (freeze mask of cells churning ≥60% of transitions).
6. stall=30 (env HARNESS_STALL) + graph HUD warmup 16 — tools must survive warmup.

**Graph tool strength (direct probe, budget 3000): clears 3/9 legacy games** —
vc33(1, legacy 2), m0r0(1 ✓ via de-alias composition), lp85(1 ✓). Misses:
cd82 (hidden-state aliasing 0.77, beyond 4-history suffix), and the click-heavy
cluster cn04/lf52/tn36/ft09 (legacy clears each at L1). ⛔ Dense click-grid on
graph was MEASURED HARMFUL (regressed vc33 1→0, unlocked none) — lights-out needs
click SEQUENCES, a dedicated toggle tool's job, not graph frontier-BFS.

**✅ PRODUCTIZED FINAL (2026-07-09): deployed harness = 7/7 solid at the real
deployment budget (GF_GIVEUP=8000)** — cn04, lf52, lp85, m0r0, r11l, tn36, vc33
all clear deployed (+cd82 ~30% stochastic via targetgrid). lf52 needs the full
8000 (marginal at 5000). Architect-APPROVED after fix cycle; deslop done; 667
tests green. Deployed = isolated performance. Key fixes
that got there (architect REJECT → all fixed, 667 tests): (1) HIGH: ownership was
INERT — runners pass frames=[] so detect() never saw transition evidence; loop now
keeps _recent_frames, feeds every detect(), re-evaluates ownership LIVE on stall;
(2) no-churn stall policy — retire the current tool only if another non-failed
tool detects strictly higher (swapping to weaker tools lost solid clears);
(3) context.py signature fixes (ACTION4 in mobility, ACTION7 not a click);
(4) world_model empty prior capped 0.10-0.25 (measured 0/25 standalone);
(5) targetgrid draw slots: failures don't exhaust the 3 injection budget.
tool_selector.md decision table aligned to measured reality (graph = explicit
default; others exact-signature/follow-up only).

**⛔ TWO STANDING NEXT-AXIS CONCLUSIONS (measured 2026-07-09, do not re-derive):**
1. **Efficiency is the real score lever, NOT coverage.** Even a confirmed clear
   (m0r0) scores game_score ≈ 0 — it used ~3000 actions vs a human's ~30, and
   RHAE squares efficiency. The graph tool's exhaustive BFS clears but is
   RHAE-worthless. NEXT AXIS = short-path / goal-directed solving, not more
   coverage. Do not chase more game-clears without efficiency.
2. **Harness tool-selection latency matters.** Serial LLM-per-switch (gemma SWA
   ~10s/call) is too slow when the right tool isn't the first pick — a click game
   where graph is the 4th pick took 20+ min for ONE game. Fix: better first-pick
   routing OR parallel tool trials. Relevant to the 9h/110-game budget.

**⛔ CRYSTALLIZED 2026-07-09 — GOAL INFERENCE is THE 25/25 bottleneck, NOT search.**
Measured full 25-game coverage (direct probe, `scripts/tool_coverage.sh`):
- `graph` frontier-BFS = **up to 7/25** and climbing (vc33, m0r0, lp85, r11l,
  tn36, lf52, cn04). Started at 4; each cleanly-ported/enriched technique recovered
  a game with NO regression: click-tiering (area/rarity/contrast) → tn36; heuristic
  FILL goal-ranking (score_goal blend) → lf52; **multi-goal trend tracker**
  (GoalMeasureTracker over the WHOLE candidate-goal family, throttled every 6th
  state) → **cn04, a TRANSFORM game** (Gap-2 progress with NO LLM). INERT: budget
  8000, promise-frontier alone. cd82 still 0 (target not in the goal family yet).
  ✅ graph frame-only multi-goal tracker (7/25) is the BEST config — keep it as default.
- ⛔ **EXHAUSTIVELY MEASURED CEILING (2026-07-09): 7/25 is the wall for EVERY approach
  tried.** More candidate-goal types REGRESS (CLEAR_COLOR lost cn04). ALL LLM goal
  inference ≤ frame-only: llm_goal 0, code-agent 0, hybrid (LLM GoalSpec → graph
  via set_external_goal) LOST cn04 (1→0) and 0 on transform games. ROOT CAUSE: the
  GoalSpec vocabulary (FILL/CLEAR/COUNT/ORDER/ON_TARGET/MOVE/MATCH) cannot EXPRESS
  the transform games' true targets, so neither heuristic trend-tracking nor LLM
  inference within it can steer there — 7/25 is the COARSE-goal ceiling.
- 🎯 **BREAKTHROUGH (2026-07-09): RICHER goal representation BREAKS the wall.**
  `graph.set_target_frame(target)` accepts an arbitrary TARGET FRAME (not a GoalSpec)
  and ranks frontiers by `_downsample` (8x8 block-majority) distance to it. The
  `probe_tool_direct --targetgrid` mode: after warmup the LLM is shown the current
  8x8 downsample and asked to DRAW the SOLVED board as an 8x8 grid; inject it.
  **RESULT: cd82 0→1** — the transform game that resisted frame-only multi-goal,
  hybrid GoalSpec, budget 8000, AND goal-weight sweep (all 0). cn04/vc33 kept.
  So graph+targetgrid clears ≥8. **THIS is the validated 25/25 frontier lever: LLM
  draws the target FRAME (beyond the GoalSpec enum), graph steers to it.** Push it:
  better target prompt / per-level re-draw / stronger model unlocks more transform
  games. Infra built: set_target_frame + set_external_goal + probe --targetgrid/--hybrid.
  ⛔ the "7/25 ceiling" was coarse-goal only — richer goal repr goes higher.
- **CORRECTED FINAL (2026-07-09, 9 probe + 8 harness samples): graph = 7/25 solid;
  cd82 clears ~30% of runs via targetgrid** — the early "8/25" was small-sample
  luck (probe 3/4 early → 0/5 late; harness 0/8 same distribution, all mechanical
  suspects excluded by trace). targetgrid is a KEPT upside-only deployed fallback
  (≤3 LLM calls; feedback-gated redraw so a paying-off target is never overwritten
  — blind periodic redraw was measured to regress). ⛔ targetgrid param space is
  CLOSED (prompt/validation/redraw-policy/model[gpt-oss fails format]/res[16
  regressed]/LLM-params all measured): ~30% draw quality is the gemma-scale
  ceiling. Past it = richer target sources (EWM executable rules / stronger
  drawer) — the dedicated research cycle. Productized infra: tools/targetgrid.py
  (shared), UnifiedAgent._maybe_draw_target (warmup 40, ≤3 draws, stall-gated),
  graph.set_target_frame/target_stalled, probe --targetgrid/TARGETGRID_MODEL/RES.
- `world_model` = 0/25 (inert standalone), `toggle` (new GF(2) lights-out tool) =
  0 (NO lights-out in the 25 — ⛔ built on an unverified assumption; `inspect_game
  .py` revealed ft09/cn04/lf52 are multi-color TRANSFORM games, not lights-out).
- 25-game taxonomy (`.wiki/raw/game_taxonomy_20260709.txt`): 11 of 25 are
  transform/recolor games whose clear needs the TARGET configuration INFERRED.
**The lever for 25/25 = working goal inference for the 11 transform games.** Two
mechanisms exist but are currently too weak: `llm_goal` (LLM picks a coarse
GoalSpec: FILL_COLOR/ORDER/ON_TARGET — ft09=0) and `code_agent` (LLM writes
bespoke Python — re86=0/8). Making EITHER actually solve transform games is the
project's core open problem (r51/r52 EWM circled it). Methodology LOCKED: run
`inspect_game.py --summary` FIRST, never build a tool on an unverified mechanic.
⚠️ VM ops: arcengine DEADLOCKS under parallel probes (run sequential); `setsid`
-detached runs HANG (run foreground-in-ssh via a client-side background shell).
See [[project_dev_test_env]] (GCP VM = Kaggle-identical) and
[[feedback_measurement_discipline]]. Note: VM SSH is flaky (frequent 255) —
launch benches setsid-detached + `</dev/null`, verify via log mtime.

**⛔ GOAL-REPRESENTATION LADDER FULLY MEASURED (2026-07-09) — do not re-climb:**
enum GoalSpec (hybrid) = 0 & LOST cn04; static target frame = +cd82 ~30% only;
executable scorer (goalcode: LLM writes goal_score(frame), sandboxed via
tools/goalcode.py + graph.set_external_scorer) = 9 clean injections, 0 unlocks,
LOST cn04. **The wall is gemma's GOAL-INFERENCE ACCURACY, not representation
expressiveness** — richer forms just express wrong goals more precisely. 25/25
needs a better goal-EVIDENCE source (cross-level clear observation / stronger
model / reward-structure learning) — genuine research. Infra all kept & tested
(set_external_goal / set_target_frame / set_external_scorer + probe --targetgrid
/--goalcode); only targetgrid ships as deployed default (upside-only). NOTE:
gemma reflexively writes `import numpy` — goalcode strips numpy imports before
sandboxing (the first sweep had 0 injections from that rejection alone).

**PARALLEL VM + MULTI-MODEL (2026-07-10, user directive):** 3 concurrent unified
runs verified deadlock-free on the VM — ⛔ the old "arcengine sequential only"
note was an artifact; parallelize benches (separate nohup + per-game --out).
VRAM 98GB holds gemma4-31b(33G)+26b-a4b(15G)+qwen30b(18G) co-loaded. sk48 1/8
x2 → **12/25 SOLID** (sk48 = unified-only win, legacy@8000=0). **ka59@30k=1/7**
→ adaptive per-game budget is a coverage lever (sb26/tr87@30k=0, their wall is
goal inference). **🚀 v7 KAGGLE-VALIDATED (2026-07-13 21:05): server score 1.6054, 23 levels/25
envs** — the 18/25 card with perfect-efficiency wall clears beats the TOP
anchor (~1.56) on the public-25 proxy. Submit ceremony recorded in the round
page (v7, -f submission.parquet, slot resets 09:00 KST). v6 (#54637991)
hidden-set rerun PENDING = first transfer datapoint.

**✅ WALL-CRACKING DAY (2026-07-13 PM): card 15→18/25** — s5i5 L1 19/20a,
re86 L1+L2 24/26+40/42a, wa30 L1 30/71a (ALL level score 1.0) via new WMA
mechanic families slider.py / transform_route.py / delivery.py (records-first
+ live-trace + measured-constants doctrine; ~25 new tests each cycle; 757
total). Also landed: motion sprite classification, action-correlated region
masking (fraction rule), transition-staleness fingerprint, merge-drag stall
guard, legend-order merge chain (10→6→15→11 — NOT colour+1!), multi-goal
detection. Banked with elimination tables in wiki: tr87 dial win-rule (5
hypotheses), dc22 confined-avatar mask discriminator (3 formulations), su15 L3
delivery (AABB/transparent-corner + indicator-block leads), wa30 L2 patrol
actor, re86 L3 geometry, s5i5 L2 reveal-matching. v2 submission staged:
dataset v3 + kernel v7 (proxy ~1.23) — submit at the 09:00 KST slot reset.

**🏁 FIRST SUBMISSION (2026-07-13 16:41 KST): #54637991 PENDING** — hidden-set
rerun in progress (gateway path). Protocol chain that got here: scorecard-JSON
is validation-only; real submissions = kaggle_evaluation gateway
(KAGGLE_IS_COMPETITION_RERUN → ARC_BASE_URL http://gateway:8001/) + a
placeholder submission.parquet in interactive runs + submit -f
submission.parquet -v N. Slot = 1/day (00:00 UTC). Today's wall-cracking work
(s5i5, re86 L1-L2 — all at level score 1.0 via slider.py/transform_route.py
mechanic families) is NOT in this submission; tomorrow's slot carries it
(public-25 proxy → ~1.21).

**🏁 KAGGLE-VALIDATED (2026-07-13 14:10): kernel v4 COMPLETE server-side —
submission.json score = 1.0721 (EXACTLY matching the local 1.072%), 19 levels
/ 25 envs / 245,867 actions, ~2h runtime.** Dataset jaehyukhyun/admorphiq-src
+ kernel admorphiq-arc-agi-3-chained-llm-free. Daily submission slot untouched
— step 3 awaits user go. Mount lessons: CLI attaches nest under
/kaggle/input/{competitions,datasets}/...; walk-resolver + ARC_AGENTS_DIR env
override in _agents_shim are the fixes.

**✅ SINGLE-ARTIFACT (2026-07-13): `--agent chained` @8000 = 15/25 cleared,
TOTAL 1.076% measured** (ChainedAgent: WMA probe first banks efficient clears
incl. ft09/tn36/tu93/lp85 which WMA also clears; unified handover recovers the
graph card; restart_on_game_over must be exposed on the wrapper — the runner
consults it). ka59 = runner-level 30k retry (+1 → 16). ⚠️ sk48 is
chain-fragile (unified solo 1, chained 0 — probe prefix perturbs it; zero
score impact). Anchors: online-RL 0.51%, M1 1.21%, top ~1.56%.

**✅ CARD 2026-07-11 05:16: 17/25 under the 3-PASS FALLBACK policy** — (1)
unified@8000: cd82 cn04 ft09 lf52 lp85 m0r0 r11l sk48 sp80 tn36 tu93 vc33;
(2) unified@30k retry: ka59, ar25; (3) **worldmodel@2000 retry (the R28
WorldModelAgent, --agent worldmodel): sb26 259a, su15 2 LEVELS/58a, ls20 88a —
all deterministic x3**. RHAE proxy ≈ 0.9% (efficient clears dominate: ar25
0.083 + su15 0.067 + ls20 0.036 + sb26 0.028) — past online-RL 0.51%, nearing
M1 1.21%. Discovery chain: efficiency diagnostic → forgotten 7/8 orch json →
driver genealogy → R28 arrangement planner. Remaining 8 walls: bp35 dc22 g50t
re86 s5i5 sc25 tr87 wa30 (WMA cheap-fails them in 50-200 actions). PORT QUEUE:
R28's object-centric planners (descend-and-sweep arrangement, selection modes,
completion-correlated colour goals) into the r53 world_model tool. Kaggle
runner: implement the 3-pass chain wall-clock-aware (pass 3 is cheap, can run
first).

**(superseded) CARD 2026-07-11 05:04: 14/25 under the ADAPTIVE-BUDGET policy** (8000
default + one 30k retry on unsolved): 12 solid @8000 + ka59 + ar25 @30k (both
3-sample; ar25 needed 100k in legacy — the unified noise stack opens it at
30k). Budget opens nothing else (10 other walls 0 @30k). Remaining 11 games:
ALL cheap axes closed by reliable measurement (budget/model/draw-diversity/
code) → the one open road = RICHER GOAL EVIDENCE (also the RHAE root).

⛔ CODE-SYNTHESIS AXIS CLOSED (2026-07-11): the reliable measurement (routing
starvation fixed via deterministic escalation, wall-clock holes closed) = wall
0/6, and escalation BREAKS sk48 (0/3 ON vs 1/2 OFF, causality pinned) →
HARNESS_CODE_ESC default OFF; infra (dynamics prompt, refine loop, caps) kept
behind the flag. Card 12/25 restored. Ops standard: scp script-file + `setsid
nohup bash ~/script.sh` + verify by the script's own log (client ssh hangs say
nothing; chmod in a hung ssh silently never runs).

Multi-model campaign CLOSED (2026-07-10 01:00): 4 models (gemma26b-a4b/
qwen3-coder-30b/gemma31b-q8/gpt-oss-120b) measured in parallel — card is
model-insensitive EXCEPT tu93+sk48 (need 31b; 26b loss 0/2 model-real); ⛔ the
13-game wall is INVARIANT under model scale/family (120b also 0 on su15/ka59/
sc25/re86/wa30) → not a model problem; draw-ensemble has no complementarity
(deprioritized). Deployed brain+drawer stays gemma4:31b-q8. Coverage lever:
ka59@30k=1 → adaptive budget (8000 default, 30k retry) at the runner level.

**✅ FINAL DEPLOYED CARD (2026-07-10 00:12): 11/25 SOLID, all verified under the
final noise stack** — cd82 cn04 ft09 lf52 lp85 m0r0 r11l sp80 tn36 tu93 vc33
(GF_GIVEUP=8000). Session arc 2026-07-09: 8 → 11. The porting chain, each step
measured: (1) legacy R38 GLOBAL CLICK-TIER GATE → ft09 closed; cd82 regressed
4/4→0/3 (gate starved the drawn-target pursuit) → fixed by bypassing the gate
whenever an explicit target/scorer is active. (2) Hash ladder pool1→pool2→
object (fire@500) — pool2/object rungs INERT for the gap games but harmless;
kept. (3) ⛔ moving-BAND mask: measured harmful (vc33 1→0 false positive,
target unmoved) — REVERTED, do not re-add. (4) **REGION-level rate mask (the
breakthrough)**: legacy GF_REGION_MASK (cells rate>0.05 → components → mask
aggregate-rate>0.7 regions ≤30% of board, dilate 1, sticky, refresh 16/32-win)
→ tu93 AND sp80 closed (+ a one-sample vc33 2/7 depth event, not solid); its
515-cell transient mask sank cn04 → fixed with the SIZE-CONDITIONAL gate
(≤128 cells masked on sight; larger additions need 2-consecutive-refresh
stability). Legacy@8000 gap set pinned: ar25 bp35 ka59 ls20 sb26 sk48 tr87
need 30k-100k budgets even in legacy (RHAE-worthless; ⛔ not port targets).
The ported-technique well is DRY — remaining 14 = goal-inference frontier +
efficiency axis. cd82 went
0/8 → 4/4 via the diagnostic chain: grid-dump trace showed gemma's drawn targets
were often GOOD; explicit-target proximity ([-1,0]) was blended at 0.05 against
integer frontier promise — PROVABLY INERT; now _TARGET_STEER_WEIGHT=50 dominates
(graph_search.py). Win condition = dominant steering × 3 stall-gated draws ×
8000 budget (probe single-draw@5000 still stochastic — deploy config matters).
⛔ Re-verified under real steering: the other 17 games' draws are genuinely wrong
(inference-accuracy wall) — 18-game probe re-sweep all 0. Next threads: (1) L2+
depth (tn36's plausible L2 target unpursued to completion — combinatorial click
space or full-res mismatch; cross-level clear-evidence lever built & tested);
(2) draw accuracy for the 17 (better evidence/models — research).

**⛔ ZERO-GRADIENT HYPOTHESIS REFUTED (2026-07-09) — 8x8 proximity is LOAD-BEARING.**
Full-res per-pixel proximity vs the kron-blocky target regressed cd82 4/4 → 0
(block-interior texture noise floor -0.38/-0.78 swamps and distorts the proven
frontier ordering) and tn36 L2 showed ZERO pixel progress over 400 calls even
with a gradient-capable metric. Reverted byte-identical (commit 0d2afb2). ⛔ do
not replace the 8x8 block-majority with full-res compare. **tn36 L2 verdict:
UNREACHABLE drawn-target region (combinatorial/programming-puzzle click space)
— leaves the targetgrid thread.** NEW LEAD: r11l L2 pursuit DID move (best_prox
-0.282 → -0.235 across windows) — gradient alive, budget-undershot → budget
scaling (16000) probed on r11l/vc33.

**⛔ MORE 2026-07-09 CLOSURES:** (a) Budget 2x (16000) does NOT unlock r11l/vc33
L2 — r11l converges (-0.109, residual = the draw's own error), vc33 frozen
(wrong draw) → L2 wall = DRAW QUALITY. (b) Redraw diversity (action-evidence
enriched redraws, r51 config-UNION idea) = NO-GAIN after 2-config sweep,
reverted; durable lesson: ⛔ never insert prose between the board grid and the
OUTPUT instruction in targetgrid prompts (gemma outputs degenerate single-colour
grids — this retro-explains the r51 "richer prompt regressed cd82"). (c) NEXT
THREAD (Gap-1, precise): legacy graph_frontier FINAL2@100k clears 10 games the
unified harness doesn't — AR25 BP35 FT09 KA59 LS20 SB26 SK48 SP80 TR87 TU93
(TU93=3, VC33=3 depth); measuring legacy @8000 on the 10 to pick port targets
(techniques that clear at deployed budget).
