---
type: lesson
date: 2026-07-15
rounds: R56
status: six probe-validity failures diagnosed and fixed (R56 bp35 determinism /
  tn36 bit-toggle / decisive-single-variable; R59 r11l bare-stepping probe
  degenerates display_to_grid + faithful passive-read recovery; R59 sk48 set_level
  replay-budget artifact; R59 cn04 set_level+RESET blame CORRECTED to a real
  executor bug after the VM reproduced the failure)
keywords: [probe-validity, available-actions, diff-threshold, determinism-probe, single-variable-probe, false-confirmation, standalone-probe-unfaithful, display-to-grid-degenerate, faithful-passive-read, run-the-runner-path, set-level-reset-non-restoration, deep-level-forcing]
---

# A probe only measures what its action actually exercises (R56)

> Three separate R56 adapters were misled by probes that LOOKED conclusive
> but exercised nothing real: a determinism probe that issued an UNAVAILABLE
> action (a no-op that trivially reproduces), a mechanic sweep whose diff
> THRESHOLD filtered out the real 3-pixel effect, and hypotheses built
> before a decisive single-variable probe. All three produced confident
> WRONG conclusions. The fix is a discipline, not a code change.

## Symptom

A probe returns a clean, repeatable signal and the adapter draws a strong
conclusion from it — then the live measurement contradicts the conclusion,
or a source read shows the probe never touched the mechanic it claimed to
characterise. Three concrete instances this round:

1. **bp35 "deterministic per-action gravity" (FALSE).** A determinism probe
   issued the same action twice from a fresh env and got byte-identical
   frames, concluding the dynamics are deterministic and frame-keyable. The
   flaw: the probe issued `ACTION1`, which is NOT in bp35's
   `available_actions` (`[3, 4, 6, 7]`) — a no-op that only ticks the step
   counter. It trivially reproduced because it did nothing. A proper probe
   of the AVAILABLE controls found bp35 is a MOMENTUM platformer with HIDDEN
   velocity (`ACTION4` displaced 2, 6, 6, 6, 6, 3 cells on successive presses
   — acceleration), so the same visible frame transitions differently under
   the same action: the `(frame-state, action) -> frame-state` graph is
   ALIASED. See [[../games/BP35]].
2. **tn36 bit-toggle masked by a diff threshold (MISSED).** An earlier
   frame-only refactor swept for interactive controls by filtering for large
   per-click diffs, and concluded the big colour-4 cells (rows 9-28) were the
   toggles. They are the program DISPLAY. The real bit row is at grid `y=44`;
   toggling one bit is a ~3-pixel change (colour 5 <-> 1) that a large-diff
   filter drops entirely. The wiki had already recorded the correct control
   layout; the fresh sweep contradicted it and was wrong. See [[../games/TN36]].
3. **Hypotheses built before a decisive probe.** Several adapters spent
   action budget testing broad mechanic guesses that a single set-one-bit /
   single-click-from-reset probe would have settled first.
4. **r11l "clicks never move legs" (FALSE — a standalone probe that did not
   replicate the runner path).** A bare-stepping probe (its own
   `env.step(click_action(...))` loop, plus poking `env._game.camera` /
   monkeypatching internals) concluded that L1 placement clicks never move a
   leg and blamed a "level-dependent camera transform". Both were artifacts:
   outside the harness's render/observation cadence the camera's
   `display_to_grid` DEGENERATES — it mapped EVERY click to grid `(0,0)`, so
   the probe's placements went off-board and refused. The tell that the probe
   was unfaithful: **L0 clears in the very same loop**, which is impossible if
   `display_to_grid` were really returning `(0,0)` for all clicks. A standalone
   probe that contradicts a known-good behaviour (L0 clearing) is measuring its
   own scaffold, not the game. The real faults were ordinary: some placements
   collide with the arena wall and are refused, and the rigid plan derails
   under refusals. See [[../games/R11L]].
5. **`set_level(n)` + `reset_action()` does NOT restore a fresh level-n state
   (INCONCLUSIVE, two games).** Forcing a deep level with `env._game.set_level(n)`
   reaches level n's board, but the follow-up `reset_action()` the runner path
   would issue between levels does NOT re-initialise it to the pristine
   first-entry state — internal counters / selection / momentary state carry
   over. This makes any probe that depends on entering level n CLEANLY
   untestable locally: sk48's replay env kept `budget=196` after
   `set_level+ACTION7` (moves silently swallowed until the parse env was
   separated from the replay env) — a genuine set_level artifact. **cn04 was a
   MISATTRIBUTION, now CORRECTED (R59 VM diagnosis).** The initial bank blamed
   this caveat for cn04's L3 chirality auto-select reaching `n8=0` without a win
   under `set_level(2)`, calling it "unconfirmed until the VM." When the VM
   measured the NATURAL chain it ALSO failed (2/5, L3 not cleared) — proving
   `set_level(2)` had FAITHFULLY reproduced the failure all along, and the real
   cause was a bug in OUR executor (the chirality RESET re-probes and derives a
   different plan, so "swap flip" is not "same geometry, opposite pairing"). The
   engine's `handle_reset` was read directly: a mid-game RESET takes the
   `level_reset()` branch and restores the current level pristinely — the
   harness was faithful; our code was wrong. Lesson: "the set_level/RESET harness
   caveat" is a convenient explanation that can MASK a real bug — before banking
   a deep-level result as "harness-INCONCLUSIVE", read the engine's reset path
   and check whether the forced entry actually diverges from the runner path (for
   cn04 it did not). See [[../games/SK48]], [[../games/CN04]].

## Root Cause

A probe is only evidence about the code path it actually drives. An
unavailable action drives no controls, so its determinism says nothing about
the game's real dynamics — but a byte-identical repeat FEELS like strong
confirmation. A diff threshold chosen for one game's effect size silently
discards a smaller-but-real effect in another. In both cases the probe's
output is internally consistent and reproducible, which is exactly what makes
the false conclusion convincing: consistency is not validity.

## Prevention

- **A determinism / dynamics repeat-probe MUST use an action that is in
  `available_actions` AND is observed to MOVE the agent.** A no-op reproduces
  trivially and proves nothing. Confirm the probe action produces a real,
  non-cosmetic state change before trusting any conclusion drawn from
  repeating it.
- **Do not trust a single diff THRESHOLD to find "the controls".** A real
  effect can be a few pixels (tn36's bit toggle is ~3 px). Before concluding
  a sweep found the interactive layer, cross-check against the wiki's already
  recorded findings for that game — a fresh probe that CONTRADICTS a recorded
  measurement is a signal to re-probe, not to overwrite.
- **Run a decisive single-variable probe BEFORE building a planner.**
  Set-one-bit, single-click-from-reset, one-move-from-a-fresh-env: isolate
  one variable and measure its exact effect first. Cheap decisive probes
  retire whole hypothesis branches that would otherwise cost action budget to
  falsify indirectly.
- **A frame-diff "restoration" check proves the DISPLAY is restored, NOT the
  hidden game state.** cn04 R60: a `level_reset` restored the visible board to a
  0-cell diff, which "proved" the retry board was pristine — yet the exact
  winning execution then failed, because the engine's win-check keys on the
  ORIGINAL marker colours (a hidden 8/13 identity the frame renders identically),
  and the re-clone's in-place `color_remap` scrambled them. Any state that does
  not render into the frame (hidden colours, RNG seeds, internal counters) is
  invisible to a pixel diff, so "the board looks identical" is NOT "the game
  state is identical". When a result hinges on restoration, confirm it with a
  BEHAVIOURAL invariant (does a known-winning sequence still win after the
  restore?), not a frame comparison. The decisive test was exactly that: fresh
  board wins, RESET-then-same-sequence loses → the RESET corrupts hidden state.
- **A standalone probe MUST replicate the runner path, and a probe that
  contradicts known-good behaviour is measuring itself.** Effects that only
  hold inside the harness's render/observation cadence (e.g. r11l's
  `camera.display_to_grid`, or the `data=` payload the `score_efficiency`
  loop passes on complex actions) silently degenerate in a bare
  `env.step` loop. Before trusting a standalone probe, confirm it reproduces a
  KNOWN result (a level the real adapter clears); if the probe says something
  the runner already disproves (r11l L0 clears, yet the probe claims no click
  ever lands), the probe is broken, not the game. **Prefer FAITHFUL PASSIVE
  READS: run the ACTUAL adapter loop and read `env._game` internals passively
  (no monkeypatching) after each real adapter action.** That gave r11l its
  ground truth — legs DO move on valid placements — that every standalone
  probe got wrong.
- **`set_level(n)` reaches a deep level but does NOT reproduce a natural entry;
  treat any result that hinges on the post-`set_level` `reset_action()` as
  INCONCLUSIVE, not a verdict.** The forced board carries internal counters /
  selection / momentary state that a natural level-n entry would not, so a
  between-level transition (a fresh budget, a chirality auto-select, a replay
  from step 0) does not fire the way it would on the runner path. When a probe
  needs a clean level-n entry and that level is only reachable naturally on the
  VM, the honest bank is "feasible offline, natural-entry confirmation pending
  on the VM" — do NOT record a local forced-entry pass/fail as the answer.
  Confirmed genuine for sk48 (replay budget frozen at 196). But this caveat is
  ALSO a convenient excuse that can mask a real bug: cn04's L3 failure was
  initially banked as "harness-INCONCLUSIVE, pending VM" and then the VM
  reproduced the SAME failure — the forced `set_level(2)` entry had been faithful
  all along, and the bug was in our executor. Before invoking the caveat, READ
  the engine's reset path (`base_game.handle_reset` → `level_reset` restores the
  current level pristinely mid-game) and verify the forced entry actually
  diverges from the runner path; if it doesn't, the local result IS the answer.

## Recovery

When a probe-derived claim is contradicted, re-derive it from a probe that
provably exercises the real controls: pick an action from
`available_actions`, verify it changes the frame, and only then draw the
conclusion. bp35's momentum/hidden-velocity mechanic and tn36's true bit-row
layout were both recovered this way (measured, then banked as honest
0-results with the corrected mechanic documented in each adapter's docstring).

## Falsification

This lesson would be wrong if a determinism probe using an unavailable action
still reliably characterised a game's real dynamics (it did not for bp35), or
if a fixed large-diff threshold reliably surfaced every game's interactive
controls (it did not for tn36). Both are disproven by measured
counterexamples this round.

## Related

- [[frame_diff_as_probe]] — the complementary lesson on frame-diff as the
  primary observation signal; this page is its failure-mode counterpart (the
  diff signal is only as good as the action that produced it).
- [[../rounds/r56_generic-kernels]] — the round whose expansion sprint
  surfaced all three instances.
- [[../games/BP35]], [[../games/TN36]] — the two adapters whose banked
  divergences carry the measured counterexamples.
- [[../games/R11L]] — the R59 counterexample: a bare-stepping probe
  degenerated `display_to_grid` and produced two wrong claims (no click lands /
  camera transform), corrected by faithful passive reads inside the real loop.
