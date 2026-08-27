"""Drive ONE tool against a side-view faller and print what it sees, decides and learns.

⛔ Why a driver of its own rather than `harness_probe.py`: the harness answers "how many levels",
which is the number that counts, but it cannot answer "why did the map stop growing on the fourth
board". This replays the harness's OWN contract — reset on a level-up, revive on a GAME_OVER, feed
`observe` only the tool's own transitions — and prints the tool's internal reading beside it. The
final number is still taken from `harness_probe.py`; this is the microscope, not the scale.

    uv run python scripts/crag_probe.py bp35 --tool crag --cap 400 --verbose
    uv run python scripts/crag_probe.py bp35 --dump 3        # settled board as glyphs
"""

from __future__ import annotations

import argparse
import pathlib
import sys

sys.path.insert(0, "src")

import numpy as np


def _settled(obs) -> np.ndarray:
    arr = np.asarray(getattr(obs, "frame", None))
    while arr.ndim > 2:
        arr = arr[-1]
    return arr.astype(np.int64)


def _glyphs(board: dict, legend: dict) -> list[str]:
    """The lattice as one character per cell, letters assigned in order of first sight."""
    if not board:
        return []
    rows = sorted({r for r, _ in board})
    cols = sorted({c for _, c in board})
    pool = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    out = []
    for r in rows:
        line = ""
        for c in cols:
            sig = board.get((r, c))
            if sig is None:
                line += " "
                continue
            if sig not in legend:
                legend[sig] = pool[len(legend) % len(pool)]
            line += legend[sig]
        out.append(f"{r:3d} |{line}|")
    return out


def _level_grids(title: str) -> list[tuple[list[str], dict]]:
    """The game's OWN boards, read straight out of its source with the engine never started.

    ⛔ DEV-TIME ONLY, and it lives in the probe rather than the tool for that reason. It exists to
    answer one question no frame can answer: when the tool stops proposing, is its map WRONG or is
    its map right and its search stuck? Those need opposite fixes.

    ⛔ `scripts/dump_sample_levels.py` cannot answer it for this family: its `Level` objects carry
    one placeholder sprite and `data=None`, because the boards are held in a separate module-level
    dict of ASCII grids keyed `grid1..gridN`, with a per-grid character -> sprite-name map beside
    them. That is what is parsed here.
    """
    import ast

    root = pathlib.Path("environment_files") / title.lower()
    src = ""
    for path in sorted(root.rglob("*.py")):
        src = path.read_text(errors="replace")
        break
    if not src:
        return []
    out: list[tuple[list[str], dict]] = []
    for node in ast.parse(src).body:
        if not isinstance(node, ast.Assign):
            continue
        value = node.value
        if not isinstance(value, ast.Dict):
            continue
        keys = [k.value for k in value.keys if isinstance(k, ast.Constant)]
        if not keys or not all(isinstance(k, str) and k.startswith("grid") for k in keys):
            continue
        for call in value.values:
            if not isinstance(call, ast.Call) or len(call.args) < 2:
                continue
            # ⛔ The grid literal is often written `[...][::-1]`, so it is a Subscript rather than
            # a list and `literal_eval` refuses it. The reversal is undone here on purpose: the
            # rows are kept in SOURCE order and everything is measured relative to the start cell,
            # which is where the tool's own origin is anchored too.
            arg = call.args[0]
            if isinstance(arg, ast.Subscript):
                arg = arg.value
            try:
                rows = ast.literal_eval(arg)
                names = ast.literal_eval(call.args[1])
            except Exception:  # noqa: BLE001
                continue
            out.append((list(rows), {ch: tuple(v) for ch, v in names.items()}))
        if out:
            return out
    return out


def _start_cell(grid) -> tuple[int, int] | None:
    rows, names = grid
    return next(((r, c) for r, line in enumerate(rows)
                 for c, ch in enumerate(line)
                 if names.get(ch, ("",))[0].startswith("player")), None)


def _truth_report(tool, grids, level: int) -> None:
    """Score the tool's map and vocabulary against the board the game actually loaded.

    The rows the tool has seen are matched to the source grid by the START cell — the body begins
    at the grid's one player glyph, and the tool's own origin puts it at a known row — so every
    mapped cell has an unambiguous truth value.
    """
    if not (0 <= level < len(grids)) or not tool._world or tool._home is None:
        print("  truth: no grid or no map")
        return
    rows, names = grids[level]
    start = _start_cell(grids[level])
    if start is None:
        print("  truth: no start cell in the grid")
        return
    # The tool's world row falls as the grid row rises: gravity is drawn mirrored on this family.
    def grid_row(world_row: int) -> int:
        return start[0] + (tool._home[0] - world_row)

    passable = {" "}
    want = {"solid": set(), "open": set(), "kill": set(), "gone": set(), "swap": set(), "flip": set()}
    seen_rows = sorted({r for r, _ in tool._world})
    right = wrong = unseen = 0
    misses: dict[str, int] = {}
    for (wr, wc), sig in sorted(tool._world.items()):
        gr = grid_row(wr)
        if not (0 <= gr < len(rows)) or wc >= len(rows[gr]):
            continue
        ch = rows[gr][wc]
        tag = names.get(ch, ("air",))[0]
        got = (
            "kill" if sig in tool._lethal else
            "gone" if sig in tool._vanish else
            "swap" if sig in tool._swap else
            "flip" if sig in tool._flip else
            "open" if tool._is_open(sig) else
            "solid" if sig in tool._solid else "?"
        )
        if ch in passable:
            truth = "open"
        elif tag.startswith("player"):
            truth = "open"
        else:
            truth = {"qclfkhjnaac": "gone", "yuuqpmlxorv": "swap", "oonshderxef": "swap",
                     "lrpkmzabbfa": "flip", "ubhhgljbnpu": "kill", "hzusueifitk": "kill",
                     "etlsaqqtjvn": "solid", "xcjjwqfzjfe": "solid",
                     "fjlzdjxhant": "exit", "aknlbboysnc": "open"}.get(tag, "solid")
        want[truth].add(ch) if truth in want else None
        if got == "?":
            unseen += 1
        elif got == truth or (truth == "exit" and sig == tool._exit):
            right += 1
        else:
            wrong += 1
            misses[f"{ch!r} truth={truth} tool={got}"] = misses.get(f"{ch!r} truth={truth} tool={got}", 0) + 1
    total = len(rows)
    print(f"  truth: map spans grid rows {grid_row(max(seen_rows))}..{grid_row(min(seen_rows))} "
          f"of {total}; cells classified right {right}, WRONG {wrong}, never named {unseen}")
    for k, n in sorted(misses.items(), key=lambda kv: -kv[1])[:8]:
        print(f"     x{n:<4d} {k}")
    exit_at = [(r, c) for r, line in enumerate(rows)
               for c, ch in enumerate(line) if names.get(ch, ("",))[0] == "fjlzdjxhant"]
    for gr, gc in exit_at:
        wr = tool._home[0] - (gr - start[0])
        inside = (wr, gc) in tool._world
        print(f"     exit at grid ({gr},{gc}) -> world row {wr}: "
              f"{'IN the map' if inside else 'NEVER SEEN'}")


def _make_tool(name: str):
    if name == "crag":
        from admorphiq.tools.crag import CragTool
        return CragTool()
    if name == "shaft":
        from admorphiq.tools.shaft import ShaftTool
        return ShaftTool()
    if name == "ledge":
        from admorphiq.tools.ledge import LedgeTool
        return LedgeTool()
    raise SystemExit(f"unknown tool {name}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("title")
    ap.add_argument("--tool", default="crag")
    ap.add_argument("--cap", type=int, default=400)
    ap.add_argument("--dump", type=int, default=0, help="print the settled board every N actions")
    ap.add_argument("--verbose", action="store_true")
    ap.add_argument("--map", action="store_true", help="print the tool's stitched world at the end")
    ap.add_argument("--bids", action="store_true",
                    help="bid on the FIRST frame of every sample game (selectivity)")
    ap.add_argument("--truth", type=int, default=-1, metavar="LEVEL",
                    help="when the tool first stops proposing on this level (0-indexed), score its "
                         "stitched map and its glyph vocabulary against the game's own level data")
    args = ap.parse_args()

    from arc_agi import Arcade, OperationMode

    from admorphiq.tools.base import Step  # noqa: F401  (documents the queue element type)

    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    if args.bids:
        # ⛔ A tool that bids on a board it cannot solve does not merely score nothing there — it
        # takes the turn from the tool that could. The bar is zero on all twenty-four others.
        hits = 0
        for env_info in sorted(arcade.get_environments(), key=lambda i: i.title or i.game_id):
            name = (env_info.title or env_info.game_id).lower()
            probe = arcade.make(env_info.game_id)
            first = probe.reset()
            bid = _make_tool(args.tool).detect([], first)
            hits += bid > 0 and not name.startswith(args.title)
            if bid > 0:
                print(f"  {name:24s} bid {bid:.2f}")
        print(f"{args.tool}: bids on {args.title} plus {hits} other game(s)")
        return
    info = next(i for i in arcade.get_environments()
                if (i.title or i.game_id).lower().startswith(args.title))
    env = arcade.make(info.game_id)
    obs = env.reset()
    print(f"{info.title}  baselines={getattr(info, 'baseline_actions', None)}")

    tool = _make_tool(args.tool)
    grids = _level_grids(args.title) if args.truth >= 0 else []
    told = False
    legend: dict = {}
    levels = 0
    deaths = 0
    marks: list[tuple[int, int]] = []
    queue: list = []
    prev_frame = None
    prev_step = None
    silent = 0
    level_start = 0

    from admorphiq.adapter import AdmorphiqAdapter
    from admorphiq.types import ActionType, GameAction

    def official(aid: int, xy=None):
        if aid == 0:
            return AdmorphiqAdapter._convert_action(GameAction(action_type=ActionType.RESET))
        if xy is None:
            return AdmorphiqAdapter._convert_action(GameAction(action_type=ActionType(aid)))
        return AdmorphiqAdapter._convert_action(
            GameAction(action_type=ActionType.ACTION6, x=int(xy[0]), y=int(xy[1])))

    for step in range(args.cap):
        state = str(getattr(obs, "state", ""))
        now = int(getattr(obs, "levels_completed", 0) or 0)
        if now != levels:
            marks.append((now, step))
            print(f"  *** LEVEL {now} cleared at action {step} "
                  f"({step - level_start} on this level, {deaths} deaths) ***")
            level_start = step
            levels = now
            deaths = 0
            tool.reset()
            queue = []
            prev_frame = None
        if "GAME_OVER" in state or "NOT_PLAYED" in state:
            deaths += 1
            if args.truth >= 0 and levels == args.truth and grids and tool._home is not None \
                    and tool._at is not None:
                start = _start_cell(grids[args.truth])
                if start is not None:
                    print(f"  {step:5d} DIED, last stood at grid"
                          f"({start[0] + (tool._home[0] - tool._at[0])},{tool._at[1]}) "
                          f"g={tool._gdir:+d} after {step - level_start} actions on this level")
            if args.verbose:
                print(f"{step:4d} GAME_OVER -> RESET")
            obs = env.step(official(0))
            queue = []
            prev_frame = None
            continue

        frame = np.asarray(_settled(obs))
        if prev_frame is not None and prev_step is not None:
            tool.observe(prev_frame, prev_step, bool((prev_frame != frame).any()))

        if args.dump and step % args.dump == 0:
            print(f"--- action {step} raw settled frame ---")
            g = _settled(obs)
            for y in range(0, 64):
                print("".join(f"{int(v):x}" if v < 16 else "?" for v in g[y]))

        if not queue:
            bid = tool.detect([], obs)
            queue = list(tool.propose([], obs))
            if args.verbose:
                extra = getattr(tool, "trace", lambda: "")()
                print(f"{step:4d} bid={bid:.2f} plan={queue[:4]} {extra}")
            if args.truth >= 0 and levels == args.truth and grids and tool._home is not None \
                    and tool._at is not None:
                start = _start_cell(grids[args.truth])
                if start is not None:
                    gr = start[0] + (tool._home[0] - tool._at[0])
                    print(f"  {step:5d} grid=({gr},{tool._at[1]}) g={tool._gdir:+d} "
                          f"-> {queue[:1]} | {getattr(tool, '_note', '')}")
            stuck = not queue or "walled in" in getattr(tool, "_note", "")
            if stuck and args.truth >= 0 and levels == args.truth and not told:
                told = True
                print(f"  *** tool ran out of moves on level {args.truth + 1} at action {step} "
                      f"({step - level_start} on this level, {deaths} deaths) ***")
                print(f"  tool says: {getattr(tool, 'trace', lambda: '')()}")
                _truth_report(tool, grids, args.truth)
            if not queue:
                silent += 1
                # ⛔ Generous, because a tool proposing nothing is NOT the end of the board: in
                # the harness the turn simply passes to another tool and this one is asked again
                # a few actions later. Stopping at thirty made a run look like a ceiling when it
                # was a pause, and truncated the count by a level.
                if silent > 150:
                    print(f"  tool went silent at action {step}")
                    break
                obs = env.step(official(4))
                prev_frame = None
                continue
            silent = 0
        aid, xy = queue.pop(0)
        prev_frame, prev_step = frame, (aid, xy)
        if xy is not None:
            act = official(aid, xy)
            obs = env.step(act, data=act.action_data.model_dump())
        else:
            obs = env.step(official(aid))

    final = int(getattr(obs, "levels_completed", 0) or 0)
    print(f"{args.title} {args.tool}: {max(final, levels)} levels in {args.cap} actions, clears {marks}")
    if args.map:
        world = getattr(tool, "_world", None)
        if world:
            print("--- stitched world ---")
            for line in _glyphs(world, legend):
                print(line)
            for sig, ch in legend.items():
                print(f"  {ch} = {sig}")


if __name__ == "__main__":
    main()
