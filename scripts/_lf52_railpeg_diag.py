"""Why railpeg goes silent on lf52's level 6 — name the branch, do not guess it.

The retire log says `railpeg:1252 x11` = `propose` returning [] after more than eight settle
clicks, i.e. `_sync` kept answering `placed=False`. Three different branches can answer that:
`board is None`, `_align` failing (`_misaligned < 6`), and `unsettled` (a piece off the lattice
phase, a cart believed mid-slide, or an OBSTACLE read on a cell the model calls a socket). They
want completely different repairs, so the branch is measured rather than reasoned about.

The instrument proves itself: it prints how many times the wrapper fired, and a run where that
count is zero is a run that measured nothing (rule 7b).

Expected feedback: a dominant branch names the repair. `unsettled` dominated by obstacles-on-
sockets means level 6's wall art is being read as furniture on the lattice; `align` dominating
means the level-6 board never matches the model carried in; `None` means `read_board` cannot see
this board at all.
"""
from __future__ import annotations

import json
import sys
from collections import Counter

import numpy as np

START_LEVEL = 5


def main() -> None:
    _seed = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    from arc_agi import Arcade, OperationMode

    from admorphiq.harness.loop import UnifiedAgent
    from admorphiq.harness.registry import default_tools
    from admorphiq.tools.railpeg import RailPegTool

    def _no_llm(*_a, **_k):
        raise RuntimeError("LLM-free")

    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    info = next(i for i in arcade.get_environments()
                if (i.title or i.game_id).lower().startswith("lf52"))
    env = arcade.make(info.game_id)
    obs = env.reset()
    tools = default_tools()
    peg = next((t for t in tools if isinstance(t, RailPegTool)), None)
    if peg is None:
        print(json.dumps({"error": "railpeg not registered"}), flush=True)
        return

    calls = Counter()
    fired = [0]
    at_level6 = [False]
    detail: list[dict] = []
    raw = RailPegTool._sync

    def wrapped(self, g):
        res = raw(self, g)
        if not at_level6[0]:
            return res
        fired[0] += 1
        board = self._read
        if board is None:
            calls["board-none"] += 1
            if len(detail) < 40:
                detail.append({"branch": "board-none"})
            return res
        placed = res is not None and res[1]
        m = res[0] if res is not None else None
        if placed:
            calls["placed"] += 1
            return res
        why = "align" if self._misaligned else "unsettled-or-noplan"
        obs_on_sockets = 0
        if m is not None:
            obs_on_sockets = len({(c[0], c[1]) for c in board.obstacles} & {
                (c[0] - 0, c[1] - 0) for c in m.sockets})
        calls[f"unplaced:{why}"] += 1
        if len(detail) < 40:
            detail.append({"branch": why, "moving": board.moving, "pitch": board.pitch,
                           "cells": len(board.window), "pieces": len(board.pieces),
                           "carts": len(board.carts), "obstacles": len(board.obstacles),
                           "obs_x_sock_rawcoords": obs_on_sockets,
                           "settles": self._settles, "misaligned": self._misaligned,
                           "driving": self._driving, "ncarts": self._ncarts,
                           "m_carts": len(m.carts) if m else -1})
        return res

    RailPegTool._sync = wrapped
    try:
        agent = UnifiedAgent(tools, _no_llm, giveup=4000, stall=80, ctx_budget=6000)
        frames = [obs]
        lvl6_action = None
        for i in range(2000):
            lvl = int(getattr(obs, "levels_completed", 0) or 0)
            if lvl >= START_LEVEL and not at_level6[0]:
                at_level6[0] = True
                lvl6_action = i
                print(f"# level 6 at action {i}", file=sys.stderr, flush=True)
            if lvl > START_LEVEL:
                break
            if at_level6[0] and i - (lvl6_action or 0) > 400:
                break
            if i % 200 == 0:
                print(f"# action {i} lvl={lvl}", file=sys.stderr, flush=True)
            act = agent.choose_action(frames, obs)
            data = act.action_data.model_dump() if getattr(act, "action_data", None) else None
            obs = env.step(act, data=data) if data else env.step(act)
            frames.append(obs)
    finally:
        RailPegTool._sync = raw

    g = np.array(obs.frame[-1], dtype=np.int16)
    board = None
    try:
        from admorphiq.tools.railpeg import read_board
        board = read_board(g)
    except Exception as exc:                                    # noqa: BLE001
        print(f"# read_board raised {exc}", file=sys.stderr, flush=True)
    print(json.dumps({
        "fired": fired[0], "branches": dict(calls), "lvl6_action": lvl6_action,
        "final_level": int(getattr(obs, "levels_completed", 0) or 0),
        "final_board": None if board is None else {
            "pitch": board.pitch, "cells": len(board.window), "pieces": len(board.pieces),
            "sockets": len(board.sockets), "rails": len(board.rails),
            "obstacles": len(board.obstacles), "carts": len(board.carts),
            "moving": board.moving},
        "detail": detail[:20],
        "tiers": dict(getattr(peg, "_tiers", {})), "why": dict(getattr(peg, "_why", {})),
        "noncapture": sorted(getattr(peg, "_noncapture", set())),
        "elsewhere": getattr(peg, "_elsewhere", None),
    }), flush=True)


if __name__ == "__main__":
    main()
