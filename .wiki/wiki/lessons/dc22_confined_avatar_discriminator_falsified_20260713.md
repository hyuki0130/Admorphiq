---
type: lesson
symptom: "graph tool's region mask swallows a confined avatar's own region (same high-action-diversity signature as genuine HUD noise), and two candidate per-key discriminators both fail to fix it"
severity: warn
first_seen: 2026-07-13
---

# The confined-avatar vs HUD-widget discriminator: two formulations measured and falsified

> Discovery incident log for the `tools/graph_search.py` region-mask family
> (see [[../rounds/r53_unified-harness]] for the full round). The landed FIX
> ([[../rounds/r53_unified-harness]] "Action-correlated masking LANDED") solves
> the ORIGINAL bug (a toggle button's region swallowed by the rate-only
> mask). This page documents a SEPARATE, deeper, still-open gap: a player
> CONFINED to a small area (e.g. a walled starting box) churns the same few
> cells under every movement key, showing the exact same "high action-
> diversity" signature a genuine HUD widget shows — so the fraction rule
> correctly refuses to spare it, and the avatar's own region gets masked,
> blinding the graph to different in-box positions.

## What was measured (both formulations, live, against dc22)

Two candidate discriminators for "does this region's per-key behaviour look
like HUD (same regardless of key) or game state (differs by key)" were
measured live (1200 and 600 step traces respectively, `--agent unified`,
`tools/graph_search.py` instrumented, zero source changes shipped for
either) BEFORE implementation, per this project's measurement discipline.

**1. Per-key diff-set Jaccard similarity** — for each action key, union the
region cells that changed under it; compute mean pairwise Jaccard across all
key pairs. Hypothesis: HUD → high similarity (same cells regardless of key);
avatar → low similarity (different cells per key).

- row63 (HUD ground truth, 71 samples): min=0.16 max=1.00 mean=0.68
- box (avatar ground truth, 57 samples): min=0.35 max=0.78 mean=0.47

Ranges overlap heavily (row63's own minimum is below the box's mean; the
box's maximum nearly reaches row63's maximum) — no threshold cleanly
separates the classes.

**Root cause of the overlap**: dc22's row-63 widget is a MONOTONICALLY
ADVANCING bar (a fill level that only grows), not a cyclically REPEATING
digit display. Cell-identity Jaccard assumes "the same key always touches
the same cells" — true for a repeating pattern, false for a bar whose
position depends on cumulative elapsed actions rather than which key caused
the tick. So even SAME-key-to-SAME-key comparisons for the counter came out
low sometimes, breaking the hypothesis's own premise for the HUD class.

**2. Per-key displacement vector** — for each transition, compute
`arrived_centroid - vacated_centroid` within the region (local-background-
aware: a walled sub-scene has its own floor colour distinct from the
frame's global background, so vacated/arrived must be computed relative to
the REGION's own dominant colour, not the whole-frame one, or a confined
avatar's movement is invisible to the metric entirely — first version of
this measurement returned zero samples for the box until this fix). Average
per key, then compute mean pairwise cosine similarity across keys.
Hypothesis: HUD → same direction regardless of key (cos ~1); avatar →
key-dependent direction (cos low, sometimes negative for opposite keys).

- row63: **UNUSABLE — zero valid samples across the entire 600-step trace.**
  A monotonic bar never vacates a cell (nothing reverts to background), so
  "arrived minus vacated" is undefined for the one ground-truth HUD case
  that actually matters on this game.
- box: mean pairwise cosine similarity **0.62-0.99 — the OPPOSITE of the
  hypothesis** (predicted LOW for game state, measured HIGH). Individual
  per-key vectors were also internally inconsistent: the SAME action key
  (e.g. id 1) showed different, sometimes physically-backwards directions
  across different refresh windows, rather than a stable per-key signature.

## What it taught

Two independent, principled-sounding "does the region's behaviour depend on
WHICH action caused it" formulations both failed on live measurement,
for two DIFFERENT reasons — cell-identity assumes a repeating pattern (fails
on a monotonic counter), and centroid-displacement assumes a rigid two-tone
foreground/background scene with clean vacate/arrive pairs every transition
(fails when the majority of transitions in a small, cluttered region don't
cleanly separate into a "moved rigid body" story, e.g. because gap-adjacent
static clutter — RE86-style — gets folded into the same connected "noisy"
component as the true moving part). Neither the cell-SET nor the
cell-CENTROID abstraction was sufficient; a real fix likely needs a
different unit of comparison (e.g. per-key VALUE identity at a per-cell
level, or a template-match of the moved sub-shape) that this session did
not reach.

## Recovery / open leads for a future session

- The confined-avatar gap remains OPEN: dc22, g50t, sc25, bp35 (all
  avatar-confined-to-a-small-area movement games) stayed at 0 clears with
  only the fraction fix in place, unchanged from before this round.
- A future attempt should measure FIRST (this project's now-established
  discipline for this exact file) before implementing, using the same
  monkey-patch-and-live-trace method these two formulations used.
- Untried ideas worth measuring: (a) per-key PIXEL-VALUE agreement (not
  just cell-set or centroid) — does cell (r,c) show the SAME colour
  transition regardless of key, vs a DIFFERENT one depending on key; (b) a
  size/shape prior — a confined avatar's region tends to be small and
  roughly SQUARE/compact (a walled room), while many real HUD widgets are
  a thin bar/strip; (c) simply not attempting to region-mask a component
  that overlaps the LAST KNOWN avatar position at all, sidestepping the
  action-correlation question entirely for that one region.

## Falsification

This page is falsified if either formulation is re-measured and found to
separate cleanly (e.g. after a bugfix in the measurement itself) — if so,
update the verdict here rather than deleting the page, and record what the
bug was.

## Related

- [[../rounds/r53_unified-harness]]
- [[../games/DC22]]
