import sys, json
order = {g: i for i, g in enumerate(
    ["lf52", "bp35", "s5i5", "dc22", "lp85", "m0r0", "vc33", "g50t", "ls20"])}
rows = [json.loads(l) for l in sys.stdin if l.strip().startswith("{")]
rows.sort(key=lambda d: order.get(d["game"], 99))
for d in rows:
    tag = "STUCK" if d["stuck"] else "ctrl "
    print("=" * 78)
    print(f"{tag} {d['game']} score={d['game_score']} lv={d['levels']} acts={d['total_actions']} "
          f"samples={d['samples']} decisions={d['decisions']} {d['elapsed_s']}s")
    print(f"  per level [samples, overtaken]: {d['by_level_samples_overtaken']}")
    for o in d["overtakes"]:
        print(f"    lvl{o['level']}  {o['incumbent']} ({o['inc_bid']}) OUTBID BY "
              f"{o['challenger']} ({o['chal_bid']})  in {o['samples']} samples, "
              f"max margin {o['max_margin']}")
