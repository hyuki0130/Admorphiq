"""Paint-order (z-order) mutation of the rendered frame, for transfer measurement.

⭐ WHAT THIS MEASURES, AND WHY IT HAD TO EXIST. Rule 7cd named the campaign's only
measured transfer defect: **a frame-only tool that identifies an object by whether it
is DRAWN is reading PAINT ORDER, not mechanics.** s5i5's L4 costs 22 extra actions on
the archived re-render because that file lists the rider BEFORE the bar it rides, so
the bar covers one cell and `TelescopeArmTool`'s candidate set goes from 2 to 9.

⛔ AND THE INSTRUMENT THAT EXISTED COULD NOT SEE IT. `render_mutation.py`'s colour
permutation is a bijection, and a bijection preserves WHICH SPRITE IS ON TOP; a
translation does too. The evidence this defect destroys is not a colour, it is a cell
that is not there. So the only mutation that can reach it is one that changes the
order sprites are painted in — which is what this module does.

⭐ WHERE THE MUTATION LIVES, AND WHY IT IS RENDER-ONLY BY CONSTRUCTION. The engine
paints with ``Camera._raw_render``, whose sprite list it sorts with
``sorted(..., key=lambda s: s.layer)`` — a STABLE sort, so within one layer the LIST
ORDER *is* the z-order and a sprite later in the list wins the pixel. Three of the 25
games (s5i5, tu93, wa30) go further and override ``_raw_render`` with a version that
does not sort at all, so for them the list order alone decides.

The mutation is installed on ``Camera.render`` — the public entry point — and NOT on
``_raw_render``, and that distinction is the whole validity argument:

  * ``Camera.render`` has exactly ONE caller inside the engine,
    ``base_game.perform_action`` (base_game.py:232), and its return value is the
    observation frame and nothing else;
  * ``BaseGame.get_pixels`` — which games DO use as game logic, to ask what colour is
    rendered at a position — calls ``camera._raw_render`` directly and is therefore
    untouched;
  * ``Level.get_sprite_at`` (click resolution) and ``Level.collides_with`` read
    ``Level._sprites``, which this module never mutates.

So the game's state trajectory stays a function of the action sequence alone, the
level structure and the win predicate are untouched, and no coordinate conjugation is
needed because the mutation moves no pixel to a different place — it only changes
which of two co-located sprites is visible there.

⛔ "SAME-LAYER SIBLINGS ONLY" IS THE RIGHT RULE FOR 22 GAMES AND MEANINGLESS FOR THREE,
AND THAT DISTINCTION COST THE FIRST ARM ITS POSITIVE CONTROL. The conservative rule —
permute only sprites sharing a layer, so the cross-layer relative order is byte-identical
— is correct wherever `layer` is a rendering property. **s5i5, tu93 and wa30 override
``Camera._raw_render`` with a version that does not sort at all**, so for those three the
raw list order IS the z-order and `layer` decides nothing about the picture.

MEASURED (`scripts/_s5i5_zprobe.py`, painting with s5i5's own painter): the rider and the
bar it rides are on DIFFERENT declared layers, so a same-layer reversal changes **0 cells
on seven of s5i5's eight levels** and the arm scored the game identical action for action
— it could not reproduce rule 7cd's known answer. A WHOLE-LIST reversal changes 2/1/2/1/6/1
cells on levels 1-6, and the live-vs-archived difference is 2/1/2/1/6/1 on the same levels,
including **L4's single cell at (43,31), live 13 -> archived 11**. The whole-list
permutation reproduces the competition's own re-render, pair for pair.

⭐ AND ON THE OTHER 22 GAMES THE WHOLE-LIST ARM *IS* THE SAME-LAYER ARM. ``_raw_render``
filters by visibility (order-preserving) and then applies a STABLE ``sorted(key=layer)``,
so reordering the input list can only ever change the order WITHIN a layer group — the
sort re-imposes the cross-layer order regardless. ``zrev`` and ``zrevall`` must therefore
return identical results on every layer-sorting game, and the round runs both so that
equality is measured rather than argued.

So both scopes ship. :func:`same_layer_permute` preserves every sprite's LAYER SLOT and is
the strictly conservative arm; :func:`whole_list_permute` permutes the list entire and is
the one that reproduces the archive. Neither touches ``Level._sprites``, so click
resolution (``Level.get_sprite_at``, which sorts by layer with ``reverse=True``) is
identical under both.

⭐ THE HUMAN DENOMINATOR IS INVARIANT — MEASURED, NOT ASSUMED. The two s5i5
serializations differ ONLY in list order (`scripts/_s5i5_srcdiff.py`: same sprite art,
same positions, same `Children`, on all eight levels) and they ship the IDENTICAL
``baseline_actions`` ``[20, 89, 106, 54, 162, 38, 86, 83]``. The competition's own
re-render of this board changed the paint order and did not change the human count, so
``metadata.json`` is still the right denominator under this arm.

⛔ WHAT IT DOES NOT PROVE. A re-painted board is the SAME BOARD with the same mechanic.
This is a floor on brittleness, like `xfergate.sh` and `rendergate.sh`, and it is not a
forecast for the 110 private games, which have different MECHANICS. Nothing here may be
quoted as a transfer coefficient.

⚠️ AND ONE HONEST WEAKNESS THIS ARM HAS THAT A COLOUR PERMUTATION DOES NOT. A colour
bijection destroys no information; hiding a sprite under another one DOES. Where the
hidden cell was the only evidence for a mechanic, a lower score is a property of the
BOARD and not of the tool — that is rule 7cd's own reading of s5i5 ("on the archived
board the rider is genuinely not in the frame, so the guess is not avoidable — only its
PRICE is"). The accounting below therefore reports what changed, and the classification
of a mover is made from the per-level evidence, never from the score alone.
"""

from __future__ import annotations

import re
import sys
from typing import Any

import numpy as np

# The single engine call site whose return value is the observation frame. Any other
# caller of ``Camera.render`` is GAME LOGIC consuming a picture (sb26 does exactly this
# — it snapshots the render into a sprite's pixels), and mutating that call would make
# the mutation change game state instead of only the view.
_OBSERVATION_CALLER_FILE = "arcengine/base_game.py"
_OBSERVATION_CALLER_FUNC = "perform_action"


# How often to pay for the burial accounting: it costs one extra `_raw_render` PER SPRITE
# per sampled frame, so it runs on every Nth frame the mutation actually changed. The first
# changed frame is always sampled (the counter is 0 there), which is the one that says
# whether the mutation bites at the opening board or only develops during play.
_BURIAL_EVERY = 40


def _buried(camera: Any, before: list[Any], after: list[Any],
            board_before: Any, board_after: Any) -> int:
    """How many sprites contribute a pixel BEFORE the permutation and none after.

    Purpose: separate evidence MOVED from evidence DELETED. Visibility is decided by the
    camera's own painter — a sprite is visible in an order when removing it changes the
    picture — so no assumption is made about layer sorting, about `pixels` versus
    `render()`, or about transparency. Three of the 25 games override `_raw_render` and
    two of those read raw pixels; re-implementing the paint rule here would answer a
    question about a different game.

    Expected feedback: 0 means the mutation only rearranged which sprite owns a contested
    cell — a lower score there is the tool's dependence on paint order. A large count means
    the picture lost objects, and a lower score is then a property of the BOARD; no
    shippable re-render can hide a game's avatar, so such a game gets NO VERDICT.
    """
    visible_before = set()
    for i, sprite in enumerate(before):
        rest = before[:i] + before[i + 1:]
        if int((np.asarray(camera._raw_render(rest)) != np.asarray(board_before)).sum()):
            visible_before.add(id(sprite))
    if not visible_before:
        return 0
    gone = 0
    for i, sprite in enumerate(after):
        if id(sprite) not in visible_before:
            continue
        rest = after[:i] + after[i + 1:]
        if not int((np.asarray(camera._raw_render(rest)) != np.asarray(board_after)).sum()):
            gone += 1
    return gone


def same_layer_permute(sprites: list[Any], kind: str) -> list[Any]:
    """Permute same-layer siblings, leaving every layer's list SLOTS where they were.

    Purpose: the mutation's one primitive. Sprites carrying layer ``L`` are collected
    in list order, permuted among themselves, and written back into the very positions
    they came from — so the relative order of any two sprites on DIFFERENT layers is
    unchanged, and the only thing that can move is which of two co-located same-layer
    sprites is painted last.

    Expected feedback: the returned list is always a permutation of the input with the
    same length and the same objects. If a caller sees a sprite gained or lost, the
    grouping is wrong and every number downstream is describing a different board.
    """
    slots: dict[int, list[int]] = {}
    for i, sprite in enumerate(sprites):
        slots.setdefault(int(sprite.layer), []).append(i)

    out = list(sprites)
    for idxs in slots.values():
        if len(idxs) < 2:
            continue
        group = [sprites[i] for i in idxs]
        if kind == "rev":
            group = group[::-1]
        elif kind == "rot":
            group = group[1:] + group[:1]
        else:  # pragma: no cover - build() is the only caller and it validates
            raise ValueError(f"unknown permutation kind {kind!r}")
        for i, sprite in zip(idxs, group):
            out[i] = sprite
    return out


def whole_list_permute(sprites: list[Any], kind: str) -> list[Any]:
    """Permute the sprite list ENTIRE — the perturbation an actual re-render exhibits.

    Purpose: reach the three games (s5i5, tu93, wa30) whose camera does not sort by layer,
    where the raw list order is the z-order and a same-layer permutation therefore changes
    almost nothing. On the other 22 this is not a wider mutation at all: the engine's
    STABLE ``sorted(key=layer)`` re-imposes the cross-layer order, so the only thing a
    whole-list permutation can change there is the order within a layer.

    Expected feedback: on a layer-sorting game this must produce results identical to
    :func:`same_layer_permute`'s arm. If a round shows `zrev` and `zrevall` disagreeing on
    such a game, the equivalence argument is wrong and BOTH arms' numbers are suspect.
    """
    if kind == "rev":
        return list(sprites)[::-1]
    if kind == "rot":
        return list(sprites[1:]) + list(sprites[:1])
    raise ValueError(f"unknown permutation kind {kind!r}")


class ZOrderMutation:
    """A permutation of the paint order that leaves the game's meaning intact."""

    name = "identity"

    def describe(self) -> dict[str, Any]:
        return {"name": self.name}

    def permute(self, sprites: list[Any]) -> list[Any]:
        return sprites


class SameLayerPermutation(ZOrderMutation):
    """Reorder each layer's sprites among themselves; nothing else changes.

    ``rev`` reverses each layer's group — the maximal disturbance, and the one that
    reproduces the archived s5i5 board's rider-under-bar. ``rot`` cycles each group by
    one, which is a DIFFERENT permutation of the same slots: two arms that disagree
    would expose a result that was luck of which pair happened to swap, exactly as
    `cperm` and `cperm2` do for colour (rule 7ce).
    """

    def __init__(self, kind: str, name: str, scope: str = "same-layer") -> None:
        if kind not in ("rev", "rot"):
            raise ValueError(f"kind must be 'rev' or 'rot', got {kind!r}")
        if scope not in ("same-layer", "whole-list"):
            raise ValueError(f"scope must be 'same-layer' or 'whole-list', got {scope!r}")
        self.kind = kind
        self.scope = scope
        self.name = name

    def describe(self) -> dict[str, Any]:
        return {"name": self.name, "kind": self.kind, "scope": self.scope}

    def permute(self, sprites: list[Any]) -> list[Any]:
        if self.scope == "whole-list":
            return whole_list_permute(sprites, self.kind)
        return same_layer_permute(sprites, self.kind)


class RandomOrder(ZOrderMutation):
    """A FIXED random re-serialisation of the board — the expected case, not the worst.

    ⭐ WHY THIS EXISTS BESIDE THE REVERSAL ARMS. A whole-list reversal is the MAXIMUM
    possible perturbation of paint order, so "14 of 25 games depend on paint order" is a
    worst-case statement. A real re-render is not a reversal — it is some other ordering.
    The competition's own re-render of s5i5 changed the picture by ONE CELL on level 4.
    What the 110 needs is the expected case: given a re-ordering, how often does a game
    move at all, and by how much.

    ⭐ ONE SCOPE SUFFICES, AND THAT IS A THEOREM ABOUT THE ENGINE'S SORT. A uniformly
    random permutation of the whole list induces, on each layer group, a uniformly random
    permutation of THAT GROUP — the relative order of a disjoint subset under a uniform
    permutation is itself uniform, and independent across disjoint subsets. The engine's
    STABLE ``sorted(key=layer)`` then discards everything except those induced within-layer
    orders. So a uniform whole-list shuffle IS the conservative same-layer arm on the 22
    layer-sorting games and the true paint order on the three that never sort. No branch is
    needed and none is taken.

    ⛔ THE ORDER IS FIXED FOR THE RUN, NOT REDRAWN PER FRAME. Re-shuffling every frame is a
    different and far more violent mutation — the board would flicker, which no re-render
    does. Each sprite is keyed ONCE, the first time it is seen, and the key is kept in a
    weak map so the mutation holds no reference the engine does not.

    ⭐ AND THE KEY MODELS WHAT A RE-SERIALISATION ACTUALLY PERMUTES. The engine APPENDS
    sprites created during play, so a re-render of the same game appends them in the same
    order and only the AUTHORED list is free to differ. The key is therefore
    ``(frame first seen, tie-break)``: everything present when a level opens is shuffled
    among itself, and anything that arrives later keeps its arrival order at the end,
    exactly as the engine would place it.

    Seed 0 is the identity — the tie-break becomes the sprite's own list position — so the
    control travels through the SAME code path as every sampled arm rather than beside it.
    """

    def __init__(self, seed: int) -> None:
        import random
        import weakref

        self.seed = int(seed)
        self.name = f"zshuf{self.seed:02d}"
        self._rng = random.Random(self.seed)
        self._keys: Any = weakref.WeakKeyDictionary()
        self._frame = 0

    def describe(self) -> dict[str, Any]:
        return {"name": self.name, "seed": self.seed, "scope": "whole-list uniform",
                "identity": self.seed == 0}

    def permute(self, sprites: list[Any]) -> list[Any]:
        self._frame += 1
        for position, sprite in enumerate(sprites):
            if sprite in self._keys:
                continue
            tiebreak = position if self.seed == 0 else self._rng.random()
            self._keys[sprite] = (self._frame, tiebreak)
        return sorted(sprites, key=lambda s: self._keys[s])


class ZOrderPatch:
    """Install the paint-order mutation on ``Camera.render`` and account for it.

    Purpose: the instrument. It owns everything that lets a number be quoted — how
    many observation frames were re-painted, how many cells actually changed, how many
    frames carried a same-layer overlap at all, and every validity violation.

    Expected feedback: read ``report["verdict"]``.

      * ``"control"`` — the identity arm. Must reproduce the baseline exactly; if it
        does not, the run has code drift and no other arm means anything.
      * ``"applied"`` — the mutation re-painted real frames and this game's score is
        comparable to the control arm.
      * ``"inert"`` — the mutation was installed and changed NOTHING: this game never
        rendered two same-layer sprites over the same cell, so it CANNOT exhibit a
        paint-order dependence. An identical score here is a property of the board and
        is never reported as a transfer success.
      * ``"partial"`` — the game called ``Camera.render`` itself, as game logic, on a
        path this instrument refuses to mutate (sb26 snapshots the render into a
        sprite). The board is then partly mutated and partly not, and rule 7ce's
        all-or-nothing lesson applies: NO VERDICT.
      * ``"invalid"`` — a permutation lost or gained a sprite. Refuse.
    """

    def __init__(self, mutation: ZOrderMutation) -> None:
        self.mutation = mutation
        self._orig: Any = None
        self._camera: Any = None
        self.report: dict[str, Any] = {
            "mutation": mutation.describe(),
            "frames_seen": 0,
            "frames_changed": 0,
            "cells_changed": 0,
            "max_cells_changed_in_a_frame": 0,
            "first_changed_frame": None,
            "buried_max": 0,
            "buried_seen": 0,
            "buried_samples": 0,
            "sprites_max": 0,
            "layers_seen": set(),
            "internal_render_calls": 0,
            "violations": [],
        }

    def install(self) -> "ZOrderPatch":
        from arcengine.camera import Camera

        self._camera = Camera
        self._orig = Camera.render
        orig = self._orig
        report = self.report
        mutation = self.mutation
        is_identity = mutation.name == "identity"

        def render(camera_self: Any, sprites: list[Any]) -> np.ndarray:
            frame = sys._getframe(1)
            from_engine = (
                frame.f_code.co_filename.endswith(_OBSERVATION_CALLER_FILE)
                and frame.f_code.co_name == _OBSERVATION_CALLER_FUNC
            )
            if not from_engine:
                # ⛔ GAME LOGIC IS READING THE PICTURE. Mutating here would change what
                # the game STORES, not what the agent SEES, and the mutation would stop
                # being render-only. Count it and hand back the untouched render.
                report["internal_render_calls"] += 1
                return orig(camera_self, sprites)
            if is_identity or not sprites:
                report["frames_seen"] += 1
                return orig(camera_self, sprites)

            report["frames_seen"] += 1
            report["sprites_max"] = max(report["sprites_max"], len(sprites))
            report["layers_seen"].update(int(s.layer) for s in sprites)

            permuted = mutation.permute(sprites)
            if len(permuted) != len(sprites) or {id(s) for s in permuted} != {
                id(s) for s in sprites
            }:
                report["violations"].append(
                    "the permutation is not a permutation — sprites were lost or gained"
                )
                return orig(camera_self, sprites)

            # ⛔ THE DIFF GOES THROUGH `_raw_render`, NOT THROUGH `render`, AND THE FIRST
            # VERSION GOT THIS WRONG. `render` runs the camera's INTERFACES after painting
            # (`camera.py:300`), and a game is free to give its interface side effects —
            # bp35 and lf52 draw their whole board from one, and calling `render` twice per
            # frame reported 272,208 and 102,399 "changed" cells on boards holding a SINGLE
            # sprite, where a permutation is by definition the identity. lf52 then came
            # back two actions faster, which was the extra interface pass and not the
            # mutation. `_raw_render` builds a fresh array from sprite state and runs no
            # interface, so it is safe to call twice; `render` is called exactly once, on
            # the order the agent is meant to see.
            board_before = camera_self._raw_render(sprites)
            board_after = camera_self._raw_render(permuted)
            if report["frames_seen"] == 1:
                # ⛔ AND THE PAINTER'S OWN DETERMINISM IS CHECKED, NOT ASSUMED — that is the
                # property the double call rests on, and it is exactly what `render` turned
                # out not to have. Three of the 25 games override `_raw_render`.
                again = camera_self._raw_render(sprites)
                if int((np.asarray(board_before) != np.asarray(again)).sum()):
                    report["violations"].append(
                        "the game's own _raw_render is not deterministic — the cell "
                        "accounting cannot separate the mutation from the painter")
            mutated = orig(camera_self, permuted)
            changed = int((np.asarray(board_before) != np.asarray(board_after)).sum())
            if changed and report["frames_changed"] % _BURIAL_EVERY == 0:
                # ⭐ THE DISTINCTION THE SCORE CANNOT MAKE. A lower score under this arm is
                # either a tool reading PAINT ORDER where the mechanic was available another
                # way, or a board whose evidence the mutation deleted — and rule 7ce's
                # shift1 lesson is that the two produce the same number and only the
                # accounting separates them. A sprite that still contributes a pixel has had
                # its evidence MOVED; a sprite contributing none has had it DELETED.
                buried = _buried(camera_self, sprites, permuted, board_before, board_after)
                report["buried_max"] = max(report["buried_max"], buried)
                report["buried_samples"] += 1
                report["buried_seen"] += buried
            if changed:
                if report["first_changed_frame"] is None:
                    report["first_changed_frame"] = report["frames_seen"]
                report["frames_changed"] += 1
                report["cells_changed"] += changed
                report["max_cells_changed_in_a_frame"] = max(
                    report["max_cells_changed_in_a_frame"], changed
                )
            return mutated

        Camera.render = render  # type: ignore[method-assign]
        return self

    def remove(self) -> None:
        if self._camera is not None and self._orig is not None:
            self._camera.render = self._orig  # type: ignore[method-assign]
            self._camera, self._orig = None, None

    def close(self) -> dict[str, Any]:
        """Close the accounting and remove the patch."""
        self.remove()
        out = dict(self.report)
        out["layers_seen"] = sorted(self.report["layers_seen"])
        if self.report["violations"]:
            out["verdict"] = "invalid"
        elif self.mutation.name == "identity":
            out["verdict"] = "control"
        elif self.report["internal_render_calls"]:
            out["verdict"] = "partial"
        elif self.report["frames_changed"] == 0:
            out["verdict"] = "inert"
        else:
            out["verdict"] = "applied"
        return out


def build(spec: str) -> ZOrderMutation:
    """Resolve a command-line arm name to its mutation object.

    Purpose: one place where the arms are named, so a round page and a rerun cannot
    disagree about what ``zrev`` meant.

    Expected feedback: a KeyError names every arm that exists. There is deliberately no
    silent default — an unrecognised arm falling back to the identity would report a
    perfect transfer over a mutation that never happened, which is the failure family
    this campaign has paid for eight times.
    """
    arms = {
        "identity": lambda: ZOrderMutation(),
        # The strictly conservative scope: no sprite may cross a layer boundary. Correct
        # wherever `layer` is a rendering property, which is 22 of the 25 games.
        "zrev": lambda: SameLayerPermutation("rev", "zrev"),
        "zrot": lambda: SameLayerPermutation("rot", "zrot"),
        # ⭐ THE ARM THAT REPRODUCES THE ARCHIVE. On a layer-sorting game the engine's
        # stable sort makes this IDENTICAL to `zrev`; on s5i5/tu93/wa30, whose camera does
        # not sort, it is the only scope that can move anything, and it reproduces the
        # live-vs-archived s5i5 difference cell for cell.
        "zrevall": lambda: SameLayerPermutation("rev", "zrevall", scope="whole-list"),
        "zrotall": lambda: SameLayerPermutation("rot", "zrotall", scope="whole-list"),
    }
    if spec in arms:
        return arms[spec]()
    # ⭐ `zshufNN` — the SAMPLED family, one fixed uniform re-serialisation per seed.
    # `zshuf00` is the identity by construction and is the control drawn from the same
    # generator as the samples; a control produced by a different code path proves less.
    match = re.fullmatch(r"zshuf(\d+)", spec)
    if match:
        return RandomOrder(int(match.group(1)))
    raise KeyError(
        f"unknown mutation {spec!r}; arms are {sorted(arms)} plus zshuf<NN>")
