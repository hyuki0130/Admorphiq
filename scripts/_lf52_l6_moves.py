"""lf52 level 6 — where the selection markers really are, and which jumps the ENGINE accepts.

⛔ The first version of this measurement read nothing, and the reason is worth keeping. State
identity was the raw frame, but a SELECT CLICK CHANGES THE FRAME (it draws a ring on the pad), so
"am I still standing on the node I am enumerating?" was false the moment enumeration began, and the
search closed the root with one pad read and four arrows tried. `states: 1, oracle_pads: 1` looked
like a tiny state space and was an instrument reporting on itself. The key here masks the two
selection colours out, so selecting and deselecting are state-neutral.

Two things measured together, because they answer the same question two ways:

  seed 1  after clicking each pad, dump EVERY colour's blobs. `csrvckunbev` (the DARK_GRAY(3)
          ring) says the pad has a legal move; `lgbyiaitpdi` (GRAY(2)) should say WHICH. Whether
          the pips are drawn 12 px out or still stacked on the pad decides if a tool can read the
          move set for one action or must pay four.
  seed 2  blind: for every pad and every one of the four landings two cells out, select then land,
          and report whether the MASKED board changed and what the green count did. This needs no
          theory of the marker at all and is the ground truth the oracle has to match.
  seed >2 randomised DFS over masked states with restart-and-replay backtracking.

Expected feedback: seed 2's `accepted` list IS level 6's move set from its start position. An
empty list, or a list that only shuffles one pair back and forth, makes the level unwinnable from
its start state and says the remaining 0.7273 of lf52 is not tool work.
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
        """Board identity with the SELECTION masked out — a ring is not a different board."""
        g = self.last.copy()
        g[(g == GRAY) | (g == DARK)] = 1
        return g.tobytes()

    def pads(self) -> list[tuple[float, float, int]]:
        g = self.g()
        return ([(b[0], b[1], GREEN) for b in blobs(g, GREEN) if b[2] >= 8]
                + [(b[0], b[1], RED) for b in blobs(g, RED) if b[2] >= 8])

    def green(self) -> int:
        return int((self.g() == GREEN).sum())

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
        gm.click(62, 2)
    return gm


def run_marker_dump(gm: Game, seed: int) -> None:
    out = []
    for pad in gm.pads():
        gm.click(round(pad[1]), round(pad[0]))
        g = gm.g()
        out.append({
            "pad": [pad[0], pad[1], pad[2]],
            "hist": {int(v): int((g == v).sum()) for v in np.unique(g)},
            "gray": [[b[0], b[1], b[2]] for b in blobs(g, GRAY)],
            "dark": [[b[0], b[1], b[2]] for b in blobs(g, DARK)],
        })
        gm.click(62, 2)
    print(json.dumps({"seed": seed, "mode": "markerdump", "detail": out}), flush=True)


def run_blind(gm: Game, seed: int) -> None:
    start_lvl = gm.lvl()
    root = gm.key()
    accepted, refused = [], []
    for pad in gm.pads():
        for dy, dx in DIRS:
            if gm.key() != root:
                gm.restart()
                for _ in range(3):
                    gm.click(62, 2)
                if gm.key() != root:
                    accepted.append({"note": "restart did not restore root"})
                    break
            ly, lx = round(pad[0] + dy * 2 * CELL), round(pad[1] + dx * 2 * CELL)
            if not (0 <= ly < 64 and 0 <= lx < 64):
                refused.append({"pad": [pad[0], pad[1]], "d": [dy, dx], "why": "offscreen"})
                continue
            g0 = gm.green()
            gm.click(round(pad[1]), round(pad[0]))
            gm.click(lx, ly)
            rec = {"pad": [pad[0], pad[1], pad[2]], "d": [dy, dx],
                   "green": [g0, gm.green()], "lvl": gm.lvl(),
                   "pads_after": [[p[0], p[1], p[2]] for p in gm.pads()]}
            (accepted if gm.key() != root else refused).append(rec)
            if gm.lvl() > start_lvl:
                print(json.dumps({"seed": seed, "mode": "blind", "cleared": True,
                                  "level": gm.lvl(), "move": rec}), flush=True)
                return
    print(json.dumps({"seed": seed, "mode": "blind", "cleared": False, "level": gm.lvl(),
                      "accepted": accepted, "n_accepted": len(accepted),
                      "n_refused": len(refused), "actions": gm.actions}), flush=True)


def run_dfs(gm: Game, seed: int, cap: int) -> None:
    rng = random.Random(seed)
    start_lvl = gm.lvl()
    root = gm.key()
    paths: dict[bytes, list] = {root: []}
    closed: dict[bytes, list] = {}
    stack = [root]
    min_green = gm.green()
    lost = 0

    def stand(node) -> bool:
        if gm.key() == node:
            return True
        gm.restart()
        for _ in range(3):
            gm.click(62, 2)
        if gm.key() != root:
            return False
        for mv in paths[node]:
            if mv[0] == "act":
                gm.simple(mv[1])
            else:
                gm.click(mv[1][0], mv[1][1])
                gm.click(mv[2][0], mv[2][1])
        return gm.key() == node

    while stack and gm.actions < cap:
        node = stack[-1]
        if node not in closed:
            if not stand(node):
                lost += 1
                stack.pop()
                continue
            moves = [("act", k) for k in (1, 2, 3, 4)]
            for pad in gm.pads():
                for dy, dx in DIRS:
                    ly, lx = round(pad[0] + dy * 2 * CELL), round(pad[1] + dx * 2 * CELL)
                    if 0 <= ly < 64 and 0 <= lx < 64:
                        moves.append(("jump", (round(pad[1]), round(pad[0])), (lx, ly)))
            rng.shuffle(moves)
            closed[node] = moves
        if not closed[node]:
            stack.pop()
            continue
        mv = closed[node].pop()
        if not stand(node):
            lost += 1
            continue
        if mv[0] == "act":
            gm.simple(mv[1])
        else:
            gm.click(mv[1][0], mv[1][1])
            gm.click(mv[2][0], mv[2][1])
        if gm.lvl() > start_lvl:
            print(json.dumps({"seed": seed, "mode": "dfs", "cleared": True, "level": gm.lvl(),
                              "path": [list(map(str, m)) for m in paths[node] + [mv]],
                              "actions": gm.actions}), flush=True)
            return
        min_green = min(min_green, gm.green())
        nxt = gm.key()
        if nxt not in paths:
            paths[nxt] = paths[node] + [mv]
            stack.append(nxt)
            print(f"# seed {seed} NEW state {len(paths)} act={gm.actions} green={gm.green()}",
                  file=sys.stderr, flush=True)
    print(json.dumps({"seed": seed, "mode": "dfs", "cleared": False, "level": gm.lvl(),
                      "states": len(paths), "closed": len(closed),
                      "open": sum(1 for n in stack if closed.get(n)),
                      "min_green": min_green, "actions": gm.actions,
                      "budget_out": gm.actions >= cap, "replay_failures": lost}), flush=True)


def main() -> None:
    seed = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    cap = int(sys.argv[2]) if len(sys.argv) > 2 else 1500
    gm = reach(seed)
    if gm is None:
        print(json.dumps({"seed": seed, "error": "did not reach level 6"}), flush=True)
        return
    print(f"# seed {seed} at level {gm.lvl()} green={gm.green()}", file=sys.stderr, flush=True)
    if seed == 1:
        run_marker_dump(gm, seed)
    elif seed == 2:
        run_blind(gm, seed)
    else:
        run_dfs(gm, seed, cap)


if __name__ == "__main__":
    main()
