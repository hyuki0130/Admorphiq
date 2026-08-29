"""bp35: is the POCKET visible before the body walks into it — and under which gravity?

⛔ Why this and not "fix `_stranded`". `_stranded` is a VETO of the family that has cost most when
relaxed: it fires only once the attempt is already walled in, and ending it in two actions beats
serving out thirty of clock. The measured cost is upstream of it — on level 2, 34 of 87 actions are
spent inside a pocket the agent walked into, and level 2 at 0.3044 is the game's worst level. The
question is therefore not whether to leave the pocket faster but whether ENTERING it was refusable
on the evidence available AT THAT MOMENT.

A dead end cannot be proved from an incomplete map. So the census is a boundary count, not a
search: a region whose every neighbouring cell is already KNOWN (solid, lethal, or off the board)
is a region whose closedness is derivable; a region with even one unmapped neighbour is a region
that might open, and refusing it would be an invention.

Recorded, per step: the body, the axis, and a snapshot of the world map and the vocabulary. When
`_stranded` fires, the pocket region R is captured, the log is walked BACK to the step at which the
body first entered R, and the region is recomputed FROM THAT STEP'S MAP — the honest evidence,
not hindsight. Both gravities are recomputed, because bp35 reverses the axis from anywhere on
screen (`lrpkmzabbfa` skips the "directly below the body" test), so "no exit" is a property of the
board AND the axis in force.

Also folded in, at the coordinator's request: whether `crag.detect` MUTATES. A `detect` that
advances a give-up counter means merely asking the tool if it recognises a board spends its
patience, and every probe here would be perturbing what it measures.

⛔ `levels_completed` is printed as a NUMBER and compared `> start`.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, "src")


def _vocab(t):
    return {"air": t._air, "open": set(t._open), "solid": set(t._solid),
            "lethal": set(t._lethal), "rows": t._rows, "cols": t._cols}


def _load(fresh, world, vocab):
    fresh._world = dict(world)
    fresh._air = vocab["air"]
    fresh._open = set(vocab["open"])
    fresh._solid = set(vocab["solid"])
    fresh._lethal = set(vocab["lethal"])
    fresh._rows = vocab["rows"]
    fresh._cols = vocab["cols"]
    return fresh


def _boundary(t, region):
    """Cells adjacent to the region that the map does not name, and the named ones by class.

    A region can only be PROVED closed when this returns zero unknowns: an unmapped neighbour is a
    cell that might be air, and a dead end asserted over one is an invention.
    """
    unknown = known_solid = known_lethal = off_map = 0
    cells = {c for c, _ in region}
    for (r, c) in cells:
        for dr, dc in ((0, -1), (0, 1), (-1, 0), (1, 0)):
            n = (r + dr, c + dc)
            if n in cells:
                continue
            if not (0 <= n[1] < t._cols):
                off_map += 1
                continue
            sig = t._world.get(n)
            if sig is None:
                unknown += 1
            elif sig in t._lethal:
                known_lethal += 1
            elif not t._is_open(sig):
                known_solid += 1
            else:
                unknown += 1   # open and reachable-looking: not a wall, so not evidence of closure
    return {"unknown_or_open": unknown, "known_solid": known_solid,
            "known_lethal": known_lethal, "off_map": off_map}


def main() -> None:
    from arc_agi import Arcade, OperationMode

    from admorphiq.tools import crag as cragmod

    cap = int(sys.argv[2]) if len(sys.argv) > 2 else 800

    _spec = importlib.util.spec_from_file_location(
        "score_eff", Path(__file__).resolve().parent / "score_efficiency.py")
    _se = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(_se)

    log: list[dict] = []
    strands: list[dict] = []
    detect_mutations: list[dict] = []

    act = cragmod.CragTool._act
    stranded = cragmod.CragTool._stranded
    detect = cragmod.CragTool.detect

    def spy_act(self, board, inks):
        # ⛔ The index is the log's own length, not a counter kept beside it: `_act` is the only
        # place crag decides anything, and a separate counter drifts the moment the tool is
        # skipped for a turn — which is exactly what happens on the board it hands over.
        rec = {"i": len(log), "level": self._level,
               "at": self._at, "gdir": self._gdir,
               "world": dict(self._world), "vocab": _vocab(self),
               "world_cells": len(self._world)}
        log.append(rec)
        out = act(self, board, inks)
        # ⛔ The note AFTER the call describes the action just chosen; the note before it is the
        # PREVIOUS turn's, and reading it as this turn's is attribution by proximity (rule 7b).
        rec["note"] = self._note
        return out

    def spy_stranded(self, arrived):
        # `_stranded` is reached from inside `_act`, so the turn's own log entry is the last one.
        if self._at is not None and self._gdir:
            region = self._region(self._at, self._gdir)
            strands.append({"i": len(log) - 1, "level": self._level,
                            "at": self._at, "gdir": self._gdir,
                            "region": set(region), "world_cells": len(self._world),
                            "boundary_now": _boundary(self, region)})
        return stranded(self, arrived)

    def spy_detect(self, frames, obs):
        keys = [k for k in vars(self) if not k.startswith("__")]
        before = {k: repr(getattr(self, k)) for k in keys}
        out = detect(self, frames, obs)
        after = {k: repr(getattr(self, k)) for k in vars(self) if not k.startswith("__")}
        diff = sorted(k for k in set(before) | set(after) if before.get(k) != after.get(k))
        if diff:
            detect_mutations.append({"i": len(log), "changed": diff})
        return out

    cragmod.CragTool._act = spy_act
    cragmod.CragTool._stranded = spy_stranded
    cragmod.CragTool.detect = spy_detect

    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    info = next(i for i in arcade.get_environments()
                if (i.title or i.game_id).lower().startswith("bp35"))

    # ⛔ The scorer's OWN `run_game` drives the steps. Re-implementing the loop is how a probe
    # ends up explaining a different run: a hand-rolled one clears FOUR bp35 boards where the
    # scorer clears five.
    res = _se.run_game(arcade, info.game_id, info.baseline_actions,
                       agent_name="unified", max_actions=cap)

    # ---- the census: for each strand, walk back to the step the body ENTERED the pocket
    findings = []
    for s in strands:
        region = s["region"]
        entry = None
        for rec in reversed(log[: s["i"]]):
            if (rec["at"], rec["gdir"]) not in region:
                entry = rec
                break
        if entry is None:
            findings.append({"strand_log_index": s["i"], "entry": None,
                             "note": "the body was inside the pocket from the attempt's first turn"})
            continue
        # The destination is where the body stood one turn after `entry`.
        after = log[entry["i"] + 1] if entry["i"] + 1 < len(log) else None
        probe = cragmod.CragTool()
        _load(probe, entry["world"], entry["vocab"])
        got = {}
        for g in (1, -1):
            here = after["at"] if after else s["at"]
            reg = probe._region(here, g)
            got[str(g)] = {"region_states": len(reg), "boundary": _boundary(probe, reg)}
        findings.append({
            "level": s["level"],
            "strand_log_index": s["i"], "strand_at": list(s["at"]), "strand_gdir": s["gdir"],
            "region_states_at_strand": len(region),
            "boundary_at_strand": s["boundary_now"],
            "world_cells_at_strand": s["world_cells"],
            "entry_log_index": entry["i"], "entry_at": list(entry["at"]),
            "entry_gdir": entry["gdir"], "entry_world_cells": len(entry["world"]),
            "turns_spent_in_pocket": s["i"] - entry["i"],
            "region_from_entrys_map": got,
        })

    print(json.dumps({
        "levels_completed": res["levels_completed"],
        "greater_than_start": int(res["levels_completed"]) > 0,
        "total_actions": res["total_actions"],
        "game_score": res["game_score"],
        "per_level": res["per_level"],
        "crag_turns_logged": len(log),
        "detect_calls_that_mutated": len(detect_mutations),
        "detect_attributes_changed": sorted({k for m in detect_mutations for k in m["changed"]}),
        "strands": len(strands),
        "findings": findings,
        # Where crag's turns actually GO, per level. The pocket theory predicts a large "walled in"
        # bar on the two expensive boards; anything else refutes it.
        "turns_by_level_and_phase": {
            str(lv): dict(Counter(
                (r.get("note") or "?").split(" ")[0] + (
                    " " + (r.get("note") or "?").split(" ")[1]
                    if len((r.get("note") or "?").split(" ")) > 1
                    and not (r.get("note") or "").split(" ")[1][:1].isdigit()
                    and "(" not in (r.get("note") or "").split(" ")[1] else "")
                for r in log if r["level"] == lv).most_common())
            for lv in sorted({r["level"] for r in log if r["level"] is not None})},
        "turns_per_level": {str(lv): sum(1 for r in log if r["level"] == lv)
                            for lv in sorted({r["level"] for r in log
                                              if r["level"] is not None})},
        # ⛔ The map does NOT shrink on a restart (`_rollback` undoes OUR edits, not the terrain),
        # so this series says plainly whether a failed attempt was WASTE or was the map-building
        # the winning attempt then runs on. A flat run through a failed attempt would mean waste.
        # ⛔ EVERY level, not only the expensive two. A plateau that is also present on the board
        # scoring 1.0 is not a cause — that is the trap rule 7b names, and four readings of another
        # game died on it.
        "world_cells_per_turn_by_level": {
            str(lv): [r["world_cells"] for r in log if r["level"] == lv]
            for lv in sorted({r["level"] for r in log if r["level"] is not None})},
        "world_cells_first_last_by_level": {
            str(lv): [next(r["world_cells"] for r in log if r["level"] == lv),
                      [r["world_cells"] for r in log if r["level"] == lv][-1]]
            for lv in sorted({r["level"] for r in log if r["level"] is not None})},
    }))


if __name__ == "__main__":
    main()
