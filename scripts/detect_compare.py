import glob, json, os
def load(d):
    out={}
    for f in sorted(glob.glob(f"{d}/*.json")):
        try: j=json.load(open(f))
        except Exception: continue
        for g in j.get("games",[]):
            out[(g.get("title") or "?").lower()]=(g.get("game_score",0.0),g.get("levels_completed",0))
    return out
card=load("scripts/rounds/SUBCAND1/games"); det=load("scripts/rounds/DETECT1/games")
ceil={}
for d in sorted(os.listdir("scripts/rounds/CEILING1")):
    p=os.path.join("scripts/rounds/CEILING1",d,"SUMMARY.txt")
    if not os.path.isfile(p): continue
    for line in open(p):
        pr=line.split()
        if len(pr)>=6 and "/" in pr[2] and pr[-1] in ("ok","ERROR"):
            ceil[d]=(float(pr[4]),int(pr[2].split("/")[0])); break
keys=sorted(set(card)|set(det))
print(f"{'game':<7}{'card':>9}{'detect':>9}{'ceiling':>9}   delta")
print("-"*48)
for g in keys:
    c=card.get(g,(0,0))[0]; d=det.get(g,(0,0))[0]; x=ceil.get(g,(0,0))[0]
    mark = "  <-- GAIN" if d-c>0.005 else ("  ⛔ REGRESSION" if c-d>0.005 else "")
    print(f"{g:<7}{c:>9.4f}{d:>9.4f}{x:>9.4f}{mark}")
print("-"*48)
n=len(keys)
print(f"{'MEAN':<7}{sum(card.get(g,(0,0))[0] for g in keys)/n:>9.4f}"
      f"{sum(det.get(g,(0,0))[0] for g in keys)/n:>9.4f}"
      f"{sum(ceil.get(g,(0,0))[0] for g in keys)/n:>9.4f}   (n={n})")
