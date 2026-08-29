"""lf52 level 6 — test EVERY verb the source offers, all at once (rule 7h).

Reading `equnaohchtj` end to end overturns the model the wiki carries for this level:

  * `qikmikecdf` makes a jump legal when the MIDPOINT holds `fozwvlovdui` **or `dgxfozncuiz`**
    and the landing cell is bare floor. `cfilhtifcb` then moves the selected pad
    UNCONDITIONALLY and only removes the midpoint when it is a same-named pad. So jumping a
    `dgxfozncuiz` (PURPLE/PINK, 'p' in the level grid) MOVES A PAD WITHOUT CAPTURING — the verb
    nobody has tested.
  * `ndtvadsrqf` matches by PREFIX, so the win count `ddaguepwkt` includes `fozwvlovdui_red`
    and every pad the camera is not showing. `grid6` is 27 cells wide against a ~11-cell screen.
  * `pchvqimdvj` is NOT a win — it greys the pads and spawns the restart pickup. `tdcblgbfxw`
    (count 2 on this level) is the win.
  * clicking a pad attaches up to four `lgbyiaitpdi` markers, colour DARK_GRAY(3), two cells out
    in each legal direction: a FRAME-OBSERVABLE LEGAL-MOVE ORACLE.

One seed = one experiment, so `pfan.sh` runs them together.

  1 dump          board census: every colour, every blob, screen extent
  2 markers       click each pad/red, read the colour-3 markers -> legal moves, observable?
  3 jumps         take every offered marker once; does green fall, does a pad move w/o capture
  4..7 arrows     ACTION1..4 x12: does the WHOLE board translate (camera) and do new pads enter
  8 action5       ACTION5 then the pickup: dead-end marker + restart, or something else
  9 greedy        prefer capture-markers, else any marker; 300 moves
  >=10 random     seeded random walk over the marker oracle, 400 moves, restart on dead end

Expected feedback: `cleared` true on any seed names a winning line for level 6. Seed 2 empty
means the marker oracle is not observable and the whole plan is off. Seed 3 showing green
UNCHANGED while a pad centroid moves is the move-without-capture, measured.
"""
from __future__ import annotations

import json
import random
import sys

import numpy as np

GREEN = 14
RED = 8
PURPLE = 15
PINK = 7
MARK = 3
CELL = 6
START_LEVEL = 5          # levels_completed on arriving at level 6


def blobs(g: np.ndarray, colour: int) -> list[tuple[float, float, int]]:
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
        out.append((round(sum(p[0] for p in cells) / len(cells), 1),
                    round(sum(p[1] for p in cells) / len(cells), 1), len(cells)))
    return sorted(out)


def top(o) -> np.ndarray:
    return np.array(o.frame[-1], dtype=np.int16)


class Board:
    """One live level-6 board plus the two clicks the protocol is made of."""

    def __init__(self, env, agent, obs):
        from admorphiq.types import ActionType as AT
        from admorphiq.types import GameAction
        self.env, self.agent, self.obs = env, agent, obs
        self.AT, self.GA = AT, GameAction
        self.actions = 0

    def lvl(self) -> int:
        return int(getattr(self.obs, "levels_completed", 0) or 0)

    def click(self, x: int, y: int):
        self.actions += 1
        self.obs = self.env.step(self.agent._convert(self.GA.coordinate(int(x), int(y))),
                                 data={"x": int(x), "y": int(y)})
        return self.obs

    def simple(self, k: int):
        self.actions += 1
        self.obs = self.env.step(self.agent._convert(self.GA.simple(self.AT(k))))
        return self.obs

    def pads(self) -> list[tuple[float, float, int]]:
        g = top(self.obs)
        return [b for b in blobs(g, GREEN) if b[2] >= 8] + [b for b in blobs(g, RED) if b[2] >= 8]

    def green(self) -> int:
        return int((top(self.obs) == GREEN).sum())

    def markers(self) -> list[tuple[float, float, int]]:
        return [b for b in blobs(top(self.obs), MARK) if 4 <= b[2] <= 60]

    def select(self, pad) -> list[tuple[float, float, int]]:
        """Click a pad; return the markers it lit. Marker = a legal landing, two cells out."""
        self.click(round(pad[1]), round(pad[0]))
        return self.markers()


def reach_level6(seed: int):
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
        if i % 200 == 0:
            print(f"# seed {seed} reaching level 6: action {i} "
                  f"lvl={int(getattr(obs, 'levels_completed', 0) or 0)}", file=sys.stderr, flush=True)
        act = agent.choose_action(frames, obs)
        data = act.action_data.model_dump() if getattr(act, "action_data", None) else None
        obs = env.step(act, data=data) if data else env.step(act)
        frames.append(obs)
    if int(getattr(obs, "levels_completed", 0) or 0) < START_LEVEL:
        return None
    b = Board(env, agent, obs)
    # The first board of a new level is mid-animation; a deselect click on a bare screen corner
    # settles it without touching the undo stack (ACTION7 would UNDO a jump later on).
    for _ in range(6):
        b.click(62, 2)
    return b


def emit(seed: int, **kw) -> None:
    print(json.dumps({"seed": seed, **kw}), flush=True)


def near(a, b, tol=2.0) -> bool:
    return abs(a[0] - b[0]) <= tol and abs(a[1] - b[1]) <= tol


def run_dump(b: Board, seed: int) -> None:
    g = top(b.obs)
    hist = {int(v): int((g == v).sum()) for v in np.unique(g)}
    emit(seed, mode="dump", layers=len(b.obs.frame), hist=hist,
         green=[(x[0], x[1], x[2]) for x in blobs(g, GREEN)],
         red=[(x[0], x[1], x[2]) for x in blobs(g, RED)],
         purple=[(x[0], x[1], x[2]) for x in blobs(g, PURPLE)],
         pink=[(x[0], x[1], x[2]) for x in blobs(g, PINK)],
         mark=[(x[0], x[1], x[2]) for x in blobs(g, MARK)],
         lvl=b.lvl())


def run_markers(b: Board, seed: int) -> None:
    out = []
    for pad in b.pads():
        before = len(b.markers())
        ms = b.select(pad)
        out.append({"pad": [pad[0], pad[1]], "before": before,
                    "markers": [[m[0], m[1], m[2]] for m in ms],
                    "offsets": [[round(m[0] - pad[0]), round(m[1] - pad[1])] for m in ms]})
        b.click(62, 2)          # deselect
    emit(seed, mode="markers", pads=len(b.pads()), detail=out, lvl=b.lvl())


def run_jumps(b: Board, seed: int) -> None:
    """Take each offered marker once. A green count that does NOT fall while a pad centroid
    moves is the move-without-capture the source predicts over a `dgxfozncuiz`."""
    start_lvl = b.lvl()
    out = []
    for pad in list(b.pads()):
        if b.lvl() > start_lvl:
            break
        ms = b.select(pad)
        if not ms:
            b.click(62, 2)
            continue
        m = ms[0]
        g0, p0 = b.green(), b.pads()
        b.click(round(m[1]), round(m[0]))
        g1, p1 = b.green(), b.pads()
        out.append({"pad": [pad[0], pad[1]], "landing": [m[0], m[1]],
                    "green": [g0, g1], "npads": [len(p0), len(p1)],
                    "moved": p0 != p1, "lvl": b.lvl()})
    emit(seed, mode="jumps", detail=out, lvl=b.lvl(), start=start_lvl,
         cleared=b.lvl() > start_lvl, actions=b.actions)


def run_arrows(b: Board, seed: int, k: int) -> None:
    """Does the WHOLE board translate (a camera scroll) and do unseen pads enter the screen?"""
    start_lvl = b.lvl()
    steps = []
    prev = top(b.obs)
    for i in range(12):
        b.simple(k)
        cur = top(b.obs)
        # a translation shows up as the best whole-board shift, not as one sprite moving
        best = (0, 0, -1.0)
        for dx in range(-8, 9):
            shifted = np.roll(prev, dx, axis=1)
            score = float((shifted[:, max(0, dx):64 + min(0, dx)]
                           == cur[:, max(0, dx):64 + min(0, dx)]).mean())
            if score > best[2]:
                best = (dx, 0, round(score, 3))
        steps.append({"i": i, "shift_x": best[0], "match": best[2],
                      "green": int((cur == GREEN).sum()),
                      "purple": int((cur == PURPLE).sum()),
                      "npads": len(b.pads()), "lvl": b.lvl()})
        prev = cur
        if b.lvl() != start_lvl:
            break
    emit(seed, mode=f"arrow{k}", detail=steps, lvl=b.lvl(), start=start_lvl,
         cleared=b.lvl() > start_lvl)


def run_action5(b: Board, seed: int) -> None:
    start_lvl = b.lvl()
    g0 = b.green()
    b.simple(5)
    g1 = b.green()
    h1 = {int(v): int((top(b.obs) == v).sum()) for v in np.unique(top(b.obs))}
    # the pickup rises from y=65 to y=51 over 7 frames; spend it in the bottom-left 16x16 corner
    b.click(4, 56)
    g2, l2 = b.green(), b.lvl()
    b.click(4, 56)
    emit(seed, mode="action5", green=[g0, g1, g2, b.green()],
         hist_after5=h1, lvl=b.lvl(), l_after_corner=l2, start=start_lvl,
         restarted=b.green() >= g0, cleared=b.lvl() > start_lvl)


def run_search(b: Board, seed: int, greedy: bool) -> None:
    """Walk the marker oracle. A capture is a marker whose MIDPOINT holds a same-coloured pad;
    everything else is a reposition. Restart (ACTION5 + pickup) when no marker exists anywhere."""
    rng = random.Random(seed)
    start_lvl = b.lvl()
    best_green = b.green()
    restarts = 0
    trace = []
    for step in range(400):
        if b.lvl() > start_lvl:
            break
        pads = b.pads()
        rng.shuffle(pads)
        chosen = None
        for pad in pads:
            ms = b.select(pad)
            if not ms:
                b.click(62, 2)
                continue
            g = top(b.obs)
            caps, reps = [], []
            for m in ms:
                my, mx = (pad[0] + m[0]) / 2, (pad[1] + m[1]) / 2
                mid = g[int(round(my)) - 2:int(round(my)) + 3, int(round(mx)) - 2:int(round(mx)) + 3]
                (caps if (mid == GREEN).any() or (mid == RED).any() else reps).append(m)
            pool = (caps or reps) if greedy else ms
            chosen = (pad, rng.choice(pool))
            break
        if chosen is None:
            b.simple(5)
            b.click(4, 56)
            restarts += 1
            if restarts > 12:
                break
            continue
        pad, m = chosen
        g0 = b.green()
        b.click(round(m[1]), round(m[0]))
        if b.green() < best_green:
            best_green = b.green()
            trace.append({"step": step, "green": b.green(), "npads": len(b.pads())})
        if step % 50 == 0:
            print(f"# seed {seed} step {step} green={b.green()} lvl={b.lvl()}",
                  file=sys.stderr, flush=True)
        _ = g0
    emit(seed, mode="greedy" if greedy else "random", lvl=b.lvl(), start=start_lvl,
         cleared=b.lvl() > start_lvl, best_green=best_green, restarts=restarts,
         actions=b.actions, trace=trace[-8:])


def main() -> None:
    seed = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    print(f"# seed {seed} start", file=sys.stderr, flush=True)
    b = reach_level6(seed)
    if b is None:
        emit(seed, mode="setup", error="did not reach level 6")
        return
    print(f"# seed {seed} at level {b.lvl()} green={b.green()}", file=sys.stderr, flush=True)
    if seed == 1:
        run_dump(b, seed)
    elif seed == 2:
        run_markers(b, seed)
    elif seed == 3:
        run_jumps(b, seed)
    elif seed in (4, 5, 6, 7):
        run_arrows(b, seed, seed - 3)
    elif seed == 8:
        run_action5(b, seed)
    elif seed == 9:
        run_search(b, seed, greedy=True)
    else:
        run_search(b, seed, greedy=False)


if __name__ == "__main__":
    main()
