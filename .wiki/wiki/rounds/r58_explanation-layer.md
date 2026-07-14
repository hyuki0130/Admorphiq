---
type: reasoning
round: R58
axis: explanation-layer
verdict: IN-PROGRESS — P0/P1 (Navigation Vertical Slice v0) + P2 (GoalLedger, calibration-fixed) built; P3 not started; residual TOP1 gap reframed as detector-selectivity (game-context weighting), not calibration — open Codex question
keywords: [explanation-layer, protocol-compiler, typed-intents, enforced-state-machine, goal-ledger, navigation-vertical-slice, playbook, falsification, strike-budget, agent25, floor-anchoring, detector-selectivity]
commit: [5ceb5ec, 3759c4f, 0f105e0, 70686d1, 0a31279, 8166efd, 29a9ca8, 2fe6c21]
date: 2026-07-15
---

# R58 — Explanation layer: protocol compiler for the weak offline LLM

> Codex verdict on teaching the offline model to use R56's kernel suite:
> build a harness-enforced protocol compiler (typed intents + an enforced
> state machine + executable goal detectors), not a bigger wiki. This
> round built the first two artifact tiers and measured/fixed the third.

## Why this exists

The user directive behind this round: the tool layer must not just clear
the public games, it must **explain itself** to the local model well
enough that the model — not hand-written per-game code — is the thing
doing the clearing on unseen (agent25/hidden) games. R56 built the kernel
computation layer; R57 named the goal-evidence vocabulary; this round is
the missing middle piece — HOW a small offline model reliably invokes
either of those without memorizing kernel names or voluntarily following
a prose checklist (the R23-era measured failure: "selector is advisory,
not enforced" — 8B-class models don't reliably follow prompt-only
routing rules, see `.wiki/wiki/lessons/selector_is_advisory_not_enforced_20260421.md`).

## Codex verdict (binding)

Full text: `docs/r58_codex_explanation_layer_20260715.md`. Reject a larger
wiki as the fix; adopt a **harness-enforced protocol compiler**. The
model should choose semantics — roles, hypotheses, goals — but should
never need to remember kernel invocation syntax or self-police a
checklist. Once it declares an intent, the harness validates the
declaration, invokes the kernel automatically, and constrains the next
response to either use or explicitly reject the result — "the tool
result was available but the model ignored it" (R53/R55's measured
failure mode) becomes structurally impossible, not just discouraged.

**Artifact stack, priority order**:

| Priority | Artifact | Status this round |
|---|---|---|
| P0 | Typed intent schemas + enforced state machine | **Built** — `src/admorphiq/explanation/protocol.py` + `intents/*.schema.json` |
| P1 | Mechanic-family protocol cards (playbooks) | **Built (navigation only)** — `explanation/playbooks/navigation.yaml` |
| P2 | Executable win-condition typology (`GoalLedger`) | **Built** — `explanation/goal_ledger.py`, tuned post-validation (see below) |
| P3 | Abstracted worked packets | Partial — `explanation/examples/navigation.jsonl` seeded; not generalized past navigation |
| Never runtime-visible | Raw adapter journeys, game pages, catalog prose | Enforced by `scripts/explanation_lint.py` (packaging lint rejects public game IDs/titles, adapter imports, absolute coordinates, fixed palettes) |

## P0/P1 — Navigation Vertical Slice v0 (`3759c4f`)

Enforced `SELECT -> FILL -> auto-COMPUTE -> CONSUME -> VERIFY` state
machine (`src/admorphiq/explanation/protocol.py`):

1. **SELECT_INTENT** — decoder enum over a short dynamic allowlist; an
   invalid declaration spends **zero kernel calls** (returns a repair
   packet), which is the concrete fix for prompt-only routing's failure
   mode measured back in the R7-R11 anchor-bias rounds
   (`.wiki/wiki/lessons/` — Qwen 3 8B anchoring on familiar strategy
   names regardless of the wiki's own instructions).
2. **FILL_INTENT** — semantic slots (mover, start, goals, passable_mask,
   ...) reference harness-owned observation objects, never raw pixel
   data — the model is never asked to print a 64x64 mask.
3. **COMPUTE** (automatic) — the harness validates references and calls
   the mapped kernel itself; a valid FILL always auto-invokes the real
   path, no separate "now call the tool" turn to forget.
4. **CONSUME_RESULT** — the next decoder schema permits only `execute` or
   `reject`; a kernel result cannot be silently bypassed by an unrelated
   next action.
5. **VERIFY** — falsifiers (strong = immediate revoke, weak = strike
   budget) decommit a wrong intent via a NAMED recovery transition back
   to intent selection, rather than the model grinding on a wrong guess
   indefinitely.

Measured this round: playbook 478/500 tok, worked packets 320+280/350
tok, adoption-funnel telemetry recorded on every transition (how many
declarations were valid, how many kernel calls followed, how many were
accepted vs. rejected) — the instrumentation needed to later measure
whether this state machine actually changes agent25 adoption, not just
whether it compiles. 20 new tests, suite 1077 green at commit time.

## P2 — GoalLedger (`0f105e0`, tuned `0a31279`)

Six kernel-only, zero-action/transition detectors
(`src/admorphiq/explanation/goal_ledger.py`) consuming PRE-CLEAR state
only, covering 6 of [[r57_win-condition-typology|R57's 8 types]]:
`arrival`(T1) / `uniformity`(T6) / `containment`(T3) / `pattern_match`(T5)
/ `elimination`(T2) / `threshold`(T7). T4 (delivery) is treated as an
arrival+elimination harness-level composition rather than its own
detector; T8 (rewrite) is honestly left unsupported — R57's own mining
found zero frame evidence for it (`tr87`). Output is capped and compact
(ledger 169.5/250 tok; `compact_injection` bundle — playbook +
description-stripped schema + one-line contract — 672/900 tok, pinned by
a token-budget test) and silent (empty result, not a speculative guess)
when evidence doesn't support a call. Detectors mutually distinct by
construction, so `insufficient_evidence` is simply "fewer than two
candidates fired".

### Real-trace validation found the v1 ledger's ranking was broken (`70686d1`)

Measurement-only pass against 21 scored real games: **TOP1 hit rate
38.1%, TOPK 57.1%**. Root cause: `goal_candidates[0]` was FIXED PIPELINE
EXECUTION ORDER, not evidence strength — `elimination` and `threshold`
(the last two detectors to run) could structurally never rank first
regardless of how strong their evidence was. Two concrete over-firing
patterns also isolated: `elimination` fired off almost any single
transition (17/24 games — nearly any action changes SOME region's exact
signature somewhere on a real board, for reasons unrelated to the actual
win condition), and `uniformity` fired on 1x1 decorative background
texture (bp35/s5i5/su15) indistinguishable, under a naive
most-members-wins rule, from a genuine toggle grid. `arrival`'s
`size <= median` filter also excluded the wiki-CONFIRMED lp85 target
outright. This commit was explicitly measurement-only — "tuning decided
separately" — so the fix landed as its own follow-up.

### The tuning fix (`0a31279`, same-session follow-up)

Every candidate now carries a `"strength"` in `[0, 1]` computed ONLY from
that detector's own structural evidence (never a per-game constant);
`goal_candidates` sorts by strength descending, ties broken by the
original fixed detector order (Python's stable sort does this for free).
Per-detector strength formulas (documented in each detector's own
docstring in `goal_ledger.py`):

- **arrival**: `uniqueness_sharpness (1/n_candidates) * size_distinctness
  (1 - size/frame_area)`; the median-size filter is replaced with a
  >50%-of-frame DOMINANCE exclusion (only rules out one huge dominant
  panel, no longer excludes an ordinary-or-larger-than-median sprite).
- **uniformity**: two new hard discriminators BEFORE any class is even
  considered — shape must span >1 cell, and a class's members must use
  `<= 3` distinct colours — tried in population-descending order so a
  large disqualified (trivial) class doesn't mask a smaller genuine one.
  Strength = `population_frac * non_triviality * colour_fit`.
- **containment**: `sibling_component (1 - 1/n_siblings) * regularity`
  (how evenly item counts are split across siblings — a real slot-grid
  holds roughly equal counts; wildly uneven reads as incidental bbox
  overlap, not a designed match).
- **pattern_match**: `item_richness * colour_richness`, both saturating
  `1 - 1/n` forms.
- **elimination**: corroboration becomes a strength PENALTY, not a firing
  gate — still fires off one transition (a harness's first-observation
  call must keep working) but the caller can supply `extra_transitions`
  for a `confirmation_component` that only reaches full confidence at 2+
  independently-vanishing transitions. Also scores `size_component`
  (how close the vanish's size is to this board's OWN median region size)
  and `signature_distinctness` (fewer simultaneously-vanishing signatures
  = less ambiguous).
- **threshold**: `run_length_component (1 - 1/n_diffs) * magnitude_component`
  (a longer, larger-swing monotonic trend is stronger evidence than one
  that barely clears the firing gate).

14 tests updated/passing, ruff clean, full suite 1110 green after the
fix (test fixtures also had to move from 1x1-dot populations to 1x2
domino shapes to keep clearing the new uniformity discriminators
without becoming trivial-texture false positives themselves — see the
diff to `tests/test_goal_ledger.py`).

### Re-validation against the same 21-game real-trace set (`8166efd`, same session)

The fix WAS re-measured against the exact set `70686d1` used, with
before/after JSONs committed for the diff
(`scripts/_r58_ledger_validation_results{,_BEFORE}.json`). Mixed result,
not a clean win:

- **TOPK 57.1% -> 76.2%** (+19.1pp) — the strength-sorted candidate list
  now surfaces the right hypothesis somewhere in its top-K much more
  often. `arrival`'s dominance-exclusion fix concretely flips the
  wiki-confirmed `lp85` target from MISS to TOP1.
- **TOP1 38.1% -> 28.6%** (a **regression**, not an improvement) — a NEW
  measured finding: a cross-detector CALIBRATION mismatch. `pattern_match`
  scores confidently right at its own firing gate, while `arrival`'s
  formula naturally scores low whenever there is genuine ambiguity (many
  tied unique-colour candidates) — so on frames where both fire,
  `pattern_match`'s systematically-inflated-near-threshold score can
  out-rank a CORRECT but appropriately-uncertain `arrival` call that used
  to win by fixed pipeline order alone.
- **Zero coverage regressions** — no game that used to get ANY correct
  candidate in its list lost that candidate entirely; the miss-rate drop
  (**MISS -19.1pp**) is real signal recovery, not a wash from new misses
  elsewhere.

### Floor-anchoring fix (`29a9ca8`, same session)

Built: `_floor_anchor(raw, gate_min, gate_max=1.0)` rescales
`arrival`/`uniformity`/`containment`/`pattern_match`'s raw strength so
each detector's OWN analytically-derived value-at-its-firing-boundary
(`gate_min`, documented per detector — a fixed constant for detectors
whose every term is gated, e.g. `pattern_match`'s ~0.53, or a per-call
expression when a term is left ungated and cancels out, e.g. `arrival`'s
`uniqueness_sharpness * 0.5`) maps to a shared floor (`0.2`, uniform
across all six — a per-detector floor would reintroduce the same
calibration gap) rather than 0. `raw >= gate_min` holds by construction
for every fired detector, so the result always lands in `[0.2, 1.0]`.
`elimination` and `threshold` are NOT floor-anchored this round (left
unchanged).

### Re-validation (`2fe6c21`, same session) — calibration bug fixed, but a DIFFERENT problem remains

Re-measured against the same 21-game set, with two unit tests pinning
"barely-fired == exactly the floor (0.2)" as a hard invariant. Result:
**TOP1 flat at 28.6%, TOPK held at 76.2%, zero regressions.** Not the
hoped-for TOP1 recovery — but the fix is still confirmed CORRECT, not
inert: internal candidate-ranking shifts moved in the predicted direction
(`arrival` TOP1 picks 13 -> 16, `pattern_match` TOP1 picks 6 -> 4 — exactly
the rebalancing floor-anchoring was built to cause), it's just that those
shifts didn't net out to a higher overall TOP1 hit rate on this
particular 21-game sample.

**Reframed conclusion**: the residual TOP1 gap is a **detector
SELECTIVITY problem, not a calibration problem** — floor-anchoring fixed
"formulas aren't comparable at the margin" (proven, provable invariant),
but a separate failure mode remains: a detector can produce
GENUINE, correctly-scored evidence for its OWN type that is nonetheless
the WRONG type for that game's actual goal (i.e., strong evidence, wrong
context — no amount of rescaling one detector's own formula fixes a
cross-TYPE context mismatch). This has been flagged as a pre-registered
open question for the next Codex consultation: whether resolving it needs
game-context weighting (some signal about which detector TYPES are even
plausible for a given board, before ranking within the fired set) rather
than any further per-detector strength tuning.

## What's still open

- **P3 (worked packets)** seeded for navigation only — not generalized to
  the other mechanic families the P1 playbook tier is meant to cover.
- **Other mechanic-family playbooks** (click_induced_motion, toggle_linear,
  rare_target_probe, ...) are DESIGNED in the Codex verdict
  (`docs/r58_codex_explanation_layer_20260715.md` §3, full YAML schema)
  but only `navigation.yaml` is actually built.
- **agent25 A/B validation** — whether the enforced protocol + tuned
  ledger together actually move LLM adoption/competence on unseen games
  (the whole point of this axis, per [[r56_generic-kernels]]'s
  script25/agent25 dual-scoreboard framing) is not yet measured. The
  adoption-funnel telemetry built in the Navigation Vertical Slice exists
  precisely to make that measurement possible next round.
- **GoalLedger TOP1 gap is now a SELECTIVITY question, not a calibration
  one** (see the re-validation section above) — a genuine, correctly-
  scored detector hit for the wrong TYPE in a given game's context needs
  some form of game-context weighting to resolve, per the pre-registered
  open question for the next Codex consultation. Floor-anchoring's own
  job (cross-detector comparability) is done and proven correct.

## Related

- [[r56_generic-kernels]] — the pure-computation layer this round teaches
  the model to invoke; script25/agent25 dual-scoreboard framing this
  round's A/B validation (open item above) will eventually report against.
- [[r57_win-condition-typology]] — the typology `GoalLedger`'s six
  detectors implement.
- [[../lessons/ft09_glyph_decode_20260715]] — a concrete example of why
  knowing the win-condition TYPE (T6/toggle-parity, per R57) was
  necessary but not sufficient without the actual target-decode work.
- [[r53_unified-harness]] / [[r55_code-repl-agent]] — the prior harness
  generations whose measured failure modes ("tool result available but
  ignored", "selector is advisory not enforced") this round's enforced
  state machine is a direct structural response to.
- [[index]]
