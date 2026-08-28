"""Does ONE peg-solitaire jump clear lf52's level 6?

The source says a click on a landing marker captures a same-named `fozwvlovdui` at the MIDPOINT,
that every pad variant is GREEN (=14) with 12 pixels at full size, and that the level is won when
the pad count falls to 2. Level 6 starts with 36 green pixels = three pads, so exactly one capture
should clear it.

Expected feedback: a green-pixel count dropping 36 -> 24 (with the level advancing) confirms the
model and makes the tool question "why does railpeg's 216 clicks never capture". No drop under any
select-then-land pair means the interaction is not two clicks and the source read is incomplete.
"""
from __future__ import annotations

import numpy as np

GREEN = 14
CELL = 6


def green_blobs(o) -> list[tuple[int, int, int]]:
    """Connected green components as (row, col, pixels), 4-connectivity."""
    g = np.array(o.frame[-1], dtype=np.int16)
    mask = g == GREEN
    seen = np.zeros_like(mask, dtype=bool)
    out: list[tuple[int, int, int]] = []
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
        ys = [p[0] for p in cells]
        xs = [p[1] for p in cells]
        out.append((sum(ys) // len(ys), sum(xs) // len(xs), len(cells)))
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

    def click(y: int, x: int):
        return env.step(agent._convert(GameAction.coordinate(int(x), int(y))),
                        data={"x": int(x), "y": int(y)})

    def ngreen(o) -> int:
        return int((np.array(o.frame[-1], dtype=np.int16) == GREEN).sum())

    # ⛔ The three pads sit at cells (4,3), (8,2), (9,4) — no two are two cells apart with a third
    # between them, so pads cannot jump pads here. The landing MARKERS are their own entity, drawn
    # in `lgbyiaitpdiDING_COLOR = DARK_GRAY = 3`; that is the colour whose count I first misread as
    # a budget gauge. Click the markers themselves.
    def blobs_of(o, colour: int) -> list[tuple[int, int, int]]:
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

    # ⛔ ARRIVED vs FRESH. The tool spends ~180 actions inside level 6 before stalling and the game
    # has no restoring undo, so the position it hands over may already be lost. ACTION5 rebuilds the
    # level; comparing the two boards is the only way to tell "the tool cannot solve this" from
    # "the tool destroyed it on the way in".
    # Assumption-free: click every cell centre once and watch the pad pixels. The cell is 6 px
    # (line 5566 builds pixels as grid*6 + origin), so a 10x10 sweep covers the board for 100
    # actions — inside the game's own 640-action level budget. If a single click can capture, this
    # finds it; if none can, the interaction needs two clicks and the responders name the pairs.
    base = ngreen(obs)
    print(f"ARRIVED: {base} green at {[(b[0], b[1]) for b in green_blobs(obs)]}", flush=True)
    hits = []
    for cy in range(10):
        for cx in range(10):
            y, x = cy * 6 + 3, cx * 6 + 3
            o2 = click(y, x)
            now = ngreen(o2)
            lvl = int(getattr(o2, "levels_completed", 0) or 0)
            if now != base:
                print(f"  click cell ({cy},{cx}) px ({y},{x}): green {base} -> {now}", flush=True)
                hits.append((cy, cx, base, now))
                base = now
            if lvl != 5:
                print(f"LEVEL CLEARED by cell ({cy},{cx})")
                return
    print(f"sweep done: {len(hits)} clicks changed the pad pixels; green now {base}")


if __name__ == "__main__":
    main()
