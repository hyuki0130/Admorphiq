"""The three PERCEPTION repairs dc22 level 6 needs, applied by monkeypatch so each can be
measured before any of them is written into `src`.

  S (bit 0)  a piece is located as the UNIQUE square of the avatar's own side, not as "this colour
     paints exactly one square".  Measured on dc22: colour 11 is the marker on all six levels and
     paints one 2x2 on every one — plus a 4x4 control in the panel on levels 4, 5 and 6, which is
     what makes the strict rule refuse and the tool latch dead.
  C (bit 1)  the pair is CARRIED across levels of a game and preferred while it still resolves.
     Measured: the rarest-two rule reads (11,14) on levels 1-3 and (9,14) on level 6, where 9 is a
     terrain token; the carried pair resolves on the whole frame on all six.
  W (bit 2)  the board WIDENS to the whole frame, and the panel's own ground becomes non-floor,
     ONLY when the marker cannot be located in the narrow board and can be in the wide one.

⛔ W is conditional because the unconditional form is MEASURED HARMFUL: board = whole frame on
every level takes dc22's level 1 from 31 actions to 52 and the game from 5 levels to 2 (mask 4),
3 (mask 6) or 4 (mask 7) depending on what it is paired with.  The recorded diagnosis — that the
panel's ground was being read as floor — is only half of it: naming that ground still leaves the
panel's controls as objects to walk to and tiles to test.  Widening on the evidence that the goal
is not in the narrow board keeps every level whose goal IS in it byte-identical.

Not a probe — imported by the dc22 probes.  `apply(mask)` is idempotent.
"""
from __future__ import annotations

from collections import Counter

import numpy as np

_APPLIED: int | None = None


def squares_of_side(board, colour: int, side: int) -> list[tuple[int, int]]:
    """Every filled `side`x`side` square of `colour` that extends in NO direction.

    ⛔ Maximality is tested on all four sides, not only up and left.  A 2x2 read out of the
    interior of a 4x4 control is a square by every local test; what separates the piece from the
    control is that the piece cannot be grown and the control's interior can.
    """
    grid = np.asarray(board)
    h, w = grid.shape
    out: list[tuple[int, int]] = []
    for y, x in np.argwhere(grid == colour):
        y, x = int(y), int(x)
        if y + side > h or x + side > w:
            continue
        if not bool((grid[y:y + side, x:x + side] == colour).all()):
            continue
        if y and bool((grid[y - 1, x:x + side] == colour).all()):
            continue
        if x and bool((grid[y:y + side, x - 1] == colour).all()):
            continue
        if y + side < h and bool((grid[y + side, x:x + side] == colour).all()):
            continue
        if x + side < w and bool((grid[y:y + side, x + side] == colour).all()):
            continue
        out.append((y, x))
    return out


def unique_square(board, colour: int, side: int) -> tuple[int, int] | None:
    got = squares_of_side(board, colour, side)
    return got[0] if len(got) == 1 else None


def apply(mask: int = 7) -> None:
    global _APPLIED
    if _APPLIED == mask:
        return
    _APPLIED = mask
    from admorphiq.tools import phase as P

    use_s, use_c, use_w = bool(mask & 1), bool(mask & 2), bool(mask & 4)

    def resolves(self, board, pair) -> bool:
        c0, c1, side = pair
        if use_s:
            # ⛔ The same locator the tool will USE, tracking included.  Testing with the strict
            # uniqueness rule while the tool locates by continuity makes `_read` refuse a board the
            # tool can read perfectly well — measured on dc22 level 6, where a control unlocks as a
            # second square of the marker's colour and the whole level goes silent.
            track = getattr(self, "_track", None) or {}
            for colour in (c0, c1):
                found = squares_of_side(board, colour, side)
                if not found or (len(found) > 1 and colour not in track):
                    return False
            return True
        # The strict inherited rule, kept here so the OFF arm of the matrix is the real control.
        for colour in (c0, c1):
            cells = np.argwhere(np.asarray(board) == colour)
            if not len(cells):
                return False
            y0, x0 = int(cells[:, 0].min()), int(cells[:, 1].min())
            y1, x1 = int(cells[:, 0].max()), int(cells[:, 1].max())
            if (y1 - y0) != (x1 - x0) or len(cells) != (y1 - y0 + 1) ** 2:
                return False
        return True

    def _read(self, g):
        top, bot = P._chrome_span(g)
        if bot - top < P._MIN_BOARD_ROWS:
            return None
        split = P._split_columns(g, top, bot)
        if split is None:
            return None
        right, panel = split
        left = np.asarray(g)[top:bot + 1, 0:right]
        whole = np.asarray(g)[top:bot + 1, :]
        # ⛔ The ground is the BOARD's, read on the board's own columns.  Taking the modal colour of
        # a widened board flips to the panel's ground the moment the panel is the wider half, and
        # every floor test then inverts.
        bg = Counter(int(v) for v in left.ravel()).most_common(1)[0][0]
        board, pair = left, None
        carry = getattr(self, "_carry", None) if use_c else None
        if carry is not None:
            track = getattr(self, "_track", None) or {}
            for cand in ((left, whole) if use_w else (left,)):
                # ⛔ A board that does not CONTAIN the piece where it was last seen is not a board
                # the piece resolves in, however many lookalikes it holds.  Without this the narrow
                # board wins back the moment it grows a square of the marker's colour of its own.
                if any(colour in track and track[colour][1] >= cand.shape[1]
                       for colour in (carry[0], carry[1])):
                    continue
                if resolves(self, cand, carry):
                    board, pair = cand, carry
                    break
        if pair is None:
            pair = P._pieces(left)
            if pair is None:
                return None
            board = left
        if board is whole:
            strip = np.asarray(g)[top:bot + 1, right:]
            panel_bg = int(Counter(int(v) for v in strip.ravel()).most_common(1)[0][0])
            if panel_bg != bg:
                self._not_floor.add(panel_bg)
        if use_c and self._rare == (pair[0], pair[1]):
            # ⛔ The pair is banked only once the tool has COMMITTED to it for this level.  `_read`
            # is called from `detect` on every frame of every game, including the transitional one
            # a level-up draws, and a pair read off that frame is not a pair the tool ever used.
            self._carry = pair
        return {"top": top, "bot": bot, "panel": panel, "board": board,
                "bg": bg, "side": pair[2], "rare": (pair[0], pair[1])}

    P.PhaseGridTool._read = _read

    if use_s:
        def _at(self, board, colour):
            """The piece of `colour`, tracked by CONTINUITY when the board grows a twin.

            ⛔ Uniqueness alone is not enough for a whole game.  Measured on dc22 level 6 at action
            293: a control UNLOCKS partway through the level and is drawn as a second 2x2 of the
            marker's own colour, so the locator that had been right for 292 actions returns None
            and the tool goes silent for the rest of the level.  A piece that was somewhere last
            turn is the candidate nearest to where it was — the avatar moves one step and the
            marker does not move at all — and that is a rule the board cannot break by drawing a
            new button somewhere else.
            """
            side = self._side or 2
            track = getattr(self, "_track", None)
            if track is None:
                track = self._track = {}
            found = squares_of_side(board, colour, side)
            if not found:
                return None
            if len(found) == 1:
                track[colour] = found[0]
                return found[0]
            was = track.get(colour)
            if was is None:
                return None
            best = min(found, key=lambda c: abs(c[0] - was[0]) + abs(c[1] - was[1]))
            track[colour] = best
            return best

        P.PhaseGridTool._at = _at

        orig_reset_s = P.PhaseGridTool.reset

        def reset_s(self):
            orig_reset_s(self)
            self._track: dict[int, tuple[int, int]] = {}

        P.PhaseGridTool.reset = reset_s

        orig_learn = P.PhaseGridTool._learn_refusal

        def _learn_refusal(self, board, cell):
            keep = {self._avatar, self._marker}
            before = set(self._not_floor)
            orig_learn(self, board, cell)
            # ⛔ A refusal must never condemn the colour the GOAL is painted in: the marker's own
            # tile would stop being floor and the route would lose the cell it is aiming at.
            self._not_floor = (self._not_floor - keep) | (before & keep)

        P.PhaseGridTool._learn_refusal = _learn_refusal

    if use_c:
        orig_reset = P.PhaseGridTool.reset

        def reset(self):
            carry = getattr(self, "_carry", None)
            orig_reset(self)
            self._carry = carry

        P.PhaseGridTool.reset = reset
