#!/usr/bin/env python3
"""What ENDS a tool's tenure? — a census across all 25 games (rule 7bd's open half).

⛔ THE QUESTION. `_EMPTY_TOLERANCE = 8` is the only number that ends a tenure by exhaustion, and
it was chosen against two boards (s5i5's 448 centre-clicks and dc22's 499). Rule 7ac closed the
routing branch and rule 7bh measured "hold the strong tool" INERT, so what is left is the shape of
the retirement rule itself. This measures, over all 25 games and without changing behaviour:

  1. every tenure boundary and its CAUSE — EMPTY / STALL / CLOCK / CODE, or none at all;
  2. the EMPTY-RUN SHAPE — the run-length encoding of "the active tool's propose() produced no
     legal step" over each tenure, so a run of eight in a row is distinguishable from eight
     scattered misses, and near-misses (runs of 1..7 the tool RECOVERED from) are counted;
  3. the tool's own scalar diagnostics AT the retirement frame, so "genuinely out" and
     "momentarily confused" have observables to be told apart by.

⛔ MIRRORS `score_efficiency.py:run_game` (rule 7x): the scorer's own `_make_agent("unified")`, an
EMPTY frames list, `restart_on_game_over` honoured, BREAK on WIN, per-level counts recorded the
same way. The per-level counts are the CONTROL — if they do not equal the banked
`scripts/rounds/R101LP85GATE/games/<game>.json` numbers the instrument moved the run and nothing
read off it is admissible (rule 7ai).

Usage:  uv run python scripts/_tenure_census.py <seed 1..25> [budget]
        seed indexes the 25 games in sorted title order.
"""

from __future__ import annotations

import json
import os
import sys
from collections import Counter


def _scalars(tool) -> dict:
    """Every scalar the tool carries plus container lengths — its own diagnostics, verbatim."""
    if tool is None:
        return {}
    out: dict = {}
    for k, v in vars(tool).items():
        if isinstance(v, bool) or v is None or isinstance(v, (int, float)):
            out[k] = v
        elif isinstance(v, str):
            out[k] = v[:80]
        elif isinstance(v, (set, list, dict, tuple)):
            out[k] = f"len={len(v)}"
    return out


def _rle(seq: list[int]) -> list[list[int]]:
    """Run-length encode a 0/1 sequence as [[value, count], ...]."""
    out: list[list[int]] = []
    for v in seq:
        if out and out[-1][0] == v:
            out[-1][1] += 1
        else:
            out.append([v, 1])
    return out


def main() -> None:
    seed = int(sys.argv[1])
    budget = int(sys.argv[2]) if len(sys.argv) > 2 else 4000

    here = os.path.dirname(os.path.abspath(__file__))
    sys.path.insert(0, os.path.join(here, "..", "src"))
    sys.path.insert(0, here)

    from arc_agi import Arcade, OperationMode  # type: ignore
    from arcengine import GameAction, GameState  # type: ignore
    from score_efficiency import _make_agent

    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    # ⛔ DEDUPE BY game_id. ceph-build's environment_files/sk48 holds TWO version dirs
    # (41055498 and d8078629) with the SAME game_id, the SAME baseline and DIFFERENT bytes, while
    # the repository has only the first — so `get_environments()` returns 26 there and 25 here, and
    # an index-addressed fan silently runs one game twice and drops the last. This is rule
    # 7 (env_metadata_duplicate_game_id) on a machine nobody re-checked.
    seen: set[str] = set()
    envs = [e for e in sorted(arcade.get_environments(), key=lambda e: e.game_id)
            if not (e.game_id in seen or seen.add(e.game_id))]
    if not 1 <= seed <= len(envs):
        print(json.dumps({"seed": seed, "error": f"only {len(envs)} games"}))
        return
    entry = envs[seed - 1]
    game_id = entry.game_id
    game = game_id.split("-")[0]

    env = arcade.make(game_id)
    obs = env.observation_space
    adapter = _make_agent("unified", game_id=game_id)

    # ---- instrument: wrap _fill_from_current so every propose round-trip is recorded ----
    # `_fill_from_current` is the ONLY place `propose()` is called and the ONLY place
    # `_empty_runs` moves (loop.py), so wrapping it captures the whole empty channel without
    # reimplementing `_legal`: the counter's delta says whether any legal step survived.
    fills: list[dict] = []           # one record per propose round-trip
    orig_fill = type(adapter)._fill_from_current

    def fill(self, frames, o):
        cur = self._current
        before = getattr(self, "_empty_runs", 0)
        orig_fill(self, frames, o)
        after = getattr(self, "_empty_runs", 0)
        retired = cur is not None and self._current is None
        # empty := no legal step survived. The counter either advanced by one, or was reset to
        # zero by the retirement itself.
        empty = 1 if (after == before + 1 or (retired and after == 0)) else 0
        fills.append({"tool": cur, "empty": empty, "retired": int(retired),
                      "level": self._last_levels})

    type(adapter)._fill_from_current = fill

    # ---- run (mirrors score_efficiency.run_game) ----
    win_levels = int(obs.win_levels)
    prev_levels = int(obs.levels_completed)
    total = 0
    this_level = 0
    per_level: list[int] = []
    restart_on_game_over = bool(getattr(adapter, "restart_on_game_over", False))

    events: list[dict] = []          # tenure boundaries
    tenure: Counter = Counter()      # actions held, per tool
    fill_marks: list[int] = []       # len(fills) at each tenure boundary, to slice the shape

    def banned_total(a) -> int:
        return sum(len(v) for v in getattr(a, "_clock_banned", {}).values())

    while total < budget:
        if adapter.is_done([], obs):
            break
        pre_cur = getattr(adapter, "_current", None)
        pre_failed = len(getattr(adapter, "_failed", ()))
        pre_banned = banned_total(adapter)
        pre_levels = getattr(adapter, "_last_levels", 0)

        try:
            action = adapter.choose_action([], obs)
        except Exception as exc:  # noqa: BLE001
            events.append({"action": total, "cause": "CRASH", "detail": str(exc)[:120]})
            break
        if not isinstance(action, GameAction):
            break

        post_cur = getattr(adapter, "_current", None)
        post_failed = len(getattr(adapter, "_failed", ()))
        post_banned = banned_total(adapter)

        if post_cur != pre_cur and pre_cur is not None:
            # A tenure ended inside this call. The cause is written by WHICH bookkeeping moved.
            if post_banned > pre_banned:
                cause = "CLOCK"                      # two agreeing deaths, level allowance
            elif getattr(adapter, "_last_levels", 0) != pre_levels:
                cause = "LEVELUP"                    # boundary drop of a clock-banned tool
            elif post_cur == "code" and post_failed <= pre_failed:
                cause = "CODE_ESC"                   # deterministic escalation, no retirement
            elif pre_cur == "code":
                cause = "CODE_END"
            elif post_cur is None:
                cause = "EMPTY"                      # _EMPTY_TOLERANCE reached
            elif post_failed > pre_failed:
                cause = "STALL"                      # redecide retired it
            else:
                cause = "OTHER"
            tool_obj = getattr(adapter, "tools", {}).get(pre_cur)
            events.append({
                "action": total,
                "level": pre_levels,
                "from": pre_cur,
                "to": post_cur,
                "cause": cause,
                "since_progress": getattr(adapter, "_since_progress", None),
                "primary_owns": getattr(adapter, "_primary_owns", None),
                "diag": _scalars(tool_obj),
            })
            fill_marks.append(len(fills))

        who = pre_cur or "HARNESS"
        tenure[who] += 1

        obs = env.step(action, data=action.action_data.model_dump()) if action.is_complex() \
            else env.step(action)
        if obs is None:
            break
        total += 1
        this_level += 1
        cur_levels = int(obs.levels_completed)
        if cur_levels > prev_levels:
            for _ in range(cur_levels - prev_levels):
                per_level.append(this_level)
                this_level = 0
            prev_levels = cur_levels
        if obs.state == GameState.WIN:
            break
        if obs.state == GameState.GAME_OVER:
            if not restart_on_game_over:
                break
            obs = env.step(GameAction.RESET)
            total += 1
            this_level += 1
            if obs is None:
                break

    # ---- empty-run shape, per tenure segment ----
    # A "tenure segment" here = the fills between two boundaries; runs are of the empty flag.
    segments: list[dict] = []
    marks = [0, *fill_marks, len(fills)]
    for a, b in zip(marks, marks[1:]):
        chunk = fills[a:b]
        if not chunk:
            continue
        segments.append({
            "tool": chunk[0]["tool"],
            "n_fills": len(chunk),
            "rle": _rle([c["empty"] for c in chunk]),
            "ended_empty": int(any(c["retired"] for c in chunk)),
        })

    # Near-misses: runs of consecutive empties the tool RECOVERED from (never reached 8).
    near: Counter = Counter()
    reached: Counter = Counter()
    for s in segments:
        runs = [n for v, n in s["rle"] if v == 1]
        for i, n in enumerate(runs):
            if n >= 8:
                reached[s["tool"]] += 1
            else:
                near[n] += 1

    print(json.dumps({
        "game": game,
        "game_id": game_id,
        "levels": prev_levels,
        "win_levels": win_levels,
        "actions": total,
        "per_level": per_level,
        "tenure": dict(tenure),
        "n_fills": len(fills),
        "events": events,
        "segments": segments,
        "near_miss_runlens": dict(sorted(near.items())),
        "reached_8": dict(reached),
    }))


if __name__ == "__main__":
    main()
