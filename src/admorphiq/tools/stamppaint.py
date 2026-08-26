"""Stamp-paint tool — reproduce a reference picture on a blank panel with region stamps.

The mechanic, recovered from frames alone:

  * two equal-sided square PANELS sit on the board — one holds a finished picture
    (the reference), the other starts as one flat colour (the canvas);
  * a row of small SWATCHES names the colours that may be used; clicking one selects it;
  * an APPLICATOR sits at one of several discrete slots. The simple actions walk it
    between slots; a COMMIT action floods one fixed region of the canvas with the
    selected colour, and the region depends only on which slot the applicator is in;
  * some slots carry a second, smaller affordance that floods a different region when
    clicked;
  * the level clears when the canvas equals the reference.

⛔ Nothing here is written down. The panel positions, the slot count, the region each slot
paints, the palette and the walk graph are all derived or MEASURED at run time, because a
constant recovered by hand does not transfer to a game whose source we never see.

Three things that are easy to get wrong, each of which decided the design:

  * **the settled frame is the LAST layer, not the first.** A commit renders its whole
    animation into one observation — 15 layers on the sample board — and layer 0 is the
    board BEFORE the stamp landed. Reading it makes every learned region empty.
  * **a region is learned from two commits, not one.** Stamping colour `a` then colour `b`
    at the same slot leaves the canvas differing in exactly the stamped cells and nowhere
    else, whatever the canvas held before. One commit only shows the cells that were not
    already that colour, which under-reads the region and then over-writes work.
  * **the applicator's own colour tracks the selection**, so the selected colour is read
    off the frame instead of assumed — a wrong assumption costs a click per stamp.

The board also draws its remaining ACTION BUDGET as a bar pinned to the bottom row, and it
LOSES when that budget runs out. The bar is what stops the learning phase: exploration is an
investment, and it is only affordable while most of the budget is still there.
"""

from __future__ import annotations

from collections import Counter, deque
from typing import Any

import numpy as np

from admorphiq.tools.base import Step, availability, has_frame, levels_completed
from admorphiq.tools.segment import background, components

__all__ = [
    "StampPaintTool",
    "settled",
    "panels",
    "swatches",
    "applicator",
    "budget_left",
    "peel",
]

Cell = tuple[int, int]
Sig = tuple[int, int, int, int, int]

# A panel small enough to be furniture is not a picture. The sample board's panels are 10
# wide; a swatch interior is 3, and the two must never be confused.
_MIN_PANEL = 6
# Swatch interiors are small squares. Anything bigger is a panel or a piece of scenery.
_SWATCH_SIDES = (2, 3, 4)
# Learning is paid for out of the same budget as the solve. Stop investing once this much
# of the bar is gone, so the plan always has room to run.
_EXPLORE_FLOOR = 0.55
# ...but a tool that knows nothing yet gains nothing by staying silent. Below this the board
# is close enough to its loss condition that spending on learning is not worth the risk.
_LAST_RESORT = 0.2
# Opposite pairs among the four simple actions. Walking a slot graph one edge at a time and
# then probing every reverse edge doubles the cost of exploration; assuming the reverse and
# CORRECTING it from the observed slot costs one action per mistake and usually none.
_OPPOSITE = {1: 2, 2: 1, 3: 4, 4: 3}
_PERPENDICULAR = {1: (3, 4), 2: (3, 4), 3: (1, 2), 4: (1, 2)}


def settled(obs: Any) -> np.ndarray:
    """The board AFTER the action finished — the last layer, never the first."""
    arr = np.asarray(getattr(obs, "frame", None))
    while arr.ndim > 2:
        arr = arr[-1]
    return arr.astype(np.int64)


def _bbox(cells: list[Cell]) -> tuple[int, int, int, int]:
    ys = [c[0] for c in cells]
    xs = [c[1] for c in cells]
    return min(ys), min(xs), max(ys), max(xs)


def _regions(g: np.ndarray) -> list[list[Cell]]:
    """Non-background regions that do not touch the frame edge.

    Connectivity ignores colour, because a picture is many colours and still one object.
    Dropping whatever touches the edge is what separates the board from the chrome: the
    scenery, the swatch strip mounted in it and the budget bar are all one edge-touching
    blob, and every piece the tool cares about is an island.
    """
    h, w = g.shape
    out: list[list[Cell]] = []
    for cells in components(g, background(g)):
        y0, x0, y1, x1 = _bbox(cells)
        if y0 == 0 or x0 == 0 or y1 == h - 1 or x1 == w - 1:
            continue
        out.append(cells)
    return out


def panels(g: np.ndarray) -> list[dict[str, Any]]:
    """Solid square islands big enough to be a picture."""
    out: list[dict[str, Any]] = []
    for cells in _regions(g):
        y0, x0, y1, x1 = _bbox(cells)
        side = y1 - y0 + 1
        if x1 - x0 + 1 != side or side < _MIN_PANEL or len(cells) != side * side:
            continue
        out.append({
            "y": y0, "x": x0, "side": side,
            "colours": {int(g[y][x]) for y, x in cells},
        })
    return out


def _pair(found: list[dict[str, Any]], remembered: tuple[int, int] | None) -> tuple[dict, dict] | None:
    """Split the two equal panels into (canvas, reference).

    The canvas is the flat one at the start of a level. Once it has paint on it that test
    stops working, so the position learned on the level's first frame is what identifies it
    from then on.
    """
    if len(found) != 2 or found[0]["side"] != found[1]["side"]:
        return None
    a, b = found
    if remembered is not None:
        for canvas, ref in ((a, b), (b, a)):
            if (canvas["y"], canvas["x"]) == remembered:
                return canvas, ref
    flat = [p for p in found if len(p["colours"]) == 1]
    if len(flat) != 1:
        return None
    canvas = flat[0]
    return canvas, (b if canvas is a else a)


def swatches(g: np.ndarray, boxes: list[dict[str, Any]]) -> dict[int, Cell]:
    """colour -> a cell to click, read from the small flat squares mounted in the chrome.

    A swatch is a flat square RINGED by one other colour. The ring test is what keeps the
    scenery out: a patch cut from a flat background is ringed by its own colour, and a patch
    straddling two regions has a ring of two.
    """
    h, w = g.shape
    keep = [(p["y"], p["x"], p["y"] + p["side"] - 1, p["x"] + p["side"] - 1) for p in boxes]
    best: dict[int, Cell] = {}
    for side in _SWATCH_SIDES:
        found: dict[int, Cell] = {}
        clash = False
        for y in range(1, h - side):
            for x in range(1, w - side):
                block = g[y:y + side, x:x + side]
                inner = {int(v) for v in block.ravel()}
                if len(inner) != 1:
                    continue
                colour = inner.pop()
                ring = {int(v) for v in g[y - 1, x - 1:x + side + 1]}
                ring |= {int(v) for v in g[y + side, x - 1:x + side + 1]}
                ring |= {int(v) for v in g[y - 1:y + side + 1, x - 1]}
                ring |= {int(v) for v in g[y - 1:y + side + 1, x + side]}
                if len(ring) != 1 or ring.pop() == colour:
                    continue
                if any(y0 <= y <= y1 and x0 <= x <= x1 for y0, x0, y1, x1 in keep):
                    continue
                if colour in found:
                    clash = True
                found[colour] = (y + side // 2, x + side // 2)
        if not clash and len(found) > len(best):
            best = found
    return best if len(best) >= 2 else {}


def applicator(g: np.ndarray, boxes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The islands that are neither panel — biggest first.

    The biggest is the thing the simple actions walk; anything else beside it is a second
    affordance offered at that slot, and it is clicked rather than committed.
    """
    skip = {(p["y"], p["x"], p["side"]) for p in boxes}
    out: list[dict[str, Any]] = []
    for cells in _regions(g):
        y0, x0, y1, x1 = _bbox(cells)
        if (y0, x0, y1 - y0 + 1) in skip:
            continue
        colours = Counter(int(g[y][x]) for y, x in cells)
        cy = sum(c[0] for c in cells) / len(cells)
        cx = sum(c[1] for c in cells) / len(cells)
        fill = colours.most_common(1)[0][0]
        inner = [c for c in cells if int(g[c[0]][c[1]]) == fill] or cells
        click = min(inner, key=lambda c: (c[0] - cy) ** 2 + (c[1] - cx) ** 2)
        out.append({
            "sig": (y0, x0, y1, x1, len(cells)),
            "fill": fill,
            "click": click,
        })
    out.sort(key=lambda d: -d["sig"][4])
    return out


def budget_left(g: np.ndarray) -> float | None:
    """Fraction of the action budget still drawn on the bottom row, when one is drawn.

    Two runs and no more: a bar that empties from one end. Anything else is board content
    and this returns None rather than guess.
    """
    row = [int(v) for v in g[-1]]
    head = row[0]
    k = 0
    while k < len(row) and row[k] == head:
        k += 1
    if k == len(row):
        return 1.0
    if len(set(row[k:])) != 1:
        return None
    return k / len(row)


def peel(
    canvas: np.ndarray,
    target: np.ndarray,
    ops: list[tuple[Any, np.ndarray]],
    colours: set[int],
    beam: int = 8,
    depth: int = 10,
) -> list[list[tuple[Any, int]]]:
    """Every way to reach the reference by stamping, found back to front.

    Stamps overwrite, so the LAST one placed decides its whole region: it is admissible only
    when the reference is one colour everywhere the stamp still decides. Peeling from the end
    turns "which sequence paints this picture" into a covering problem, and the beam keeps
    several coverings so the caller can pick the one that is cheapest to walk.
    """
    todo = np.ones(canvas.shape, dtype=bool)
    need = canvas != target
    frontier = [(todo, need, ())]
    done: list[tuple[tuple[Any, int], ...]] = []
    for _ in range(depth):
        grown: list[tuple[np.ndarray, np.ndarray, tuple]] = []
        for left, want, seq in frontier:
            for key, region in ops:
                live = region & left
                if not (live & want).any():
                    continue
                vals = {int(v) for v in target[live]}
                if len(vals) != 1:
                    continue
                colour = vals.pop()
                if colour not in colours:
                    continue
                nxt = (left & ~region, want & ~region, seq + ((key, colour),))
                if not nxt[1].any():
                    done.append(nxt[2])
                else:
                    grown.append(nxt)
        if not grown:
            break
        grown.sort(key=lambda t: (int(t[1].sum()), len(t[2])))
        frontier = grown[:beam]
    return [list(reversed(seq)) for seq in done]


class StampPaintTool:
    """Harness tool wrapping the stamp-paint mechanic."""

    name = "stamppaint"

    def __init__(self) -> None:
        # The mechanic — measured once, carried across levels.
        self._ops: dict[tuple[Sig, Sig | None], np.ndarray] = {}
        self._edges: dict[tuple[Sig, int], Sig] = {}
        self._tried: dict[Sig, set[int]] = {}
        self._slots: set[Sig] = set()
        self._survey: set[Sig] = set()
        self._visited: set[Sig] = set()
        self._last_move: int | None = None
        self._since_new = 0
        self._from: tuple[Sig, int] | None = None
        # Per level.
        self._canvas_at: tuple[int, int] | None = None
        self._level: int | None = None
        self._learn: dict[str, Any] | None = None
        self._plan: list[tuple[Any, int]] | None = None
        self._seen: Counter[str] = Counter()

    # -- lifecycle ---------------------------------------------------------

    def reset(self) -> None:
        """Drop the level, keep the mechanic. A new board re-teaches nothing."""
        self._canvas_at = None
        self._learn = None
        self._plan = None
        self._from = None
        self._seen = Counter()
        self._visited = set()

    def observe(self, prev: np.ndarray, action: Step, changed: bool) -> None:
        """Stateless: every reading is taken from the settled frame inside propose."""

    # -- perception --------------------------------------------------------

    def _read(self, obs: Any) -> dict[str, Any] | None:
        g = settled(obs)
        if g.ndim != 2 or g.shape[0] < 8 or g.shape[0] != g.shape[1]:
            return None
        found = panels(g)
        split = _pair(found, self._canvas_at)
        if split is None:
            return None
        canvas, ref = split
        pal = swatches(g, found)
        if not pal:
            return None
        parts = applicator(g, found)
        if not parts:
            return None
        side = canvas["side"]
        cy, cx = canvas["y"], canvas["x"]
        ry, rx = ref["y"], ref["x"]
        return {
            "g": g,
            "canvas": g[cy:cy + side, cx:cx + side],
            "target": g[ry:ry + side, rx:rx + side],
            "origin": (cy, cx),
            "palette": pal,
            "slot": parts[0]["sig"],
            "colour": parts[0]["fill"],
            "extras": parts[1:],
        }

    def detect(self, frames: list[Any], obs: Any) -> float:
        """Two equal panels, a palette that can paint the reference, and a walkable applicator.

        The palette test is the load-bearing one: a picture whose colours the swatches cannot
        supply is not this mechanic, however square its panels are.
        """
        if not has_frame(obs):
            return 0.0
        simple, action6 = availability(obs)
        if not action6 or 5 not in simple or len({1, 2, 3, 4} & set(simple)) < 2:
            return 0.0
        try:
            read = self._read(obs)
        except Exception:  # noqa: BLE001 - detect must never crash the harness
            return 0.0
        if read is None:
            return 0.0
        wanted = {int(v) for v in read["target"].ravel()}
        blank = {int(v) for v in read["canvas"].ravel()}
        if not wanted <= (set(read["palette"]) | blank):
            return 0.0
        if read["colour"] not in read["palette"]:
            return 0.0
        return 0.85

    # -- slot graph --------------------------------------------------------

    def _walkmap(self) -> dict[tuple[Sig, int], Sig]:
        """Measured edges, plus the reverse of each one assumed until measured otherwise.

        Probing all four directions out of every slot doubles what exploration costs. The
        reverse of a move that worked is the one assumption these controls reliably support,
        and a wrong one is corrected by the very next frame at the price of one action.
        """
        guess: dict[tuple[Sig, int], Sig] = {}
        for (src, act), dst in self._edges.items():
            if dst == src:
                continue
            guess[(dst, _OPPOSITE[act])] = src
        guess.update(self._edges)
        return guess

    def _routes(self, here: Sig) -> dict[Sig, tuple[int, int]]:
        """slot -> (hops, first action) for every slot reachable from `here`."""
        walk = self._walkmap()
        out: dict[Sig, tuple[int, int]] = {}
        queue: deque[tuple[Sig, int, int]] = deque()
        for act in (1, 2, 3, 4):
            nxt = walk.get((here, act))
            if nxt is not None and nxt != here and nxt not in out:
                out[nxt] = (1, act)
                queue.append((nxt, 1, act))
        while queue:
            node, hops, first = queue.popleft()
            for act in (1, 2, 3, 4):
                nxt = walk.get((node, act))
                if nxt is None or nxt == node or nxt in out or nxt == here:
                    continue
                out[nxt] = (hops + 1, first)
                queue.append((nxt, hops + 1, first))
        return out

    def _probe_order(self, here: Sig) -> list[int]:
        """Which direction to try next when hunting for an unseen slot.

        The reverse of the move that just worked leads straight back where we came from, so
        it goes last; the direction that just worked goes first, because a layout that
        rewarded it once usually rewards it again.
        """
        tried = self._tried.setdefault(here, set())
        order: list[int] = []
        if self._last_move is not None:
            order = [self._last_move, *_PERPENDICULAR[self._last_move], _OPPOSITE[self._last_move]]
        order += [1, 2, 3, 4]
        out: list[int] = []
        for act in order:
            if act not in tried and act not in out:
                out.append(act)
        return out

    # -- learning ----------------------------------------------------------

    def _begin_learn(self, key: tuple[Sig, Sig | None], read: dict[str, Any]) -> Step | None:
        """Queue the two commits whose DIFFERENCE is the stamped region.

        Stamping colour `a` and then colour `b` at one slot leaves the canvas differing in
        exactly the stamped cells, whatever it held before. A single commit only reveals the
        cells that were not already that colour, which under-reads the region — and a region
        read short is a region that silently overwrites finished work.
        """
        pal = read["palette"]
        first = read["colour"] if read["colour"] in pal else min(pal)
        second = min(c for c in pal if c != first)
        if key[1] is None:
            act: Step = (5, None)
        else:
            spot = next((e["click"] for e in read["extras"] if e["sig"] == key[1]), None)
            if spot is None:
                return None
            act = (6, (spot[1], spot[0]))
        steps: list[Step] = []
        if read["colour"] != first:
            steps.append(self._pick(pal, first))
        steps.append(act)
        mark = len(steps) - 1
        steps.append(self._pick(pal, second))
        steps.append(act)
        self._learn = {
            "key": key, "steps": steps, "i": 0,
            "a": mark, "b": len(steps) - 1, "before": None, "slot": key[0],
        }
        return self._advance_learn(read)

    @staticmethod
    def _pick(palette: dict[int, Cell], colour: int) -> Step:
        y, x = palette[colour]
        return (6, (x, y))

    def _advance_learn(self, read: dict[str, Any]) -> Step | None:
        job = self._learn
        if job is None:
            return None
        if read["slot"] != job["slot"]:
            self._learn = None                     # the applicator moved under us
            return None
        done = job["i"] - 1
        if done == job["a"]:
            job["before"] = read["canvas"].copy()
        elif done == job["b"]:
            before = job["before"]
            self._learn = None
            if before is None or before.shape != read["canvas"].shape:
                return None
            region = before != read["canvas"]
            self._ops[job["key"]] = region
            if job["key"][1] is not None and region.any():
                # A brand-new kind of affordance means the board grew one this level; every
                # slot NOT YET LOOKED AT may have grown one too. ⛔ Slots already seen this
                # level are excluded: re-adding them each time an affordance was learned put
                # visited slots back in the queue and sent the survey back down the ring it
                # had just walked.
                self._survey |= self._slots - self._visited
            return None
        step = job["steps"][job["i"]]
        job["i"] += 1
        return step

    def _needs_visit(self, read: dict[str, Any]) -> bool:
        """Is anything left that is worth paying actions to learn?"""
        here = read["slot"]
        if (here, None) not in self._ops:
            return True
        if any((here, e["sig"]) not in self._ops for e in read["extras"]):
            return True
        return bool(self._survey - {here}) or self._since_new < 2

    # -- planning ----------------------------------------------------------

    def _cost(self, plan: list[tuple[Any, int]], here: Sig, colour: int,
              routes: dict[Sig, tuple[int, int]]) -> int | None:
        total = 0
        for key, want in plan:
            if key[0] != here:
                leg = routes.get(key[0])
                if leg is None:
                    return None
                total += leg[0]
                here = key[0]
                routes = self._routes(here)
            total += 1
            if want != colour:
                total += 1
                colour = want
        return total

    def _make_plan(self, read: dict[str, Any]) -> list[tuple[Any, int]] | None:
        here = read["slot"]
        routes = self._routes(here)
        ops = [
            (key, region) for key, region in self._ops.items()
            if region.any() and (key[0] == here or key[0] in routes)
        ]
        if not ops:
            return None
        best: tuple[int, list[tuple[Any, int]]] | None = None
        for plan in peel(read["canvas"], read["target"], ops, set(read["palette"])):
            price = self._cost(plan, here, read["colour"], routes)
            if price is not None and (best is None or price < best[0]):
                best = (price, plan)
        return best[1] if best else None

    # -- the loop ----------------------------------------------------------

    def propose(self, frames: list[Any], obs: Any) -> list[Step]:
        if not has_frame(obs):
            return []
        level = levels_completed(obs)
        if level != self._level:
            self._level = level
            self.reset()
        read = self._read(obs)
        if read is None:
            return []
        if self._canvas_at is None:
            self._canvas_at = read["origin"]
        if np.array_equal(read["canvas"], read["target"]):
            return []

        self._arrive(read)

        # ⛔ A board seen too many times means the plan is cycling rather than progressing.
        # This game LOSES on an action budget, so silence keeps whatever is already won.
        stamp = f"{read['slot']}|{read['colour']}|{read['canvas'].tobytes().hex()}"
        self._seen[stamp] += 1
        if self._seen[stamp] > 4:
            return []

        step = self._advance_learn(read)
        if step is not None:
            return [step]

        left = budget_left(read["g"])
        if self._needs_visit(read):
            # Learning is an INVESTMENT and it is only affordable while most of the budget is
            # still there. The exception is a tool handed a board it knows nothing about with
            # the budget half gone: refusing to learn there guarantees nothing, so learn while
            # any real room remains — but never in the last stretch, because this board LOSES
            # when the bar empties and a loss costs the levels already won.
            rich = left is None or left > _EXPLORE_FLOOR
            if not rich and self._plan is None:
                self._plan = self._make_plan(read)
                rich = not self._plan and (left is None or left > _LAST_RESORT)
            if rich:
                step = self._explore(read)
                if step is not None:
                    return [step]

        return self._execute(read)

    def _arrive(self, read: dict[str, Any]) -> None:
        here = read["slot"]
        came = self._from
        self._from = None
        if came is not None:
            self._edges[(came[0], came[1])] = here
            if came[0] != here:
                self._last_move = came[1]
        if here not in self._slots:
            self._slots.add(here)
            self._since_new = 0
        elif came is not None and came[0] != here:
            self._since_new += 1
        self._tried.setdefault(here, set())
        self._visited.add(here)
        self._survey.discard(here)

    def _explore(self, read: dict[str, Any]) -> Step | None:
        here = read["slot"]
        if (here, None) not in self._ops:
            return self._begin_learn((here, None), read)
        for extra in read["extras"]:
            if (here, extra["sig"]) not in self._ops:
                return self._begin_learn((here, extra["sig"]), read)
        routes = self._routes(here)
        # ⛔ NEAREST first, never a fixed order. Walking the outstanding slots in the order
        # their signatures happen to sort in made the survey zigzag across the ring and cost
        # 23 actions where one lap costs 7 — measured, and it is what put this board over its
        # own human action count.
        wanted = [s for s in self._slots if (s, None) not in self._ops] + list(self._survey)
        legs = [(routes[s][0], routes[s][1]) for s in wanted if s != here and s in routes]
        if legs:
            return self._walk(here, min(legs)[1])
        # Two moves that turn up nothing new, with every known slot mutually reachable, is
        # where hunting stops. Counting only moves that actually CHANGED slot is load-bearing:
        # a direction the layout refuses is information, not a dead end, and counting those
        # cut the walk short after four of the eight slots.
        if self._since_new < 2:
            nxt = next(iter(self._probe_order(here)), None)
            if nxt is not None:
                return self._walk(here, nxt)
        return None

    def _walk(self, here: Sig, act: int) -> Step:
        self._tried.setdefault(here, set()).add(act)
        self._from = (here, act)
        return (act, None)

    def _execute(self, read: dict[str, Any]) -> list[Step]:
        if self._plan is None:
            self._plan = self._make_plan(read)
        if not self._plan:
            self._plan = None
            return []
        (slot, extra), want = self._plan[0]
        here = read["slot"]
        if here != slot:
            leg = self._routes(here).get(slot)
            if leg is None:
                self._plan = None
                return []
            return [self._walk(here, leg[1])]
        if read["colour"] != want:
            if want not in read["palette"]:
                self._plan = None
                return []
            return [self._pick(read["palette"], want)]
        self._plan.pop(0)
        if extra is None:
            return [(5, None)]
        spot = next((e["click"] for e in read["extras"] if e["sig"] == extra), None)
        if spot is None:
            self._plan = None
            return []
        return [(6, (spot[1], spot[0]))]
