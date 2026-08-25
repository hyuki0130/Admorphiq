"""Pins for the R98 round page's integrity: its instrument index and its entry numbering.

Purpose
-------
Two probes this round were written, run, and their findings recorded while the scripts
themselves existed only in a shell command — a finding whose instrument cannot be found has
to be re-derived to be re-checked. A table was added to fix that, and within the hour a new
script was missing from it, because a table is only current until the next thing is built.

Expected feedback
-----------------
A failure names the script that was added without being listed. Add a row saying what
question it answers, not what it does — a reader arrives with a question, not a filename.
"""

from __future__ import annotations

import re
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_PAGE = _ROOT / ".wiki" / "wiki" / "rounds" / "r98_flow-deflection.md"
_SCRIPTS = _ROOT / "scripts" / "rounds" / "R98"


def test_every_r98_script_is_named_on_the_round_page() -> None:
    """Purpose: keeps the instruments index honest as the round grows.
    Expected feedback: a failure means a tool exists that the page cannot lead a reader to."""
    page = _PAGE.read_text()
    missing = sorted(p.name for p in _SCRIPTS.glob("*.py") if p.name not in page)
    assert not missing, f"scripts absent from the round page: {missing}"


def test_entry_numbers_above_six_are_unique() -> None:
    """Purpose: the round page cites its own findings by number — "#54", "#89", "#121" — and
    `rounds/index.md` does too, so a reused number silently sends a reader to the wrong
    finding. Numbers 1-6 recur legitimately: markdown restarts each list block, and the low
    ones belong to narrative sub-lists rather than to entries. Everything above that is an
    entry reference and has to resolve.

    Expected feedback: a failure names the number cited twice, which is the reference that
    would have taken a reader somewhere other than where the citation meant."""
    # An anchored list-item prefix, not "starts with a digit and has a dot nearby". The first
    # version of this parser swallowed lines like "0/9 FAIL" and died on them — the same class
    # of error this round has been catching all day, in the check rather than in the thing
    # checked.
    numbers = [
        int(match.group(1))
        for match in re.finditer(r"^(\d{1,3})\. ", _PAGE.read_text(), re.MULTILINE)
    ]
    entries = [n for n in numbers if n >= 7]
    duplicates = sorted({n for n in entries if entries.count(n) > 1})
    assert not duplicates, f"entry numbers cited more than once: {duplicates}"
