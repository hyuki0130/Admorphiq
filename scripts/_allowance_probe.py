"""Is a game's remaining ACTION ALLOWANCE readable off the frame, and what does the run waste?

bp35 loses its level at exactly 64 actions and draws that count as a bar along frame row 63 — the
outer band `tools/segment.board_changed` deliberately ignores, so nothing in the codebase reads it.
Eleven of the twenty-five games declare a per-level allowance in their level data, and on ten of
them the game's OWN human baseline EXCEEDS that allowance (ls20 declares 42 on every level against
human counts up to 192; wa30 declares 70 on its last against 415). A baseline larger than the
allowance can only be a baseline that contains RETRIES.

That reframes what the metric is paying for. If a level is lost and silently restarted, the score
keeps every action already spent, so the lever on those games is "do not gamble the last twenty
actions", which needs the agent to know how many it has left.

⛔ This measures the READER, and nothing else. No tool is patched. Three questions, per game:
  (a) does any outer band carry a monotone function of actions-since-the-attempt-started?
  (b) does that reading RESET when the level restarts — i.e. does it mark attempt boundaries?
  (c) how many of the run's actions are spent in attempts that were then thrown away?

Expected feedback: a band whose value equals the action count exactly gives a free, frame-only
allowance reader and free attempt boundaries. A band that merely correlates is not good enough — a
tool told it has more budget than it does will plan past the end of the level. No band at all on a
game that declares an allowance means the allowance is real but invisible, and the tool can only
learn it by dying once.

Usage: _allowance_probe.py <index 1..25> [cap]   — one JSON line per game.
"""
from __future__ import annotations

import json
import sys

import numpy as np

BANDS = ("row0", "row63", "col0", "col63")


def _band(g: np.ndarray, name: str) -> np.ndarray:
    if name == "row0":
        return g[0, :]
    if name == "row63":
        return g[63, :]
    if name == "col0":
        return g[:, 0]
    return g[:, 63]


def main() -> None:
    idx = int(sys.argv[1])
    cap = int(sys.argv[2]) if len(sys.argv) > 2 else 1200

    from arc_agi import Arcade, OperationMode

    from admorphiq.harness.loop import UnifiedAgent
    from admorphiq.harness.registry import default_tools

    def _no_llm(*_a, **_k):
        raise RuntimeError("LLM-free")

    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    infos = sorted(arcade.get_environments(), key=lambda i: (i.title or i.game_id).lower())
    if idx < 1 or idx > len(infos):
        print(json.dumps({"index": idx, "error": f"only {len(infos)} environments"}))
        return
    info = infos[idx - 1]
    title = (info.title or info.game_id).lower()[:4]
    print(f"# {title}: starting", file=sys.stderr, flush=True)

    env = arcade.make(info.game_id)
    obs = env.reset()
    agent = UnifiedAgent(default_tools(), _no_llm, giveup=cap, stall=80, ctx_budget=6000)
    frames = [obs]

    last_grid = {"g": None}

    def grid(o):
        # ⛔ the engine returns `frame=[]` while the game sits in GAME_OVER or WIN — which is
        # EXACTLY the moment this probe is trying to observe, since that is where an attempt ends.
        # Indexing it crashed the run on the games that die most, i.e. the ones being measured.
        f = getattr(o, "frame", None)
        if not f:
            return last_grid["g"]
        last_grid["g"] = np.array(f[-1], dtype=np.int16)
        return last_grid["g"]

    ref = {b: _band(grid(obs), b).copy() for b in BANDS}
    since = dict.fromkeys(BANDS, 0)
    exact = dict.fromkeys(BANDS, 0)
    stepped = dict.fromkeys(BANDS, 0)
    prev_n = dict.fromkeys(BANDS, 0)
    resets: dict[str, list[int]] = {b: [] for b in BANDS}
    maxn = dict.fromkeys(BANDS, 0)
    lvl = int(getattr(obs, "levels_completed", 0) or 0)
    start_lvl = lvl
    lvl_marks: list[tuple[int, int]] = []
    steps = 0

    while steps < cap:
        act = agent.choose_action(frames, obs)
        data = act.action_data.model_dump() if getattr(act, "action_data", None) else None
        obs = env.step(act, data=data) if data else env.step(act)
        frames.append(obs)
        if len(frames) > 8:
            frames.pop(0)
        steps += 1
        g = grid(obs)
        if g is None:
            continue
        now = int(getattr(obs, "levels_completed", 0) or 0)
        # ⛔ a level number that MOVED says nothing about which way (rule 7f): record the number.
        if now != lvl:
            lvl_marks.append((steps, now))
            lvl = now
            for b in BANDS:
                ref[b] = _band(g, b).copy()
                since[b] = 0
                prev_n[b] = 0
            continue
        for b in BANDS:
            n = int(np.count_nonzero(_band(g, b) != ref[b]))
            since[b] += 1
            if n < prev_n[b] - 1:
                # the strip fell back: an attempt ended and a fresh allowance was handed out
                resets[b].append(since[b] - 1)
                ref[b] = _band(g, b).copy()
                since[b] = 0
                n = 0
            if n == since[b]:
                exact[b] += 1
            if n == prev_n[b] + 1:
                stepped[b] += 1
            maxn[b] = max(maxn[b], n)
            prev_n[b] = n
        if steps % 200 == 0:
            print(f"# {title}: {steps} actions, level {lvl}", file=sys.stderr, flush=True)

    best = max(BANDS, key=lambda b: exact[b])
    out = {
        "index": idx, "title": title, "actions": steps,
        "start_level": start_lvl, "end_level": lvl, "advanced": lvl > start_lvl,
        "level_marks": lvl_marks[:12],
        "bands": {b: {"exact": round(exact[b] / max(1, steps), 3),
                      "stepped": round(stepped[b] / max(1, steps), 3),
                      "resets": len(resets[b]),
                      "reset_lengths": resets[b][:10],
                      "max": maxn[b]} for b in BANDS},
        "best_band": best,
        "best_exact": round(exact[best] / max(1, steps), 3),
    }
    print(json.dumps(out), flush=True)


if __name__ == "__main__":
    main()
