"""Repeat the dc22 oracle full-game run; varying parameter FIRST = repetition index.

Purpose: a single clear is a draw, not a rate.  Prints ONE JSON line per run.
"""
import sys, json, io, contextlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))


def main():
    rep = int(sys.argv[1])
    max_actions = int(sys.argv[2]) if len(sys.argv) > 2 else 8000
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        import _dc22_oracle_full as O
        sys.argv = ["x", str(max_actions)]
        O.main()
    last = [l for l in buf.getvalue().splitlines() if l.startswith("{")]
    out = json.loads(last[-1]) if last else {}
    print(json.dumps({"rep": rep, "levels_completed": out.get("levels_completed"),
                      "win_levels": out.get("win_levels"),
                      "total_actions": out.get("total_actions"),
                      "game_score": out.get("game_score"),
                      "per_level": out.get("per_level")}), flush=True)


if __name__ == "__main__":
    main()
