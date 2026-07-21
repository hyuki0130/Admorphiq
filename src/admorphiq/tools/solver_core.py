"""Executable solver cores — the patchable, sandbox-runnable heart of two tools.

R93-min: the foundation for a tool-fork-and-patch loop. An offline LLM patches
OUR tool's REAL code (not code authored from scratch), so the card the model sees
must BE the code the tool executes — no drifting hand-maintained copies.

Each core is a plain module-level function that is BOTH:
  (a) actually executed by its tool at runtime (``ToggleTool.propose`` /
      ``PaintFloodTool.propose`` delegate to it), and
  (b) shown verbatim to the LLM as the patchable core (``source_card`` assembles
      the REAL source via ``inspect.getsource`` — helpers included so the block
      is self-contained).

Sandbox contract (see ``run_code``): a core may use ONLY ``np`` (numpy), Python
builtins, and the helper functions whose source ``source_card`` bundles. No
imports at runtime — every dependency is either injected (``np``) or in the card.
The cores read ``current_frame`` (list[list[int]] in the sandbox, ndarray at
tool runtime — both are ``np.asarray``-ed), ``transitions`` (a list of
``{"action", "xy": [x, y] | None, "before", "after"}`` dicts), and call
``act(name, x=None, y=None)`` to QUEUE actions (``"CLICK"`` with x,y for ACTION6).

Parity between the two execution paths (tool vs card-through-sandbox) is proven in
``tests/test_solver_core.py``; that test is the definition of "same".
"""

from __future__ import annotations

import inspect
from typing import Any, Callable

import numpy as np

# Reused verbatim from toggle.py so there is ONE implementation; source_card
# bundles their text (via inspect) so the sandbox block is self-contained.
from admorphiq.tools.base import color_histogram
from admorphiq.tools.toggle import _binarize, _gf2_solve

__all__ = [
    "toggle_core",
    "paint_core",
    "paint_plan",
    "source_card",
    "format_core_trace",
]

# A click's flipped-cell set is a toggle STENCIL only if it is small and local.
_MAX_STENCIL = 12
# Learn at least this many distinct click stencils before attempting a GF(2) solve.
_MIN_STENCILS = 4
_BACKGROUND = 0  # colour index 0 is background across ARC-AGI-3 frames


# ── toggle / lights-out core ────────────────────────────────────────────────

def _diff_cells(before: Any, after: Any) -> list[tuple[int, int]]:
    """The (row, col) cells that differ between two same-shape grids."""
    a = np.asarray(before)
    b = np.asarray(after)
    if a.shape != b.shape:
        return []
    ys, xs = np.where(a != b)
    return [(int(y), int(x)) for y, x in zip(ys, xs)]


def _stencils_from_transitions(
    transitions: list[dict[str, Any]],
) -> dict[tuple[int, int], set[tuple[int, int]]]:
    """Rebuild each click's toggle stencil from observed click transitions: the
    set of cells a click at (x, y) flipped, kept only if it is small (1.._MAX)."""
    stencils: dict[tuple[int, int], set[tuple[int, int]]] = {}
    for t in transitions:
        xy = t.get("xy")
        if xy is None:
            continue
        cells = _diff_cells(t["before"], t["after"])
        if 1 <= len(cells) <= _MAX_STENCIL:
            stencils[(int(xy[0]), int(xy[1]))] = set(cells)
    return stencils


def _next_probe(
    frame: np.ndarray, clicked: set[tuple[int, int]],
) -> tuple[int, int] | None:
    """A click on a cell not yet clicked — foreground cells first (the actual
    interactive/lit cells), then a coarse grid to cover the rest. Deterministic."""
    f = np.asarray(frame)
    h, w = f.shape
    hist = color_histogram(f)
    bg = int(hist.argmax()) if hist.any() else 0
    candidates: list[tuple[int, int]] = []
    ys, xs = np.where(f != bg)
    for y, x in zip(ys, xs):
        candidates.append((int(x), int(y)))
    step = max(1, min(h, w) // 8)
    for y in range(step // 2, h, step):
        for x in range(step // 2, w, step):
            candidates.append((x, y))
    for x, y in candidates:
        if (x, y) not in clicked:
            return (x, y)
    return None


def _solve_board(
    frame: np.ndarray,
    stencils: dict[tuple[int, int], set[tuple[int, int]]],
    trace: list[str] | None = None,
) -> list[tuple[int, int]] | None:
    """Build A·x = b over GF(2) from the learned stencils and current board, for
    BOTH uniform targets (all-off / all-on); return the (x, y) click plan for
    whichever solves with the fewest clicks, or None if neither solves."""
    bits, _off, _on = _binarize(np.asarray(frame))
    h, w = bits.shape
    clicks = sorted(stencils)
    n_cells = h * w
    a = np.zeros((n_cells, len(clicks)), dtype=np.uint8)
    for j, click in enumerate(clicks):
        for (r, c) in stencils[click]:
            if 0 <= r < h and 0 <= c < w:
                a[r * w + c, j] = 1
    best: list[tuple[int, int]] | None = None
    for target in (0, 1):
        b = ((bits.reshape(-1) ^ target) % 2).astype(np.uint8)
        x = _gf2_solve(a, b)
        if x is None:
            if trace is not None:
                trace.append(f"GF2 inconsistent for target={target}")
            continue
        plan = [(int(clicks[j][0]), int(clicks[j][1]))
                for j in range(len(clicks)) if x[j]]
        if plan and (best is None or len(plan) < len(best)):
            best = plan
    return best


def toggle_core(
    current_frame: Any,
    transitions: list[dict[str, Any]],
    act: Callable[..., None],
    trace: list[str] | None = None,
) -> None:
    """Lights-out core: rebuild click stencils from the observed transitions,
    GF(2)-solve for a uniform board and queue the plan; if there are not yet
    enough stencils (<_MIN_STENCILS), queue the next systematic probe click."""
    frame = np.asarray(current_frame)
    stencils = _stencils_from_transitions(transitions)
    if len(stencils) >= _MIN_STENCILS:
        plan = _solve_board(frame, stencils, trace)
        if plan:
            if trace is not None:
                trace.append(f"plan={len(plan)} clicks")
            for (x, y) in plan:
                act("CLICK", x, y)
            return
    probe = _next_probe(frame, set(stencils))
    if probe is not None:
        if trace is not None:
            trace.append(
                f"stencils={len(stencils)} (<{_MIN_STENCILS}) -> "
                f"probe ({probe[0]},{probe[1]})"
            )
        act("CLICK", probe[0], probe[1])


# ── paint / flood-fill core ─────────────────────────────────────────────────

def _bg_regions(
    frame: np.ndarray, background: int = _BACKGROUND,
) -> list[list[tuple[int, int]]]:
    """4-connected components of ``background``-coloured cells (list-stack flood
    fill; no collections import so it runs unchanged inside the sandbox)."""
    f = np.asarray(frame)
    h, w = f.shape
    seen = np.zeros((h, w), dtype=bool)
    out: list[list[tuple[int, int]]] = []
    for r in range(h):
        for c in range(w):
            if seen[r, c] or int(f[r, c]) != background:
                continue
            comp: list[tuple[int, int]] = []
            stack = [(r, c)]
            seen[r, c] = True
            while stack:
                y, x = stack.pop()
                comp.append((y, x))
                for ny, nx in ((y + 1, x), (y - 1, x), (y, x + 1), (y, x - 1)):
                    if 0 <= ny < h and 0 <= nx < w and not seen[ny, nx] \
                            and int(f[ny, nx]) == background:
                        seen[ny, nx] = True
                        stack.append((ny, nx))
            out.append(comp)
    return out


def paint_plan(
    frame: np.ndarray,
    background: int = _BACKGROUND,
    max_clicks: int = 14,
    trace: list[str] | None = None,
) -> list[tuple[int, int]]:
    """Click points ``(x=col, y=row)`` to flood the remaining background regions:
    the LARGEST still-background 4-connected components first, one click each at
    a background cell of the component. Deterministic (size then position)."""
    f = np.asarray(frame)
    comps = _bg_regions(f, background)
    comps.sort(key=lambda comp: (-len(comp), comp[0]))
    clicks: list[tuple[int, int]] = []
    for comp in comps[:max_clicks]:
        ys = [p[0] for p in comp]
        xs = [p[1] for p in comp]
        cy = int(round(sum(ys) / len(ys)))
        cx = int(round(sum(xs) / len(xs)))
        if int(f[cy, cx]) != background:  # snap onto a real background cell
            cy, cx = comp[len(comp) // 2]
        clicks.append((cx, cy))
    if trace is not None:
        trace.append(f"paint regions={len(comps)} -> {len(clicks)} clicks")
    return clicks


def _infer_fill_color(
    transitions: list[dict[str, Any]], background: int = _BACKGROUND,
) -> int:
    """The colour clicks paint background with, inferred from click transitions:
    the most common ``background -> new`` recolouring that DOMINATES (>=60%) its
    click's changed cells. -1 when no click transition matches the mechanic."""
    votes: dict[int, int] = {}
    for t in transitions:
        if t.get("xy") is None:
            continue
        before = np.asarray(t["before"])
        after = np.asarray(t["after"])
        if before.shape != after.shape:
            continue
        diff = before != after
        n = int(diff.sum())
        if n == 0:
            continue
        olds = before[diff]
        news = after[diff]
        bg = olds == background
        if not bg.any():
            continue
        vals, counts = np.unique(news[bg], return_counts=True)
        if int(counts.max()) >= 0.6 * n:
            top = int(vals[counts.argmax()])
            votes[top] = votes.get(top, 0) + 1
    if not votes:
        return -1
    return max(votes, key=lambda k: votes[k])


def paint_core(
    current_frame: Any,
    transitions: list[dict[str, Any]],
    act: Callable[..., None],
    trace: list[str] | None = None,
) -> None:
    """Paint/flood core: infer the fill colour from observed click transitions;
    once confirmed, queue clicks filling the largest remaining background regions;
    before it is confirmed, queue one probe click to elicit the mechanic."""
    frame = np.asarray(current_frame)
    fill = _infer_fill_color(transitions)
    if fill < 0:
        if trace is not None:
            trace.append("fill mechanic unconfirmed -> probe 1 region")
        clicks = paint_plan(frame, max_clicks=1, trace=trace)
    else:
        if trace is not None:
            trace.append(f"fill_color={fill} -> fill regions")
        clicks = paint_plan(frame, trace=trace)
    for (x, y) in clicks:
        act("CLICK", x, y)


# ── card assembly + trace formatting ────────────────────────────────────────

_CARD_HEADER = (
    "# ── SANDBOX CONTRACT — you may PATCH the core function below ──────────────\n"
    "# It runs in a sandbox with ONLY: np (numpy), Python builtins, and the\n"
    "# helper fns whose source is shown here. NO imports (they are blocked).\n"
    "# current_frame = list[list[int]] grid; transitions = list of\n"
    "#   {'action': str, 'xy': [x, y] | None, 'before': grid, 'after': grid};\n"
    "# act(name, x=None, y=None) QUEUES an action ('CLICK' with x=col, y=row)."
)

# Functions bundled into each card, in dependency order (a fn only references
# names defined above it). These are the REAL functions the tool executes.
_CARD_FNS: dict[str, list[Callable[..., Any]]] = {
    "toggle": [
        color_histogram, _binarize, _gf2_solve,
        _diff_cells, _stencils_from_transitions, _next_probe, _solve_board,
        toggle_core,
    ],
    "paint": [
        _bg_regions, paint_plan, _infer_fill_color, paint_core,
    ],
}

# Module constants each card's functions reference (as default args / in bodies).
# Emitted from the LIVE module value so the card never drifts from the source.
_CARD_CONSTS: dict[str, tuple[str, ...]] = {
    "toggle": ("_MAX_STENCIL", "_MIN_STENCILS"),
    "paint": ("_BACKGROUND",),
}


def source_card(tool_name: str) -> str:
    """Assemble the REAL, sandbox-runnable source the LLM patches: the core
    function's source + every helper it needs (via ``inspect.getsource``, so the
    card can never drift from the code the tool executes).

    A ``from __future__ import annotations`` line is prepended because the card is
    re-exec'd WITHOUT this module's own future import — otherwise the retrieved
    annotations (``Any`` / ``Callable``) would be evaluated at def-time and raise
    NameError in the import-free sandbox. The referenced module constants are
    emitted from their live values for the same reason (they appear in defaults).
    """
    if tool_name not in _CARD_FNS:
        raise KeyError(f"no solver card for tool {tool_name!r}")
    consts = "\n".join(f"{n} = {globals()[n]}" for n in _CARD_CONSTS[tool_name])
    parts = ["from __future__ import annotations", _CARD_HEADER, consts]
    parts.extend(inspect.getsource(fn) for fn in _CARD_FNS[tool_name])
    return "\n\n".join(parts)


def format_core_trace(trace: list[str]) -> str:
    """One decision per line, for prompt injection (patcher localization info)."""
    return "\n".join(f"- {line}" for line in trace) if trace else "(no decisions)"
