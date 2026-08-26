"""Read a rewrite grammar off the board and spell the translated string.

The mechanic, recovered from the frame alone (verified against the sample board this
was built on, 2026-08-27):

* Every piece on the board is a FRAMED TILE: a solid square of one colour with a
  stencil of a second colour painted inside it. The frame colour is the piece's
  ALPHABET; the stencil is its LETTER. Letters are drawn at an arbitrary rotation
  per board, so a letter's identity is its stencil canonicalised over the four
  rotations -- measured: all 21 letters of the three alphabets stay distinct under
  that canonicalisation, so nothing is lost by collapsing rotation.
* Tiles sit shoulder to shoulder in runs. Two runs on the same row are the two
  halves of ONE REWRITE RULE when the gap between them is not empty -- a rule bar
  is painted across the gap, behind the tiles, so only the gap shows it. A gap that
  is flat background separates two independent rules on the same row.
* Rows carrying no rule are the PROBLEM: the topmost is the SOURCE string, the rest
  are the ANSWER slots. Rules are ordered top-to-bottom then left-to-right, and the
  source is parsed greedily -- at each position the FIRST rule whose left side
  matches wins. The answer must be the concatenation of the winning right sides.
* Three translation depths exist. Which one a board uses is not stated anywhere, but
  it is decidable: only the right depth yields a string of the answer's length in the
  answer's alphabet. `plain` emits the matched rule's right side; `double` looks that
  right side up as another rule's left side and emits ITS right side; `tree` expands
  each letter of the right side through the rule it heads.

Control (four simple actions, no click):
    3 / 4  move the cursor one slot backwards / forwards, wrapping
    1 / 2  cycle the selected slot's letter backwards / forwards through its alphabet

The cycle order is NOT visible in the frame, so the tool learns it: every letter
change it causes is recorded as a successor edge, and a slot is driven whichever way
the learned edges already prove is shorter. This costs a handful of actions on the
first slot and nothing afterwards.

⛔ A wrong action is charged: the board carries an action budget (the bar pinned to
the bottom edge) and ends the game when it runs out. So `detect` returns 0.0 unless
the whole target string has actually been derived -- a board that merely looks like
tiles gets no bid.
"""

from __future__ import annotations

from typing import Any, NamedTuple

import numpy as np

from admorphiq.tools import segment
from admorphiq.tools.base import Step, availability, has_frame, levels_completed

__all__ = ["RuleRewriteTool"]

Canon = tuple[int, ...]

# Tile sides worth testing. Below 5 a frame plus a stencil does not fit; above 13 a
# 64-wide board cannot hold a row of them.
_SIDES = range(5, 14)
# A grammar needs at least one rule (two tiles) plus a source and an answer slot.
_MIN_TILES = 4
# How far to walk a letter ring before declaring it broken. The ring's real size is
# never assumed -- it is whatever the learned successor edges close into.
_MAX_RING = 16


class Tile(NamedTuple):
    """One framed tile: where it is, which alphabet frames it, which letter it shows."""

    y: int
    x: int
    side: int
    frame_colour: int
    letter: Canon


class Rule(NamedTuple):
    """One rewrite rule: the run left of a bar, the run right of it."""

    lhs: tuple[Tile, ...]
    rhs: tuple[Tile, ...]


class Board(NamedTuple):
    """Everything the plan needs, all of it read off one frame."""

    side: int
    rules: tuple[Rule, ...]
    source: tuple[Tile, ...]
    answer: tuple[Tile, ...]
    cursor: int | None          # index into answer, or into the flattened rule sets
    edit_rules: bool            # True when the cursor sits on a rule, not on an answer slot
    sets: tuple[tuple[Tile, ...], ...]  # the editable groups, in cursor order


def _grid(obs: Any) -> np.ndarray:
    """The CURRENT board: the LAST layer, not the first.

    One action can render many frames -- a win animation here runs 36 of them -- and the
    level that follows is already drawn in the final layer. Reading the first layer showed
    the board that had just been finished, so the tool saw no cursor and idled away one
    action at every level boundary. Measured: 5 actions over a six-level run.
    """
    fr = np.asarray(getattr(obs, "frame", None))
    if fr.ndim >= 3:
        fr = fr[-1]
    return fr.astype(np.int64)


# --- perception -------------------------------------------------------------------


def _canon(mask: np.ndarray) -> Canon:
    """A stencil's identity, taken over the four rotations it may be drawn at."""
    best: Canon | None = None
    for k in range(4):
        t = tuple(int(v) for v in np.rot90(mask, k).ravel())
        if best is None or t < best:
            best = t
    return best  # type: ignore[return-value]


def _framed_tiles(g: np.ndarray, side: int, backgrounds: set[int]) -> list[Tile]:
    """Every `side`x`side` square with a flat frame and a two-colour interior.

    Requiring the frame colour to be a NON-background colour is load-bearing: without
    it the cursor's own bracket, sitting in a field of backdrop, reads as a tile.
    """
    h, w = g.shape
    if side + 2 > min(h, w):
        return []
    win = np.lib.stride_tricks.sliding_window_view(g, (side, side))
    ring = np.zeros((side, side), dtype=bool)
    ring[0, :] = ring[-1, :] = True
    ring[:, 0] = ring[:, -1] = True

    border = win[:, :, ring]
    corner = border[:, :, :1]
    flat = (border == corner).all(axis=2)

    inner = win[:, :, 1:side - 1, 1:side - 1]
    inner_flat = inner.reshape(inner.shape[0], inner.shape[1], -1)
    is_ink = inner_flat != corner
    # All ink cells must be the same colour: compare every one of them to their max.
    ink_hi = np.where(is_ink, inner_flat, np.int64(-1 << 30)).max(axis=2, keepdims=True)
    one_ink = ((inner_flat == ink_hi) | ~is_ink).all(axis=2) & is_ink.any(axis=2)

    ok = flat & one_ink
    for c in backgrounds:
        ok &= corner[:, :, 0] != c

    out: list[Tile] = []
    taken = np.zeros(g.shape, dtype=bool)
    for y, x in zip(*np.where(ok)):
        y, x = int(y), int(x)
        if taken[y:y + side, x:x + side].any():
            continue
        taken[y:y + side, x:x + side] = True
        p = int(g[y, x])
        block = g[y + 1:y + side - 1, x + 1:x + side - 1]
        out.append(Tile(y, x, side, p, _canon((block != p).astype(np.int8))))
    return out


def _rows(tiles: list[Tile]) -> list[list[Tile]]:
    """Tiles grouped by their top edge, each row left to right."""
    by_y: dict[int, list[Tile]] = {}
    for t in tiles:
        by_y.setdefault(t.y, []).append(t)
    return [sorted(by_y[y], key=lambda t: t.x) for y in sorted(by_y)]


def _runs(row: list[Tile], side: int) -> list[list[Tile]]:
    """Split a row wherever the tiles stop touching."""
    out: list[list[Tile]] = [[row[0]]]
    for t in row[1:]:
        if t.x == out[-1][-1].x + side:
            out[-1].append(t)
        else:
            out.append([t])
    return out


def _read_board(g: np.ndarray) -> Board | None:
    """Parse the whole board, or return None if it is not this kind of board."""
    backgrounds = segment.background(g, 2)
    best: tuple[int, list[Tile]] | None = None
    for side in _SIDES:
        tiles = _framed_tiles(g, side, backgrounds)
        if len(tiles) < _MIN_TILES:
            continue
        if best is None or len(tiles) > len(best[1]):
            best = (side, tiles)
    if best is None:
        return None
    side, tiles = best

    rules: list[tuple[int, int, Rule]] = []
    problem: list[list[Tile]] = []
    for row in _rows(tiles):
        runs = _runs(row, side)
        linked = False
        for a, b in zip(runs, runs[1:]):
            x0 = a[-1].x + side
            x1 = b[0].x
            gap = g[row[0].y:row[0].y + side, x0:x1]
            # A bar painted behind the tiles shows only in the gap, so a gap that is
            # not one flat colour is a rule; a flat gap separates two rules.
            if gap.size and len({int(v) for v in gap.ravel()}) > 1:
                rules.append((row[0].y, x0, Rule(tuple(a), tuple(b))))
                linked = True
        if not linked:
            problem.append(row)
    if not rules or len(problem) < 2:
        return None
    # The problem must sit below every rule, or we have mis-read the board.
    if problem[0][0].y < max(r[0] for r in rules):
        return None

    rules.sort(key=lambda r: (r[0], r[1]))
    ordered = tuple(r[2] for r in rules)
    source = tuple(problem[0])
    answer = tuple(t for row in problem[1:] for t in row)

    sets = tuple(s for r in ordered for s in (r.lhs, r.rhs))
    cursor, edit_rules = _read_cursor(g, side, tiles, answer, sets)
    return Board(side, ordered, source, answer, cursor, edit_rules, sets)


def _read_cursor(
    g: np.ndarray,
    side: int,
    tiles: list[Tile],
    answer: tuple[Tile, ...],
    sets: tuple[tuple[Tile, ...], ...],
) -> tuple[int | None, bool]:
    """Which slot is selected, and is it an answer slot or a whole rule side?

    The cursor is a bracket drawn above and below its target in a colour used nowhere
    else, so its column extent names the target and its row extent names the ROW. Both
    are needed: on a board whose rules stack in columns, three different rule sides
    occupy the same columns, and matching on columns alone drove every letter change
    into the wrong rule (measured, and it cost a whole level's budget).
    """
    used = {t.frame_colour for t in tiles} | _ink_colours(g, tiles)
    used |= segment.background(g, 2)
    covered = np.zeros(g.shape, dtype=bool)
    for t in tiles:
        covered[t.y:t.y + side, t.x:t.x + side] = True

    marks: list[tuple[int, int, float]] = []
    for c in {int(v) for v in g.ravel()} - used:
        ys, xs = np.where((g == c) & ~covered)
        if not len(xs):
            continue
        marks.append((int(xs.min()), int(xs.max()), (int(ys.min()) + int(ys.max())) / 2))

    tol = side // 2 + 1

    def hit(group: tuple[Tile, ...]) -> bool:
        span = (group[0].x + 1, group[-1].x + side - 2)
        mid = group[0].y + (side - 1) / 2
        return any(m[0] == span[0] and m[1] == span[1] and abs(m[2] - mid) <= tol for m in marks)

    for i, t in enumerate(answer):
        if hit((t,)):
            return i, False
    for i, group in enumerate(sets):
        if hit(group):
            return i, True
    return None, False


def _ink_colours(g: np.ndarray, tiles: list[Tile]) -> set[int]:
    out: set[int] = set()
    for t in tiles:
        block = g[t.y + 1:t.y + t.side - 1, t.x + 1:t.x + t.side - 1]
        out |= {int(v) for v in block.ravel()} - {t.frame_colour}
    return out


# --- the grammar ------------------------------------------------------------------


def _matches(seq: tuple[Tile, ...], i: int, pattern: tuple[Tile, ...]) -> bool:
    if i + len(pattern) > len(seq):
        return False
    return all(seq[i + k].letter == p.letter for k, p in enumerate(pattern))


def _expand(rhs: tuple[Tile, ...], rules: tuple[Rule, ...], mode: str) -> tuple[Tile, ...] | None:
    """Apply the board's translation depth to one rule's right side."""
    if mode == "plain":
        return rhs
    if mode == "tree":
        out: list[Tile] = []
        for letter in rhs:
            for r in rules:
                if r.lhs[0].letter == letter.letter:
                    out.extend(r.rhs)
                    break
            else:
                return None
        return tuple(out)
    for r in rules:
        # The engine compares the two sides pairwise and stops at the shorter one,
        # so a prefix agreement is a match.
        if all(a.letter == b.letter for a, b in zip(rhs, r.lhs)):
            return r.rhs
    return None


def _translate(
    source: tuple[Tile, ...], rules: tuple[Rule, ...], mode: str
) -> list[Tile] | None:
    """Greedy left-to-right rewrite, first matching rule wins."""
    out: list[Tile] = []
    i = 0
    guard = 0
    while i < len(source):
        guard += 1
        if guard > len(source) + 4:
            return None
        for r in rules:
            if not _matches(source, i, r.lhs):
                continue
            got = _expand(r.rhs, rules, mode)
            if got is None:
                continue
            out.extend(got)
            i += len(r.lhs)
            break
        else:
            return None
    return out


def _target(board: Board) -> list[Canon] | None:
    """The answer string, and with it the board's translation depth.

    Only the right depth produces a string of the answer's length written in the
    answer's alphabet, so the depth is measured rather than assumed.
    """
    if not board.answer:
        return None
    want_colour = board.answer[0].frame_colour
    for mode in ("plain", "double", "tree"):
        got = _translate(board.source, board.rules, mode)
        if got is None or len(got) != len(board.answer):
            continue
        if any(t.frame_colour != want_colour for t in got):
            continue
        return [t.letter for t in got]
    return None


# --- turning a letter into presses -------------------------------------------------


def _walk(start: Canon, goal: Canon, succ: dict[Canon, Canon]) -> int | None:
    cur = start
    for d in range(_MAX_RING):
        if cur == goal:
            return d
        nxt = succ.get(cur)
        if nxt is None:
            return None
        cur = nxt
    return None


def _letter_moves(cur: Canon, goal: Canon, succ: dict[Canon, Canon]) -> tuple[int, int] | None:
    """(action id, presses) to turn `cur` into `goal`, or None if not yet learned."""
    if cur == goal:
        return None
    fwd = _walk(cur, goal, succ)
    bwd = _walk(goal, cur, succ)
    if fwd is None and bwd is None:
        return None
    if bwd is None or (fwd is not None and fwd <= bwd):
        return 2, fwd  # type: ignore[return-value]
    return 1, bwd


def _route(n: int, start: int, need: list[int]) -> list[int]:
    """Cheapest order to visit every slot that needs work, moving on a ring of n."""
    if not need:
        return []

    def dist(a: int, b: int) -> int:
        d = (a - b) % n
        return min(d, n - d)

    m = len(need)
    full = 1 << m
    best = [[None] * m for _ in range(full)]  # type: ignore[var-annotated]
    for j in range(m):
        best[1 << j][j] = (dist(start, need[j]), -1)
    for mask in range(full):
        for j in range(m):
            if not mask >> j & 1 or best[mask][j] is None:
                continue
            cost = best[mask][j][0]
            for k in range(m):
                if mask >> k & 1:
                    continue
                nm = mask | 1 << k
                cand = cost + dist(need[j], need[k])
                if best[nm][k] is None or cand < best[nm][k][0]:
                    best[nm][k] = (cand, j)
    end = min(range(m), key=lambda j: best[full - 1][j][0])
    order: list[int] = []
    mask, j = full - 1, end
    while j >= 0:
        order.append(need[j])
        prev = best[mask][j][1]
        mask ^= 1 << j
        j = prev
    order.reverse()
    return order


# --- editing the rules instead of the answer ---------------------------------------


def _uniform(group: tuple[Tile, ...]) -> bool:
    return len({t.letter for t in group}) == 1


def _cycle_of(letter: Canon, succ: dict[Canon, Canon]) -> list[Canon] | None:
    """The alphabet's ring, if enough successor edges have been learned to close it."""
    ring = [letter]
    cur = letter
    for _ in range(32):
        nxt = succ.get(cur)
        if nxt is None:
            return None
        if nxt == letter:
            return ring if len(ring) > 1 else None
        if nxt in ring:
            return None
        ring.append(nxt)
        cur = nxt
    return None


def _shifts(group: tuple[Tile, ...], succ: dict[Canon, Canon]) -> list[tuple[Canon, ...]] | None:
    """Every pattern a group can be turned into -- it advances as ONE piece, so the
    offsets between its letters never change and only the whole ring is reachable."""
    base = tuple(t.letter for t in group)
    ring = _cycle_of(base[0], succ)
    if ring is None:
        return None
    where = {c: i for i, c in enumerate(ring)}
    if any(c not in where for c in base):
        return None
    n = len(ring)
    return [tuple(ring[(where[c] + d) % n] for c in base) for d in range(n)]


def _can_show(
    group: tuple[Tile, ...], want: tuple[Canon, ...], succ: dict[Canon, Canon]
) -> bool:
    """Could this group be made to read `want`, given what the cycle order is known to be?"""
    base = tuple(t.letter for t in group)
    if len(base) != len(want):
        return False
    if base == want:
        return True
    if len(base) == 1:
        return True  # a single letter reaches every letter of its alphabet
    if _uniform(group) and len(set(want)) == 1:
        return True
    opts = _shifts(group, succ)
    return opts is not None and want in opts


LEARN = "learn"


def _solve_rule_edit(board: Board, succ: dict[Canon, Canon]) -> Any:
    """Choose a letter for each editable rule side so the FIXED answer comes out.

    Returns a {set index: wanted pattern} plan, the string LEARN when the alphabet's
    cycle order is still needed to enumerate a group's options, or None when the board
    cannot be solved this way.
    """
    if not board.source or not board.answer:
        return None
    src = [t.letter for t in board.source]
    ans = [t.letter for t in board.answer]
    s_colour = board.source[0].frame_colour
    t_colour = board.answer[0].frame_colour
    entry = [i for i, r in enumerate(board.rules) if r.lhs[0].frame_colour == s_colour]
    if not entry:
        return None
    mid_colour = board.rules[entry[0]].rhs[0].frame_colour
    if mid_colour == t_colour:
        return _solve_direct(board, src, ans, entry, succ)
    dispatch = [
        i for i, r in enumerate(board.rules)
        if r.lhs[0].frame_colour == mid_colour and r.rhs[0].frame_colour == t_colour
    ]
    if not dispatch:
        return None
    return _solve_two_stage(board, src, ans, entry, dispatch, succ)


def _entry_choices(src: list[Canon], entry: list[int], cap: int = 200_000) -> Any:
    """Left sides worth trying: a rule that matches nothing in the source is inert,
    so only the letters the source actually contains can change the parse."""
    alphabet = sorted(set(src))
    if len(alphabet) ** len(entry) > cap:
        return None

    def walk(depth: int) -> Any:
        if depth == 0:
            yield ()
            return
        for head in walk(depth - 1):
            for letter in alphabet:
                yield head + (letter,)

    return walk(len(entry))


def _parse_with(board: Board, src: list[Canon], chosen: dict[int, Canon]) -> list[int] | None:
    """Which rule fires at each source position, first match in board order winning."""
    fired: list[int] = []
    i = 0
    while i < len(src):
        for ri in range(len(board.rules)):
            letter = chosen.get(ri)
            if letter is None:
                continue
            n = len(board.rules[ri].lhs)
            if i + n > len(src) or any(src[i + k] != letter for k in range(n)):
                continue
            fired.append(ri)
            i += n
            break
        else:
            return None
    return fired


def _solve_direct(
    board: Board, src: list[Canon], ans: list[Canon], entry: list[int],
    succ: dict[Canon, Canon],
) -> Any:
    """One hop: the matched rule's right side IS the answer fragment."""
    combos = _entry_choices(src, entry)
    if combos is None:
        return None
    best: tuple[int, dict[int, tuple[Canon, ...]]] | None = None
    for combo in combos:
        chosen = dict(zip(entry, combo))
        fired = _parse_with(board, src, chosen)
        if fired is None:
            continue
        j = 0
        want: dict[int, tuple[Canon, ...]] = {}
        for ri in fired:
            m = len(board.rules[ri].rhs)
            if j + m > len(ans):
                break
            block = tuple(ans[j:j + m])
            j += m
            if want.setdefault(ri, block) != block:
                break
            if not _can_show(board.rules[ri].rhs, block, succ):
                break
        else:
            if j != len(ans):
                continue
            plan = {2 * ri: (letter,) * len(board.rules[ri].lhs) for ri, letter in chosen.items()}
            plan.update({2 * ri + 1: block for ri, block in want.items()})
            best = _keep_cheaper(best, board, plan)
    return None if best is None else best[1]


def _solve_two_stage(
    board: Board, src: list[Canon], ans: list[Canon], entry: list[int],
    dispatch: list[int], succ: dict[Canon, Canon],
) -> Any:
    """Two hops: the matched rule emits middle letters, each looked up again.

    The middle groups carry more than one letter, so their options cannot be listed
    until the alphabet's cycle order has been learned -- hence the LEARN request.
    """
    combos = _entry_choices(src, entry)
    if combos is None:
        return None
    best: tuple[int, dict[int, tuple[Canon, ...]]] | None = None
    learn = False
    for combo in combos:
        chosen = dict(zip(entry, combo))
        fired = _parse_with(board, src, chosen)
        if fired is None:
            continue
        distinct = sorted(set(fired))
        options = []
        for ri in distinct:
            group = board.rules[ri].rhs
            opts = _shifts(group, succ)
            if opts is None:
                learn = True
                options = []
                break
            options.append(opts)
        if not options:
            continue
        for pick in _product(options):
            mid = dict(zip(distinct, pick))
            for expand in ("tree", "whole"):
                plan = _fit_dispatch(board, ans, fired, mid, dispatch, chosen, succ, expand)
                if plan is not None:
                    best = _keep_cheaper(best, board, plan)
                    if best[0] == len(best[1]):
                        return best[1]
    if best is not None:
        return best[1]
    return LEARN if learn else None


def _product(options: list[list[tuple[Canon, ...]]]) -> Any:
    if not options:
        yield ()
        return
    for head in _product(options[:-1]):
        for tail in options[-1]:
            yield head + (tail,)


def _fit_dispatch(
    board: Board, ans: list[Canon], fired: list[int],
    mid: dict[int, tuple[Canon, ...]], dispatch: list[int],
    chosen: dict[int, Canon], succ: dict[Canon, Canon], expand: str,
) -> dict[int, tuple[Canon, ...]] | None:
    """Give every middle letter a rule to be looked up by, and check the answer tiles."""
    if expand == "tree":
        keys = [b for ri in fired for b in mid[ri]]
    else:
        # The engine compares a whole right side against a left side pairwise, stopping
        # at the shorter -- so the group's FIRST letter is what decides the lookup.
        keys = [mid[ri][0] for ri in fired]
    order = list(dict.fromkeys(keys))
    if len(order) > len(dispatch):
        return None
    for perm in _perms(dispatch, len(order)):
        assign = dict(zip(order, perm))
        j = 0
        want: dict[int, tuple[Canon, ...]] = {}
        ok = True
        for b in keys:
            rj = assign[b]
            m = len(board.rules[rj].rhs)
            if j + m > len(ans):
                ok = False
                break
            block = tuple(ans[j:j + m])
            j += m
            if want.setdefault(rj, block) != block:
                ok = False
                break
        if not ok or j != len(ans):
            continue
        if any(not _can_show(board.rules[rj].rhs, blk, succ) for rj, blk in want.items()):
            continue
        spare = _spare_letter(board, dispatch, order, succ)
        idle = [rj for rj in dispatch if rj not in perm]
        if idle and spare is None:
            continue
        plan = {2 * ri: (letter,) * len(board.rules[ri].lhs) for ri, letter in chosen.items()}
        # The middle groups are part of the answer: the search picked a specific
        # pattern for each one and the lookups were fitted to it.
        plan.update({2 * ri + 1: pat for ri, pat in mid.items()})
        for b, rj in assign.items():
            plan[2 * rj] = (b,) * len(board.rules[rj].lhs)
        for rj in idle:
            # An unused lookup rule must not shadow a used one: park it on a letter no
            # lookup needs, because the FIRST rule whose left side matches wins.
            plan[2 * rj] = (spare,) * len(board.rules[rj].lhs)  # type: ignore[misc]
        plan.update({2 * rj + 1: blk for rj, blk in want.items()})
        return plan
    return None


def _spare_letter(
    board: Board, dispatch: list[int], used: list[Canon], succ: dict[Canon, Canon]
) -> Canon | None:
    ring = _cycle_of(board.rules[dispatch[0]].lhs[0].letter, succ)
    if ring is None:
        return None
    for c in ring:
        if c not in used:
            return c
    return None


def _perms(items: list[int], k: int) -> Any:
    if k == 0:
        yield ()
        return
    for i, it in enumerate(items):
        for tail in _perms(items[:i] + items[i + 1:], k - 1):
            yield (it,) + tail


def _keep_cheaper(
    best: tuple[int, dict[int, tuple[Canon, ...]]] | None,
    board: Board,
    plan: dict[int, tuple[Canon, ...]],
) -> tuple[int, dict[int, tuple[Canon, ...]]]:
    """Prefer the plan that leaves the most groups already reading correctly."""
    score = sum(1 for i, w in plan.items() if tuple(t.letter for t in board.sets[i]) == w)
    return best if best is not None and best[0] >= score else (score, plan)


# --- the tool ----------------------------------------------------------------------


class RuleRewriteTool:
    """Solve a board that states a rewrite grammar and asks for the translation."""

    name = "rule_rewrite"

    def __init__(self) -> None:
        self._succ: dict[Canon, Canon] = {}
        self._prev: np.ndarray | None = None
        self._prev_action: int | None = None
        self._level = -1
        self._plan: dict[int, tuple[Canon, ...]] | None = None
        self._plan_key: Any = None
        self._stuck = False
        self._learned = 0

    # -- lifecycle ------------------------------------------------------------------

    def reset(self) -> None:
        # The alphabet's cycle order is a property of the game, not of the level, so it
        # survives a level change; everything derived from the layout does not.
        self._prev = None
        self._prev_action = None
        self._plan = None
        self._plan_key = None
        self._stuck = False
        self._learned = 0

    def observe(self, prev: np.ndarray, action: Step, changed: bool) -> None:
        # Learning happens in propose() against the frame it is handed, so that the
        # tool stays correct whether or not the harness reports transitions.
        return

    # -- detection ------------------------------------------------------------------

    def detect(self, frames: list[Any], obs: Any) -> float:
        if not has_frame(obs):
            return 0.0
        simple, action6 = availability(obs)
        if action6 or not {1, 2, 3, 4} <= set(simple):
            return 0.0
        board = _read_board(_grid(obs))
        if board is None or board.cursor is None:
            return 0.0
        if board.edit_rules:
            got = _solve_rule_edit(board, self._succ)
            return 0.9 if got is not None else 0.0
        return 0.9 if _target(board) is not None else 0.0

    # -- planning -------------------------------------------------------------------

    def propose(self, frames: list[Any], obs: Any) -> list[Step]:
        if not has_frame(obs):
            return []
        level = levels_completed(obs)
        if level != self._level:
            self._level = level
            self.reset()
        g = _grid(obs)
        board = _read_board(g)
        if board is None or board.cursor is None:
            self._prev, self._prev_action = g, None
            return []
        self._learn(board)

        step = self._next_step(board)
        self._prev = g
        self._prev_action = step[0] if step else None
        return [step] if step else []

    def _learn(self, board: Board) -> None:
        """Record which letter follows which, from a letter change we just caused."""
        if self._prev is None or self._prev_action not in (1, 2):
            return
        before = _read_board(self._prev)
        if before is None or before.side != board.side:
            return
        old = {(t.y, t.x): t.letter for t in before.source + before.answer}
        old.update({(t.y, t.x): t.letter for r in before.rules for t in r.lhs + r.rhs})
        new = {(t.y, t.x): t.letter for t in board.source + board.answer}
        new.update({(t.y, t.x): t.letter for r in board.rules for t in r.lhs + r.rhs})
        for key, was in old.items():
            now = new.get(key)
            if now is None or now == was:
                continue
            if self._prev_action == 2:
                self._succ[was] = now
            else:
                self._succ[now] = was

    def _learn_step(self, board: Board) -> Step | None:
        """Turn a group that shows two different letters until its ring closes.

        One press of such a group reveals two successor edges at once, so the whole
        alphabet order falls out in a handful of actions -- and the game charges for
        actions, so this is done on purpose and only when a plan needs it.
        """
        targets = [i for i, s in enumerate(board.sets) if not _uniform(s)]
        if not targets:
            return None
        here = board.cursor
        assert here is not None
        n = len(board.sets)
        if here in targets:
            return (2, None)
        goto = min(targets, key=lambda i: min((i - here) % n, (here - i) % n))
        return (4, None) if (goto - here) % n <= (here - goto) % n else (3, None)

    def _next_step(self, board: Board) -> Step | None:
        if board.edit_rules:
            groups = board.sets
            if self._plan is None or self._plan_key != board.answer:
                if self._stuck:
                    return None
                plan = _solve_rule_edit(board, self._succ)
                if plan is None:
                    # Re-running a search that already said no would spend the level's
                    # budget on the same answer, so it is asked once.
                    self._stuck = True
                    return None
                if plan is LEARN:
                    if self._learned >= _MAX_RING:
                        self._stuck = True
                        return None
                    self._learned += 1
                    return self._learn_step(board)
                self._plan, self._plan_key = plan, board.answer
            wants = [self._plan.get(i) for i in range(len(groups))]
        else:
            target = _target(board)
            if target is None:
                return None
            groups = tuple((t,) for t in board.answer)
            wants = [(c,) for c in target]

        cur = [tuple(t.letter for t in s) for s in groups]
        need = [i for i, w in enumerate(wants) if w is not None and cur[i] != w]
        if not need:
            # Everything already reads correctly, but the board only re-checks itself
            # after a letter changes -- so nudge one and let the next turn undo it.
            return (2, None)

        here = board.cursor
        if here in need:
            want = wants[here]
            assert want is not None
            for now, goal in zip(cur[here], want):
                if now == goal:
                    continue
                move = _letter_moves(now, goal, self._succ)
                # Not yet learned which way is shorter: step forward, which both makes
                # progress and teaches the successor edge.
                return (2, None) if move is None else (move[0], None)
            return (2, None)

        order = _route(len(groups), here, need)
        goto = order[0]
        n = len(groups)
        return (4, None) if (goto - here) % n <= (here - goto) % n else (3, None)
