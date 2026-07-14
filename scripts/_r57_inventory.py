import numpy as np, json, glob, os

def inspect(path):
    d = np.load(path, allow_pickle=False)
    keys = list(d.keys())
    out = {"path": path, "keys": keys}
    if "meta" in keys:
        meta = json.loads(str(d["meta"]))
        out["meta"] = meta
    if "levels_completed_after" in keys:
        lv = d["levels_completed_after"]
        out["n_rows"] = len(lv)
        out["max_level"] = int(lv.max()) if len(lv) else -1
        # find level-up indices: where lv[i] > lv[i-1] (or lv[0]>0)
        ups = []
        prev = 0
        for i, v in enumerate(lv):
            if v > prev:
                ups.append((i, prev, int(v)))
                prev = int(v)
        out["level_up_indices"] = ups
    return out

print("=== data/transitions/train ===")
for f in sorted(glob.glob("data/transitions/train/*.npz")):
    info = inspect(f)
    meta = info.get("meta", {})
    print(f"{os.path.basename(f):15s} rows={info.get('n_rows','?'):>6}  max_lv={info.get('max_level','?')}  ups={len(info.get('level_up_indices',[]))}  win_levels={meta.get('win_levels')}  gold_level_idx={meta.get('gold_level_indices')}")

print()
print("=== data/traces ===")
for f in sorted(glob.glob("data/traces/*.npz")):
    if f.endswith("index.json"): continue
    info = inspect(f)
    meta = info.get("meta", {})
    print(f"{os.path.basename(f):20s} rows={info.get('n_rows','?'):>6}  max_lv={info.get('max_level','?')}  ups={len(info.get('level_up_indices',[]))}  win_levels={meta.get('win_levels')}  strategy={meta.get('strategy')}")
