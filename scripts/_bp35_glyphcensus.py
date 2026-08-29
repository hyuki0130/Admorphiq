"""bp35: is a LETHAL glyph distinguishable from a safe one in the frame BEFORE contact?

⛔ Why this is the question. bp35 scores 0.2220 and its loss is NOT the level-6 wall — it is the
two failed attempts that precede each winning one. Per level, from the gate baseline:

    level 2   87 actions vs 48 human   =  8 spike +  34 spike + 43 CLEARED   (43 < 48)
    level 5   60 actions vs 33 human   = 14 spike +  14 spike + 30 CLEARED   (30 < 33)

The winning attempt already BEATS the human on both boards; removing the two exploratory deaths
takes bp35 0.2220 -> 0.3304. `crag._learn_death` only names a glyph lethal on an UNEXPLAINED
landing, so the tool deliberately gambles on unseen ground and pays two deaths per board to learn
which drawn kinds kill. That price is only avoidable if the killer is READABLE before it is touched.

Method, two independent instruments that must agree:

  ANALYTIC  — every sprite in the game's own table is rasterised over the background exactly as the
              engine composites it, and crag's OWN `_sig` (the order-free colour histogram of the
              4x4 core at pitch 6) is computed for it. Collisions are reported as sprite pairs.
  LIVE      — the game is played through the SCORER'S OWN agent factory; at every action the
              settled frame is read with crag's OWN `fit_lattice` / `read_lattice`, each screen cell
              is mapped to its board cell through the camera, and the cell's Sig is filed against
              the sprite names the ENGINE has there. The mapping is self-checked: the residual of
              the pixel alignment and the number of distinct sigs covering the wall glyph are both
              printed, and a mapping that is wrong cannot make the wall look like one kind.

Expected feedback: a Sig that covers BOTH a lethal name and a non-lethal one on the SAME board is a
hard negative — bp35's remaining 0.1084 is unreachable by perception and the deaths are the price of
the game. A clean split, with the per-board CELL COUNTS, says crag can name the spike lethal from
the frame and never walk into it.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, "src")

GRID_W = 11
GRID_H = 39
PITCH = 6
# The engine's own verdict, read off `fsvnqdbzrp`: it stops the fall on any name outside PASSABLE,
# wins on the gem and loses on the spike. `hzusueifitk` carries the metadata name "ubhhgljbnpu",
# so a name-level classification sees ONE lethal name and two drawn kinds.
LETHAL_NAMES = {"ubhhgljbnpu", "hzusueifitk"}
GEM_NAME = "fjlzdjxhant"


def load_module():
    p = Path(__file__).resolve().parents[1] / "environment_files/bp35/0a0ad940/bp35.py"
    spec = importlib.util.spec_from_file_location("bp35mod", p)
    m = importlib.util.module_from_spec(spec)
    sys.modules["bp35mod"] = m
    spec.loader.exec_module(m)
    return m


def analytic(m) -> dict:
    """crag's signature for every sprite in the table, composited the way the engine draws it."""
    import numpy as np

    from admorphiq.tools.crag import _sig

    # A cell is drawn over the background; unmapped sprite characters are transparent (-1).
    bg = int(m.BACKGROUND_COLOR)
    out: dict[str, dict] = {}
    for key, spr in m.ymmwcccrhb.items():
        arr = spr.ieikpxxuml()
        tile = np.full((7, 7), bg, dtype=np.int64)
        h, w = arr.shape
        tile[:h, :w] = np.where(arr >= 0, arr, bg)
        core = tile[1:PITCH - 1, 1:PITCH - 1]
        out[key] = {"name": spr.name, "sig": _sig(core.astype(np.int64))}
    by_sig: dict[tuple, list[str]] = {}
    for key, rec in out.items():
        by_sig.setdefault(rec["sig"], []).append(key)
    collisions = []
    for sig, keys in by_sig.items():
        names = {out[k]["name"] for k in keys}
        lethal = names & LETHAL_NAMES
        if lethal and names - LETHAL_NAMES:
            collisions.append({"sig": [list(t) for t in sig], "keys": sorted(keys),
                               "names": sorted(names)})
    return {
        "sprite_sigs": {k: {"name": v["name"], "sig": [list(t) for t in v["sig"]]}
                        for k, v in sorted(out.items())},
        "sigs_sharing_a_lethal_and_a_safe_sprite": collisions,
        "two_spike_kinds_share_a_sig": out["ubhhgljbnpu"]["sig"] == out["hzusueifitk"]["sig"],
    }


def main() -> None:
    import numpy as np
    from arc_agi import Arcade, OperationMode
    from arcengine import GameAction, GameState

    from admorphiq.tools.crag import fit_lattice, read_lattice, settled_layer

    # ⛔ argv[1] is the fan SEED (pfan.sh passes it), argv[2] the action cap.
    cap = int(sys.argv[2]) if len(sys.argv) > 2 else 800

    m = load_module()
    ana = analytic(m)

    _spec = importlib.util.spec_from_file_location(
        "score_eff", Path(__file__).resolve().parent / "score_efficiency.py")
    _se = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(_se)

    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    info = next(i for i in arcade.get_environments()
                if (i.title or i.game_id).lower().startswith("bp35"))
    env = arcade.make(info.game_id)
    obs = env.reset()
    game = getattr(env, "_game", None) or getattr(env, "game", None)
    agent = _se._make_agent("unified", info.game_id)

    # sig -> board level -> Counter of the engine's name-set at that cell
    filed: dict[tuple, dict[int, Counter]] = {}
    residuals: Counter = Counter()
    lattices: Counter = Counter()

    truth: Counter = Counter()

    def snapshot() -> None:
        # ⛔ Re-read the scene EVERY step. It is replaced on a level change, and a reference taken
        # at reset reports level 1 and an empty board for the whole run — which looks exactly like
        # "no spike is ever on screen" and is a measurement of nothing.
        scene = game.oztjzzyqoek
        g = settled_layer(obs)
        lat = fit_lattice(np.asarray(g))
        if lat is None:
            lattices["no_lattice"] += 1
            return
        p, oy, ox = lat
        lattices[f"p{p}"] += 1
        if p != PITCH:
            return
        board, _inks = read_lattice(np.asarray(g), p, oy, ox)
        cam = int(scene.camera.rczgvgfsfb[1])
        lvl = int(scene.qswcochjodb)
        for (r, c), sig in board.items():
            px, py = ox + c * p, oy + r * p
            if px % PITCH or (py + cam) % PITCH:
                residuals["unaligned"] += 1
                continue
            residuals["aligned"] += 1
            gx, gy = px // PITCH, (py + cam) // PITCH
            if not (0 <= gx < GRID_W and 0 <= gy < GRID_H):
                continue
            names = frozenset(i.name for i in scene.hdnrlfmyrj.jhzcxkveiw(gx, gy)
                              if not i.name.startswith("player"))
            truth[tuple(sorted(names))] += 1
            filed.setdefault(sig, {}).setdefault(lvl, Counter())[tuple(sorted(names))] += 1

    restart_on_game_over = bool(getattr(agent, "restart_on_game_over", False))
    start_done = int(getattr(obs, "levels_completed", 0) or 0)
    stopped, step = "budget", 0
    snapshot()
    for step in range(cap):
        if agent.is_done([], obs):
            stopped = "agent_is_done"
            break
        act = agent.choose_action([], obs)
        data = act.action_data.model_dump() if getattr(act, "action_data", None) else None
        obs = env.step(act, data=data) if data else env.step(act)
        if obs is None:
            stopped = "obs_none"
            break
        snapshot()
        if getattr(obs, "state", None) == GameState.WIN:
            stopped = "WIN"
            break
        if getattr(obs, "state", None) == GameState.GAME_OVER:
            if not restart_on_game_over:
                stopped = "GAME_OVER_break"
                break
            obs = env.step(GameAction.RESET)
            if obs is None:
                stopped = "obs_none_after_reset"
                break

    end_done = int(getattr(obs, "levels_completed", 0) or 0)

    # --- the verdict: does any observed Sig cover both a lethal cell and a non-lethal one?
    rows, ambiguous = [], []
    for sig, per_lvl in filed.items():
        allnames: Counter = Counter()
        for cnt in per_lvl.values():
            allnames.update(cnt)
        lethal_hits = sum(n for k, n in allnames.items() if set(k) & LETHAL_NAMES)
        safe_hits = sum(n for k, n in allnames.items() if not (set(k) & LETHAL_NAMES))
        rec = {"sig": [list(t) for t in sig],
               "lethal_cells": lethal_hits, "safe_cells": safe_hits,
               "content": {"+".join(k) if k else "(empty)": n
                           for k, n in allnames.most_common(6)},
               "levels": sorted(per_lvl)}
        rows.append(rec)
        if lethal_hits and safe_hits:
            ambiguous.append(rec)
    rows.sort(key=lambda r: -(r["lethal_cells"] + r["safe_cells"]))

    lethal_sigs = [r for r in rows if r["lethal_cells"] and not r["safe_cells"]]
    # per level: how many DISTINCT sigs are lethal-only, and how many cells they cover
    per_level: dict[str, dict] = {}
    for sig, cnt in filed.items():
        for lvl, c in cnt.items():
            leth = sum(n for k, n in c.items() if set(k) & LETHAL_NAMES)
            saf = sum(n for k, n in c.items() if not (set(k) & LETHAL_NAMES))
            d = per_level.setdefault(str(lvl), {"lethal_sigs": set(), "safe_sigs": set(),
                                                "both_sigs": set(), "lethal_cell_reads": 0})
            if leth and saf:
                d["both_sigs"].add(sig)
            elif leth:
                d["lethal_sigs"].add(sig)
            elif saf:
                d["safe_sigs"].add(sig)
            d["lethal_cell_reads"] += leth
    per_level = {k: {"lethal_only_sigs": len(v["lethal_sigs"]),
                     "safe_only_sigs": len(v["safe_sigs"]),
                     "AMBIGUOUS_sigs": len(v["both_sigs"]),
                     "lethal_cell_reads": v["lethal_cell_reads"]}
                 for k, v in sorted(per_level.items(), key=lambda kv: int(kv[0]))}

    print(json.dumps({
        "levels_completed_start": start_done,
        "levels_completed_end": end_done,
        "greater_than_start": end_done > start_done,
        "actions_total": step + 1,
        "why_stopped": stopped,
        "lattice_pitches": dict(lattices),
        "engine_cell_contents": {"+".join(k) if k else "(empty)": v for k, v in truth.most_common(20)},
        "alignment": dict(residuals),
        "analytic": ana,
        "live_verdict": {
            "distinct_sigs_seen": len(rows),
            "sigs_that_are_lethal_ONLY": len(lethal_sigs),
            "sigs_covering_BOTH_lethal_and_safe": len(ambiguous),
            "ambiguous": ambiguous[:8],
            "lethal_only": lethal_sigs[:8],
            "per_level": per_level,
        },
        "top_sigs": rows[:14],
    }))


if __name__ == "__main__":
    main()
