#!/usr/bin/env python3
"""WHY does crag's `_stitch` say "lost"? — a census of the ALIGNMENT SEARCH itself (rule 7bh).

⛔ THE QUESTION. On bp35 `crag` makes 230 `propose` calls, 8 of them NOPLAN, and all eight are
`_quit("window does not belong to this board")` — `_stitch` returning "lost". At the first empty the
ONLY tool field that moves is `self._rows` 10 -> 9, which is verbatim the hazard `_widen_band`'s own
docstring names: the window is a fixed height in PIXELS and not in CELLS, so the same window reads as
ten rows on one frame and nine on the next. `_widen_band` guards against it by keeping the WIDEST
ever seen. `_stitch` does not: its shift search runs `range(lo - self._rows, hi + self._rows + 1)`.

This probe does NOT change behaviour (rule 7o). It wraps `_stitch`, and on every call that returns
"lost" it re-runs the alignment offline against a SNAPSHOT of the map taken before the real call, and
separates the three candidate causes so the fix is chosen by evidence rather than by the briefing:

  * RANGE  — a shift outside `range(lo - rows, hi + rows + 1)` would have been accepted;
  * ALLOW  — a shift inside the range would have been accepted but `_admissible` refused it;
  * PICTURE— no shift anywhere agrees >= _ALIGN_FIT, so the window really is a different picture and
             a wider range buys nothing. ⛔ This is the outcome that closes the axis, and it is the
             one the briefing does not predict.
  * OVERLAP— a shift DOES agree, but on fewer than `_ALIGN_MIN` comparable cells, so the floor threw
             it away. A window that has scrolled into unmapped board cannot meet an overlap floor,
             which would make the floor — not the row read — the field at fault.

⛔ MIRRORS `score_efficiency.py:run_game` (rule 7x): the scorer's own `_make_agent`, an EMPTY frames
list, `restart_on_game_over` honoured (`arcengine.GameAction.RESET`, an Enum MEMBER), BREAK on WIN,
per-level action counts recorded the same way. Banked control: [18,87,45,23,46] / 726a / 0.24556.

Modes (chosen by seed, so one fan covers every arm):
  pure    — no wrapping at all. CONTROL: must equal the banked per-level counts (rule 7ai).
  census  — wraps `_stitch` and records. Must ALSO equal them, or the instrument moved the run.
  bids    — which of the 25 games crag bids on at all, so a change to it is scoped before it is made.

Usage:  uv run python scripts/_crag_stitch.py <seed 1..N>
"""

from __future__ import annotations

import json
import os
import sys
from collections import Counter

ARMS = [
    ("bp35", "pure"),
    ("bp35", "census"),
    ("bp35", "census"),
    ("bp35", "pure"),
    ("-", "bids"),
]

GAMES = ["ar25", "bp35", "cd82", "cn04", "dc22", "ft09", "g50t", "ka59", "lf52", "lp85",
         "ls20", "m0r0", "r11l", "re86", "s5i5", "sb26", "sc25", "sk48", "sp80", "su15",
         "tn36", "tr87", "tu93", "vc33", "wa30"]


def _bids(arcade, make_agent) -> dict:
    """Which games does crag bid on? A one-frame question, asked of every game."""
    out = {}
    envs = {e.game_id: f"{e.game_id} {e.title or ''}".lower() for e in arcade.get_environments()}
    for want in GAMES:
        gid = next((g for g, lab in envs.items() if want in lab), None)
        if gid is None:
            out[want] = "no such game"
            continue
        env = arcade.make(gid)
        obs = env.observation_space
        tool = make_agent("unified", game_id=gid).tools["crag"]
        try:
            bid = float(tool.detect([], obs))
        except Exception as exc:  # noqa: BLE001
            bid = f"raised {exc!r}"[:120]
        out[want] = bid
    return out


def main() -> None:
    seed = int(sys.argv[1])
    game, mode = ARMS[(seed - 1) % len(ARMS)]
    budget = 4000

    here = os.path.dirname(os.path.abspath(__file__))
    sys.path.insert(0, os.path.join(here, "..", "src"))
    sys.path.insert(0, here)

    from arc_agi import Arcade, OperationMode  # type: ignore
    from arcengine import GameAction, GameState  # type: ignore
    from score_efficiency import _make_agent

    from admorphiq.tools import crag as crag_mod

    arcade = Arcade(operation_mode=OperationMode.OFFLINE)

    if mode == "bids":
        print(json.dumps({"arm": {"mode": mode, "seed": seed},
                          "bids": _bids(arcade, _make_agent)}))
        return

    want = game.strip().lower()
    game_id = next(
        e.game_id for e in arcade.get_environments()
        if want in f"{e.game_id} {e.title or ''}".lower()
    )
    env = arcade.make(game_id)
    obs = env.observation_space
    adapter = _make_agent("unified", game_id=game_id)
    tool = adapter.tools["crag"]

    fit, amin = crag_mod._ALIGN_FIT, crag_mod._ALIGN_MIN
    calls: list[dict] = []
    step_no = {"n": 0}
    orig = tool._stitch

    def score_at(world, volatile, board, body, shift, dc=0):
        agree = total = 0
        for (r, c), sg in board.items():
            if (r, c) == body:
                continue
            was = world.get((r + shift, c + dc))
            if was is None or was in volatile or sg in volatile:
                continue
            total += 1
            agree += was == sg
        return (agree / total if total else 0.0), total

    def admissible(at, gdir, row, allow):
        if allow is None or at is None or gdir == 0:
            return True
        delta = (row - at[0]) * gdir
        if allow == 0:
            return delta == 0
        return delta >= 0 if allow > 0 else delta <= 0

    def wrapped(readings, allow):
        # Snapshot everything the offline replay needs, BEFORE the real call mutates it.
        world = dict(tool._world)
        volatile = set(tool._volatile)
        at, gdir, origin = tool._at, tool._gdir, tool._origin
        rows_in = tool._rows
        rows_seen = [max(r for r, _ in b) + 1 for _, _, b, _, _ in readings] if readings else []
        outcome, board, inks, body = orig(readings, allow)
        rec = {"step": step_no["n"], "outcome": outcome, "allow": allow,
               "rows_in": rows_in, "rows_seen": rows_seen, "n_readings": len(readings),
               "world": len(world)}
        if outcome == "lost" and world:
            lo = min(r for r, _ in world)
            hi = max(r for r, _ in world)
            in_lo, in_hi = lo - rows_in, hi + rows_in
            wide = max(rows_seen + [rows_in]) + 4
            best = {"any": (0.0, None, None), "inrange": (0.0, None, None),
                    "adm": (0.0, None, None), "adm_inrange": (0.0, None, None),
                    "nofloor": (0.0, None, None)}
            profile: list = []
            floored = 0
            for idx, (oy, ox, brd, _ink, bdy) in enumerate(readings):
                for shift in range(lo - wide, hi + wide + 1):
                    sc, total = score_at(world, volatile, brd, bdy, shift)
                    ok_adm0 = admissible(at, gdir, bdy[0] + shift, allow)
                    if total and (sc >= 0.7 or total >= amin):
                        profile.append([idx, shift, round(sc, 3), total,
                                        int(in_lo <= shift <= in_hi), int(ok_adm0)])
                    if total >= 4 and (round(sc, 3), shift, idx) > best["nofloor"]:
                        best["nofloor"] = (round(sc, 3), shift, idx)
                    if total < amin:
                        floored += 1
                        continue
                    ok_r = in_lo <= shift <= in_hi
                    ok_a = admissible(at, gdir, bdy[0] + shift, allow)
                    cand = (round(sc, 3), shift, idx)
                    if cand > best["any"]:
                        best["any"] = cand
                    if ok_r and cand > best["inrange"]:
                        best["inrange"] = cand
                    if ok_a and cand > best["adm"]:
                        best["adm"] = cand
                    if ok_r and ok_a and cand > best["adm_inrange"]:
                        best["adm_inrange"] = cand
            # ⛔ THE STITCH SEARCHES ONE AXIS. If the camera also PANS, no vertical shift can
            # ever match and the row read is beside the point. Offered here as a 2-D replay.
            pan = [0.0, None, None, None, 0]
            for idx, (oy, ox, brd, _ink, bdy) in enumerate(readings):
                for shift in range(lo - wide, hi + wide + 1):
                    for dc in range(-tool._cols, tool._cols + 1):
                        sc, total = score_at(world, volatile, brd, bdy, shift, dc)
                        if total < amin:
                            continue
                        if round(sc, 3) > pan[0]:
                            pan = [round(sc, 3), shift, dc, idx, total]
            cause = "PICTURE"
            if best["adm"][0] >= fit and best["adm_inrange"][0] < fit:
                cause = "RANGE"
            elif best["inrange"][0] >= fit and best["adm_inrange"][0] < fit:
                cause = "ALLOW"
            elif best["adm_inrange"][0] >= fit:
                cause = "NONE?"
            elif best["nofloor"][0] >= fit:
                cause = "OVERLAP"
            rec.update({"cause": cause, "best": {k: list(v) for k, v in best.items()},
                        "range": [in_lo, in_hi], "at": at, "gdir": gdir, "origin": origin,
                        "cols": tool._cols, "world_rows": [lo, hi], "floored": floored,
                        "pan": pan,
                        "bodies": [b for _, _, _, _, b in readings],
                        "profile": sorted(profile, key=lambda r: -r[2])[:25]})
        calls.append(rec)
        return outcome, board, inks, body

    if mode != "pure":
        tool._stitch = wrapped

    prev_levels = int(obs.levels_completed)
    level_counts: list[int] = []
    this_level = 0
    actions = 0

    while actions < budget:
        if adapter.is_done([], obs):
            break
        step_no["n"] = actions
        action = adapter.choose_action([], obs)
        if not isinstance(action, GameAction):
            break
        obs = env.step(action, data=action.action_data.model_dump()) if action.is_complex() \
            else env.step(action)
        if obs is None:
            break
        actions += 1
        this_level += 1
        cur = int(obs.levels_completed)
        if cur > prev_levels:
            for _ in range(cur - prev_levels):
                level_counts.append(this_level)
                this_level = 0
            prev_levels = cur
        if obs.state == GameState.WIN:
            break
        if obs.state == GameState.GAME_OVER:
            obs = env.step(GameAction.RESET)
            actions += 1
            this_level += 1
            if obs is None:
                break

    lost = [c for c in calls if c["outcome"] == "lost"]
    print(json.dumps({
        "arm": {"game": game, "mode": mode, "seed": seed},
        "levels": prev_levels,
        "actions": actions,
        "level_counts": level_counts,
        "n_stitch": len(calls),
        "outcomes": dict(Counter(c["outcome"] for c in calls)),
        "rows_hist": dict(Counter(c["rows_in"] for c in calls)),
        "causes": dict(Counter(c.get("cause", "-") for c in lost)),
        "lost": lost,
    }))


if __name__ == "__main__":
    main()
