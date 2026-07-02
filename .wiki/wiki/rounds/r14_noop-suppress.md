---
title: R14 — noop suppress
type: round-log
round: R14
axis: efficiency action-selection
keywords: [noop-suppress, exact-frame-hash]
verdict: FAIL (byte-identical)
commit: none
date: 2026-07-02
---

# R14 — noop suppress

**Axis**: efficiency action-selection · **Verdict**: FAIL (byte-identical)
**Keywords**: noop-suppress, exact-frame-hash

No-op suppression keyed on (exact frame_hash, action). Byte-identical result — exact frames never repeat so the gate never fired.

**Related rounds**: [[r15_dead-action-prune]]
See the map: [[rounds_index]]. Deployed-card lineage + reliable metric: [[online_rl_sprint_round_log]].
