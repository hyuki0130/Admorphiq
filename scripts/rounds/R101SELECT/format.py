import sys, json
for ln in sys.stdin:
    ln = ln.strip()
    if not ln.startswith("{"):
        continue
    d = json.loads(ln)
    tag = "STUCK" if d["stuck"] else "ctrl "
    print("=" * 78)
    print(f"{tag} {d['game']}  score={d['game_score']}  {d['levels']}/{d['win_levels']}  "
          f"acts={d['total_actions']}  handovers={d['n_handovers']}  {d['elapsed_s']}s")
    for h in d["handovers"]:
        print(f"  step={h['step']:4d} lvl={h['level']} attempt_lvl={h['attempt_level']} "
              f"retired={h['retired']} reason={h['reason']} -> WINNER={h['winner']} "
              f"owns={h['primary_owns']} survived={h['survived_actions']} "
              f"proposed_after={h['proposed_after_win']}")
        print(f"      top={h['top_bid']} tied={h['tied_at_top']} losers={h['losers']} "
              f"n_zero={h['n_zero']}")
        print(f"      bids(now,best)={h['bids']}")
        if h['failed_before'] or h['banned_before']:
            print(f"      failed_before={h['failed_before']} banned={h['banned_before']}")
    print(f"  best_any_frame={d['best_bid_any_frame']}")
