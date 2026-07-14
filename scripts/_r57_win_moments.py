"""R57: characterize win-condition predicates at level-up moments using kernels.

Offline analysis only. Reads data/traces/<game>.npz, finds level-up
transitions (levels_completed_after increments), and computes region/diff
statistics on the before/after frame pair using src/admorphiq/kernels.
"""
import numpy as np, json, glob, os, sys
from collections import Counter

sys.path.insert(0, "src")
from admorphiq.kernels import find_regions, frame_diff, multiset_signature

def mode_color(frame):
    vals, counts = np.unique(frame, return_counts=True)
    return int(vals[np.argmax(counts)])

def region_summary(regions):
    return [
        {"color": r["color"], "size": r["size"], "bbox": r["bbox"], "centroid": r["centroid"]}
        for r in regions
    ]

def analyze_game(path):
    d = np.load(path, allow_pickle=False)
    if "levels_completed_after" not in d.keys():
        return None
    lv = d["levels_completed_after"]
    frames = d["frames"]
    next_frames = d["next_frames"]
    meta = json.loads(str(d["meta"])) if "meta" in d.keys() else {}
    events = []
    prev = 0
    for i, v in enumerate(lv):
        if v > prev:
            before = frames[i]
            after = next_frames[i]
            bg_before = mode_color(before)
            bg_after = mode_color(after)
            diff = frame_diff(before.tolist(), after.tolist())
            regs_before = find_regions(before.tolist(), background=bg_before)
            regs_after = find_regions(after.tolist(), background=bg_after)
            # color histograms
            hist_before = Counter(before.flatten().tolist())
            hist_after = Counter(after.flatten().tolist())
            colors_vanished = [c for c in hist_before if hist_before[c] > 0 and hist_after.get(c, 0) == 0 and c != bg_before]
            colors_appeared = [c for c in hist_after if hist_after[c] > 0 and hist_before.get(c, 0) == 0 and c != bg_after]
            # multiset comparison (shape+color) before/after among non-bg regions
            sig_before = Counter((r["color"], multiset_signature(r)) for r in regs_before)
            sig_after = Counter((r["color"], multiset_signature(r)) for r in regs_after)
            sig_vanished = list((sig_before - sig_after).elements())
            sig_appeared = list((sig_after - sig_before).elements())
            events.append({
                "row_index": int(i),
                "level_from": int(prev),
                "level_to": int(v),
                "diff_count": diff["count"],
                "diff_bbox": diff["bbox"],
                "n_regions_before": len(regs_before),
                "n_regions_after": len(regs_after),
                "region_count_delta": len(regs_after) - len(regs_before),
                "bg_before": bg_before,
                "bg_after": bg_after,
                "colors_vanished": colors_vanished,
                "colors_appeared": colors_appeared,
                "n_sig_vanished": len(sig_vanished),
                "n_sig_appeared": len(sig_appeared),
                "hist_before_top": hist_before.most_common(5),
                "hist_after_top": hist_after.most_common(5),
            })
            prev = int(v)
    return {"game": os.path.basename(path).replace(".npz",""), "meta": {k: meta.get(k) for k in ("title","win_levels","baseline_actions","strategy")}, "events": events}

out = {}
for f in sorted(glob.glob("data/traces/*.npz")):
    base = os.path.basename(f)
    if base in ("tr87_l1_reset.npz",):
        continue
    r = analyze_game(f)
    if r:
        out[r["game"]] = r

with open("scripts/_r57_win_moments.json", "w") as fh:
    json.dump(out, fh, indent=2, default=str)

for g, r in out.items():
    print(f"\n=== {g} (win_levels={r['meta']['win_levels']}) ===")
    for e in r["events"]:
        print(f"  L{e['level_from']}->{e['level_to']}: diff={e['diff_count']:4d} bbox={e['diff_bbox']} "
              f"regions {e['n_regions_before']}->{e['n_regions_after']} (Δ{e['region_count_delta']:+d}) "
              f"vanished_colors={e['colors_vanished']} appeared_colors={e['colors_appeared']} "
              f"sig_vanish={e['n_sig_vanished']} sig_appear={e['n_sig_appeared']}")
