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

⛔ THE PERMUTATION IS SAME-LAYER ONLY, AND THAT IS NOT A DETAIL. Reordering across
layers would change what the engine draws on top in ways a re-render is NOT free to
make — layer is an authored property. Reordering SAME-LAYER siblings changes only
which of two co-located sprites wins a pixel, which is exactly the s5i5 perturbation
and exactly what a legitimate re-serialisation of the same board may differ in.
:func:`same_layer_permute` therefore preserves every sprite's LAYER SLOT: the sprites
carrying layer L occupy the same list positions before and after, permuted among
themselves, so the cross-layer relative order is byte-identical.

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

import sys
from typing import Any

import numpy as np

# The single engine call site whose return value is the observation frame. Any other
# caller of ``Camera.render`` is GAME LOGIC consuming a picture (sb26 does exactly this
# — it snapshots the render into a sprite's pixels), and mutating that call would make
# the mutation change game state instead of only the view.
_OBSERVATION_CALLER_FILE = "arcengine/base_game.py"
_OBSERVATION_CALLER_FUNC = "perform_action"


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

    def __init__(self, kind: str, name: str) -> None:
        if kind not in ("rev", "rot"):
            raise ValueError(f"kind must be 'rev' or 'rot', got {kind!r}")
        self.kind = kind
        self.name = name

    def describe(self) -> dict[str, Any]:
        return {"name": self.name, "kind": self.kind, "scope": "same-layer siblings"}

    def permute(self, sprites: list[Any]) -> list[Any]:
        return same_layer_permute(sprites, self.kind)


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

            reference = orig(camera_self, sprites)
            mutated = orig(camera_self, permuted)
            changed = int((np.asarray(reference) != np.asarray(mutated)).sum())
            if changed:
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
        "zrev": lambda: SameLayerPermutation("rev", "zrev"),
        "zrot": lambda: SameLayerPermutation("rot", "zrot"),
    }
    if spec not in arms:
        raise KeyError(f"unknown mutation {spec!r}; arms are {sorted(arms)}")
    return arms[spec]()
