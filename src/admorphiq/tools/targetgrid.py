"""Target-grid goal inference — the LLM draws the solved board (shared core).

The measured 25/25-frontier lever (r53): the GoalSpec vocabulary cannot express
the transform games' true targets, but an arbitrary TARGET FRAME can. Ask the
offline LLM to DRAW the solved board as a small grid, validate the draw, and
inject it via :meth:`GraphSearchTool.set_target_frame` so frontier ranking steers
toward it. cd82 is the measured proof (0 under every coarse-goal approach → 1).

Measured-optimal configuration (do not "improve" without re-measuring — every
cheap variation was swept and regressed or was inert): gemma4-31b drawer, simple
prompt, 8×8 resolution, first-64 parse, lenient validation with one retry.

One implementation shared by the probe (scripts/probe_tool_direct.py) and the
deployed harness (admorphiq/harness/loop.py).
"""

from __future__ import annotations

import re

import numpy as np

from admorphiq.tools.graph_search import _downsample

__all__ = ["build_target_prompt", "parse_and_validate_target", "TARGET_RES"]

# Measured-optimal resolution (res=16 regressed cd82; 8 is the sweet spot).
TARGET_RES = 8


def build_target_prompt(
    frame: np.ndarray, res: int = TARGET_RES,
    solved_example: np.ndarray | None = None,
) -> str:
    """The validated simple prompt: show the current res×res downsample, ask for
    the solved board as res lines of res integers. (Enriching this prompt with
    transitions/reasoning was MEASURED to regress — keep the base simple.)

    ``solved_example`` is CROSS-LEVEL CLEAR EVIDENCE: the board captured at the
    moment a previous level of the SAME game cleared. Levels within a game share
    mechanics, so showing what "solved" actually looked like turns blind goal
    inference into evidence-based inference — the measured wall is inference
    accuracy, and this is the strongest goal evidence the agent can ever hold.
    """
    cur = _downsample(np.asarray(frame), res)
    rows = "\n".join(" ".join(str(int(v)) for v in r) for r in cur)
    example = ""
    if solved_example is not None:
        ex = _downsample(np.asarray(solved_example), res)
        ex_rows = "\n".join(" ".join(str(int(v)) for v in r) for r in ex)
        example = (
            f"\nA PREVIOUS level of this same game looked like this ({res}x{res}) "
            "at the moment it was SOLVED — the new level's goal is analogous:\n"
            + ex_rows + "\n"
        )
    return (
        f"An ARC-AGI-3 grid puzzle. The board below is a {res}x{res} downsample "
        "(colours 0-15, 0=background) of the CURRENT state:\n" + rows + "\n"
        + example + "\n"
        f"Reason about the goal, then OUTPUT the {res}x{res} grid of the SOLVED board "
        f"(what it looks like when the level is complete) as {res} lines of {res} "
        f"space-separated integers 0-15. Output ONLY the {res} lines, no prose."
    )


def parse_and_validate_target(
    txt: str, frame: np.ndarray, res: int = TARGET_RES
) -> tuple[np.ndarray | None, str]:
    """Parse a drawn target out of raw LLM text and sanity-check it.

    Returns ``(target_res_grid, "ok")`` or ``(None, reject_reason)``. Validation
    is deliberately LENIENT — it only guards against GARBAGE draws (degenerate /
    identical-to-current / hallucinated palette); a wrongly rejected good target
    just leaves graph on its proven frame-only base.
    """
    nums = [int(x) for x in re.findall(r"-?\d+", txt)]
    ncells = res * res
    if len(nums) < ncells:
        return None, f"<{ncells} numbers"
    tgt = np.array(nums[:ncells], dtype=np.int64).reshape(res, res)
    if len(np.unique(tgt)) < 2:
        return None, "degenerate (single colour)"
    cur = _downsample(np.asarray(frame), res)
    if np.array_equal(tgt, cur):
        return None, "identical to current (no goal)"
    palette = set(int(v) for v in np.unique(np.asarray(frame)))
    in_palette = float(np.mean([int(v) in palette for v in tgt.ravel()]))
    if in_palette < 0.8:
        return None, f"hallucinated colours ({in_palette:.0%} in palette)"
    return tgt, "ok"
