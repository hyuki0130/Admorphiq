"""Exhaust lf52 level 6's reachable state space, using the game's OWN legal-move oracle.

Reading the source settled what a click does. Selecting a pad calls `xpcuvjyrgu`, which tests all
four directions with `qikmikecdf` (midpoint holds a pad or a `dgxfozncuiz`; landing is bare floor
or a cart) and, for each that passes, attaches a `lgbyiaitpdi` marker two cells out. The sprites
name their own colours:

    csrvckunbev   20 px DARK_GRAY(3) ring ON the pad   -> this pad has AT LEAST ONE legal move
    lgbyiaitpdi    8 px GRAY(2) pip 12 px away         -> that exact landing is legal

GRAY is absent from level 6's palette until a pad is selected, so both are unambiguous. One click
therefore enumerates a pad's entire move set, which is what makes exhausting the level affordable
inside its 640-action budget.

The question this answers is not "which move wins" but "is there a winning move at all". The
visible quarter of the board holds one adjacent pair (a GREEN and a RED, which cannot capture each
other because `cfilhtifcb` removes the midpoint only when its name equals the jumper's) and two
pads with no neighbour. If that is the whole reachable component, level 6 is unwinnable from its
start state and lf52's remaining 0.7273 is not tool work.

Search: DFS over frame-identity states; backtracking replays the move prefix after an ACTION5 +
bottom-left-corner restart, which was measured to restore the board (green 36 -> 0 -> 36).

Expected feedback: `cleared` true names the winning line. `cleared` false with `frontier_open` 0
is a PROOF BY EXHAUSTION that no line exists, and the closed state count is its size. A run that
ends on `budget` proves nothing and says so.
"""
from __future__ import annotations

import json
import random
import sys

import numpy as np

GREEN, RED, GRAY, DARK = 14, 8, 2, 3
CELL = 6
START_LEVEL = 5
DIRS = ((0, -1), (0, 1), (-1, 0), (1, 0))       # (dy, dx) in cells


def blobs(g: np.ndarray, colour: int) -> list[tuple[float, float, int]]:
    mask = g == colour
    seen = np.zeros_like(mask, dtype=bool)
    out = []
    for r, c in map(tuple, np.argwhere(mask)):
        if seen[r, c]:
            continue
        stack, cells = [(r, c)], []
        seen[r, c] = True
        while stack:
            y, x = stack.pop()
            cells.append((y, x))
            for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                ny, nx = y + dy, x + dx
                if 0 <= ny < mask.shape[0] and 0 <= nx < mask.shape[1] \
                        and mask[ny, nx] and not seen[ny, nx]:
                    seen[ny, nx] = True
                    stack.append((ny, nx))
        out.append((round(sum(p[0] for p in cells) / len(cells), 1),
                    round(sum(p[1] for p in cells) / len(cells), 1), len(cells)))
    return sorted(out)


class Game:
    def __init__(self, env, agent, obs):
        from admorphiq.types import ActionType as AT
        from admorphiq.types import GameAction
        self.env, self.agent = env, agent
        self.AT, self.GA = AT, GameAction
        self.obs = obs
        self.last = np.array(obs.frame[-1], dtype=np.int16)
        self.actions = 0

    def _absorb(self, obs):
        self.obs = obs
        if getattr(obs, "frame", None):
            self.last = np.array(obs.frame[-1], dtype=np.int16)
        return self.last

    def g(self) -> np.ndarray:
        return self.last

    def lvl(self) -> int:
        return int(getattr(self.obs, "levels_completed", 0) or 0)

    def click(self, x: int, y: int) -> np.ndarray:
        self.actions += 1
        return self._absorb(self.env.step(self.agent._convert(self.GA.coordinate(int(x), int(y))),
                                          data={"x": int(x), "y": int(y)}))

    def simple(self, k: int) -> np.ndarray:
        self.actions += 1
        return self._absorb(self.env.step(self.agent._convert(self.GA.simple(self.AT(k)))))

    def key(self) -> bytes:
        return self.last.tobytes()

    def pads(self) -> list[tuple[float, float, int]]:
        g = self.g()
        return ([(b[0], b[1], GREEN) for b in blobs(g, GREEN) if b[2] >= 8]
                + [(b[0], b[1], RED) for b in blobs(g, RED) if b[2] >= 8])

    def legal(self, pad) -> list[tuple[int, int]]:
        """Click the pad and read the markers it lit. Returns landing pixels (x, y)."""
        self.click(round(pad[1]), round(pad[0]))
        g = self.g()
        ring = [b for b in blobs(g, DARK) if b[2] >= 12
                and abs(b[0] - pad[0]) < 4 and abs(b[1] - pad[1]) < 4]
        pips = [b for b in blobs(g, GRAY) if 4 <= b[2] <= 14]
        out = []
        for dy, dx in DIRS:
            ly, lx = pad[0] + dy * 2 * CELL, pad[1] + dx * 2 * CELL
            if any(abs(p[0] - ly) < 4 and abs(p[1] - lx) < 4 for p in pips):
                out.append((round(lx), round(ly)))
        return out if out else ([] if not ring else [])

    def restart(self) -> None:
        self.simple(5)
        self.click(4, 56)


def reach(seed: int):
    from arc_agi import Arcade, OperationMode

    from admorphiq.harness.loop import UnifiedAgent
    from admorphiq.harness.registry import default_tools

    def _no_llm(*_a, **_k):
        raise RuntimeError("LLM-free")

    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    info = next(i for i in arcade.get_environments()
                if (i.title or i.game_id).lower().startswith("lf52"))
    env = arcade.make(info.game_id)
    obs = env.reset()
    agent = UnifiedAgent(default_tools(), _no_llm, giveup=4000, stall=80, ctx_budget=6000)
    frames = [obs]
    for i in range(2500):
        if int(getattr(obs, "levels_completed", 0) or 0) >= START_LEVEL:
            break
        if i % 300 == 0:
            print(f"# seed {seed} action {i}", file=sys.stderr, flush=True)
        act = agent.choose_action(frames, obs)
        data = act.action_data.model_dump() if getattr(act, "action_data", None) else None
        obs = env.step(act, data=data) if data else env.step(act)
        frames.append(obs)
    if int(getattr(obs, "levels_completed", 0) or 0) < START_LEVEL:
        return None
    gm = Game(env, agent, obs)
    for _ in range(6):
        gm.click(62, 2)                    # settle the level-up animation
    return gm


def main() -> None:
    seed = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    cap = int(sys.argv[2]) if len(sys.argv) > 2 else 900
    rng = random.Random(seed)
    gm = reach(seed)
    if gm is None:
        print(json.dumps({"seed": seed, "error": "did not reach level 6"}), flush=True)
        return
    start_lvl = gm.lvl()
    root = gm.key()
    base_green = int((gm.g() == GREEN).sum())
    print(f"# seed {seed} at level {start_lvl} green={base_green}", file=sys.stderr, flush=True)

    # move = ("jump", pad_index, landing) or ("act", k)
    closed: dict[bytes, list] = {}
    paths: dict[bytes, list] = {root: []}
    stack = [root]
    oracle_hits = 0
    oracle_pads = 0
    min_green = base_green
    cleared = False
    reached_lvl = start_lvl
    budget_out = False
    lost = 0

    def replay(path) -> bool:
        gm.restart()
        if gm.key() != root:
            for _ in range(4):
                gm.click(62, 2)
        for mv in path:
            if mv[0] == "act":
                gm.simple(mv[1])
            else:
                gm.click(mv[1][0], mv[1][1])
                gm.click(mv[2][0], mv[2][1])
        return gm.key() in paths

    while stack and gm.actions < cap:
        node = stack[-1]
        if node not in closed:
            # stand on `node` before enumerating it
            if gm.key() != node:
                if not replay(paths[node]):
                    lost += 1
                    stack.pop()
                    continue
            moves = []
            for pad in gm.pads():
                oracle_pads += 1
                lands = gm.legal(pad)
                if lands:
                    oracle_hits += 1
                for land in lands:
                    moves.append(("jump", (round(pad[1]), round(pad[0])), land))
                gm.click(62, 2)                       # deselect
                if gm.key() != node:                  # a stray click changed the board
                    break
            for k in (1, 2, 3, 4):
                moves.append(("act", k))
            rng.shuffle(moves)
            closed[node] = moves
        if not closed[node]:
            stack.pop()
            continue
        mv = closed[node].pop()
        if gm.key() != node and not replay(paths[node]):
            lost += 1
            continue
        if mv[0] == "act":
            gm.simple(mv[1])
        else:
            gm.click(mv[1][0], mv[1][1])
            gm.click(mv[2][0], mv[2][1])
        lvl = gm.lvl()
        if lvl > start_lvl:                            # rule 7f: DIRECTION, and print it
            cleared = True
            reached_lvl = lvl
            print(f"# seed {seed} LEVEL UP {start_lvl} -> {lvl} via {mv}", file=sys.stderr, flush=True)
            break
        gr = int((gm.g() == GREEN).sum())
        min_green = min(min_green, gr)
        nxt = gm.key()
        if nxt not in paths:
            paths[nxt] = paths[node] + [mv]
            stack.append(nxt)
        if gm.actions % 100 < 3:
            print(f"# seed {seed} act={gm.actions} states={len(paths)} green={gr}",
                  file=sys.stderr, flush=True)
    else:
        budget_out = gm.actions >= cap

    print(json.dumps({
        "seed": seed, "cleared": cleared, "start_level": start_lvl, "level": reached_lvl,
        "states": len(paths), "closed": len(closed),
        "frontier_open": sum(1 for n in stack if closed.get(n)),
        "base_green": base_green, "min_green": min_green,
        "actions": gm.actions, "budget_out": budget_out, "replay_failures": lost,
        "oracle_pads": oracle_pads, "oracle_with_moves": oracle_hits,
    }), flush=True)


if __name__ == "__main__":
    main()
