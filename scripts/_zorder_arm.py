#!/usr/bin/env python3
"""The Z-ORDER arm — can the corpus even EXHIBIT the transfer failure rule 7cd named?

⛔ THE DEFECT (rule 7cd): a frame-only tool that identifies an object by whether it is DRAWN is
reading PAINT ORDER, not mechanics. s5i5 L4 costs 22 extra actions because the archived source lists
the rider before the bar it rides, so the bar covers it. **We found that only because s5i5 happened
to have an archive whose list order differed**, and the colour-permutation arm (rule 7ce) cannot
produce it — a colour permutation preserves z-order by construction.

⛔ WHAT THE ENGINE ACTUALLY DOES WITH LIST ORDER — read before writing anything, and it is THREE
things, not one:

  1. `Camera._raw_render` sorts by `layer` with Python's STABLE `sorted`, so within a layer the list
     order IS the z-order and a later sprite is drawn OVER an earlier one. Negative pixels are
     transparent, so a sprite's footprint is its cells with `pixel >= 0`.
  2. ⛔ `Level` line 201 sorts `reverse=True` — also stable — and returns the FIRST hit. So within a
     layer, list order also decides WHICH SPRITE A HIT-TEST RETURNS. That is MECHANICAL, not visual.
  3. ⛔ `Level._merge_sys_static_pixel_perfect_on_init` merges every PIXEL_PERFECT `sys_static`
     sprite of a layer into one, LEFT TO RIGHT in list order, and then rewrites the list as
     `others + merged`.

So "same-layer reordering only changes which of two co-located sprites wins a pixel" is TOO STRONG,
and a game that moves under this mutation may be moving for reason 2 rather than reason 1. That
distinction is a deliverable, not a footnote.

ARMS (mode is the pfan REST argument):
  runtime   ⛔ THE CENSUS THAT MATTERS. `census` below counts sprites that overlap AT LEVEL START,
            and s5i5's own defect is INVISIBLE to it — its only declared overlap is on L8 while the
            known failure is L4, because the rider is co-located with the bar only once the game
            MOVES it there. So co-location is sampled from the LIVE level during the scored run.
  census    engine-truth OPENING-FRAME overlap census, NO game run. `Level.__init__` is monkeypatched before the
            game module is imported, so the RAW constructor list is captured pre-merge, with real
            Sprite objects — positions, layer, visibility and `render()` all from the engine.
  identity  rewrite the source with the permutation set to identity, then run. ⛔ THE NEGATIVE
            CONTROL, and it tests the REWRITE MACHINERY and not merely the run: it must reproduce
            `scripts/rounds/R101SHIPPED` exactly.
  reverse   reverse each same-layer group of each level's sprite list, then run.
  rot1      rotate each same-layer group by one, then run.

⭐ THE POSITIVE CONTROL IS s5i5: the mutation must reproduce the known 39 -> 61 on L4 when it puts
the rider under the bar. An arm that cannot score its own known positive has measured nothing.

VALIDITY is checked on the ENGINE's own objects, not on the text: after rewriting, the module is
re-imported and the multiset of (art signature, x, y, layer, visible) per level must be IDENTICAL —
only the ORDER may differ. That is `scripts/_s5i5_srcdiff.py`'s canonicalisation applied to live
sprites, which is strictly stronger than applying it to source.

Usage:  uv run python scripts/_zorder_arm.py <seed 1..25> <census|identity|reverse|rot1>
"""
from __future__ import annotations

import ast
import hashlib
import importlib.util
import json
import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

GAMES = ["ar25", "bp35", "cd82", "cn04", "dc22", "ft09", "g50t", "ka59", "lf52", "lp85",
         "ls20", "m0r0", "r11l", "re86", "s5i5", "sb26", "sc25", "sk48", "sp80", "su15",
         "tn36", "tr87", "tu93", "vc33", "wa30"]


def _game_file(envdir: Path, game: str) -> Path:
    hits = sorted(envdir.glob(f"{game}/*/{game}.py"))
    if not hits:
        raise SystemExit(f"no source for {game} under {envdir}")
    return hits[0]


def _capture(path: Path) -> list[list]:
    """The RAW constructor sprite list of every level, with the engine's own Sprite objects.

    ⛔ Captured by monkeypatching `Level.__init__` BEFORE the game module is imported: `Level`
    reorders its own list at construction (`others + merged`), so reading `_sprites` afterwards is
    reading a DIFFERENT order from the one the source declares.
    """
    import arcengine

    grabbed: list[list] = []
    real_init = arcengine.Level.__init__

    def init(self, sprites=None, *a, **k):
        grabbed.append(list(sprites or []))
        return real_init(self, sprites, *a, **k)

    arcengine.Level.__init__ = init
    try:
        spec = importlib.util.spec_from_file_location(f"_zg_{path.stem}_{id(path)}", path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
    finally:
        arcengine.Level.__init__ = real_init
    return grabbed


def _sig(s) -> str:
    px = s.render()
    return hashlib.md5(px.tobytes() + f"{px.shape}".encode()).hexdigest()[:10]


def _canon(levels: list[list]) -> list[list[tuple]]:
    """Per level, the multiset-able description of every placement, ORDER STRIPPED."""
    return [sorted((_sig(s), int(s.x), int(s.y), int(s.layer), bool(s.is_visible))
                   for s in lv) for lv in levels]


def _live_level(env):
    """The level object the engine is currently running, or None."""
    g = getattr(env, "_game", None) or getattr(env, "game", None)
    for attr in ("_level", "level", "current_level"):
        lv = getattr(g, attr, None)
        if lv is not None:
            sp = getattr(lv, "_sprites", None) or getattr(lv, "sprites", None)
            if sp:
                return list(sp)
    for obj in vars(g).values() if g is not None else []:
        sp = getattr(obj, "_sprites", None)
        if sp:
            return list(sp)
    return None


def _overlaps(lv: list) -> dict:
    """Same-layer, both-visible sprite pairs whose non-transparent footprints share a cell."""
    import numpy as np

    boxes = []
    for s in lv:
        px = s.render()
        boxes.append((int(s.layer), bool(s.is_visible), int(s.x), int(s.y), np.asarray(px) >= 0))
    pairs, cells = 0, set()
    for i in range(len(boxes)):
        li, vi, xi, yi, mi = boxes[i]
        if not vi:
            continue
        ci = {(yi + r, xi + c) for r, c in zip(*mi.nonzero())}
        for j in range(i + 1, len(boxes)):
            lj, vj, xj, yj, mj = boxes[j]
            if not vj or lj != li:
                continue
            cj = {(yj + r, xj + c) for r, c in zip(*mj.nonzero())}
            inter = ci & cj
            if inter:
                pairs += 1
                cells |= inter
    return {"pairs": pairs, "cells": len(cells)}


def _rewrite(src_path: Path, dst_path: Path, mode: str) -> dict:
    """Reorder each level's `sprites=[...]` list WITHIN same-layer groups, in the SOURCE text.

    Element source spans are taken from the AST, so every element is moved verbatim; nothing but the
    order of the list can change. The layer of an element is the sprite table's `layer=` kwarg,
    overridden by any `.set_layer(n)` in the element's own expression.
    """
    src = src_path.read_text()
    tree = ast.parse(src)
    lines = src.splitlines(keepends=True)
    offs = [0]
    for ln in lines:
        offs.append(offs[-1] + len(ln))

    def span(node) -> tuple[int, int]:
        return (offs[node.lineno - 1] + node.col_offset,
                offs[node.end_lineno - 1] + node.end_col_offset)

    # name -> declared layer
    layer_of: dict[str, int] = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.Dict):
            continue
        for k, v in zip(node.keys, node.values):
            if (isinstance(k, ast.Constant) and isinstance(k.value, str)
                    and isinstance(v, ast.Call) and getattr(v.func, "id", "") == "Sprite"):
                lay = 0
                for kw in v.keywords:
                    if kw.arg == "layer":
                        try:
                            lay = int(ast.literal_eval(kw.value))
                        except Exception:  # noqa: BLE001
                            lay = 0
                layer_of[k.value] = lay

    edits: list[tuple[int, int, str]] = []
    stats = {"levels": 0, "groups": 0, "moved": 0}
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Assign)
                and any(getattr(t, "id", "") == "levels" for t in node.targets)):
            continue
        for lv in node.value.elts:            # type: ignore[attr-defined]
            for kw in lv.keywords:            # type: ignore[attr-defined]
                if kw.arg != "sprites" or not isinstance(kw.value, ast.List):
                    continue
                elts = kw.value.elts
                if not elts:
                    continue
                stats["levels"] += 1
                texts, layers = [], []
                for e in elts:
                    a, b = span(e)
                    texts.append(src[a:b])
                    txt = src[a:b]
                    name = None
                    for sub in ast.walk(e):
                        if (isinstance(sub, ast.Subscript)
                                and getattr(sub.value, "id", "") == "sprites"
                                and isinstance(sub.slice, ast.Constant)):
                            name = sub.slice.value
                    lay = layer_of.get(name, 0)
                    if ".set_layer(" in txt:
                        try:
                            lay = int(txt.split(".set_layer(")[1].split(")")[0])
                        except Exception:  # noqa: BLE001
                            pass
                    layers.append(lay)
                order = list(range(len(elts)))
                groups: dict[int, list[int]] = {}
                for i, lay in enumerate(layers):
                    groups.setdefault(lay, []).append(i)
                for lay, idxs in groups.items():
                    if len(idxs) < 2:
                        continue
                    stats["groups"] += 1
                    if mode == "reverse":
                        perm = list(reversed(idxs))
                    elif mode == "rot1":
                        perm = idxs[1:] + idxs[:1]
                    else:
                        perm = list(idxs)
                    for slot, srcidx in zip(idxs, perm):
                        order[slot] = srcidx
                        if slot != srcidx:
                            stats["moved"] += 1
                first_a, _ = span(elts[0])
                _, last_b = span(elts[-1])
                indent = " " * elts[0].col_offset
                body = (",\n" + indent).join(texts[i] for i in order)
                edits.append((first_a, last_b, body))

    for a, b, body in sorted(edits, reverse=True):
        src = src[:a] + body + src[b:]
    dst_path.parent.mkdir(parents=True, exist_ok=True)
    dst_path.write_text(src)
    return stats


def main() -> None:
    seed = int(sys.argv[1])
    mode = sys.argv[2] if len(sys.argv) > 2 else "census"
    game = GAMES[(seed - 1) % len(GAMES)]
    budget = 4000

    envdir = ROOT / "environment_files"
    src = _game_file(envdir, game)
    before = _capture(src)

    out: dict = {"game": game, "mode": mode,
                 "n_levels": len(before),
                 "sprites_per_level": [len(lv) for lv in before]}

    ov = [_overlaps(lv) for lv in before]
    out["overlap_pairs_per_level"] = [o["pairs"] for o in ov]
    out["overlap_cells_per_level"] = [o["cells"] for o in ov]
    out["levels_with_overlap"] = sum(1 for o in ov if o["pairs"])
    out["total_overlap_pairs"] = sum(o["pairs"] for o in ov)
    out["can_exhibit"] = out["total_overlap_pairs"] > 0

    if mode == "census":
        print(json.dumps(out))
        return

    if mode == "runtime":
        # ⛔ Sample the LIVE level: two same-layer visible sprites sharing a cell at ANY time during
        # the scored run. A declared-placement census cannot see a rider that only meets its bar
        # because the game moved it, which is exactly s5i5's own defect.
        from arc_agi import Arcade, OperationMode

        spec = importlib.util.spec_from_file_location(
            "score_eff", ROOT / "scripts/score_efficiency.py")
        se = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(se)
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
        seen: dict[int, dict] = {}
        real_factory = se._make_agent

        def factory():
            inner = real_factory("unified", game_id=info.game_id)
            tick = {"n": 0}

            class Watch:
                restart_on_game_over = getattr(inner, "restart_on_game_over", False)

                def is_done(self, frames, obs):
                    return inner.is_done(frames, obs)

                def choose_action(self, frames, obs):
                    tick["n"] += 1
                    if tick["n"] % 5 == 1:
                        lv = _live_level(held.get("env"))
                        if lv is not None:
                            L = int(getattr(obs, "levels_completed", -1))
                            o = _overlaps(lv)
                            e = seen.setdefault(L, {"samples": 0, "with": 0, "max_pairs": 0,
                                                    "max_cells": 0, "n_sprites": 0})
                            e["samples"] += 1
                            e["n_sprites"] = max(e["n_sprites"], len(lv))
                            if o["pairs"]:
                                e["with"] += 1
                                e["max_pairs"] = max(e["max_pairs"], o["pairs"])
                                e["max_cells"] = max(e["max_cells"], o["cells"])
                    return inner.choose_action(frames, obs)

            return Watch()

        res = se.run_game(arcade, info.game_id, info.baseline_actions,
                          agent_name="unified", max_actions=budget, adapter_factory=factory)
        banked = json.load(open(ROOT / f"scripts/rounds/R101SHIPPED/games/{game}.json"))["games"][0]
        per = [p["agent_actions"] for p in res.get("per_level", [])]
        bper = [p["agent_actions"] for p in banked["per_level"]]
        out.update({
            "per_level": per, "banked_per_level": bper,
            "control_ok": per == bper,
            "runtime_by_level": {str(k): v for k, v in sorted(seen.items())},
            "runtime_levels_with_overlap": sum(1 for v in seen.values() if v["with"]),
            "runtime_can_exhibit": any(v["with"] for v in seen.values()),
            "runtime_max_sprites": max((v["n_sprites"] for v in seen.values()), default=0),
        })
        print(json.dumps(out))
        return

    # --- mutate into a PRIVATE environments dir --------------------------------------------
    work = Path(f"/tmp/_zo_{game}_{mode}")
    shutil.rmtree(work, ignore_errors=True)
    shutil.copytree(envdir, work / "environment_files")
    dst = _game_file(work / "environment_files", game)
    for pyc in dst.parent.glob("__pycache__"):
        shutil.rmtree(pyc, ignore_errors=True)
    out["rewrite"] = _rewrite(src, dst, mode)

    after = _capture(dst)
    out["valid_same_placements"] = _canon(before) == _canon(after)
    out["order_changed"] = [
        [(_sig(s), int(s.x), int(s.y)) for s in a] != [(_sig(s), int(s.x), int(s.y)) for s in b]
        for a, b in zip(before, after)]
    out["levels_reordered"] = sum(1 for x in out["order_changed"] if x)

    if not out["valid_same_placements"]:
        out["error"] = "MUTATION INVALID — placements differ, not just order"
        print(json.dumps(out))
        return

    os.environ["ENVIRONMENTS_DIR"] = str(work / "environment_files")
    from arc_agi import Arcade, OperationMode

    spec = importlib.util.spec_from_file_location("score_eff", ROOT / "scripts/score_efficiency.py")
    se = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(se)

    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    info = next(i for i in arcade.get_environments()
                if (i.title or i.game_id).lower().startswith(game))
    res = se.run_game(arcade, info.game_id, info.baseline_actions,
                      agent_name="unified", max_actions=budget)

    banked = json.load(open(ROOT / f"scripts/rounds/R101SHIPPED/games/{game}.json"))["games"][0]
    per = [p["agent_actions"] for p in res.get("per_level", [])]
    bper = [p["agent_actions"] for p in banked["per_level"]]
    out.update({
        "per_level": per, "banked_per_level": bper,
        "game_score": res.get("game_score"), "banked_score": banked["game_score"],
        "total_actions": int(res.get("total_actions", -1)),
        "identical": per == bper and abs((res.get("game_score") or -1)
                                         - banked["game_score"]) < 1e-9,
    })
    shutil.rmtree(work, ignore_errors=True)
    print(json.dumps(out))


if __name__ == "__main__":
    main()
