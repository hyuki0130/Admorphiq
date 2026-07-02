---
title: R18 — object prior full25
type: round-log
round: R18
axis: exploration-prior
keywords: [object-click-prior, full-25, single-seed-noise]
verdict: FAIL (noise)
commit: none
date: 2026-07-02
---

# R18 — object prior full25

**Axis**: exploration-prior · **Verdict**: FAIL (noise)
**Keywords**: object-click-prior, full-25, single-seed-noise

Re-tested object-prior on full-25: 0.0047 vs 0.0051 baseline = within single-seed NOISE. Lesson: single-seed full-25 unreliable, need >=3 seeds.

**Related rounds**: [[r16_object-click-prior]], [[r17_full25-baseline]]
See the map: [[rounds_index]]. Deployed-card lineage + reliable metric: [[online_rl_sprint_round_log]].
