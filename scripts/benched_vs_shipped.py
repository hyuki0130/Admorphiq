"""Does the SHIPPED configuration score what the BENCHED one does, game by game?

The notebook's chain gets a dead LLM callable and the deployed GF_GIVEUP; the bench builds a
live LLM backend and takes the runner's. If those diverge anywhere, the benched number is not
the card's number and the difference has to be named rather than averaged away.
"""
import glob
import json


def load(directory: str) -> dict[str, float]:
    out: dict[str, float] = {}
    for path in sorted(glob.glob(directory + "/*.json")):
        try:
            payload = json.load(open(path))
        except (OSError, json.JSONDecodeError):
            continue
        for game in payload.get("games", []):
            if "error" in game:
                continue
            out[(game.get("title") or "?").lower()] = game.get("game_score", 0.0)
    return out


benched = load("scripts/rounds/DETECT9/games")
shipped = load("scripts/rounds/SHIPPED1/games")
both = sorted(set(benched) & set(shipped))
print(f"{'game':<7}{'benched':>10}{'shipped':>10}")
differ = 0
for game in both:
    mark = "  <-- DIFFERS" if abs(benched[game] - shipped[game]) > 0.0005 else ""
    differ += bool(mark)
    print(f"{game:<7}{benched[game]:>10.4f}{shipped[game]:>10.4f}{mark}")
print(f"\ncompared {len(both)} game(s); {differ} differ")
