---
round: R84
axis: queue-scan / bounded-frontier audit
keywords: bounded-frontier, queue-scan, open-bounded, multi-session, settled, sc25, dc22, wa30, r11l, vc33, ar25, sp80, tr87, sk48, bp35, r11l-placeability
verdict: bounded frontier ESSENTIALLY EXHAUSTED — 1 marginal OPEN-BOUNDED (r11l L1), rest SETTLED-⛔ or MULTI-SESSION
commit: (this docs round)
---

# R84 — bounded-opportunity queue scan (task #108, 2026-07-19)

Triggered because two consecutive assignments (tu93 R82, ka59 R83) turned out
already-settled — the queue picture was stale. Surveyed every non-conquered,
non-hard-parked game's NEXT-level wall from its game page's latest bank and
classified each. **Load-bearing finding: the bounded frontier is essentially
exhausted.** The remaining lift is multi-session builds; only one marginal
bounded candidate exists (r11l L1).

## Classification (each cites its game page's latest verdict)

| game | now | next wall | class | why (bank citation) |
|---|---|---|---|---|
| **tr87** | 3/6 @0.2857 | L4 (idx3) | ⛔ SETTLED | L4 `double_translation` killed by INVISIBLE markers; L5 CRACKED but UNREACHABLE behind L4 (0 card payoff). "⛔ decisive blocker (R59): L5=idx4 UNREACHABLE." |
| **sk48** | 4/8 @0.2778 | L4 (idx4) | ⛔ SETTLED | agent-L4 CLOSED single-control-UNSOLVABLE: 94,921-state BFS proves the control can never overlap a colour-8 cell ([8,9,8] topologically unformable), no free snake to bridge. |
| **sc25** | 3/6 @0.0427 | L3 nav | ⛔ SETTLED | "sc25 navigation is CLOSED permanently at 3/6"; the greedy/BFS decoupled-nav reopen is "the bolt-on is a dead end", a re-architecture not a tweak. |
| **dc22** | 1/6 @0.0272 | L1 | MULTI-SESSION | "2/6 is not a bounded-pass target here"; reopen = a sequential-subgoal planner tracking barrier-open subgoals under a tight fuse. |
| **wa30** | 2/9 @0.0667 | L2 | MULTI-SESSION | "L2 BANKED… well beyond a one-pass reactive build"; reopen = composite-layer parse + multi-pickup follower-collision sim + search. |
| **ar25** | 2/8 @0.0833 | L2 | MULTI-SESSION | "well beyond one bounded pass; banked docs-only; closes the sprint at 2/8"; reopen = a JOINT geared-coverage kernel (two-mode control model first). |
| **vc33** | 1/7 @0.0357 | L1 | MULTI-SESSION | "L1+ banked (no gold oracle) … beyond a bounded pass and not a small gated fix." |
| **bp35** | 1/9 @0.0145 | L1 | MULTI-SESSION | reopen "REVISED — harder than the original"; the path-opening blocks are OFF-SCREEN above the viewport (needs viewport-scroll reconstruction). |
| **sp80** | 2/6 @0.1429 | L2 | MULTI-SESSION | ⚠️ **premise CORRECTED by [[r92_sp80-l2-premise-correction]]**: L2 has NO angled deflectors (the "L2+ deflector flow-rule" citation was a MISDIAGNOSIS — those sprite tags don't exist; real deflectors are L5/L6). L2 = straight-block multi-source/multi-piece coverage, SAME physics as L1. Still MULTI-SESSION, but for multi-piece perception/tracking (self-inflicted merge), NOT a new flow rule. |
| **r11l** | 1/6 @0.0476 | L1 (idx1) | **OPEN-BOUNDED (marginal)** | "Grouping, body-exclusion, strike-avoidance are SOLVED; only edge-placement feasibility remains." Untried option (a): **learn the placeable region from observed click→move successes** instead of the frame `is_free` predicate (which fails under the DISPLAY→GRID camera transform near the octagon wall). |

## Ranked OPEN-BOUNDED opportunities (by RHAE gain = level-weight × plausibility)

1. **r11l L1** — the ONLY candidate. Weight = 2 (level index 1) / Σ(1..6)=21;
   a clean L1 clear at ~1.0 would take r11l 1/6 @0.0476 → ~0.14 (+~0.095).
   Plausibility MODERATE: everything else on L1 is solved, and option (a)
   (learned placeability from click→move feedback) is an UNTRIED, bounded-
   shaped "learn from observed transitions" delta that sidesteps the camera
   transform R59 could not isolate (option (b)). Risk: if placement feedback is
   too sparse/thrashy under the 60-action budget, it degrades to the same
   transform slog → then r11l is MULTI-SESSION too and the frontier is fully
   exhausted.

## Verdict

The bounded frontier is essentially exhausted: 3 SETTLED-⛔, 6 MULTI-SESSION
(each parked WITH a spec), 1 marginal OPEN-BOUNDED (r11l L1). The remaining
card lift is multi-session builds — a deliberate resource decision, not a
sequence of bounded rounds. Next action: attempt r11l L1 learned-placeability
as the single bounded shot; bank it MULTI-SESSION if the feedback loop can't
close within budget.
