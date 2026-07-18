"""Shared sprite-read helpers for the L7 bar-shift measurement probes (dev-time
measurement only; the real controller is frame-only)."""
from __future__ import annotations
from collections import Counter

import numpy as np

MOV = "0031cppcuvqlbi"


def cross_sprite(env, color):
    for s in env._game.current_level.get_sprites_by_tag(MOV):
        cc = Counter(int(v) for row in s.pixels for v in row if v not in (-1, 0))
        if cc and cc.most_common(1)[0][0] == color:
            return s
    return None


def bars(s):
    """(x, y, w, h, vbar_abs_col, hbar_abs_row) from the sprite pixels."""
    px = s.pixels
    h, w = px.shape
    vcol = max(range(w), key=lambda c: int(np.sum(px[:, c] != -1)))
    hrow = max(range(h), key=lambda r: int(np.sum(px[r, :] != -1)))
    return s.x, s.y, w, h, s.x + vcol, s.y + hrow


def sel_color(env):
    for s in env._game.current_level.get_sprites_by_tag(MOV):
        if int(s.pixels[s.height // 2, s.width // 2]) == 0:
            cc = Counter(int(v) for row in s.pixels for v in row if v not in (-1, 0))
            return cc.most_common(1)[0][0] if cc else -1
    return None
