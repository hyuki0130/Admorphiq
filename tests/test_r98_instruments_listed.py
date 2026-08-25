"""Pin: every R98 script is named in the round page's Instruments table.

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
