"""Render-only mutations of the OBSERVATION, for transfer measurement.

⭐ WHAT THIS MEASURES. Whether the generic tools read the board's STRUCTURE or its
PIXELS. A mutation here changes how a board is presented to the agent — the colour
labels, the position on the canvas — and changes nothing about what the board means.
A tool that reads mechanics must therefore play the identical move sequence; every
action that differs is a render dependence, and it is measured per game.

⛔ WHAT IT DOES NOT PROVE. It does not predict a game we have never seen, which is
what all 110 private games are. A relabelled board is still the SAME BOARD with the
same mechanic. This is a floor on brittleness, exactly as `xfergate.sh`'s archived
re-render is, and it must not be quoted as a transfer coefficient. What it buys over
`xfergate.sh` is coverage: the archive holds a re-render for only 14 of the 25 games
(sk48's "archive" is the same version hash, byte-identical — a self-substitution), and
this instrument applies to all 25 because it manufactures the mutation.

⭐ WHY THE MUTATION IS AT THE OBSERVATION BOUNDARY AND NOT IN THE GAME'S SOURCE.
The validity of the instrument is the deliverable: a mutation that changes the MECHANIC
produces a lower score that means nothing and looks exactly like a transfer failure.
Mutating the source cannot be shown safe without reading every line of a 41,000-line
game. Mutating the observation is safe BY CONSTRUCTION:

  * the game object never sees a mutated frame — the mutation is applied to a copy,
    strictly after ``env.step()`` returns;
  * the action that reaches the game is mapped back into the game's own coordinates,
    so the engine receives exactly the input it would have received unmutated;
  * therefore the game's state trajectory is a function of the action sequence alone,
    the level structure and the win predicate are untouched, and ``baseline_actions``
    in ``metadata.json`` is still the right denominator.

The residual assumption, stated rather than hidden: that the HUMAN baseline is invariant
under the mutation. For a colour permutation it is — a human never sees a colour INDEX,
only a palette, and a bijection maps a palette to another palette of equally distinct
colours. For a rigid translation it is, provided nothing is pushed off the canvas, which
:class:`Translate` checks on every frame and refuses when violated.

⛔ THE REFUSAL PATH IS THE POINT. Eight instruments in this campaign have failed by
reporting ABSENCE — a guard that could not see reported success. So every mutation
counts what it actually changed, and :class:`MutantAgent` refuses a verdict when:

  * a non-identity mutation changed NO cell of any frame (it did not apply, or the
    game's colour alphabet happens to be fixed by this permutation) — an inert
    mutation is reported as inert, never as a transfer success;
  * a colour outside 0..15 was observed (the lookup table would be wrong);
  * a translation lost board content off the canvas, or the agent clicked into the
    synthetic band so no in-range game coordinate exists.
"""

from __future__ import annotations

from typing import Any

import numpy as np

# The ARC colour alphabet. Frames are composited, so -1 (sprite transparency) never
# reaches the agent; a value outside this range means the assumption is wrong and the
# run is refused rather than silently mis-mapped.
N_COLOURS = 16


def derangement(n: int = N_COLOURS, mult: int = 7, add: int = 3) -> list[int]:
    """A fixed-point-free bijection of ``range(n)``: ``c -> (mult*c + add) % n``.

    Purpose: give the colour mutation a permutation that is reproducible from its
    parameters alone (no seed file, no RNG version) and that moves EVERY colour, so
    "the score is identical" can never be explained by the mutation having left the
    game's own palette alone.

    Expected feedback: a ValueError here means the parameters do not generate a
    derangement, and the caller must pick others — it is not a condition to work
    around, because a permutation with a fixed point weakens every claim made from it.
    """
    perm = [(mult * c + add) % n for c in range(n)]
    if sorted(perm) != list(range(n)):
        raise ValueError(f"mult={mult} is not invertible mod {n}")
    fixed = [c for c in range(n) if perm[c] == c]
    if fixed:
        raise ValueError(f"mult={mult} add={add} fixes {fixed} — not a derangement")
    return perm


def fixing(perm: list[int], keep: int) -> list[int]:
    """Return a bijection equal to ``perm`` except that ``keep`` maps to itself.

    Purpose: the background-preserving colour arm. ``perm`` sends ``keep -> a`` and
    ``p -> keep`` for some ``p``; the returned map sends ``keep -> keep`` and
    ``p -> a``, which is still a bijection because the same value set is assigned to
    the same key set.

    Expected feedback: used to separate "the tool keys on the literal background
    colour" from "the tool keys on colour labels generally". If a game survives this
    arm and not the full one, the dependence is on the background value specifically.
    """
    out = list(perm)
    p = perm.index(keep)
    out[keep], out[p] = keep, perm[keep]
    if sorted(out) != list(range(len(perm))):
        raise ValueError("fixing() broke the bijection")
    return out


class RenderMutation:
    """A relabelling of the observation that leaves the game's meaning intact."""

    name = "identity"

    def describe(self) -> dict[str, Any]:
        return {"name": self.name}

    def apply(self, layers: list[np.ndarray], report: dict[str, Any]) -> list[np.ndarray]:
        return layers

    def to_game_xy(self, x: int, y: int, report: dict[str, Any]) -> tuple[int, int]:
        """Map a click the agent made in MUTATED coordinates back to the game's."""
        return x, y

    def to_agent_xy(self, x: int, y: int) -> tuple[int, int]:
        """Map the echoed ``action_input`` from game coordinates to the agent's."""
        return x, y


class ColourPermutation(RenderMutation):
    """Relabel every cell of every layer through a bijection of the 16 colours.

    Structure — regions, adjacency, equality and inequality of cells, counts, the
    background's identity as "the most common value" — is preserved exactly. Only the
    labels move. The click coordinates are untouched, so this arm needs no action
    conjugation and cannot lose board content: it is the strongest-validity mutation
    available and the one to read first.
    """

    def __init__(self, perm: list[int], name: str = "cperm",
                 fix_background: bool = False) -> None:
        if sorted(perm) != list(range(N_COLOURS)):
            raise ValueError("perm is not a bijection of 0..15")
        self.base = perm
        self.perm = perm
        self.fix_background = fix_background
        self.name = name
        self._table: np.ndarray | None = None
        self._resolved = not fix_background

    def describe(self) -> dict[str, Any]:
        return {"name": self.name, "perm": self.perm,
                "fix_background": self.fix_background,
                "fixed_points": [c for c in range(N_COLOURS) if self.perm[c] == c]}

    def apply(self, layers: list[np.ndarray], report: dict[str, Any]) -> list[np.ndarray]:
        if not self._resolved:
            # The background is only known once a frame has been seen; ``_view``
            # records it before calling here.
            self.perm = fixing(self.base, int(report["background_first_frame"]))
            self._resolved, self._table = True, None
        out = []
        for layer in layers:
            arr = np.asarray(layer)
            if self._table is None or self._table.dtype != arr.dtype:
                self._table = np.array(self.perm, dtype=arr.dtype)
            out.append(self._table[arr])
        return out


class Translate(RenderMutation):
    """Shift the whole board by (dy, dx), filling the vacated band with background.

    The agent's clicks are mapped back by the inverse shift, so the engine receives
    the coordinate it would have received unmutated — the mutation is a conjugation
    of the whole interaction, not merely of the picture.

    ⛔ VALIDITY IS CHECKED ON EVERY FRAME, NOT ASSUMED, AND THE CONDITION IS TWO-SIDED.
    The board must already carry a UNIFORM MARGIN of at least the shift on BOTH the
    leaving and the entering side, of the SAME colour, which then fills the vacated
    band. Under that condition the mutated frame differs from the original only by
    moving the content rigidly inside a margin it already had — a camera pan. Anything
    weaker changes the picture: a first version required only that the outgoing band be
    uniform and background-coloured, which on a walled board deletes one wall row and
    leaves the opposite side open. The game is REFUSED when the condition fails, and a
    refused game is never reported as a transfer failure — a lower score from a broken
    mutation and a lower score from a brittle tool look identical in the number alone.
    """

    def __init__(self, dy: int, dx: int) -> None:
        if dy == 0 and dx == 0:
            raise ValueError("a zero translation is the identity — use Identity")
        self.dy, self.dx = dy, dx
        self.name = f"shift{dy}_{dx}"

    def describe(self) -> dict[str, Any]:
        return {"name": self.name, "dy": self.dy, "dx": self.dx}

    def apply(self, layers: list[np.ndarray], report: dict[str, Any]) -> list[np.ndarray]:
        out = []
        for layer in layers:
            arr = np.asarray(layer)
            h, w = arr.shape
            ay, ax = abs(self.dy), abs(self.dx)
            bands = []
            if ay:
                bands += [arr[:ay, :], arr[h - ay:, :]]
            if ax:
                bands += [arr[:, :ax], arr[:, w - ax:]]
            values = {int(v) for band in bands for v in np.unique(band)}
            if len(values) != 1:
                report["violations"].append(
                    f"no uniform margin of {ay}/{ax} on both sides — the leaving and "
                    f"entering bands hold {sorted(values)}, so the shift would move "
                    f"board content across the canvas edge")
                return layers
            fill = values.pop()

            shifted = np.full_like(arr, fill)
            ys, yd = (slice(self.dy, h), slice(0, h - self.dy)) if self.dy >= 0 \
                else (slice(0, h + self.dy), slice(-self.dy, h))
            xs, xd = (slice(self.dx, w), slice(0, w - self.dx)) if self.dx >= 0 \
                else (slice(0, w + self.dx), slice(-self.dx, w))
            shifted[ys, xs] = arr[yd, xd]
            out.append(shifted)
        return out

    def to_game_xy(self, x: int, y: int, report: dict[str, Any]) -> tuple[int, int]:
        gx, gy = x - self.dx, y - self.dy
        if not (0 <= gx < 64 and 0 <= gy < 64):
            report["violations"].append(
                f"agent clicked ({x},{y}) in the synthetic band — no game coordinate")
            return max(0, min(63, gx)), max(0, min(63, gy))
        return gx, gy

    def to_agent_xy(self, x: int, y: int) -> tuple[int, int]:
        return x + self.dx, y + self.dy


class MutantAgent:
    """Wrap an agent so it plays a render-mutated view of an unmutated game.

    Purpose: the whole instrument. It owns the accounting that lets a number be
    quoted — how many frames were mutated, how many cells actually changed, which
    colours the game ever showed, and every validity violation.

    Expected feedback: read ``report["verdict"]``. ``"applied"`` means the mutation
    took effect on real frames and the score is comparable to the control arm.
    ``"inert"`` and ``"invalid"`` both mean NO VERDICT for that game — an inert
    mutation scoring identically says nothing at all, which is the failure mode that
    has cost this campaign eight instruments.
    """

    def __init__(self, inner: Any, mutation: RenderMutation) -> None:
        self.inner = inner
        self.mutation = mutation
        self.report: dict[str, Any] = {
            "mutation": mutation.describe(),
            "frames_seen": 0,
            "frames_changed": 0,
            "cells_changed": 0,
            "clicks_mapped": 0,
            "colours_seen": set(),
            "background_first_frame": None,
            "violations": [],
        }

    # The run loop reads these off the adapter; delegate rather than reimplement.
    def __getattr__(self, item: str) -> Any:
        return getattr(self.inner, item)

    def _view(self, obs: Any) -> Any:
        layers = list(obs.frame)
        if not layers:
            return obs
        flat = np.concatenate(
            [np.asarray(x, dtype=np.int64).reshape(-1) for x in layers])
        lo, hi = int(flat.min()), int(flat.max())
        if lo < 0 or hi >= N_COLOURS:
            # ⛔ The lookup table would silently mis-map. Refuse rather than relabel.
            self.report["violations"].append(
                f"observed colour {lo}..{hi} outside 0..{N_COLOURS - 1}")
            return obs
        self.report["colours_seen"].update(int(v) for v in np.unique(flat))
        if self.report["background_first_frame"] is None:
            self.report["background_first_frame"] = int(
                np.bincount(flat, minlength=N_COLOURS).argmax())
        mutated = self.mutation.apply(layers, self.report)
        self.report["frames_seen"] += 1
        changed = sum(int((np.asarray(a) != np.asarray(b)).sum())
                      for a, b in zip(layers, mutated))
        if changed:
            self.report["frames_changed"] += 1
            self.report["cells_changed"] += changed

        view = obs.model_copy()
        view.frame = mutated
        data = dict(getattr(obs.action_input, "data", {}) or {})
        if "x" in data and "y" in data:
            ax, ay = self.mutation.to_agent_xy(int(data["x"]), int(data["y"]))
            if 0 <= ax < 64 and 0 <= ay < 64:
                data["x"], data["y"] = ax, ay
                view.action_input = obs.action_input.model_copy(update={"data": data})
        return view

    def is_done(self, frames: list[Any], obs: Any) -> bool:
        return self.inner.is_done(frames, self._view(obs))

    def choose_action(self, frames: list[Any], obs: Any) -> Any:
        action = self.inner.choose_action(frames, self._view(obs))
        if getattr(action, "is_complex", None) and action.is_complex():
            d = action.action_data
            gx, gy = self.mutation.to_game_xy(int(d.x), int(d.y), self.report)
            if (gx, gy) != (int(d.x), int(d.y)):
                action.set_data({"game_id": d.game_id, "x": gx, "y": gy})
                self.report["clicks_mapped"] += 1
        return action

    def close(self) -> dict[str, Any]:
        """Close the accounting: 'applied' | 'inert' | 'invalid'."""
        out = dict(self.report)
        out["colours_seen"] = sorted(self.report["colours_seen"])
        if self.report["violations"]:
            out["verdict"] = "invalid"
        elif self.mutation.name == "identity":
            out["verdict"] = "control"
        elif self.report["frames_changed"] == 0:
            out["verdict"] = "inert"
        else:
            out["verdict"] = "applied"
        return out


def build(spec: str) -> RenderMutation:
    """Resolve a command-line mutation name to its object.

    Purpose: one place where the arms of the instrument are named, so a round page
    and a rerun cannot disagree about what ``cperm`` meant.

    Expected feedback: a KeyError names every arm that exists — the instrument has no
    silent default, because an unrecognised arm silently falling back to the identity
    would report a perfect transfer over a mutation that never happened.
    """
    arms = {
        "identity": lambda: RenderMutation(),
        "cperm": lambda: ColourPermutation(derangement(), name="cperm"),
        # ⛔ A SECOND, INDEPENDENT PERMUTATION. One derangement scoring identically could
        # in principle be luck of which labels happened to swap; two that disagree with
        # each other would expose it, and two that both hold is a much stronger claim.
        "cperm2": lambda: ColourPermutation(
            derangement(mult=5, add=1), name="cperm2"),
        "cpermbg": lambda: ColourPermutation(
            derangement(), name="cpermbg", fix_background=True),
        "shift1": lambda: Translate(1, 1),
        "shift3": lambda: Translate(3, 3),
    }
    if spec not in arms:
        raise KeyError(f"unknown mutation {spec!r}; arms are {sorted(arms)}")
    return arms[spec]()
