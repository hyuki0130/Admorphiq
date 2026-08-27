"""Drive the pillar-transfer tool against a live game and report how deep it gets.

``--read`` prints what the tool recovered from the first frame instead of playing, which is
how a misperception is separated from a mis-plan. ``--sweep`` reports the tool's bid on every
sample game, because a tool that bids on a board it cannot solve costs another tool its turn.
"""

from __future__ import annotations

import argparse
import sys

sys.path.insert(0, "src")

from admorphiq.tools.base import frame_2d  # noqa: E402
from admorphiq.tools.pillar_transfer import PillarTransferTool, _read, _solve  # noqa: E402


def describe(obs) -> None:
    board = _read(frame_2d(obs))
    if board is None:
        print("  board: not read")
        return
    print(f"  axis={board.axis} sign={board.sign:+d} unit={board.unit}")
    print(f"  channels={board.channels}")
    for i, p in enumerate(board.pillars):
        print(f"  pillar {i}: lane {p.lane_lo}-{p.lane_hi} stretch {p.seg_lo}-{p.seg_hi} "
              f"height={p.height} cap={p.cap}")
    for r in board.riders:
        print(f"  rider mark={r.mark} on pillar {r.pillar} mark_lo={r.mark_lo}")
    for s in board.sockets:
        print(f"  socket mark={s.mark} channel {s.channel} mark_lo={s.mark_lo}")
    for s in board.steppers:
        print(f"  stepper {s.src} -> {s.dst} click(row,col)={s.click}")
    for g in board.gates:
        print(f"  gate {g.low}<->{g.high} at heights {g.at_low}/{g.at_high} click={g.click}")
    print(f"  plan={_solve(board)}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("title", nargs="?", default="vc33")
    ap.add_argument("--cap", type=int, default=600)
    ap.add_argument("--read", action="store_true")
    ap.add_argument("--sweep", action="store_true")
    args = ap.parse_args()

    from arc_agi import Arcade, OperationMode
    from arcengine import GameAction

    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    infos = list(arcade.get_environments())

    if args.sweep:
        rows = []
        for info in infos:
            env = arcade.make(info.game_id)
            obs = env.reset()
            bid = PillarTransferTool().detect([], obs)
            rows.append(((info.title or info.game_id).lower()[:4], bid))
        rows.sort(key=lambda r: -r[1])
        for name, bid in rows:
            print(f"  {name}  {bid:.2f}")
        return

    info = next(i for i in infos if (i.title or i.game_id).lower().startswith(args.title))
    print(f"{args.title}: baseline={info.baseline_actions}")
    env = arcade.make(info.game_id)
    obs = env.reset()
    tool = PillarTransferTool()
    if args.read:
        describe(obs)
        return

    print(f"  detect={tool.detect([], obs):.2f}")
    done = 0
    acted = 0
    idle = 0
    mark = 0
    prev = frame_2d(obs)
    while acted < args.cap and idle < 4:
        steps = tool.propose([], obs)
        if not steps:
            idle += 1
            print(f"     no plan at action {acted} (level {done})")
            describe(obs)
            break
        for _, xy in steps:
            obs = env.step(GameAction.ACTION6, data={"x": xy[0], "y": xy[1]})
            acted += 1
            cur = frame_2d(obs)
            if cur.shape == prev.shape:
                tool.observe(prev, (6, xy), bool((prev != cur).any()))
                prev = cur
        new = int(getattr(obs, "levels_completed", done) or 0)
        if new != done:
            print(f"  level {new}: cleared in {acted - mark} actions (total {acted})")
            mark = acted
            done = new
            tool.reset()
        state = str(getattr(obs, "state", ""))
        if "WIN" in state:
            print(f"     WIN at {acted}")
            break
        if "GAME_OVER" in state:
            print(f"     GAME_OVER at {acted}")
            break
    print(f"{args.title} pillar_transfer: {done} levels in {acted} actions")


if __name__ == "__main__":
    main()
