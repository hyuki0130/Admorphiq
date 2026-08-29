"""The FLOOR for ls20's level 7: how few steps would the final map have allowed?

The routing claim needs a floor, not a proxy. Play the level as the tool does, keep the LAST frame,
recover the walkable cells from it, and BFS from where the avatar started to where it finished. That
shortest path is what a router with perfect knowledge would have spent; the difference against the
302 actually walked is the recoverable share, and the human's 186 sits somewhere between.

Expected feedback: a floor near 302 means the route is already close to optimal for this map and
ls20 is not an opportunity. A floor far below means routing is worth building.
"""
from __future__ import annotations

from collections import deque

import numpy as np


def main() -> None:
    from arc_agi import Arcade, OperationMode

    from admorphiq.harness.loop import UnifiedAgent
    from admorphiq.harness.registry import default_tools

    def _no_llm(*_a, **_k):
        raise RuntimeError("LLM-free")

    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    info = next(i for i in arcade.get_environments()
                if (i.title or i.game_id).lower().startswith("ls20"))
    env = arcade.make(info.game_id)
    obs = env.reset()
    agent = UnifiedAgent(default_tools(), _no_llm, giveup=4000, stall=80, ctx_budget=6000)
    frames = [obs]
    lvl = 0
    first = last = None
    steps = 0
    for _ in range(4000):
        if agent.is_done(frames, obs):
            break
        act = agent.choose_action(frames, obs)
        data = act.action_data.model_dump() if getattr(act, "action_data", None) else None
        obs = env.step(act, data=data) if data else env.step(act)
        frames.append(obs)
        now = int(getattr(obs, "levels_completed", 0) or 0)
        g = np.array(obs.frame[-1], dtype=np.int16)
        if now != lvl:
            if lvl == 6:
                break
            lvl = now
            first = g.copy()
            steps = 0
            continue
        if lvl == 6:
            steps += 1
            last = g.copy()
    if first is None or last is None:
        print("level 7 not observed")
        return

    # Walkable = whatever the avatar's own colour can stand on. Take the union of every colour that
    # is NOT the wall: the wall is the colour that never changes anywhere across the level.
    diff = first != last
    bg = np.bincount(last.ravel()).argmax()
    walk = (last != bg) | diff
    ys, xs = np.where(diff)
    if not len(ys):
        print("nothing moved")
        return
    start = (int(np.where(first != bg)[0].mean()), int(np.where(first != bg)[1].mean()))
    goal = (int(ys.mean()), int(xs.mean()))

    def bfs(src, dst):
        q, seen = deque([(src, 0)]), {src}
        while q:
            (y, x), d = q.popleft()
            if (y, x) == dst:
                return d
            for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                ny, nx = y + dy, x + dx
                if 0 <= ny < walk.shape[0] and 0 <= nx < walk.shape[1] \
                        and walk[ny, nx] and (ny, nx) not in seen:
                    seen.add((ny, nx))
                    q.append(((ny, nx), d + 1))
        return None

    d = bfs(start, goal)
    print(f"ls20 level 7: walked {steps} steps; walkable cells {int(walk.sum())}; "
          f"pixel-BFS start{start} -> end{goal} = {d}")
    print("  (human baseline 186; a cell is ~4 px on this board, so divide the BFS by the pitch)")


if __name__ == "__main__":
    main()
