#!/usr/bin/env python3
"""What does the DISCARDED OUTER BAND cost? — read the consumer, not the guard.

⛔ THE QUESTION (raised by rule 7cb's own numbers). `segment.board_changed` throws away the frame's
outer band ON PURPOSE — rule 7c, because a step counter at (63,63) once made 71 of 71 cd82 clicks
read as "responsive". But the census found r11l producing its ONLY visible effect out there on
**39 of 82 actions of levels it CLEARS**, bp35 on 205 of 499, cd82 on 28 of 131. So: when the
harness believes an action did nothing, what does it actually DO differently?

⛔ THE CHAIN, read off the source before measuring anything (`harness/loop.py:715-760`):

    changed       = (prev != frame).any()          BAND INCLUDED -> the ACTIVE tool's observe()
    board_changed = segment.board_changed(...)     BAND DISCARDED -> tools with augmenter=True
    novelty       = base_hash(frame)               BAND INCLUDED -> _since_progress, stall, retire
    _empty_runs                                    reads NEITHER; it counts propose() returning []

**Exactly one tool in the registry sets `augmenter = True`: `deadsig`.** So the entire cost of the
discarded band flows through one path:

    deadsig.observe(board_changed) -> _changed_any[cls] -> globally_dead(cls)
      -> GraphSearchTool._drop_dead  -> the class is WITHHELD from graph's candidate list

`globally_dead` needs `changed_any == 0` AND >= 12 tries from >= 3 distinct states, and ONE observed
change anywhere revives it forever. So a class is wrongly killed only if EVERY one of a dozen
observations was band-only.

WHAT IS MEASURED, per game, over the real scored run:
  1. BAND BEHAVIOUR, classified by BEHAVIOUR and not by position (the observation phase's own rule,
     `strategies/inferential.py:273` — a pixel changing under >= 80% of actions is a counter/HUD).
     Band pixels are split into `hud` (>= 80% of actions) and `action_dependent` (the rest).
  2. THE MISLABEL, by running TWO shadow `DeadSignatureTool`s side by side over the SAME
     transitions — one fed the band-discarded flag the harness uses, one fed the raw flag — and
     asking each which action classes it calls `globally_dead`. The difference IS the cost.
     ⛔ Real instances of the real class, never a re-implementation of its thresholds.
  3. THE CONSUMER, by wrapping `GraphSearchTool._drop_dead`: how many times it is called, how often
     it actually WITHHELD something, which keys, on which level, and whether that level cleared.
     ⭐ If it never withholds, the band costs zero and the question is closed.

CONTROLS (rule 7ai).
  NEGATIVE  per-level counts AND game score must equal `scripts/rounds/R101SHIPPED/games/<g>.json`.
  POSITIVE  both shadows must be able to say YES and NO; `band_only_actions` must be non-zero on the
            games the census named and zero on the ones it did not. A run where the band never
            moves has measured nothing about the band.

Usage:  uv run python scripts/_band_cost.py <seed 1..25>
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

GAMES = ["ar25", "bp35", "cd82", "cn04", "dc22", "ft09", "g50t", "ka59", "lf52", "lp85",
         "ls20", "m0r0", "r11l", "re86", "s5i5", "sb26", "sc25", "sk48", "sp80", "su15",
         "tn36", "tr87", "tu93", "vc33", "wa30"]
HUD_FRAC = 0.8   # the observation phase's own threshold for "this pixel is a counter"


def main() -> None:
    seed = int(sys.argv[1])
    game = GAMES[(seed - 1) % len(GAMES)]
    budget = int(sys.argv[2]) if len(sys.argv) > 2 else 4000

    from arc_agi import Arcade, OperationMode

    from admorphiq.tools import graph_search as gs
    from admorphiq.tools.base import frame_2d, has_frame
    from admorphiq.tools.dead_signature import DeadSignatureTool
    from admorphiq.tools.segment import board_changed, edge_band

    _spec = importlib.util.spec_from_file_location(
        "score_eff", Path(__file__).resolve().parent / "score_efficiency.py")
    se = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(se)

    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    info = next(i for i in arcade.get_environments()
                if (i.title or i.game_id).lower().startswith(game))

    # --- the consumer, wrapped ------------------------------------------------------------
    drops: list[dict] = []
    calls = {"n": 0, "cut": 0}
    raw_drop = gs.GraphSearchTool._drop_dead
    cur = {"lvl": -1, "step": 0}

    def wrapped_drop(self, state, keys):
        out = raw_drop(self, state, keys)
        calls["n"] += 1
        if len(out) != len(keys):
            calls["cut"] += 1
            if len(drops) < 40:
                lost = [k for k in keys if k not in out]
                drops.append({"lvl": cur["lvl"], "step": cur["step"],
                              "n_keys": len(keys), "n_live": len(out),
                              "dropped": [str(k) for k in lost[:12]]})
        return out

    gs.GraphSearchTool._drop_dead = wrapped_drop

    # --- two shadow deadsigs, real instances of the real class ----------------------------
    sh_board = DeadSignatureTool()
    sh_raw = DeadSignatureTool()
    seen_cls: set = set()

    band_hits: dict = {"count": None, "n": 0}
    # ⛔ THE PER-PIXEL ">= 80% OF ACTIONS" TEST CANNOT SEE A COUNTER, and `segment.py`'s own
    # docstring says why: "a bar that shrinks or a counter that marches touches each cell once, so
    # no cell reaches a 'changes under most actions' threshold". So the behavioural test is asked at
    # the REGION level and PER ACTION CLASS, which is the coordinator's own phrasing: does the band
    # advance with every action regardless of which action it was, or does it depend on the action?
    band_cls: dict = {}
    rows: list[dict] = []

    real_factory = se._make_agent
    _agent_ref: dict = {}

    def factory():
        inner = real_factory("unified", game_id=info.game_id)
        _agent_ref["a"] = inner
        prev: dict = {"g": None, "step": None, "lvl": 0}

        class Watch:
            restart_on_game_over = getattr(inner, "restart_on_game_over", False)

            def is_done(self, frames, obs):
                return inner.is_done(frames, obs)

            def choose_action(self, frames, obs):
                g = frame_2d(obs).astype(np.int16) if has_frame(obs) else None
                lvl = int(getattr(obs, "levels_completed", -1))
                # close the PREVIOUS transition (rule 7c: observe never sees the next frame)
                if prev["g"] is not None and g is not None and prev["g"].shape == g.shape:
                    raw = bool((prev["g"] != g).any())
                    brd = bool(board_changed(prev["g"], g))
                    diff = prev["g"] != g
                    band = edge_band(g.shape)
                    if band_hits["count"] is None:
                        band_hits["count"] = np.zeros(g.shape, dtype=np.int64)
                    if band_hits["count"].shape == diff.shape:
                        band_hits["count"] += (diff & band).astype(np.int64)
                        band_hits["n"] += 1
                    st = prev["step"]
                    if st is not None:
                        sh_board.observe(prev["g"], st, brd)
                        sh_raw.observe(prev["g"], st, raw)
                        seen_cls.add(sh_board._action_class(st))
                    bchg = bool((diff & band).any())
                    if st is not None:
                        c = str(sh_board._action_class(st))
                        e = band_cls.setdefault(c, [0, 0])
                        e[0] += 1
                        e[1] += int(bchg)
                    rows.append({"lvl": prev["lvl"], "raw": raw, "brd": brd,
                                 "band_only": raw and not brd, "band_chg": bchg,
                                 "who": prev.get("who")})
                # the harness resets every tool on a level-up; the shadows must mirror it
                if lvl > prev["lvl"]:
                    sh_board.reset()
                    sh_raw.reset()
                cur["lvl"], cur["step"] = lvl, len(rows)
                act = inner.choose_action(frames, obs)
                # ⛔ Take the HARNESS's OWN `_prev_step` rather than rebuilding one from the
                # GameAction: that is the exact tuple it hands to `observe`, so the shadows are
                # fed byte-for-byte what the real deadsig is fed. Rebuilding it is where an
                # instrument silently starts measuring a different quantity.
                prev.update(g=g, lvl=lvl,
                            step=getattr(inner, "_prev_step", None),
                            who=getattr(inner, "_current", None) or "HARNESS")
                return act

        return Watch()

    res = se.run_game(arcade, info.game_id, info.baseline_actions,
                      agent_name="unified", max_actions=budget, adapter_factory=factory)

    banked = json.load(open(Path(__file__).resolve().parent
                            / f"rounds/R101SHIPPED/games/{game}.json"))["games"][0]
    per = [p["agent_actions"] for p in res.get("per_level", [])]
    bper = [p["agent_actions"] for p in banked["per_level"]]
    ncl = len(bper)

    def _rep(c):
        """A representative Step for an action CLASS key, so the real `globally_dead` can be
        asked about it. Mirrors `DeadSignatureTool._action_class`: ("s", id) or
        ("c", id, x//block, y//block), and coord is (x, y)."""
        if c[0] == "s":
            return (int(c[1]), None)
        return (int(c[1]), (int(c[2]) * sh_board.block, int(c[3]) * sh_board.block))

    dead_board = {str(c) for c in seen_cls if sh_board.globally_dead(_rep(c))}
    dead_raw = {str(c) for c in seen_cls if sh_raw.globally_dead(_rep(c))}

    band = band_hits["count"]
    n = max(1, band_hits["n"])
    hud_px = int((band >= HUD_FRAC * n).sum()) if band is not None else 0
    act_px = int(((band > 0) & (band < HUD_FRAC * n)).sum()) if band is not None else 0
    top = sorted(((int(v), int(i // band.shape[1]), int(i % band.shape[1]))
                  for i, v in enumerate(band.ravel()) if v), reverse=True)[:6] \
        if band is not None else []

    # graph's OWN discard is BEHAVIOURAL (>= _HUD_FRAC of observations) and position-free, and it
    # feeds the harness's progress signal via `state_key` — a DIFFERENT discard from the positional
    # band. Recorded so the two are never conflated.
    _gt = _agent_ref.get("a")
    _gm = getattr(_gt.tools.get("graph"), "_mask", None) if _gt is not None else None
    _shape = list(band.shape) if band is not None else None
    if _gm is None:
        _gmask = [0, 0]
    else:
        _bd = edge_band(_gm.shape)
        _gmask = [int(_gm.sum()), int((_gm & _bd).sum())]

    out = {
        "game": game,
        "per_level": per, "banked_per_level": bper,
        "total_actions": int(res.get("total_actions", -1)),
        "game_score": res.get("game_score"), "banked_score": banked["game_score"],
        "control_ok": per == bper and abs((res.get("game_score") or -1)
                                          - banked["game_score"]) < 1e-9,
        "transitions": len(rows),
        # 1. band behaviour, classified by BEHAVIOUR
        "band_only_actions": sum(1 for r in rows if r["band_only"]),
        "band_only_cleared": sum(1 for r in rows if r["band_only"] and r["lvl"] < ncl),
        "band_px_hud": hud_px, "band_px_action_dependent": act_px,
        # region-level counter test: how often does ANY band pixel move, and does it depend on
        # WHICH action was taken? A counter advances on ~every action of ~every class.
        "band_changed_actions": sum(1 for r in rows if r["band_chg"]),
        "band_changed_frac": round(sum(1 for r in rows if r["band_chg"]) / max(1, len(rows)), 3),
        "band_rate_by_class": {k: [v[0], v[1], round(v[1] / max(1, v[0]), 2)]
                               for k, v in sorted(band_cls.items(), key=lambda kv: -kv[1][0])[:10]},
        "band_classes_always": sum(1 for v in band_cls.values() if v[0] >= 5 and v[1] == v[0]),
        "band_classes_never": sum(1 for v in band_cls.values() if v[0] >= 5 and v[1] == 0),
        "band_classes_mixed": sum(1 for v in band_cls.values() if v[0] >= 5 and 0 < v[1] < v[0]),
        "graph_mask_px": _gmask[0], "graph_mask_in_band": _gmask[1], "frame_shape": _shape,
        "band_px_top": [{"n": v, "y": y, "x": x, "frac": round(v / n, 3)} for v, y, x in top],
        # 2. the mislabel
        "classes_seen": len(seen_cls),
        "dead_under_board": sorted(dead_board),
        "dead_under_raw": sorted(dead_raw),
        "wrongly_dead": sorted(dead_board - dead_raw),
        # 3. the consumer
        "drop_dead_calls": calls["n"], "drop_dead_withheld": calls["cut"],
        "drops_head": drops[:8],
        "drop_levels_cleared": sorted({d["lvl"] for d in drops if d["lvl"] < ncl}),
        "n_cleared_levels": ncl,
    }
    print(json.dumps(out))


if __name__ == "__main__":
    main()
