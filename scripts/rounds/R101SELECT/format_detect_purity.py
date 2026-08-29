import sys, json
rows = [json.loads(l) for l in sys.stdin if l.strip().startswith("{")]
rows.sort(key=lambda d: d.get("seed", 0))
ctl = {r["mode"]: r for r in rows if r.get("mode") in ("none", "all")}
for m in ("none", "all"):
    r = ctl.get(m)
    if r:
        exp = 823 if m == "none" else 827
        ok = "OK" if r["total_actions"] == exp else "!! CONTROL FAILED"
        print(f"CONTROL {m:5} expect {exp}  got {r['total_actions']}  {ok}")
print()
bad = [r for r in rows if r.get("mode") == "one" and r.get("delta_vs_baseline") not in (0, None)]
good = [r for r in rows if r.get("mode") == "one" and r.get("delta_vs_baseline") == 0]
print(f"OFFENDERS ({len(bad)}):")
for r in bad:
    print(f"  {r['tool']:18} actions={r['total_actions']:5} delta={r['delta_vs_baseline']:+4} "
          f"score={r['game_score']} samples={r['samples']}")
print(f"\nCLEAN ({len(good)}): {' '.join(sorted(r['tool'] for r in good))}")
miss = [r for r in rows if r.get("mode") == "unused_arm"]
print(f"\nunused arms: {len(miss)}   total rows: {len(rows)}")
