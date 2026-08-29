"""bp35: on the turns when the map does not grow, does the body REVISIT states or traverse new ones?

⛔ Why this is the only open question on bp35. The longest UNBROKEN run of turns during which the
world map gains nothing separates the boards cleanly — 4, 5, 10 on the boards at >= 0.956 against 25
and 40 on the boards at <= 0.515 — but that is a correlation and it was offered as one. A flat map
during a long walk to a known exit is ALSO what a correct traversal of a 39-row board looks like.
Only REVISITING is waste, and the distinction is measurable.

⚠️ And there is a measured reason to expect innocent re-crossing. `_rollback` clears `_visited` on
every restart, and its docstring records that KEEPING it "takes the tool from three levels to one":
after a death the run has to walk its way back out, because "the route to the frontier is only
knowable in terms of ground the tool is willing to re-cross". So ground re-crossed BETWEEN attempts
is paid for on purpose. The question is strictly about revisits WITHIN one attempt.

Recorded per crag turn: the body's (cell, axis), the map size, `len(_visited)`, the action emitted
and the note that chose it. Attempts are split on the body returning home with `_visited` reset.
Then, for the longest flat run on every board:

    turns · distinct states · revisits · max visits to any one state · direction changes
    len(_visited) growth (1 per turn == crag itself saw no repeat) · action mix

A corridor walked out and back has max_visits 2 and one direction change. A cycle has max_visits >= 3
or many reversals. ⛔ Reported for EVERY board, because a shape also present on the board scoring
1.0000 is not a cause — that is the trap rule 7b names.

⛔ CENSUS ONLY. Nothing here changes the tool.
⛔ `levels_completed` is printed as a NUMBER and compared `> start`.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, "src")


def _runs(vals):
    """Maximal groups of consecutive equal values -> list of (start_index, length)."""
    out, i = [], 0
    while i < len(vals):
        j = i
        while j + 1 < len(vals) and vals[j + 1] == vals[i]:
            j += 1
        out.append((i, j - i + 1))
        i = j + 1
    return out


def _shape(rows):
    """The trajectory census for one stretch of turns."""
    states = [(tuple(r["at"]), r["gdir"]) for r in rows if r["at"] is not None]
    cells = [s[0] for s in states]
    seen = Counter(states)
    cols = [c[1] for c in cells]
    # A reversal along the row the body walks: the sign of the column step changes.
    steps = [b - a for a, b in zip(cols, cols[1:]) if b != a]
    reversals = sum(1 for a, b in zip(steps, steps[1:]) if (a > 0) != (b > 0))
    vis = [r["visited"] for r in rows]
    # ⛔ A turn on which the body does not move is NOT pacing when the action was a click: `_click`
    # leaves the body where it is unless the click was on its own support, so a terrain edit reads
    # as a repeated state by construction. Counting those as revisits overstates the waste, and on
    # this game half the turns in a flat run are clicks.
    acts = [r["action"] for r in rows]
    dup = [k for k in range(1, len(rows))
           if rows[k]["at"] is not None and rows[k]["at"] == rows[k - 1]["at"]
           and rows[k]["gdir"] == rows[k - 1]["gdir"]]
    dup_after_click = sum(1 for k in dup if acts[k - 1] == 6)
    return {
        "consecutive_duplicate_turns": len(dup),
        "of_those_the_previous_action_was_a_click": dup_after_click,
        "turns": len(rows),
        "distinct_states": len(seen),
        "distinct_cells": len(set(cells)),
        "revisits": len(states) - len(seen),
        "max_visits_to_one_state": max(seen.values()) if seen else 0,
        "states_visited_more_than_twice": sum(1 for v in seen.values() if v > 2),
        "column_reversals": reversals,
        "visited_set_grew_by": (vis[-1] - vis[0]) if vis else 0,
        "visited_growth_equals_turns": bool(vis and (vis[-1] - vis[0]) == len(rows) - 1),
        "actions": dict(Counter(r["action"] for r in rows).most_common()),
        "notes": dict(Counter((r["note"] or "?").split(" ")[0] for r in rows).most_common()),
        "cells": [list(c) for c in cells[:60]],
        "cell_action_pairs": [[list(s0[0]), s0[1], a] for s0, a in
                              list(zip(states, acts))[:60]],
    }


def main() -> None:
    from arc_agi import Arcade, OperationMode

    from admorphiq.tools import crag as cragmod

    cap = int(sys.argv[2]) if len(sys.argv) > 2 else 800

    _spec = importlib.util.spec_from_file_location(
        "score_eff", Path(__file__).resolve().parent / "score_efficiency.py")
    _se = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(_se)

    log: list[dict] = []
    act = cragmod.CragTool._act

    def spy_act(self, board, inks):
        rec = {"i": len(log), "level": self._level, "at": self._at, "gdir": self._gdir,
               "world_cells": len(self._world), "visited": len(self._visited),
               "edits": len(self._edits)}
        log.append(rec)
        out = act(self, board, inks)
        rec["note"] = self._note
        rec["action"] = int(out[0][0]) if out else -1
        return out

    cragmod.CragTool._act = spy_act

    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    info = next(i for i in arcade.get_environments()
                if (i.title or i.game_id).lower().startswith("bp35"))
    res = _se.run_game(arcade, info.game_id, info.baseline_actions,
                       agent_name="unified", max_actions=cap)

    out = {}
    for lv in sorted({r["level"] for r in log if r["level"] is not None}):
        rows = [r for r in log if r["level"] == lv]
        # ⛔ Attempts are split where `_visited` RESETS — `_rollback` empties it on every restart,
        # so a drop in its size is the restart boundary. Splitting on the body's position instead
        # would confuse a restart with an ordinary fall back to the opening.
        bounds = [0] + [k for k in range(1, len(rows))
                        if rows[k]["visited"] < rows[k - 1]["visited"]] + [len(rows)]
        attempts = [rows[a:b] for a, b in zip(bounds, bounds[1:]) if b > a]
        flat = _runs([r["world_cells"] for r in rows])
        start, length = max(flat, key=lambda t: t[1])
        run = rows[start : start + length]
        # Which attempt does the longest flat run sit in, and does it span a restart?
        spans = sum(1 for a in attempts
                    if any(r["i"] in {x["i"] for x in run} for r in a))
        out[str(lv)] = {
            "board": lv + 1,
            "turns_on_board": len(rows),
            "attempt_lengths": [len(a) for a in attempts],
            "longest_flat_run_turns": length,
            "flat_run_spans_n_attempts": spans,
            "longest_flat_run": _shape(run),
            "per_attempt": [_shape(a) for a in attempts],
        }

    print(json.dumps({
        "levels_completed": res["levels_completed"],
        "greater_than_start": int(res["levels_completed"]) > 0,
        "total_actions": res["total_actions"],
        "game_score": res["game_score"],
        "per_level": [(x["agent_actions"], x["human_actions"], x["score"])
                      for x in res["per_level"]],
        "boards": out,
    }))


if __name__ == "__main__":
    main()
