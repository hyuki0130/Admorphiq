"""R57 deep-dive: for zero/near-zero-diff or ambiguous win events, look at the
whole gold block for that level (not just the single triggering action) to
see the full predicate that was established, plus action/reward context.
"""
import numpy as np, json, sys
sys.path.insert(0, "src")
from admorphiq.kernels import find_regions, frame_diff, multiset_signature
from collections import Counter

def mode_color(frame):
    vals, counts = np.unique(frame, return_counts=True)
    return int(vals[np.argmax(counts)])

def dive(game, level_from_list=None):
    d = np.load(f"data/traces/{game}.npz", allow_pickle=False)
    lv = d["levels_completed_after"]
    lvidx = d["level_index"]
    actions = d["actions"]
    rewards = d["rewards"]
    is_gold = d["is_gold"]
    frames = d["frames"]
    next_frames = d["next_frames"]
    print(f"\n########## {game} ##########")
    prev = 0
    for i, v in enumerate(lv):
        if v > prev:
            lf = int(prev)
            if level_from_list and lf not in level_from_list:
                prev = int(v); continue
            # find gold block: rows with level_index == lf and is_gold True, ending at i
            block_start = i
            while block_start > 0 and lvidx[block_start-1] == lf and is_gold[block_start-1]:
                block_start -= 1
            print(f"-- level {lf}->{v}: gold block rows [{block_start},{i}] ({i-block_start+1} actions) --")
            acts = actions[block_start:i+1]
            print(f"   actions: {acts.tolist()}")
            print(f"   reward at event row {i}: {rewards[i]}  action={actions[i]}")
            # full-block diff: frame at block_start (before) vs next_frames[i] (after level clear)
            before = frames[block_start]
            after = next_frames[i]
            bg_b, bg_a = mode_color(before), mode_color(after)
            diff = frame_diff(before.tolist(), after.tolist())
            regs_b = find_regions(before.tolist(), background=bg_b)
            regs_a = find_regions(after.tolist(), background=bg_a)
            hist_b = Counter(before.flatten().tolist())
            hist_a = Counter(after.flatten().tolist())
            vanished = [c for c in hist_b if hist_b[c]>0 and hist_a.get(c,0)==0 and c!=bg_b]
            appeared = [c for c in hist_a if hist_a[c]>0 and hist_b.get(c,0)==0 and c!=bg_a]
            sig_b = Counter((r["color"], multiset_signature(r)) for r in regs_b)
            sig_a = Counter((r["color"], multiset_signature(r)) for r in regs_a)
            print(f"   FULL-BLOCK diff: count={diff['count']} bbox={diff['bbox']} regions {len(regs_b)}->{len(regs_a)} "
                  f"vanished_colors={vanished} appeared_colors={appeared} "
                  f"sig_vanish={len(list((sig_b-sig_a).elements()))} sig_appear={len(list((sig_a-sig_b).elements()))}")
            prev = int(v)

import sys as _s
game = _s.argv[1]
dive(game)
