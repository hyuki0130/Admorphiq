"""The avatar's real trajectory on ls20's level 7, and the floor that follows from it.

The first floor attempt used the centroid of every non-background pixel as "start" and got a
meaningless 12. The avatar is not a centroid: it is the small blob that moves between consecutive
frames. Tracking THAT gives a real trajectory, and the shortest path over the walkable cells between
its first and last position is the floor a perfect router would have spent.

Expected feedback: a floor close to the 302 walked means the route is near-optimal for this map and
ls20 is not an opportunity. A floor far below it sizes the routing prize honestly for the first time.
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
    prev = None
    path: list[tuple[int, int]] = []
    seen_union = None
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
            lvl, prev, path = now, None, []
            seen_union = None
            continue
        if lvl != 6:
            continue
        if seen_union is None:
            seen_union = np.zeros_like(g, dtype=bool)
        if prev is not None:
            d = np.argwhere(g != prev)
            seen_union |= (g != prev)
            # The avatar is the SMALL moving thing. A frame where half the board changed is a
            # reveal, not a step, and its centroid is not a position — skip it rather than average
            # it in, which is exactly the error that produced a floor of 12.
            if 0 < len(d) <= 40:
                path.append((int(d[:, 0].mean()), int(d[:, 1].mean())))
        prev = g

    if len(path) < 2:
        print(f"no usable trajectory ({len(path)} points)")
        return
    walk = seen_union.copy()
    for y, x in path:                       # everywhere the avatar actually stood is walkable
        walk[max(0, y - 1):y + 2, max(0, x - 1):x + 2] = True

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

    span = max(abs(path[i][0] - path[i - 1][0]) + abs(path[i][1] - path[i - 1][1])
               for i in range(1, len(path)))
    d = bfs(path[0], path[-1])
    print(f"ls20 level 7: {len(path)} tracked steps of 302; avatar {path[0]} -> {path[-1]}")
    print(f"  largest single-step displacement {span} px (the cell pitch)")
    print(f"  shortest walkable path between them: {d} px"
          f" = {'?' if d is None else round(d / max(1, span))} cells")
    print("  human baseline 186 actions")


if __name__ == "__main__":
    main()
