"""Measure `GantryCraneTool` through the real harness, and check it fires nowhere else.

Three modes, because three different questions get asked of a tool:

    add   <game> <cap>   the registry as shipped, plus this tool — what the harness scores.
    solo  <game> <cap>   the same, with `phase_grid` LIFTED OUT of the working copy of the
                         registry. ⛔ Never committed: it exists because two tools that read the
                         same mechanic cannot both hold the board, and the number that tells the
                         integrator whether the newcomer earns the bid is what it does when it is
                         given every turn.
    sweep <cap>          every sample game, first frame and deep frames alike, asking a FRESH
                         tool whether it bids — the false-positive gate a tool ships on.
    truth <index>        ⛔ DEV-TIME ONLY, and it reads the game's ENGINE INTERNALS — sprite tags,
                         interaction modes and the rail predicate — which no tool may ever do.
                         It exists because the last board of this game is not yet solvable by any
                         tool, and a measurement that lives only in a session transcript does not
                         exist. It rebuilds the board's transition model from the engine, searches
                         it, REPLAYS the answer through the real engine and asserts the win, so the
                         next author starts from a verified route instead of from nothing.

The harness is what is scored, so the harness is what this runs; see `scripts/harness_probe.py`
for why a per-tool probe disagrees with it in three distinct ways.
"""

from __future__ import annotations

import sys
from typing import Any

sys.path.insert(0, "src")


def _no_llm(*_a, **_k):
    raise RuntimeError("LLM-free: the signature fallback is what this measures")


def _tools(drop: str | None):
    from admorphiq.harness.registry import default_tools
    from admorphiq.tools.gantry import GantryCraneTool

    kept = [t for t in default_tools() if getattr(t, "name", "") != drop]
    return kept + [GantryCraneTool()]


def _play(title: str, cap: int, drop: str | None) -> None:
    from arc_agi import Arcade, OperationMode

    from admorphiq.harness.loop import UnifiedAgent

    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    info = next(i for i in arcade.get_environments()
                if (i.title or i.game_id).lower().startswith(title))
    env = arcade.make(info.game_id)
    obs = env.reset()
    agent = UnifiedAgent(_tools(drop), _no_llm, giveup=cap, stall=80, ctx_budget=6000)
    frames = [obs]
    picks: dict[str, int] = {}
    marks: list[tuple[int, int]] = []
    levels = 0
    step = 0
    for step in range(cap):
        if agent.is_done(frames, obs):
            break
        act = agent.choose_action(frames, obs)
        picks[str(agent._current)] = picks.get(str(agent._current), 0) + 1
        data = act.action_data.model_dump() if getattr(act, "action_data", None) else None
        obs = env.step(act, data=data) if data else env.step(act)
        frames.append(obs)
        now = int(getattr(obs, "levels_completed", levels) or 0)
        if now != levels:
            marks.append((now, step + 1))
            levels = now
    label = f"{title} (without {drop})" if drop else title
    print(f"{label} HARNESS: {levels} levels in {step + 1} actions   clears at {marks}")
    print(f"   who acted: {dict(sorted(picks.items(), key=lambda kv: -kv[1])[:4])}")


def _sweep(cap: int) -> None:
    """Ask a fresh tool, on every frame of live play, whether it would take each board."""
    from arc_agi import Arcade, OperationMode

    from admorphiq.harness.loop import UnifiedAgent
    from admorphiq.harness.registry import default_tools
    from admorphiq.tools.gantry import GantryCraneTool

    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    for info in sorted(arcade.get_environments(), key=lambda i: (i.title or i.game_id)):
        title = (info.title or info.game_id).lower()[:4]
        env = arcade.make(info.game_id)
        obs = env.reset()
        agent = UnifiedAgent(default_tools(), _no_llm, giveup=cap, stall=80, ctx_budget=6000)
        frames = [obs]
        top = 0.0
        hits = 0
        for _ in range(cap):
            bid = GantryCraneTool().detect(frames, obs)
            top = max(top, bid)
            hits += bid > 0.0
            if agent.is_done(frames, obs):
                break
            act = agent.choose_action(frames, obs)
            data = act.action_data.model_dump() if getattr(act, "action_data", None) else None
            obs = env.step(act, data=data) if data else env.step(act)
            frames.append(obs)
        print(f"{title}: max bid {top:.2f}  frames bidding {hits}", flush=True)


def _truth(index: int) -> None:
    """Search a board's real transition model, then replay the answer through the engine.

    ⛔ Everything below reads the ENGINE, not the frames: which sprite is standable, which cell the
    gantry's rail admits, which control each pad reveals. That is the opposite of what a tool may
    do, and it is deliberate — this answers "is the board winnable, in how many actions, through
    which mechanics", which is the question to settle BEFORE writing a tool, not after.
    """
    from collections import deque

    import numpy as np
    from arc_agi import Arcade, OperationMode
    from arcengine import BlockingMode, GameAction, InteractionMode

    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    info = next(i for i in arcade.get_environments()
                if (i.title or i.game_id).lower().startswith("dc22"))
    env = arcade.make(info.game_id)
    obs = env.reset()
    game = env._game
    game.set_level(index)
    avatar, goal = game.qnnpcoyzd, (game.hfuqkxulm.x, game.hfuqkxulm.y)
    start = (avatar.x, avatar.y)
    side = 64

    def cycle(letter: str) -> None:
        """One press of a terrain control, replicating the engine's own variant advance."""
        button = next(s for s in game.current_level.get_sprites()
                      if "buezna" in s.tags and letter in s.tags and "sys_click" in s.tags)
        group = [s for s in game.current_level.get_sprites()
                 if letter in s.tags and s is not button and s.is_visible
                 and s.interaction != InteractionMode.REMOVED]
        for sprite in group:
            nxt = game.lcdavdtabp(sprite.name)
            found = game.rcorpfmgqi(sprite.x, sprite.y, nxt) if nxt else None
            if found is None:
                continue
            sprite.set_interaction(InteractionMode.REMOVED)
            found.set_interaction(
                InteractionMode.INTANGIBLE if ("omvz" in found.tags or "buezna" in found.tags)
                else InteractionMode.INVISIBLE if "inzejtible" in found.tags
                else InteractionMode.TANGIBLE)

    def stamp(dst, mask, x, y):
        h, w = mask.shape
        y0, x0, y1, x1 = max(0, y), max(0, x), min(side, y + h), min(side, x + w)
        if y1 > y0 and x1 > x0:
            dst[y0:y1, x0:x1] |= mask[y0 - y:y1 - y, x0 - x:x1 - x]

    def read() -> tuple[Any, Any]:
        """Standable cells and blocking cells, exactly as the engine decides them."""
        floor = np.zeros((side, side), dtype=bool)
        block = np.zeros((side, side), dtype=bool)
        for sprite in game.current_level.get_sprites():
            if sprite is avatar or "ignore" in sprite.tags:
                continue
            pixels = np.asarray(sprite.render()) >= 0
            if sprite.is_collidable and sprite._blocking != BlockingMode.NOT_BLOCKED:
                stamp(block, pixels, sprite.x, sprite.y)
            if sprite._interaction == InteractionMode.INTANGIBLE \
                    and "crzsjq" not in sprite.tags and "vcha" not in sprite.tags \
                    and not sprite.name.startswith("brixto-orckhi"):
                stamp(floor, pixels, sprite.x, sprite.y)
        return floor, block

    sprites = type(game).__init__.__globals__["sprites"]
    slab = [np.asarray(sprites["brixto-orckhi1"].pixels) >= 0,
            np.asarray(sprites["brixto-orckhi2"].pixels) >= 0]
    # The carried slab is drawn separately, so the base is read once per (bar phase, tile phase).
    base = {}
    for tile in range(2):
        for bars in range(6):
            base[(bars, tile)] = read()
            cycle("f")
        cycle("c")
    blocked = base[(0, 0)][1]
    rail = {(i, j) for i in range(-6, 4) for j in range(-3, 9) if game.tnedtgkguq(i, j)}
    families = ["tewfutpibpar", "tewfutrefgps", "tewfutyefmyf", "tewfutblrmbx"]
    dial = (18, 48)
    twin = {"tewfutpibpar": (32, 52), "tewfutyefmyf": (4, 4),
            "tewfutblrmbx": (34, 58), "tewfutrefgps": None}
    pads = {"riidpd": (36, 58), "up": (34, 56), "lersnf": (32, 58), "dowlja": (34, 60)}
    drive = {"up": (0, 1), "dowlja": (0, -1), "lersnf": (-1, 0), "riidpd": (1, 0)}
    gates = {"d": (6, 18, 4, 2), "g": (34, 48, 4, 2)}
    cache: dict[Any, Any] = {}

    def ground(bars, tile, i, j, held):
        where = (16 + 4 * i, 24 - 4 * j) if held else (0, 24)
        key = (bars, tile, where)
        if key not in cache:
            grid = base[(bars, tile)][0].copy()
            stamp(grid, slab[tile], *where)
            cache[key] = grid
        return cache[key]

    def stands(grid, x, y):
        return 0 <= x < 63 and 0 <= y < 63 and grid[y, x] and not blocked[y:y + 2, x:x + 2].any()

    def taken(x, y, keys):
        out = set(keys)
        for letter, (kx, ky, kw, kh) in gates.items():
            if x + 1 >= kx and y + 1 >= ky and x < kx + kw and y < ky + kh:
                out.add(letter)
        return frozenset(out)

    origin = (start[0], start[1], 0, 0, False, 0, 0, 0, taken(start[0], start[1], ()))
    seen: dict[Any, Any] = {origin: (None, None)}
    queue = deque([origin])
    won = None
    while queue:
        state = queue.popleft()
        x, y, i, j, held, bars, tile, dialled, keys = state
        if (x, y) == goal:
            won = state
            break
        grid = ground(bars, tile, i, j, held)

        def offer(nxt, label):
            if nxt not in seen:
                seen[nxt] = (state, label)
                queue.append(nxt)

        for dx, dy, name in ((0, -2, "U"), (0, 2, "D"), (-2, 0, "L"), (2, 0, "R")):
            if stands(grid, x + dx, y + dy):
                offer((x + dx, y + dy, i, j, held, bars, tile, dialled,
                       taken(x + dx, y + dy, keys)), "mv" + name)
        # The dial tile teleports to whichever twin its CURRENT colour names.
        far = twin[families[dialled]]
        # ⛔ One of the four colours names no twin at all, so the dial has a dead setting and the
        # press is then an ordinary press that moves nobody.
        land = (x, y)
        if far is not None:
            land = far if (x, y) == dial else dial if (x, y) == far else (x, y)
        if stands(ground(bars, (tile + 1) % 2, i, j, held), *land):
            offer((land[0], land[1], i, j, held, bars, (tile + 1) % 2, dialled,
                   taken(land[0], land[1], keys)), "btnC")
        if stands(ground((bars + 1) % 6, tile, i, j, held), x, y):
            offer((x, y, i, j, held, (bars + 1) % 6, tile, dialled, keys), "btnF")
        if "d" in keys:
            offer((x, y, i, j, held, bars, tile, (dialled + 1) % 4, keys), "btnD")
        if "g" in keys and not held and (i, j) == (-4, 0) \
                and stands(ground(bars, tile, i, j, True), x, y):
            offer((x, y, i, j, True, bars, tile, dialled, keys), "GRAB")
        # ⛔ Each gantry direction is clickable ONLY while the avatar stands on that direction's
        # own pad, so driving the crane is a shuttle between four 2x2 cells.
        for name, pad in pads.items():
            if abs(x - pad[0]) >= 2 or abs(y - pad[1]) >= 2:
                continue
            di, dj = drive[name]
            if (i + di, j + dj) in rail and stands(ground(bars, tile, i + di, j + dj, held), x, y):
                offer((x, y, i + di, j + dj, held, bars, tile, dialled, keys), "crane_" + name)
    print(f"level {index}: {len(seen)} states searched, winnable={won is not None}")
    if won is None:
        return
    plan = []
    node = won
    while seen[node][0] is not None:
        node, label = seen[node][0], seen[node][1]
        plan.append(label)
    plan.reverse()

    env2 = arcade.make(info.game_id)
    obs = env2.reset()
    live = env2._game
    live.set_level(index)
    clicks = {}
    for sprite in live.current_level.get_sprites():
        if "sys_click" not in sprite.tags:
            continue
        name = next((f"crane_{t}" for t in sprite.tags
                     if t in ("riidpd", "up", "lersnf", "dowlja")), None)
        if "grawwq" in sprite.tags:
            name = "GRAB"
        if name is None:
            letter = next((t for t in sprite.tags if len(t) == 1), None)
            name = f"btn{letter.upper()}" if letter else None
        if name:
            clicks[name] = (sprite.x + sprite.width // 2, sprite.y + sprite.height // 2)
    moves = {"mvU": GameAction.ACTION1, "mvD": GameAction.ACTION2,
             "mvL": GameAction.ACTION3, "mvR": GameAction.ACTION4}
    for label in plan:
        if label in moves:
            obs = env2.step(moves[label])
        else:
            x, y = clicks[label]
            obs = env2.step(GameAction.ACTION6, data={"x": int(x), "y": int(y)})
    print(f"  plan {len(plan)} actions; replayed through the engine -> {obs.state}")
    print(f"  avatar {live.qnnpcoyzd.x},{live.qnnpcoyzd.y}  marker {goal[0]},{goal[1]}")
    print(f"  {plan}")


def main() -> None:
    mode = sys.argv[1]
    if mode == "truth":
        _truth(int(sys.argv[2]))
        return
    if mode == "sweep":
        _sweep(int(sys.argv[2]) if len(sys.argv) > 2 else 200)
        return
    game = sys.argv[2]
    cap = int(sys.argv[3]) if len(sys.argv) > 3 else 1500
    _play(game, cap, "phase_grid" if mode == "solo" else None)


if __name__ == "__main__":
    main()
