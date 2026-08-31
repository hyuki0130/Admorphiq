"""Frame-only L5 maze reconstruction (pixel push-walls + snapped refills),
validated byte-exact against GT. Reuses the adapter's _parse primitives.
"""
from __future__ import annotations
import json, sys
from collections import Counter
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from admorphiq.adapters25.ls20 import (
    _find_avatar, _cell_counts, _classify_changer, _decode_token,
    _decode_goal_preview, _find_refills, _GOAL_BORDER, _PALETTE, _FLOOR_COLOR,
    _PLAYABLE_MAX_ROW, _CELL,
)

ROT = 1


def detect_pushwalls_pixel(grid):
    """Return list of (sx, sy, dx, dy) sprite top-lefts + push dir, from
    length-5 colour-1 lines with an adjacent colour-4 wall. Push is AWAY from
    the wall. Also returns the set of colour-1 pixels consumed by lines."""
    H, W = len(grid), len(grid[0])
    walls = []
    consumed = set()
    # horizontal length-5 lines
    for y in range(H):
        x = 0
        while x <= W - 5:
            if all(grid[y][x + i] == ROT for i in range(5)):
                above = grid[y - 1][x] if y - 1 >= 0 else -9
                below = grid[y + 1][x] if y + 1 < H else -9
                if above == 4:  # wall above -> push down; sprite top row = y
                    walls.append((x, y, 0, 1))
                    for i in range(5):
                        consumed.add((x + i, y))
                elif below == 4:  # wall below -> push up; sprite top = y-4
                    walls.append((x, y - 4, 0, -1))
                    for i in range(5):
                        consumed.add((x + i, y))
                x += 5
            else:
                x += 1
    # vertical length-5 lines
    for x in range(W):
        y = 0
        while y <= H - 5:
            if all(grid[y + i][x] == ROT for i in range(5)) and (x, y) not in consumed:
                left = grid[y][x - 1] if x - 1 >= 0 else -9
                right = grid[y][x + 1] if x + 1 < W else -9
                if left == 4:  # wall left -> push right; sprite left col = x
                    walls.append((x, y, 1, 0))
                    for i in range(5):
                        consumed.add((x, y + i))
                elif right == 4:  # wall right -> push left; sprite left = x-4
                    walls.append((x - 4, y, -1, 0))
                    for i in range(5):
                        consumed.add((x, y + i))
                y += 5
            else:
                y += 1
    return walls, consumed


def parse_l5(grid):
    avatar = _find_avatar(grid)
    ax, ay = avatar
    ox, oy = ax % _CELL, ay % _CELL
    xs = list(range(ox, len(grid[0]) - _CELL + 1, _CELL))
    ys = list(range(oy, len(grid) - _CELL + 1, _CELL))

    def snap(sx, sy):
        return (sx - (sx - ox) % _CELL, sy - (sy - oy) % _CELL)

    pw_raw, consumed = detect_pushwalls_pixel(grid)
    pushwalls = [(sx, sy, dx, dy, 5, 5) for (sx, sy, dx, dy) in pw_raw]

    goals = []
    goal_req = None
    changers = {}
    hard_walls = set()
    passable = set()
    for x in xs:
        for y in ys:
            hh = _cell_counts(grid, x, y)
            dom = hh.most_common(1)[0][0]
            if y < _PLAYABLE_MAX_ROW and dom == _GOAL_BORDER and sum(hh.get(c, 0) for c in _PALETTE) >= 3:
                goals.append((x, y))
                if goal_req is None:
                    goal_req = _decode_goal_preview(grid, x, y)
                passable.add((x, y))
                continue
            if dom == _FLOOR_COLOR:
                passable.add((x, y))
            else:
                hard_walls.add((x, y))
            if y < _PLAYABLE_MAX_ROW:
                kind = _classify_changer(hh, dom)
                if kind is not None:
                    changers[(x, y)] = kind
    goal = goals[0] if len(goals) == 1 else None
    token = _decode_token(grid)
    refills = {snap(sx, sy) for (sx, sy) in _find_refills_raw(grid, xs, ys)}
    # push collision cells must be passable
    for (sx, sy, dx, dy, w, h) in pushwalls:
        passable.add((sx, sy))
    return {
        "avatar": avatar, "goal": goal, "goal_req": goal_req, "token": token,
        "changers": changers, "refills": refills, "passable": passable,
        "hard_walls": hard_walls, "pushwalls": pushwalls,
        "consumed_ones": consumed,
    }


def _find_refills_raw(grid, xs, ys):
    """Return the RAW refill sprite top-left pixel positions (colour-11 ring)."""
    H, W = len(grid), len(grid[0])
    out = set()
    seen = set()
    for r in range(min(H - 2, 60)):
        for c in range(W - 2):
            if (r, c) in seen:
                continue
            if (grid[r][c] == 11 and grid[r][c + 1] == 11 and grid[r + 1][c] == 11
                    and grid[r + 1][c + 2] == 11 and grid[r + 1][c + 1] != 11):
                out.add((c, r))
                for dr in range(3):
                    for dc in range(3):
                        seen.add((r + dr, c + dc))
    return out


def main():
    d = json.load(open("scratchpad/ls20_l5_settled.json"))
    grid = [tuple(row) for row in d["grid"]]
    parsed = parse_l5(grid)
    gt = json.load(open("scratchpad/ls20_l5_gt.json"))
    # compare push-walls
    gt_pw = {(w["x"], w["y"], w["dx"], w["dy"]) for w in gt["pushwalls"]}
    my_pw = {(sx, sy, dx, dy) for (sx, sy, dx, dy, w, h) in parsed["pushwalls"]}
    print("GT pushwalls:", sorted(gt_pw))
    print("MY pushwalls:", sorted(my_pw))
    print("pushwalls MATCH:", gt_pw == my_pw)
    print("goal", parsed["goal"], "req", parsed["goal_req"])
    print("changers", parsed["changers"])
    print("token", parsed["token"])
    print("refills", sorted(parsed["refills"]))
    print("hard_walls count", len(parsed["hard_walls"]))


if __name__ == "__main__":
    main()
