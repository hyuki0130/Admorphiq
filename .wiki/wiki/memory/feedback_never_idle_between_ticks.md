---
name: feedback_never_idle_between_ticks
description: "Never wait for the next cron tick — the cron is a watchdog, not a work queue; keep measuring continuously"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: bb13c818-83df-45a0-b3ba-ed04d6fc1192
  modified: 2026-08-24T14:42:37.370Z
---

The 10-minute `/loop` cron on this project is a **watchdog**, not a work schedule. Its job is to
notice if work has stalled and restart it — not to hand out one task per firing.

**Why:** the user said so twice, with visible frustration ("왜 진행중인게 없어?", "이어서 한다며..
왜 안해?", "왜 자꾸 멈추는거야.."), after I finished a commit and idled until the next tick. Ending
a turn with "다음은 X를 재겠습니다" and then stopping wastes the whole interval.

**How to apply:** after committing a step, immediately run the next measurement in the same turn.
Only stop when genuinely blocked on the user or on a long background job — and even then, start
something else that does not depend on it. Never end a turn with a stated next step left unstarted.

Related: [[feedback_never_stop]], [[feedback_measurement_discipline]].
