"""script25 quarantined adapter: TN36 (opcode-column program-synthesis).

*** QUARANTINE — MODEL-NEVER-VISIBLE. See admorphiq.adapters25's package
docstring. ***

**Mechanic (fully decoded R56e, built R56f).** TN36 is a program-synthesis
puzzle. A row of N OPCODE COLUMNS (each a small stack of bit cells encoding a
number `value = Σ 1<<i`) sits above a play button. You set each column's value
by clicking its bit cells, click play ONCE, and the player sprite then executes
the columns left-to-right as a fixed instruction set (`dfguzecnsr`, unit 4px):
`1/34`=left, `2`=right, `3`=down, `33`=up, `10-13`=double-move, `5/6/7/16`=
rotate, `8/9`=scale±, `14/15/63`=recolour, `0`=noop/reset. WIN = the player
matches the goal in x, y, rotation, scale AND colour. Every ACTION6 advances a
deadline wall one cell (~61-click budget on L0). The R56b "unfindable
frame-selector" bank was FALSE — the frames ARE the visible columns.

**This adapter (R56f) — frame-only, goal-directed.** It reads the board from
the frame (no engine internals): the bit-panel box, its columns and each bit
cell's on/off (a bit renders as the BACKGROUND colour when ON, a foreground
colour when OFF), the play button, and the player + goal sprites. It then
SEARCHES per-column move opcodes in a small offline simulator to move the
player onto the goal, sets each column's bits to the chosen opcode, and clicks
play. L0 (player straight above goal, 5 columns) clears in ~7 clicks: all
columns = opcode 3 (down×5).

**Scope**: movement-only levels (the search covers the move opcodes). Levels
needing rotation/scale/colour matching, interior walls / toggling kill-zones,
or multi-run checkpoint sequencing are not yet modelled — those columns fall
outside the move search and are banked for the follow-up build. The floor is
the L0 clear.

Composition from ``admorphiq.kernels``: find_regions (board + panel parse).
"""

from __future__ import annotations

from itertools import product
from typing import Any

from admorphiq.adapters25.base import (
    GameAction,
    GameAdapter,
    canonical_layer,
    click_action,
    has_frame,
    most_common_color,
    reset_action,
    state_name,
)
from admorphiq.kernels import find_regions

GAME_ID = "tn36"

Cell = tuple[int, int]
Grid = tuple[tuple[int, ...], ...]

_GIVEUP_DEFAULT = 200

# Click camera offset: a click at display x maps to grid col x+2, so to hit a
# cell whose frame column is C we click at C-2 (measured on tn36-ef4dde99).
_CLICK_DX = -2

# Move opcodes and their per-execution cell displacement (dx, dy), unit = 1
# cell. The search only uses single-cell moves — enough for straight-line
# levels like L0; double-moves and non-move opcodes are a follow-up.
_MOVE_OPCODES: dict[int, Cell] = {
    1: (-1, 0),
    2: (1, 0),
    3: (0, 1),
    33: (0, -1),
    34: (-1, 0),
}

_CELL_PX = 4  # CSPOIQWER — one opcode move = 4 frame pixels


class Adapter(GameAdapter):
    """Frame-only opcode-column program synthesis: parse the panel, search a
    move program that lands the player on the goal, set bits, play."""

    GAME_ID = GAME_ID

    def __init__(self, giveup: int = _GIVEUP_DEFAULT) -> None:
        self.restart_on_game_over = True
        self._giveup = giveup
        self._step = 0
        self._levels_seen = -1
        self._clicks: list[Cell] = []
        self._played = False
        self._settle = 0

    # ── harness contract ────────────────────────────────────────────────

    def is_done(self, frames: list[Any], latest_frame: Any) -> bool:
        return state_name(latest_frame) == "WIN" or self._step >= self._giveup

    def choose_action(self, frames: list[Any], latest_frame: Any) -> GameAction:
        state = state_name(latest_frame)
        if state == "GAME_OVER":
            self._reset_plan()
            return reset_action()
        if state == "NOT_PLAYED" or not has_frame(latest_frame):
            self._levels_seen = -1
            self._reset_plan()
            return reset_action()

        levels = int(getattr(latest_frame, "levels_completed", 0) or 0)
        if levels != self._levels_seen:
            first = self._levels_seen == -1
            self._levels_seen = levels
            self._reset_plan()
            # A level TRANSITION animates for several frames; parsing that
            # transient board mis-reads it (and then the whole level's deadline
            # is wasted idling on a wrong program). Settle before the first
            # parse of a NEW level — the very first board is already settled.
            self._settle = 0 if first else 6

        self._step += 1

        if self._settle > 0:
            self._settle -= 1
            return click_action(0, 0)

        if self._clicks:
            return click_action(*self._clicks.pop(0))
        if self._played:
            # Program already sent for this board; wait for the outcome by
            # issuing harmless idle clicks (they advance the wall but let the
            # execution animation resolve into WIN / next level).
            return click_action(0, 0)

        grid = canonical_layer(latest_frame)
        plan = _plan(grid)
        if plan is None:
            return reset_action()
        self._clicks = plan
        self._played = True
        return click_action(*self._clicks.pop(0))

    def _reset_plan(self) -> None:
        self._clicks = []
        self._played = False


# ── planning ────────────────────────────────────────────────────────────────


def _plan(grid: Grid) -> list[Cell] | None:
    """Return the click sequence (bit toggles then play) that solves a
    movement level, or None if the board cannot be parsed / searched."""
    board = _parse(grid)
    if board is None:
        return None
    columns, play_click, blobs = board
    if len(blobs) < 2 or not columns:
        return None

    program = _search_program(columns, blobs)
    if program is None:
        return None

    clicks: list[Cell] = []
    for col, opcode in zip(columns, program):
        clicks.extend(_column_toggle_clicks(col, opcode))
    clicks.append(play_click)
    return clicks


def _search_program(columns: list[dict], blobs: list[Cell]) -> list[int] | None:
    """Search a per-column move opcode assignment that lands the player on the
    goal in the offline simulator. Tries both blob-as-player assignments so the
    player/goal ambiguity (they share a colour) resolves itself."""
    n = len(columns)
    max_bits = max(len(c["bits"]) for c in columns)
    # Opcodes expressible within every column's bit width.
    opcodes = [op for op in _MOVE_OPCODES if op < (1 << max_bits)]
    if not opcodes or n > 6:
        return None

    def cells(a: int, b: int) -> int:
        return int(round((b - a) / _CELL_PX))

    for start, goal in ((blobs[0], blobs[1]), (blobs[1], blobs[0])):
        target = (cells(start[0], goal[0]), cells(start[1], goal[1]))
        found = _search_delta(opcodes, n, target)
        if found is not None:
            return found
    return None


def _search_delta(opcodes: list[int], n: int, target: Cell) -> list[int] | None:
    """Find n opcodes whose summed displacement equals ``target`` (cells)."""
    tdx, tdy = target
    # Prune: try the straight cases first (all same opcode), then the product.
    for op in opcodes:
        dx, dy = _MOVE_OPCODES[op]
        if dx * n == tdx and dy * n == tdy:
            return [op] * n
    if n <= 6:
        for combo in product(opcodes, repeat=n):
            sx = sum(_MOVE_OPCODES[o][0] for o in combo)
            sy = sum(_MOVE_OPCODES[o][1] for o in combo)
            if sx == tdx and sy == tdy:
                return list(combo)
    return None


def _column_toggle_clicks(col: dict, opcode: int) -> list[Cell]:
    """Clicks that set ``col`` to ``opcode``: for each bit, toggle iff its
    current on/off differs from the opcode's bit. Bit i (LSB first, ordered by
    the cell's position) contributes 1<<i."""
    clicks: list[Cell] = []
    for i, bit in enumerate(col["bits"]):
        want_on = bool(opcode & (1 << i))
        if bit["on"] != want_on:
            clicks.append((bit["col"] + _CLICK_DX, bit["row"]))
    return clicks


# ── frame parse ───────────────────────────────────────────────────────────────


def _parse(grid: Grid):
    """Parse (columns, play_click, blobs) from the frame, or None.

    The frame has an OUTER border colour (most common) and an inner PLAYFIELD
    background (the large dark region enclosing everything). Crucially a bit
    "lights" to the border colour when ON, so we must parse against the
    PLAYFIELD background, not the border — otherwise ON bits vanish.

    columns: list of {bits: [{row, col, on}]} left-to-right.
    play_click: (x, y) click point for the play button.
    blobs: player & goal anchors (bbox top-left as (x, y)), same colour.
    """
    if not grid or not grid[0]:
        return None
    border = most_common_color(grid)
    height = len(grid)

    # Editor panel = the darkest (min colour value) LARGE region that is not the
    # border. On single-panel levels (L0) it is the whole dark playfield; on
    # multi-panel levels (L1) it is the colour-0 editable panel, distinct from a
    # lighter reference panel that merely DISPLAYS the target. Selecting by
    # min-colour (0 = darkest) rather than size picks the editor either way.
    outer = find_regions(grid, background=border)
    large = [rg for rg in outer if rg["size"] >= 80]
    if not large:
        return None
    editor = min(large, key=lambda rg: rg["color"])
    playfield = editor["color"]
    er0, ec0, er1, ec1 = editor["bbox"]

    regions = find_regions(grid, background=playfield)

    # Play button = the largest non-border region low in the frame whose x
    # overlaps the editor panel (multi-panel levels have a second play button
    # under the reference panel — pick the editor's).
    play = _find_play_button(regions, height, border, ec0, ec1)
    if play is None:
        return None
    play_x, play_y = play

    # Player + goal = a colour with exactly two equal-size small regions above
    # the bit band; anchor on each bbox top-left (matches the sprite origin).
    blobs = _find_blobs(regions, border, playfield)
    if len(blobs) < 2:
        return None
    blob_bottom = max(y for _, y in blobs)

    # Bit cells: small regions inside the editor panel's x-span, in the band
    # between the blobs and the play button. A bit is ON when its colour ==
    # border (it "lights" to the border colour), OFF otherwise. Each column has
    # 2..6 such cells stacked top→bottom = bit0..bitN (weight 2^i, validated
    # live by per-cell click).
    band_top = blob_bottom
    band_bot = play_y
    inner = [
        rg
        for rg in regions
        if rg["size"] <= 8
        and band_top < rg["centroid"][0] < band_bot
        and ec0 <= rg["centroid"][1] <= ec1
        and rg["color"] != playfield
    ]
    if len(inner) < 2:
        return None
    on_color = border

    columns = _group_columns(inner, on_color)
    if not columns:
        return None

    return columns, (play_x, play_y), blobs


def _group_columns(inner: list[dict], on_color: int) -> list[dict]:
    """Cluster bit cells into columns by x, each column's bits ordered by y
    (top→bottom = LSB→MSB). Marks each bit on/off by colour == on_color."""
    cells = [
        {
            "row": int(round(rg["centroid"][0])),
            "col": int(round(rg["centroid"][1])),
            "on": rg["color"] == on_color,
        }
        for rg in inner
    ]
    cells.sort(key=lambda b: b["col"])
    columns: list[dict] = []
    cur: list[dict] = []
    last_col = None
    for b in cells:
        if last_col is not None and b["col"] - last_col > 3:
            columns.append({"bits": sorted(cur, key=lambda x: x["row"])})
            cur = []
        cur.append(b)
        last_col = b["col"]
    if cur:
        columns.append({"bits": sorted(cur, key=lambda x: x["row"])})
    if not columns:
        return []
    # Keep only columns with the modal bit count (the real opcode columns).
    widths = [len(c["bits"]) for c in columns]
    common = max(set(widths), key=widths.count)
    return [c for c in columns if len(c["bits"]) == common]


def _find_play_button(regions: list[dict], height: int, border: int, ec0: int, ec1: int):
    """The play button = the largest non-border region in the bottom third of
    the frame whose x overlaps the editor panel span ``[ec0, ec1]`` (multi-panel
    levels carry a second play button under the reference panel — this picks the
    editor's). Returns the (x, y) click point with the camera offset applied."""
    best = None
    for rg in regions:
        cr, cc = rg["centroid"]
        if cr < height * 0.66 or rg["color"] == border:
            continue
        if not (ec0 <= cc <= ec1):
            continue
        if best is None or rg["size"] > best[0]:
            best = (rg["size"], int(round(cc)) + _CLICK_DX, int(round(cr)))
    if best is None:
        return None
    return best[1], best[2]


def _find_blobs(regions: list[dict], border: int, playfield: int) -> list[Cell]:
    """Player + goal sprites: two equal-size same-colour regions (they share a
    colour and are ~4x4). Anchor on each bbox TOP-LEFT = (col, row) = (x, y),
    which matches the engine sprite origin (centroids are clip-skewed).
    Returns them ordered top→bottom."""
    by_color: dict[int, list[dict]] = {}
    for rg in regions:
        if rg["color"] in (border, playfield):
            continue
        if 8 <= rg["size"] <= 20:
            by_color.setdefault(rg["color"], []).append(rg)
    # Player/goal = a colour with EXACTLY two blocky regions (the program
    # DISPLAY colour appears many times, so it is excluded by this count). If
    # several qualify, prefer the vertically-aligned pair (same x = a mover and
    # its target).
    best = None
    for _color, rgs in by_color.items():
        if len(rgs) != 2:
            continue
        misalign = abs(rgs[0]["bbox"][1] - rgs[1]["bbox"][1])
        if best is None or misalign < best[0]:
            best = (misalign, rgs)
    if best is None:
        return []
    # The PLAYER renders as a SOLID block, the GOAL as a sparse outline/marker,
    # so the player has the higher fill ratio (colour pixels / bbox area).
    # Ordering player-first removes the move-search's orientation ambiguity
    # (both blobs otherwise admit a valid straight program).
    def fill(rg: dict) -> float:
        r0, c0, r1, c1 = rg["bbox"]
        return rg["size"] / max(1, (r1 - r0 + 1) * (c1 - c0 + 1))

    rgs = sorted(best[1], key=fill, reverse=True)
    return [(rg["bbox"][1], rg["bbox"][0]) for rg in rgs]
