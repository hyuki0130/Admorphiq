"""`detect` must be a QUESTION, not a move — this pins the population that violates it.

Purpose
-------
The harness asks every registered tool `detect(frames, obs)` on the same board it then asks
`propose` about. A `detect` that mutates makes the run depend on how often it is ASKED, which no
caller controls. Measured 2026-08-30: `railpeg.detect` runs the planner and advances `_sincecapture`
and `_barren` — two counters with a threshold of THREE that decide when the tool stops proposing —
so merely asking that tool whether it recognises a board spends a third of its patience. Sampling
every tool's bid every 10 actions moved lf52 from 823 to 827 actions; bisecting 50 arms attributed
all four to `railpeg` alone, with both a negative and a positive control passing exactly.

Expected feedback
-----------------
FAIL means the count of tools whose `detect` reaches a mutating line has CHANGED. Going UP is a new
tool written in the unsafe shape and it should be rewritten in `socketmerge`'s pattern — save the
state tuple, mutate while reading, restore in a `finally`, which is pure by construction rather than
by luck. Going DOWN is a repair, and the number here should be lowered in the same commit.

⚠️ The scan is static: it reports REACHABILITY, not a verdict. A tool listed here may never touch its
mutating line on any public board — and that is precisely the risk, because the evaluation is 110
boards nobody has seen with the identical tool set, so "clean on lf52" is not "pure".
"""

from __future__ import annotations

import subprocess
from pathlib import Path

# Measured 2026-08-30 by scripts/detect_purity_scan.sh at commit a14c14ed.
_KNOWN_IMPURE = 19


def test_detect_purity_population_has_not_grown() -> None:
    root = Path(__file__).resolve().parent.parent
    out = subprocess.run(
        ["bash", str(root / "scripts" / "detect_purity_scan.sh")],
        capture_output=True,
        text=True,
        cwd=root,
        check=True,
    ).stdout
    tail = [ln for ln in out.splitlines() if "tools have a detect" in ln]
    assert tail, f"the scan changed its output shape; cannot read a count from:\n{out}"
    n = int(tail[-1].split()[0])
    assert n == _KNOWN_IMPURE, (
        f"{n} tools have a detect that reaches a mutating line; the pinned count is "
        f"{_KNOWN_IMPURE}.\n"
        "UP: a new tool mutates in detect. Copy socketmerge — save the state tuple, mutate while "
        "reading, restore in a finally.\n"
        "DOWN: a repair; lower _KNOWN_IMPURE in the same commit.\n"
        f"{out}"
    )
