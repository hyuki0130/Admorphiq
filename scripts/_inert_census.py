#!/usr/bin/env python3
"""INERT-ACTION CENSUS across all 25 games, restricted to levels the agent CLEARS.

⛔ THE QUESTION. On lf52's level 6 — a level the game never clears — `world_model` spends 117
actions and changes the board ZERO times, and with `deadsig` and `llm_goal` 131 of 500 actions
produce ONE board change between them (rule 7bw). There it costs nothing: a level that never clears
is scored zero however it is spent. **The question with score attached is whether the same waste
happens on levels that DO clear**, where an inert action is a direct efficiency loss and RHAE
SQUARES it — and where it would cost on every one of the 110 unseen games.

⛔ AN INERT ACTION IS NOT AUTOMATICALLY WASTE, and conflating them is how this becomes the twelfth
instrument returning a plausible number for a quantity it is not measuring. `deadsig` EXISTS to
discover that an action is inert, and discovering it costs the action. So every inert action is
classified by whether its own KEY had already been observed inert EARLIER ON THE SAME LEVEL:

    inert_first   the first time this key is seen inert here — that is INFORMATION, paid for once
    inert_repeat  the key was already known inert on this level — spent and never used

⚠️ TWO KEYS, because one of them undercounts by construction. `strict` is (action id, x, y), so two
clicks at different pixels are different keys and a click-prober never "repeats". `coarse` is the
action id alone, which for a click tool asks "how many clicks did it spend after the first one that
did nothing". Neither is right alone; both are reported.

⛔ THE CHANGE TEST IS `segment.board_changed`, NOT `(prev != cur).any()` — rule 7c: a board with an
action counter at the frame's edge makes the raw test TRUE for every action including refusals, and
a guard built on it recorded nothing across 227 transitions on the very level it was written for.
BOTH are recorded, so the gap between them measures how badly the raw test would have lied here.

CONTROLS (rule 7ai).
  NEGATIVE  per-level counts and the total must equal `scripts/rounds/R101SHIPPED/games/<g>.json`.
            A different number means this probe is describing a different run (rule 7aj.2).
  POSITIVE  `raw_changed` and `board_changed` must both be able to say YES and NO. A census whose
            inert count is zero everywhere has measured nothing; so has one that is 100% inert.
            `pos_*` fields print both directions per game.

Usage:  uv run python scripts/_inert_census.py <seed 1..25>
"""
from __future__ import annotations

import importlib.util
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

GAMES = ["ar25", "bp35", "cd82", "cn04", "dc22", "ft09", "g50t", "ka59", "lf52", "lp85",
         "ls20", "m0r0", "r11l", "re86", "s5i5", "sb26", "sc25", "sk48", "sp80", "su15",
         "tn36", "tr87", "tu93", "vc33", "wa30"]


def main() -> None:
    seed = int(sys.argv[1])
    game = GAMES[(seed - 1) % len(GAMES)]
    budget = int(sys.argv[2]) if len(sys.argv) > 2 else 4000

    from arc_agi import Arcade, OperationMode

    from admorphiq.tools.base import frame_2d, has_frame
    from admorphiq.tools.segment import board_changed

    _spec = importlib.util.spec_from_file_location(
        "score_eff", Path(__file__).resolve().parent / "score_efficiency.py")
    se = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(se)

    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    info = next(i for i in arcade.get_environments()
                if (i.title or i.game_id).lower().startswith(game))

    held: dict = {}
    real_make = arcade.make

    def make(gid, *a, **k):
        env = real_make(gid, *a, **k)
        held["env"] = env
        return env

    arcade.make = make

    rows: list[dict] = []
    real_factory = se._make_agent

    def factory():
        inner = real_factory("unified", game_id=info.game_id)
        prev: dict = {"g": None}

        class Watch:
            restart_on_game_over = getattr(inner, "restart_on_game_over", False)

            def is_done(self, frames, obs):
                return inner.is_done(frames, obs)

            def choose_action(self, frames, obs):
                # ⛔ The change is read at the NEXT decision, because `observe` is never given the
                # frame that follows its own action (rule 7c). So each row closes the PREVIOUS one.
                g = frame_2d(obs).astype("int16") if has_frame(obs) else None
                if rows and prev["g"] is not None and g is not None:
                    last = rows[-1]
                    if last.get("raw") is None:
                        last["raw"] = bool((prev["g"] != g).any())
                        last["brd"] = bool(board_changed(prev["g"], g))
                act = inner.choose_action(frames, obs)
                dat = getattr(act, "action_data", None)
                xy = ((int(getattr(dat, "x", -1)), int(getattr(dat, "y", -1)))
                      if dat is not None and hasattr(dat, "x") else None)
                rows.append({
                    "lvl": int(getattr(obs, "levels_completed", -1)),
                    "who": getattr(inner, "_current", None) or "HARNESS",
                    "aid": int(getattr(act, "id", getattr(act, "value", -1)))
                    if not isinstance(getattr(act, "id", None), str) else str(act.id),
                    "name": str(getattr(act, "name", act)),
                    "xy": xy, "raw": None, "brd": None,
                })
                prev["g"] = g
                return act

        return Watch()

    res = se.run_game(arcade, info.game_id, info.baseline_actions,
                      agent_name="unified", max_actions=budget, adapter_factory=factory)

    rows = [r for r in rows if r["raw"] is not None]

    banked = json.load(open(Path(__file__).resolve().parent
                             / f"rounds/R101SHIPPED/games/{game}.json"))["games"][0]
    per = [p["agent_actions"] for p in res.get("per_level", [])]
    bper = [p["agent_actions"] for p in banked["per_level"]]

    # Levels that CLEARED are exactly the ones with a per_level entry (0-indexed lvl == i).
    cleared = {i: banked["per_level"][i] for i in range(len(banked["per_level"]))}

    out: dict = {
        "game": game,
        "per_level": per,
        "total_actions": int(res.get("total_actions", -1)),
        "game_score": res.get("game_score"),
        "banked_per_level": bper,
        "banked_score": banked["game_score"],
        "control_ok": per == bper and abs((res.get("game_score") or -1)
                                          - banked["game_score"]) < 1e-9,
        "rows": len(rows),
        # POSITIVE controls, both directions, both tests.
        "pos_raw_changed": sum(1 for r in rows if r["raw"]),
        "pos_raw_inert": sum(1 for r in rows if not r["raw"]),
        "pos_brd_changed": sum(1 for r in rows if r["brd"]),
        "pos_brd_inert": sum(1 for r in rows if not r["brd"]),
    }

    # --- per CLEARED level ------------------------------------------------------------------
    seen_strict: dict[int, set] = defaultdict(set)
    seen_coarse: dict[int, set] = defaultdict(set)
    lvl_stat: dict[int, dict] = {}
    runs: dict[int, dict] = {}
    for r in rows:
        L = r["lvl"]
        st = lvl_stat.setdefault(L, {"n": 0, "inert": 0, "first_s": 0, "rep_s": 0,
                                     "first_c": 0, "rep_c": 0, "dead": 0, "edge": 0,
                                     "dead_rep_s": 0, "dead_rep_c": 0,
                                     "by_tool": Counter(), "inert_by_tool": Counter(),
                                     "rep_by_tool": Counter(), "dead_by_tool": Counter()})
        st["n"] += 1
        # ⛔ THREE CLASSES, because two of them want different verdicts. `board_changed` ignores the
        # outer band ON PURPOSE (rule 7c: an edge counter otherwise makes every action look live) —
        # but a game that draws a selection marker or a HUD readout in that band has its REAL effect
        # discarded by the same rule. So an action is only called unambiguously inert when NOTHING
        # changed anywhere; one that moved only the band is recorded separately and never counted as
        # waste without a second look.
        if not r["raw"]:
            st["dead"] += 1
            st["dead_by_tool"][r["who"]] += 1
        elif not r["brd"]:
            st["edge"] += 1
        st["by_tool"][r["who"]] += 1
        if not r["brd"]:
            st["inert"] += 1
            st["inert_by_tool"][r["who"]] += 1
            ks = (r["aid"], r["xy"])
            kc = r["aid"]
            if ks in seen_strict[L]:
                st["rep_s"] += 1
                st["rep_by_tool"][r["who"]] += 1
                if not r["raw"]:
                    st["dead_rep_s"] += 1
            else:
                st["first_s"] += 1
                seen_strict[L].add(ks)
            if kc in seen_coarse[L]:
                st["rep_c"] += 1
                if not r["raw"]:
                    st["dead_rep_c"] += 1
            else:
                st["first_c"] += 1
                seen_coarse[L].add(kc)
        # longest run of consecutive inert actions by ONE tool — the livelock signature
        rn = runs.setdefault(L, {"cur": 0, "who": None, "best": 0, "best_who": None})
        if not r["brd"] and r["who"] == rn["who"]:
            rn["cur"] += 1
        elif not r["brd"]:
            rn["cur"], rn["who"] = 1, r["who"]
        else:
            rn["cur"], rn["who"] = 0, None
        if rn["cur"] > rn["best"]:
            rn["best"], rn["best_who"] = rn["cur"], rn["who"]

    lv: list[dict] = []
    for L in sorted(lvl_stat):
        st = lvl_stat[L]
        info_l = cleared.get(L)
        lv.append({
            "lvl": L + 1,
            "cleared": info_l is not None,
            "agent_actions": info_l["agent_actions"] if info_l else None,
            "human_actions": info_l["human_actions"] if info_l else None,
            "score": info_l["score"] if info_l else None,
            "sampled": st["n"],
            "inert": st["inert"],
            "inert_first_strict": st["first_s"], "inert_repeat_strict": st["rep_s"],
            "inert_first_coarse": st["first_c"], "inert_repeat_coarse": st["rep_c"],
            "dead": st["dead"], "edge_only": st["edge"],
            "dead_repeat_strict": st["dead_rep_s"], "dead_repeat_coarse": st["dead_rep_c"],
            "dead_by_tool": dict(st["dead_by_tool"]),
            "by_tool": dict(st["by_tool"]),
            "inert_by_tool": dict(st["inert_by_tool"]),
            "repeat_by_tool": dict(st["rep_by_tool"]),
            "longest_inert_run": runs[L]["best"], "run_tool": runs[L]["best_who"],
        })
    out["levels"] = lv

    # --- counterfactual: what would a CLEARED level score without its repeat-inert actions? ---
    win_levels = int(banked["win_levels"])
    denom = sum(range(1, win_levels + 1))
    cf = {}
    for key, field in (("strict", "inert_repeat_strict"), ("coarse", "inert_repeat_coarse"),
                       ("dead_strict", "dead_repeat_strict"),
                       ("dead_coarse", "dead_repeat_coarse")):
        gained = 0.0
        detail = []
        for e in lv:
            if not e["cleared"] or e["agent_actions"] is None:
                continue
            a, h, s = e["agent_actions"], e["human_actions"], e["score"]
            k = e[field]
            a2 = max(1, a - k)
            s2 = min(h / a2, 1.0) ** 2
            if s2 > s + 1e-12:
                detail.append({"lvl": e["lvl"], "a": a, "k": k, "score": s, "score_cf": s2})
            gained += e["lvl"] * (max(s2, s) - s)
        cf[key] = {"game_score_gain": round(gained / denom, 6),
                   "mean_gain_over_25": round(gained / denom / 25, 6),
                   "levels_improved": detail}
    out["counterfactual"] = cf
    print(json.dumps(out))


if __name__ == "__main__":
    main()
