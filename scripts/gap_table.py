"""Measured gap table: what the SHIPPED card scores vs what the ADAPTER ceiling reaches.

Purpose: turn "adapters25 has depth we do not ship" from a remembered claim into a per-game
measurement, so the port backlog is ordered by evidence.

Expected feedback: each row is (card score/levels, ceiling score/levels, gap). Rows are sorted by
the score gap, largest first — that ordering IS the port priority.
"""
import glob
import json
import os

CARD = "scripts/rounds/SUBCAND1/games"
CEIL = "scripts/rounds/CEILING1"

card = {}
for f in sorted(glob.glob(f"{CARD}/*.json")):
    d = json.load(open(f))
    for g in d.get("games", []):
        card[(g.get("title") or "?").lower()] = (g.get("game_score", 0.0),
                                                 g.get("levels_completed", 0))

ceil = {}
for d in sorted(os.listdir(CEIL)):
    p = os.path.join(CEIL, d, "SUMMARY.txt")
    if not os.path.isfile(p):
        continue
    for line in open(p):
        parts = line.split()
        if len(parts) >= 6 and "/" in parts[2] and parts[-1] in ("ok", "ERROR"):
            lv = int(parts[2].split("/")[0])
            ceil[d] = (float(parts[4]), lv)
            break

rows = []
for g in sorted(set(card) | set(ceil)):
    cs, cl = card.get(g, (0.0, 0))
    xs, xl = ceil.get(g, (0.0, 0))
    rows.append((xs - cs, g, cs, cl, xs, xl))
rows.sort(reverse=True)

print(f"{'game':<7}{'card':>9}{'lvl':>5}   {'ceiling':>9}{'lvl':>5}   {'gap':>9}")
print("-" * 52)
for gap, g, cs, cl, xs, xl in rows:
    flag = "  <-- PORT" if gap > 0.01 else ""
    print(f"{g:<7}{cs:>9.4f}{cl:>5}   {xs:>9.4f}{xl:>5}   {gap:>9.4f}{flag}")
print("-" * 52)
print(f"{'MEAN':<7}{sum(r[2] for r in rows)/len(rows):>9.4f}"
      f"{sum(r[3] for r in rows):>5}   "
      f"{sum(r[4] for r in rows)/len(rows):>9.4f}{sum(r[5] for r in rows):>5}   "
      f"{sum(r[0] for r in rows)/len(rows):>9.4f}")
