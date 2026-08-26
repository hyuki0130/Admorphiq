---
name: feedback-online-rl-is-the-spine
description: "The performance lever for ARC-AGI-3 is TEST-TIME ONLINE CNN+RL (learn fresh per game), NOT sample-specific algorithm primitives or offline-on-public RL — both fail to transfer to the 110 private games"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: c7e91ecf-c8c0-4c3c-bd62-4722ff123df5
---

User directive (firm, repeated 2026-06-30, with frustration): stop building sample-specific
algorithm primitives; the path to the 110 PRIVATE games is RL that LEARNS GENERALLY over many
rounds. CLAUDE.md already said this (BC=warm-start; real path = world-model + online/test-time
learning + RL). I violated it by spending a day on an algorithm track.

**What's wrong with the two dead ends:**
- Sample-specific algorithms (R45-R50: arrangement/sort_match/merge_drag — got the 25-game proxy
  to ~1.4%): hand-coded heuristics fit to the public game classes. They do NOT transfer to novel
  private-game mechanics. KEEP an algorithm primitive ONLY if it's proven general (transfers to a
  held-out split); otherwise it's worthless for the leaderboard.
- Offline RL on the public games (the failed R44 1.54% run + my offline `_rl_track.sh`): same
  transfer-weak half as BC (BC measured 0% transfer). Training on public games memorizes them.

**The winning recipe (researched 2026-06-30 from StochasticGoose / Dries Smit, 1st place ARC-AGI-3
preview, 12.58%): CNN + RL learned FRESH PER GAME AT TEST TIME.**
- CNN = our existing PerceptionModel (action-legality head ACTION1-5 + spatial coord head for
  ACTION6, 4101 logits). Top team used the same shape.
- SPARSE reward: +1 only on level completion. No frame-change shaping (rewards wiggling).
- OFF-POLICY replay: store every (frame,action,next_frame,reward), hash-deduped (our buffer.py).
- ONLINE: retrain the CNN every few env steps off-policy from the buffer; RESET buffer between
  levels; bias exploration toward predicted frame-changing actions.
- NO offline pretraining (BC warm-start optional). ~8h/game, <100k steps. Minimal transfer — the
  learning happens INSIDE each unseen game, which is exactly why it generalizes to the 110.
- They explicitly avoided LLMs (hundreds of steps = millions of tokens).

**How to apply:** the deployed agent should be the online test-time CNN+RL learner. Validate on the
25 public games — since it learns fresh per game, all 25 are effectively unseen = the generality
test. Sources: medium.com/@dries.epos 1st-place writeup; github.com/DriesSmit/ARC3-solution;
arcprize.org/blog/arc-agi-3-preview-30-day-learnings. Relates to [[project-general-direction-worldmodel]],
[[project-bc-transfer-ceiling]], [[feedback-rl-not-abandoned]].
