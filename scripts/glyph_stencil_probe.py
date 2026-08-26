"""Recover the "paint the stencil onto the tile lattice" mechanic from frames alone.

⛔ No game id, no coordinate constant, no tile size, no pitch. Everything below is
DERIVED from the frame, because a constant recovered by hand does not transfer to a
private game — which is the whole point of the generic tool track.

The mechanic, as measured on ft09 (round r101):
  * the board is a lattice of equal square tiles, uniformly coloured;
  * one or more tiles instead carry a 3x3 STENCIL drawn at every second pixel;
  * the stencil's centre pixel is the MARKER colour a click paints with;
  * a stencil cell whose ink is the "fill" ink means "paint that neighbour".

The one structural trap, measured: the board sits inside a coloured FRAME, and a frame
touches every tile, so plain connected components merge the whole board into one blob.
`_peel` removes a container's own colour and re-runs the split — a generic step, not an
ft09 one: any component far larger than its siblings is a container, not a tile.
"""

from __future__ import annotations

import sys
from collections import Counter
from typing import Any

sys.path.insert(0, "src")

from admorphiq.adapters25.base import canonical_layer  # noqa: E402

Grid = list[list[int]]
Cell = tuple[int, int]


def _components(g: Grid, blocked: set[int]) -> list[list[Cell]]:
    n = len(g)
    seen = [[False] * n for _ in range(n)]
    out: list[list[Cell]] = []
    for y in range(n):
        for x in range(n):
            if g[y][x] in blocked or seen[y][x]:
                continue
            stack = [(y, x)]
            seen[y][x] = True
            cells: list[Cell] = []
            while stack:
                cy, cx = stack.pop()
                cells.append((cy, cx))
                for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    ny, nx = cy + dy, cx + dx
                    if 0 <= ny < n and 0 <= nx < n and not seen[ny][nx] and g[ny][nx] not in blocked:
                        seen[ny][nx] = True
                        stack.append((ny, nx))
            out.append(cells)
    return out


def _peel(g: Grid, comps: list[list[Cell]], blocked: set[int]) -> list[tuple[list[Cell], bool]]:
    """A component far larger than its siblings is a CONTAINER; drop its colour and re-split.

    The flag says whether the piece came OUT of a container. That is not bookkeeping: a game
    that draws a frame around one panel is telling you which panel is live, and clicking a
    tile in a dead panel is fatal on ft09 (measured — an out-of-board click resets the level).
    """
    if len(comps) < 2:
        return [(c, False) for c in comps]
    sizes = sorted(len(c) for c in comps)
    typical = sizes[len(sizes) // 2]
    out: list[tuple[list[Cell], bool]] = []
    for c in comps:
        if len(c) <= 4 * typical:
            out.append((c, False))
            continue
        wall = Counter(g[y][x] for y, x in c).most_common(1)[0][0]
        inner = {(y, x) for y, x in c}
        sub = _components(
            [[g[y][x] if (y, x) in inner and g[y][x] != wall else -1 for x in range(len(g))] for y in range(len(g))],
            blocked | {-1, wall},
        )
        out.extend([(s, True) for s in sub] if sub else [(c, False)])
    return out


def tiles(g: Grid) -> dict[Cell, dict[str, Any]]:
    """Square, equal-sized blocks on a regular lattice — the board's cells."""
    bg = Counter(v for row in g for v in row).most_common(1)[0][0]
    comps = _peel(g, _components(g, {bg}), {bg})
    found: dict[Cell, dict[str, Any]] = {}
    for c, framed in comps:
        y0 = min(q[0] for q in c)
        x0 = min(q[1] for q in c)
        h = max(q[0] for q in c) - y0 + 1
        w = max(q[1] for q in c) - x0 + 1
        if h != w or h < 4 or len(c) != h * w:
            continue
        found[(y0, x0)] = {"size": h, "colours": {g[y][x] for y, x in c}, "framed": framed}
    if not found:
        return {}
    side = Counter(t["size"] for t in found.values()).most_common(1)[0][0]
    kept = {o: t for o, t in found.items() if t["size"] == side}
    live = {o: t for o, t in kept.items() if t["framed"]}
    return live or kept


def all_tiles(g: Grid) -> dict[Cell, dict[str, Any]]:
    """Every panel, live or not — the worked examples live in the dead ones."""
    bg = Counter(v for row in g for v in row).most_common(1)[0][0]
    found: dict[Cell, dict[str, Any]] = {}
    for c, framed in _peel(g, _components(g, {bg}), {bg}):
        y0 = min(q[0] for q in c)
        x0 = min(q[1] for q in c)
        h = max(q[0] for q in c) - y0 + 1
        w = max(q[1] for q in c) - x0 + 1
        if h != w or h < 4 or len(c) != h * w:
            continue
        found[(y0, x0)] = {"size": h, "colours": {g[y][x] for y, x in c}, "framed": framed}
    if not found:
        return {}
    side = Counter(t["size"] for t in found.values()).most_common(1)[0][0]
    return {o: t for o, t in found.items() if t["size"] == side}


def _pitch(origins: list[Cell], side: int = 0) -> int:
    """The lattice step is the COMMONEST gap, never the smallest.

    Measured: taking the minimum read the 2-pixel offset between two unrelated panels as the
    board's pitch, and every neighbour lookup then missed.
    """
    gaps: list[int] = []
    for axis in (0, 1):
        vals = sorted({o[axis] for o in origins})
        gaps += [b - a for a, b in zip(vals, vals[1:]) if b - a >= side]
    return Counter(gaps).most_common(1)[0][0] if gaps else 0


def _stencil(g: Grid, origin: Cell) -> tuple[int, list[list[int]]]:
    y0, x0 = origin
    return g[y0 + 2][x0 + 2], [[g[y0 + 2 * i][x0 + 2 * j] for j in range(3)] for i in range(3)]


def read_code(g: Grid, board: dict[Cell, dict[str, Any]], pitch: int) -> dict[int, bool]:
    """Learn ink -> tile-colour from the WORKED EXAMPLES already on screen.

    ⛔ Do not infer it from ink frequency. Measured on ft09 level 1: the two inks appear four
    times each, so frequency cannot separate "paint this one" from "leave this one", and the
    tie-break that picked the smaller colour was right by luck on level 1 and wrong later.

    The panels around the live board are solved instances of the same stencil. A panel counts
    as worked only when its ink -> colour map is ONE-TO-ONE: an untouched board maps every ink
    to the blank colour, which is a map but carries no code.

    What is learned is a ROLE — paint this cell, or leave it — never an absolute colour.
    Measured: ft09 level 1 paints in colour 8 and level 2 in colour 12, so a code recorded as
    "ink 0 means colour 8" is silently dead one level later, which is exactly how it failed.
    """
    code: Counter[tuple[int, int]] = Counter()
    for origin, tile in board.items():
        if len(tile["colours"]) == 1:
            continue
        marker, ink = _stencil(g, origin)
        y0, x0 = origin
        seen: dict[int, set[int]] = {}
        for i in range(3):
            for j in range(3):
                if (i, j) == (1, 1):
                    continue
                nb = board.get((y0 + (i - 1) * pitch, x0 + (j - 1) * pitch))
                if nb is None or len(nb["colours"]) != 1:
                    continue
                seen.setdefault(ink[i][j], set()).add(next(iter(nb["colours"])))
        if len(seen) < 2 or any(len(v) != 1 for v in seen.values()):
            continue                                   # ambiguous, or an untouched board
        if len({next(iter(v)) for v in seen.values()}) < len(seen):
            continue                                   # not one-to-one: no code here
        for k, v in seen.items():
            code[(k, next(iter(v)) == marker)] += 1
    out: dict[int, bool] = {}
    for (k, v), _ in code.most_common():
        out.setdefault(k, v)
    return out


def plan(g: Grid, code: dict[int, bool] | None = None) -> tuple[list[Cell], dict[int, bool]]:
    """Every click the live stencils call for, plus the code in force.

    The code is CARRIED between levels. Measured on ft09: level 1 surrounds the live board
    with solved panels that define ink -> colour, and level 2 ships the bare board with no
    example on screen at all. A tool that re-derives the code from each frame goes blind the
    moment the game stops repeating the lesson.
    """
    board = tiles(g)
    if not board:
        return [], code or {}
    side = next(iter(board.values()))["size"]
    pitch = _pitch(list(board), side)
    if pitch <= 0:
        return [], code or {}
    every = all_tiles(g)
    learned = read_code(g, every, _pitch(list(every), side) or pitch)
    code = learned or (code or {})
    if not code:
        return [], code
    palette = {next(iter(t["colours"])) for t in board.values() if len(t["colours"]) == 1}
    clicks: list[Cell] = []
    for origin, tile in board.items():
        if len(tile["colours"]) == 1:
            continue
        marker, ink = _stencil(g, origin)
        rest = sorted(palette - {marker}) or sorted(palette)
        if not rest:
            continue
        other = rest[0]
        y0, x0 = origin
        for i in range(3):
            for j in range(3):
                if (i, j) == (1, 1):
                    continue
                role = code.get(ink[i][j])
                if role is None:
                    continue
                # A stencil states BOTH halves: this cell must carry the marker, or must carry
                # the other colour. Levels 1-2 start uniform so only the paint half ever fires;
                # level 3 starts mixed and needs the "must NOT be the marker" half too.
                want = marker if role else other
                nb = board.get((y0 + (i - 1) * pitch, x0 + (j - 1) * pitch))
                if nb is None or len(nb["colours"]) != 1 or nb["colours"] == {want}:
                    continue
                clicks.append((y0 + (i - 1) * pitch + 2, x0 + (j - 1) * pitch + 2))
    return sorted(set(clicks)), code


def main() -> None:
    from arc_agi import Arcade, OperationMode
    from arcengine import GameAction

    title = sys.argv[1] if len(sys.argv) > 1 else "ft09"
    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    info = next(i for i in arcade.get_environments() if (i.title or i.game_id).lower().startswith(title))
    env = arcade.make(info.game_id)
    obs = env.reset()
    done = 0
    acted = 0
    stale = 0
    code: dict[int, bool] = {}
    # Replan after EVERY click. Measured: the frame that follows a level-up still shows the
    # board just finished, so a batch computed once executes the previous level's plan against
    # the next level's board. One click dismisses it and the real board is readable.
    while acted < 200 and stale < 3:
        if not (getattr(obs, "frame", None) or []):
            print("     the frame went empty — stopping")
            break
        g = canonical_layer(obs)
        board = tiles(g)
        clicks, code = plan(g, code)
        if not clicks:
            if stale == 0:
                every = all_tiles(g)
                side = next(iter(board.values()))["size"] if board else 0
                stencils = [o for o, v in board.items() if len(v["colours"]) > 1]
                print(f"     stalled at level {done}: live={len(board)} all={len(every)} side={side} "
                      f"pitch={_pitch(list(board), side) if board else 0} stencils={stencils} code={code}")
                pit = _pitch(list(board), side) if board else 8
                for o in stencils:
                    mk, ink = _stencil(g, o)
                    nb = [[(lambda v: None if v is None else sorted(v["colours"]))(
                            board.get((o[0] + (i - 1) * pit, o[1] + (j - 1) * pit)))
                           for j in range(3)] for i in range(3)]
                    print(f"       {o} marker={mk} ink={ink} neighbours={nb}")
            stale += 1
            obs = env.step(GameAction.ACTION6, data={"x": 0, "y": 0})
            acted += 1
            continue
        stale = 0
        y, x = clicks[0]
        obs = env.step(GameAction.ACTION6, data={"x": x, "y": y})
        acted += 1
        new = int(getattr(obs, "levels_completed", done) or 0)
        if new < done:
            print(f"     level RESET ({done} -> {new}) after {acted} actions — stopping")
            break
        if new != done:
            side = next(iter(board.values()))["size"]
            print(f"  level {new}: cleared — board {len(board)} tiles, side {side}, "
                  f"pitch {_pitch(list(board), side)} ({acted} actions so far)")
            done = new
    print(f"{title} glyph-stencil: {done} levels in {acted} actions")


if __name__ == "__main__":
    main()
