"""re86 level 2 (index 1) costs 46 actions against a human 42 — every other level of the game
scores 1.0. This probe answers, in ONE parameterised script, every hypothesis that could explain
the four extra actions, so they can be run TOGETHER (rule 7h) instead of one at a time.

    uv run python scripts/_re86_l2.py <mode> [repeat]

Modes (the varying first argument, so `scripts/pfan.sh` can fan them):

  1  trace      every level-2 action: which tool issued it, the action, whether the BOARD changed,
                and — from engine truth — which piece was selected and whether the move was
                REVERTED (out-of-camera). Classifies each action: move / select / inert / refused.
  2  ground     level-2 ground truth from the engine: piece start positions, the displacement each
                piece needs, and the arithmetic minimum (moves of 3px + ACTION5 selection cycles).
  3  optimal    plan the minimum sequence from mode-2 truth and REPLAY it live; reports the level
                number afterwards so a collapse cannot read as a clear (rule 7f).
  4  attempts   is level 2 ever lost and retried? splits level 2 into attempts.
  5  fallback   how many level-2 actions came from the harness probe fallback rather than a tool.
  6  repeat     run the whole game and print the per-level action counts (determinism).

Every mode prints ONE json line. Progress goes to stderr from the first action (rule 7e).
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

TAG_PIECE = "0031cppcuvqlbi"
TAG_TARGET = "0054xnsuqceejm"
STEP = 3
LEVEL = 1          # zero-based index of the level whose cost we are chasing
CAP = 900


def _log(*a):
    print(*a, file=sys.stderr, flush=True)


def _arcade():
    from arc_agi import Arcade, OperationMode
    return Arcade(operation_mode=OperationMode.OFFLINE)


def _agent(cap: int = CAP):
    from admorphiq.harness.loop import UnifiedAgent
    from admorphiq.harness.registry import default_tools

    def _no_llm(*_a, **_k):
        raise RuntimeError("LLM-free: the signature fallback is what this measures")

    return UnifiedAgent(default_tools(), _no_llm, giveup=cap, stall=80, ctx_budget=6000)


def _pieces(game):
    return game.current_level.get_sprites_by_tag(TAG_PIECE)


def _selected(game):
    """Index of the piece whose centre carries the selection marker, or -1."""
    ps = _pieces(game)
    for i, s in enumerate(ps):
        if int(s.pixels[s.height // 2, s.width // 2]) == 0:
            return i
    return -1


def _positions(game):
    return [(int(s.x), int(s.y)) for s in _pieces(game)]


def _board(obs):
    import numpy as np
    fr = obs.frame
    a = np.asarray(fr[-1] if isinstance(fr, list) else fr)
    return a


def _changed(prev, cur):
    from admorphiq.tools.segment import board_changed
    return board_changed(prev, cur)


def _drive_to_level(env, agent, level: int, log_every: int = 50):
    """Play with the real harness until `levels_completed` reaches `level`."""
    obs = env.reset()
    frames = [obs]
    for n in range(CAP):
        done = int(getattr(obs, "levels_completed", 0) or 0)
        if done >= level:
            return obs, frames, n
        act = agent.choose_action(frames, obs)
        data = act.action_data.model_dump() if getattr(act, "action_data", None) else None
        obs = env.step(act, data=data) if data else env.step(act)
        frames.append(obs)
        if n % log_every == 0:
            _log(f"  drive step={n} level={done}")
    raise RuntimeError(f"never reached level {level}")


# ---------------------------------------------------------------- mode 1: trace
def mode_trace() -> dict:
    env = _arcade().make("re86")
    agent = _agent()
    obs, frames, pre = _drive_to_level(env, agent, LEVEL)
    game = env._game
    _log(f"  at level {LEVEL} after {pre} actions")
    start = int(getattr(obs, "levels_completed", 0) or 0)
    rows = []
    prev_board = _board(obs)
    prev_pos = _positions(game)
    prev_sel = _selected(game)
    for n in range(CAP):
        act = agent.choose_action(frames, obs)
        tool = str(agent._current)
        name = str(getattr(act, "name", act))
        data = act.action_data.model_dump() if getattr(act, "action_data", None) else None
        obs = env.step(act, data=data) if data else env.step(act)
        frames.append(obs)
        cur_board = _board(obs)
        pos = _positions(game)
        sel = _selected(game)
        moved = pos != prev_pos
        ch = _changed(prev_board, cur_board)
        kind = ("move" if moved else
                "select" if sel != prev_sel else
                "changed-nomove" if ch else "INERT")
        rows.append({"i": n, "tool": tool, "act": name, "kind": kind,
                     "sel": sel, "pos": pos, "changed": bool(ch)})
        _log(f"  L2 {n:3d} {tool:<14} {name:<8} {kind:<14} sel={sel} pos={pos}")
        prev_board, prev_pos, prev_sel = cur_board, pos, sel
        lvl = int(getattr(obs, "levels_completed", 0) or 0)
        if lvl > start:
            break
        if str(getattr(obs, "state", "")).endswith("GAME_OVER"):
            rows[-1]["kind"] = "GAME_OVER"
            break
    counts: dict[str, int] = {}
    tools: dict[str, int] = {}
    for r in rows:
        counts[r["kind"]] = counts.get(r["kind"], 0) + 1
        tools[r["tool"]] = tools.get(r["tool"], 0) + 1
    return {"mode": "trace", "level2_actions": len(rows), "pre": pre,
            "kinds": counts, "tools": tools, "rows": rows}


# ------------------------------------------------------------ mode 2: ground truth
def _target_offsets(game):
    """For each target sprite, the colour it demands and where its pixels sit on the canvas."""
    import numpy as np
    out = []
    for t in game.current_level.get_sprites_by_tag(TAG_TARGET):
        px = np.asarray(t.pixels)
        cells = [(int(t.y + i), int(t.x + j)) for i, j in np.argwhere(px != -1).tolist()]
        cols = sorted({int(v) for v in px[px != -1].tolist()})
        out.append({"x": int(t.x), "y": int(t.y), "colours": cols, "n_cells": len(cells)})
    return out


def _piece_info(game):
    import numpy as np
    out = []
    for s in _pieces(game):
        px = np.asarray(s.pixels)
        body = px[(px != -1) & (px != 0)]
        col = int(body[0]) if body.size else -1
        out.append({"x": int(s.x), "y": int(s.y), "w": int(s.width), "h": int(s.height),
                    "colour": col, "n_cells": int((px != -1).sum()),
                    "tags": list(getattr(s, "tags", []))})
    return out


def mode_ground() -> dict:
    env = _arcade().make("re86")
    agent = _agent()
    obs, frames, pre = _drive_to_level(env, agent, LEVEL)
    game = env._game
    return {"mode": "ground", "pre": pre,
            "selected": _selected(game),
            "pieces": _piece_info(game),
            "targets": _target_offsets(game),
            "step_counter": game.current_level.get_data("StepCounter")}


# ---------------------------------------------------------------- mode 3: optimal
def _feasible_offsets(game):
    """Every 3-pixel-aligned position at which a piece does not CONTRADICT the target.

    The filter is a necessary condition only (a piece pixel must equal the target's demand where
    the target demands anything but 4 or -1); the joint answer is then handed to the engine's OWN
    win predicate, so nothing here re-implements the rule (rule 7g).
    """
    import numpy as np
    tgt = game.current_level.get_sprites_by_tag(TAG_TARGET)[0]
    tp = np.asarray(tgt.pixels)
    th, tw = tp.shape
    cam_w, cam_h = int(game.camera.width), int(game.camera.height)
    out = []
    for s in _pieces(game):
        px = np.asarray(s.pixels)
        body = [(int(i), int(j), int(px[i, j])) for i, j in np.argwhere(px != -1).tolist()]
        w, h = int(s.width), int(s.height)
        ok = []
        for y in range(-h, cam_h + h):
            if (y - int(s.y)) % STEP:
                continue
            for x in range(-w, cam_w + w):
                if (x - int(s.x)) % STEP:
                    continue
                if not (0 <= x + w // 2 < cam_w and 0 <= y + h // 2 < cam_h):
                    continue
                good = True
                for i, j, v in body:
                    ty, tx = y + i - int(tgt.y), x + j - int(tgt.x)
                    if 0 <= ty < th and 0 <= tx < tw:
                        d = int(tp[ty, tx])
                        if d != -1 and d != 4 and d != v:
                            good = False
                            break
                if good:
                    ok.append((x, y))
        out.append(ok)
    return out


def _select_cost(n, s0, order, final):
    """ACTION5 presses to visit `order` cyclically from `s0` and end on `final`."""
    cost, cur = 0, s0
    for p in list(order) + [final]:
        cost += (p - cur) % n
        cur = p
    return cost


def _plan(game):
    """Cheapest (moves + selection presses) plan whose end state the ENGINE calls a win."""
    from itertools import permutations, product
    n = len(_pieces(game))
    s0 = _selected(game)
    start = _positions(game)
    feas = _feasible_offsets(game)
    scratch = copy.deepcopy(game)
    sp = _pieces(scratch)

    def wins(pos, sel):
        for s, (x, y) in zip(sp, pos):
            s.set_position(int(x), int(y))
        scratch.gxncswszaq()                      # the engine's own centre restore
        t = sp[sel]
        t.pixels[t.height // 2, t.width // 2] = 0
        return bool(scratch.jeiavrvavi())

    best = None
    for combo in product(*feas):
        moved = [i for i in range(n) if combo[i] != tuple(start[i])]
        dist = sum(abs(combo[i][0] - start[i][0]) + abs(combo[i][1] - start[i][1])
                   for i in range(n)) // STEP
        for final in range(n):
            if not wins(list(combo), final):
                continue
            for order in permutations(moved):
                c = dist + _select_cost(n, s0, order, final)
                if best is None or c < best[0]:
                    best = (c, combo, order, final)
    if best is None:
        return None
    _cost, combo, order, final = best
    seq, cur = [], s0
    for p in list(order) + [final]:
        seq += [5] * ((p - cur) % n)
        cur = p
        if p < n and combo[p] != tuple(start[p]):
            dx = combo[p][0] - start[p][0]
            dy = combo[p][1] - start[p][1]
            seq += [4 if dx > 0 else 3] * (abs(dx) // STEP)
            seq += [2 if dy > 0 else 1] * (abs(dy) // STEP)
    return seq


def mode_optimal() -> dict:
    from arcengine import GameAction
    A = {1: GameAction.ACTION1, 2: GameAction.ACTION2, 3: GameAction.ACTION3,
         4: GameAction.ACTION4, 5: GameAction.ACTION5}
    env = _arcade().make("re86")
    agent = _agent()
    obs, frames, pre = _drive_to_level(env, agent, LEVEL)
    game = env._game
    _log("  searching...")
    seq = _plan(game)
    if seq is None:
        return {"mode": "optimal", "found": False, "pre": pre}
    _log(f"  plan is {len(seq)} actions: {seq}")
    start = int(getattr(obs, "levels_completed", 0) or 0)
    for k, a in enumerate(seq):
        obs = env.step(A[a])
        lvl = int(getattr(obs, "levels_completed", 0) or 0)
        _log(f"  replay {k+1}/{len(seq)} act={a} level={lvl}")
        if lvl > start:
            return {"mode": "optimal", "found": True, "n": len(seq), "seq": seq,
                    "cleared_at": k + 1, "level_after": lvl, "verified": True, "pre": pre}
    return {"mode": "optimal", "found": True, "n": len(seq), "seq": seq,
            "verified": False, "level_after": int(getattr(obs, "levels_completed", 0) or 0),
            "pre": pre}


# --------------------------------------------------------------- mode 4: attempts
def mode_attempts() -> dict:
    env = _arcade().make("re86")
    agent = _agent()
    obs, frames, pre = _drive_to_level(env, agent, LEVEL)
    start = int(getattr(obs, "levels_completed", 0) or 0)
    attempts = [[0, "running"]]
    for n in range(CAP):
        act = agent.choose_action(frames, obs)
        data = act.action_data.model_dump() if getattr(act, "action_data", None) else None
        obs = env.step(act, data=data) if data else env.step(act)
        frames.append(obs)
        attempts[-1][0] += 1
        lvl = int(getattr(obs, "levels_completed", 0) or 0)
        if lvl > start:
            attempts[-1][1] = "CLEARED"
            break
        if str(getattr(obs, "state", "")).endswith("GAME_OVER"):
            attempts[-1][1] = "binned"
            attempts.append([0, "running"])
        if n % 20 == 0:
            _log(f"  L2 {n} attempts={attempts}")
    return {"mode": "attempts", "pre": pre, "attempts": attempts,
            "total": sum(a[0] for a in attempts)}


# --------------------------------------------------------------- mode 5: fallback
def mode_fallback() -> dict:
    env = _arcade().make("re86")
    agent = _agent()
    tagged = {"n": 0}
    real_probe = agent._probe

    def _probe(simple_ids, action6):
        tagged["n"] += 1
        return real_probe(simple_ids, action6)

    agent._probe = _probe            # type: ignore[method-assign]
    obs, frames, pre = _drive_to_level(env, agent, LEVEL)
    before = tagged["n"]
    start = int(getattr(obs, "levels_completed", 0) or 0)
    n = 0
    for n in range(CAP):
        act = agent.choose_action(frames, obs)
        data = act.action_data.model_dump() if getattr(act, "action_data", None) else None
        obs = env.step(act, data=data) if data else env.step(act)
        frames.append(obs)
        if int(getattr(obs, "levels_completed", 0) or 0) > start:
            break
        if n % 20 == 0:
            _log(f"  L2 {n} fallback_fills={tagged['n'] - before}")
    return {"mode": "fallback", "level2_actions": n + 1,
            "fallback_fills_before_l2": before,
            "fallback_fills_in_l2": tagged["n"] - before}


# ----------------------------------------------------------------- mode 6: repeat
def mode_repeat() -> dict:
    env = _arcade().make("re86")
    agent = _agent(4000)
    obs = env.reset()
    frames = [obs]
    done = 0
    per = []
    cur = 0
    for n in range(4000):
        if agent.is_done(frames, obs):
            break
        act = agent.choose_action(frames, obs)
        data = act.action_data.model_dump() if getattr(act, "action_data", None) else None
        obs = env.step(act, data=data) if data else env.step(act)
        frames.append(obs)
        cur += 1
        lvl = int(getattr(obs, "levels_completed", 0) or 0)
        if lvl > done:
            per.append(cur)
            cur = 0
            done = lvl
            _log(f"  cleared level {done} in {per[-1]}")
    return {"mode": "repeat", "per_level": per, "cleared": done}



# ------------------------------------------------------------- mode 7: which branch
def mode_branch() -> dict:
    """Same trace, but tagging WHICH method of the tool emitted each action.

    ⛔ Written after a change to the discovery heading moved two other levels and left level 2
    byte-identical: without the tag, "the nudge is direction-blind" is a reading of the source,
    not of the run (rule 7g).
    """
    env = _arcade().make("re86")
    agent = _agent()
    obs, frames, pre = _drive_to_level(env, agent, LEVEL)
    tool = agent.tools["cover_targets"]
    tag = {"who": None}

    def wrap(name):
        real = getattr(tool, name)

        def inner(*a, **k):
            out = real(*a, **k)
            if out not in (None, []):
                tag["who"] = name
            return out
        return inner

    for nm in ("_toward", "_blind", "_inward", "_cycle", "_park", "_walk", "_discover"):
        setattr(tool, nm, wrap(nm))

    start = int(getattr(obs, "levels_completed", 0) or 0)
    rows = []
    game = env._game
    prev_pos = _positions(game)
    for n in range(CAP):
        tag["who"] = None
        act = agent.choose_action(frames, obs)
        name = str(getattr(act, "name", act))
        data = act.action_data.model_dump() if getattr(act, "action_data", None) else None
        obs = env.step(act, data=data) if data else env.step(act)
        frames.append(obs)
        pos = _positions(game)
        rows.append({"i": n, "act": name, "who": tag["who"], "pos": pos,
                     "moved": pos != prev_pos})
        _log(f"  L2 {n:3d} {name:<8} who={tag['who']} pos={pos}")
        prev_pos = pos
        if int(getattr(obs, "levels_completed", 0) or 0) > start:
            break
    who: dict[str, int] = {}
    for r in rows:
        who[str(r["who"])] = who.get(str(r["who"]), 0) + 1
    return {"mode": "branch", "level2_actions": len(rows), "who": who, "rows": rows}


MODES = {1: mode_trace, 2: mode_ground, 3: mode_optimal,
         4: mode_attempts, 5: mode_fallback, 6: mode_repeat, 7: mode_branch}


def main() -> None:
    mode = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    fn = MODES.get(((mode - 1) % len(MODES)) + 1)
    _log(f"[re86-l2] mode={mode} -> {fn.__name__}")
    try:
        out = fn()
    except Exception as exc:                       # noqa: BLE001
        out = {"mode": mode, "error": f"{type(exc).__name__}: {exc}"}
    out["arg"] = mode
    print(json.dumps(out))


if __name__ == "__main__":
    main()
