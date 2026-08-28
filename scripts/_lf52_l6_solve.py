"""Find the one capture that clears lf52's level 6.

The protocol was read off levels 1-5, where the tool wins: ONE ACTION6 click removes exactly 12
green pixels (one pad), consecutive clicks step two cells, and the level advances the moment the pad
count reaches 2. Level 6 arrives with 36 green = 3 pads, so a single capture clears it.

The earlier attempt failed because it used a PAD as the jumper. The mover is the 32-pixel sprite
that arrows displace one cell (colour 12 on this board); the click names the LANDING cell, two away,
with the captured pad at the midpoint.

Expected feedback: green 36 -> 24 and the level advancing names the exact (piece, landing) pair and
makes this a tool lever. Every landing refused means the mover is not colour 12, and the next thing
to identify is which sprite the arrows actually move.
"""
from __future__ import annotations

import numpy as np

GREEN = 14
CELL = 6


def blobs(o, colour: int) -> list[tuple[int, int, int]]:
    g = np.array(o.frame[-1], dtype=np.int16)
    mask = g == colour
    seen = np.zeros_like(mask, dtype=bool)
    out = []
    for r, c in map(tuple, np.argwhere(mask)):
        if seen[r, c]:
            continue
        stack = [(r, c)]
        seen[r, c] = True
        cells = []
        while stack:
            y, x = stack.pop()
            cells.append((y, x))
            for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                ny, nx = y + dy, x + dx
                if 0 <= ny < mask.shape[0] and 0 <= nx < mask.shape[1] \
                        and mask[ny, nx] and not seen[ny, nx]:
                    seen[ny, nx] = True
                    stack.append((ny, nx))
        out.append((sum(p[0] for p in cells) // len(cells),
                    sum(p[1] for p in cells) // len(cells), len(cells)))
    return out


def main() -> None:
    from arc_agi import Arcade, OperationMode

    from admorphiq.harness.loop import UnifiedAgent
    from admorphiq.harness.registry import default_tools
    from admorphiq.types import GameAction

    def _no_llm(*_a, **_k):
        raise RuntimeError("LLM-free")

    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    info = next(i for i in arcade.get_environments()
                if (i.title or i.game_id).lower().startswith("lf52"))
    env = arcade.make(info.game_id)
    obs = env.reset()
    agent = UnifiedAgent(default_tools(), _no_llm, giveup=4000, stall=80, ctx_budget=6000)
    frames = [obs]
    for _ in range(4000):
        if int(getattr(obs, "levels_completed", 0) or 0) >= 5:
            break
        act = agent.choose_action(frames, obs)
        data = act.action_data.model_dump() if getattr(act, "action_data", None) else None
        obs = env.step(act, data=data) if data else env.step(act)
        frames.append(obs)
    if int(getattr(obs, "levels_completed", 0) or 0) < 5:
        print("did not reach level 6")
        return

    def ngreen(o) -> int:
        return int((np.array(o.frame[-1], dtype=np.int16) == GREEN).sum())

    g = np.array(obs.frame[-1], dtype=np.int16)
    present = {int(v): int((g == v).sum()) for v in np.unique(g)}
    print("level 6 colours:", present, flush=True)
    pads = blobs(obs, GREEN)
    print(f"pads ({ngreen(obs) // 12}): {[(p[0], p[1]) for p in pads]}", flush=True)

    # Any non-background colour with a single small blob is a candidate mover.
    movers: list[tuple[int, int, int]] = []
    for v, n in present.items():
        if v in (GREEN,) or n > 60 or n < 4:
            continue
        for b in blobs(obs, v):
            movers.append((b[0], b[1], v))
    print("mover candidates (row, col, colour):", movers, flush=True)

    base = ngreen(obs)
    # ⛔ Do not guess which sprite is the mover — that guess has been wrong twice. The capture is
    # defined by the PAD: whatever jumps, it starts one cell to one side of a pad and lands one cell
    # to the other. Enumerating the pads' own flanks needs no theory of the mover at all, and it is
    # 12 pairs rather than a sweep.
    for py, px, _n in pads:
        for dy, dx in ((0, 1), (0, -1), (1, 0), (-1, 0)):
            sy, sx = py - dy * CELL, px - dx * CELL
            ly, lx = py + dy * CELL, px + dx * CELL
            if not (0 <= sy < 64 and 0 <= sx < 64 and 0 <= ly < 64 and 0 <= lx < 64):
                continue
            env.step(agent._convert(GameAction.coordinate(int(sx), int(sy))),
                     data={"x": int(sx), "y": int(sy)})
            o2 = env.step(agent._convert(GameAction.coordinate(int(lx), int(ly))),
                          data={"x": int(lx), "y": int(ly)})
            now = ngreen(o2)
            lvl = int(getattr(o2, "levels_completed", 0) or 0)
            if now != base:
                print(f"  select ({sy},{sx}) -> land ({ly},{lx}) over pad ({py},{px}): "
                      f"green {base} -> {now}", flush=True)
                base = now
            if lvl != 5:
                print(f"LEVEL CLEARED: select ({sy},{sx}) land ({ly},{lx})")
                return
    print(f"no capture; green still {base}")


if __name__ == "__main__":
    main()
