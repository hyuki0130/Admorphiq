"""What does `crag` actually SEE on bp35, action by action, level by level?

Why this probe exists
---------------------
bp35 is the corpus's largest gap: **0.24556**, worth +0.0302 of the mean. It clears five of nine
levels and the loss is DEPTH — levels 6-9 never clear, and ~507 of its 726 actions are spent on
level 6 alone. The recorded reading is that `crag` retires there with `_refuted` False, `_mute` 0,
`_idle` 8 — the harness pulls it off the board at HALF its own 16-idle patience — holding a map of
15 known cells against a board it cannot stitch: *"a tool that cannot read the board, not one that
was interrupted."*

⛔ THAT IS A DESCRIPTION, NOT AN ATTRIBUTION. Rule 7g: only a run says which branch fires, on which
level, at which action. This logs `crag`'s own perception state on every one of its turns.

⛔ AND IT CARRIES THE CONTRAST BUILT IN (rule 7b). bp35 clears L1 at 18/21 and L4 at 23/38, both
scoring 1.0000. Four readings of s5i5 died by describing something equally true of the level that
CLEARS. Every field here is reported per level, so any claim about level 6 has to be checked
against levels 1 and 4 before it is believed.

What it records, per `crag.propose` turn
----------------------------------------
level · in-level action index · the `_stitch` outcome (grow / home / lost) · the `_quit` reason if
it quit · map size `len(self._world)` · the glyph vocabulary broken out by class · how many lattice
origins `_readings` offered · `_idle` / `_mute` / `_refuted` · whether it returned a step or nothing.
Plus which tool the harness actually picked each action, so a handover is visible as a handover.

⛔ NO SOURCE EDITS. `crag.py` is shared and another agent owns bp35's DYNAMICS lane; everything here
is a wrapper installed at runtime on the class.

Both controls
-------------
POSITIVE — the run must reproduce the banked R101SHIPPED bp35: 0.24556, per-level
[18, 87, 45, 23, 46]. A wrapper that perturbs the run is describing a different one (rule 7aj#2).
NEGATIVE — levels 1 and 4 clear at 1.0000, so their rows are the control: whatever is blamed for
level 6 must NOT be equally true there.

    bash scripts/pfan.sh bp35see scripts/_bp35_see.py 1 "" 1
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT / "src"))
sys.path.insert(0, str(_ROOT / "scripts"))

BUDGET = 4000


def main() -> None:
    import score_efficiency as se
    from arc_agi import Arcade, OperationMode

    from admorphiq.harness import registry
    from admorphiq.tools import crag as cg

    rows: list[dict] = []
    ctx = {"lvl": 0, "act": 0, "pick": None}
    picks: Counter = Counter()
    stitch_out = {"v": None}

    # -- the stitch's own verdict, captured where it is produced -------------------------
    orig_stitch = cg.CragTool._stitch

    def stitch(self, readings, allow):  # noqa: ANN001, ANN202
        out = orig_stitch(self, readings, allow)
        stitch_out["v"] = out[0] if isinstance(out, tuple) else None
        return out

    cg.CragTool._stitch = stitch

    orig_quit = cg.CragTool._quit

    def quit_(self, why):  # noqa: ANN001, ANN202
        ctx["quit"] = why
        return orig_quit(self, why)

    cg.CragTool._quit = quit_

    orig_readings = cg.CragTool._readings

    def readings(self, g):  # noqa: ANN001, ANN202
        out = orig_readings(self, g)
        ctx["n_readings"] = len(out)
        return out

    cg.CragTool._readings = readings

    orig_propose = cg.CragTool.propose

    def propose(self, frames, obs):  # noqa: ANN001, ANN202
        ctx["quit"] = None
        ctx["n_readings"] = None
        stitch_out["v"] = None
        steps = orig_propose(self, frames, obs)
        rows.append({
            "lvl": ctx["lvl"], "act": ctx["act"],
            "stitch": stitch_out["v"],
            "quit": ctx["quit"],
            "note": getattr(self, "_note", None),
            "n_readings": ctx["n_readings"],
            "world": len(getattr(self, "_world", {}) or {}),
            "vocab": self._vocabulary(),
            "open": len(getattr(self, "_open", ()) or ()),
            "solid": len(getattr(self, "_solid", ()) or ()),
            "lethal": len(getattr(self, "_lethal", ()) or ()),
            "vanish": len(getattr(self, "_vanish", ()) or ()),
            "swap": len(getattr(self, "_swap", ()) or ()),
            "flip": len(getattr(self, "_flip", ()) or ()),
            "inert": len(getattr(self, "_inert", ()) or ()),
            "pocket": len(getattr(self, "_pocket", ()) or ()),
            "volatile": len(getattr(self, "_volatile", ()) or ()),
            "edits": len(getattr(self, "_edits", {}) or {}),
            "rows": getattr(self, "_rows", None),
            "gdir": getattr(self, "_gdir", None),
            "at": list(self._at) if getattr(self, "_at", None) else None,
            "idle": getattr(self, "_idle", None),
            "mute": getattr(self, "_mute", None),
            "refuted": bool(getattr(self, "_refuted", False)),
            "steps": len(steps),
        })
        return steps

    cg.CragTool.propose = propose

    # -- who the harness actually gives the board to -------------------------------------
    def wrap_any(cls: type) -> None:
        if cls.__dict__.get("_bp_wrapped") or cls is cg.CragTool:
            return
        op = cls.propose
        nm = cls.__name__

        def p(self, frames, obs):  # noqa: ANN001, ANN202
            picks[nm] += 1
            ctx["pick"] = nm
            return op(self, frames, obs)

        cls.propose, cls._bp_wrapped = p, True

    for t in registry.default_tools():
        wrap_any(type(t))

    orig_make = se._make_agent

    def make(*a, **k):  # noqa: ANN002, ANN003
        adapter = orig_make(*a, **k)
        inner = adapter.choose_action

        def choose(frames, obs):  # noqa: ANN001
            lvl = int(getattr(obs, "levels_completed", 0) or 0)
            if lvl != ctx["lvl"]:
                ctx["lvl"], ctx["act"] = lvl, 0
            out = inner(frames, obs)
            ctx["act"] += 1
            return out

        adapter.choose_action = choose
        return adapter

    se._make_agent = make

    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    info = [e for e in arcade.get_environments()
            if "bp35" in f"{e.game_id} {e.title or ''}".lower()][0]
    res = se.run_game(arcade, info.game_id, info.baseline_actions,
                      agent_name="unified", max_actions=BUDGET)

    banked = json.loads((_ROOT / "scripts" / "rounds" / "R101SHIPPED"
                         / "games" / "bp35.json").read_text())
    per = [p.get("agent_actions") for p in res.get("per_level", [])]
    got = round(float(res.get("game_score", 0.0)), 6)

    # -- per level, the perception summary ------------------------------------------------
    by: dict[int, dict] = {}
    for r in rows:
        d = by.setdefault(r["lvl"], {
            "turns": 0, "quits": 0, "steps": 0, "stitch": Counter(), "quit_why": Counter(),
            "world_max": 0, "world_end": 0, "vocab_max": 0, "n_readings": Counter(),
            "idle_max": 0, "mute_max": 0, "rows": None, "gdir": Counter(),
            "vocab_end": None, "classes_end": None, "pocket_max": 0,
        })
        d["turns"] += 1
        d["steps"] += 1 if r["steps"] else 0
        d["quits"] += 1 if r["quit"] else 0
        d["stitch"][str(r["stitch"])] += 1
        if r["quit"]:
            d["quit_why"][r["quit"]] += 1
        d["world_max"] = max(d["world_max"], r["world"])
        d["world_end"] = r["world"]
        d["vocab_max"] = max(d["vocab_max"], r["vocab"])
        d["vocab_end"] = r["vocab"]
        d["classes_end"] = {k: r[k] for k in
                            ("open", "solid", "lethal", "vanish", "swap", "flip", "inert")}
        d["pocket_max"] = max(d["pocket_max"], r["pocket"])
        d["volatile_max"] = max(d.get("volatile_max", 0), r["volatile"])
        d["volatile_end"] = r["volatile"]
        d["edits_max"] = max(d.get("edits_max", 0), r["edits"])
        d["volatile_end"] = r["volatile"]
        d["edits_max"] = max(d["edits_max"], r["edits"])
        d["n_readings"][str(r["n_readings"])] += 1
        d["idle_max"] = max(d["idle_max"], r["idle"] or 0)
        d["mute_max"] = max(d["mute_max"], r["mute"] or 0)
        d["rows"] = r["rows"]
        d["gdir"][str(r["gdir"])] += 1
    for d in by.values():
        for k in ("stitch", "quit_why", "n_readings", "gdir"):
            d[k] = dict(d[k].most_common(6))

    print(json.dumps({
        "score": got,
        "banked": round(float(banked["total_score"]), 6),
        "BANKED_MISMATCH": abs(got - float(banked["total_score"])) > 1e-6,
        "per_level": per,
        "banked_per_level": [p["agent_actions"] for p in banked["games"][0]["per_level"]],
        "levels": res.get("levels_completed"),
        "picks": dict(picks),
        "crag_turns": len(rows),
        "by_level": {str(k): v for k, v in sorted(by.items())},
    }, sort_keys=True))


if __name__ == "__main__":
    main()
