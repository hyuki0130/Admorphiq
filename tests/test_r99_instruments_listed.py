"""Pin the R99 round page's instrument index.

Purpose
-------
R98 paid for this lesson: probes were written, run, and their findings recorded while the
scripts existed only in a shell command, and a finding whose instrument cannot be found has to
be RE-DERIVED to be re-checked. R99 produced nine instruments in one session; this keeps the
page's table honest about them.

Expected feedback
-----------------
A pass means every script the round leans on is findable from the page. A failure names the
script that was added without being listed — add the row, do not delete the test.
"""

from pathlib import Path

PAGE = Path(".wiki/wiki/rounds/r99_detection-dispatch.md")
INSTRUMENTS = [
    "scripts/detector_falsepos.py",
    "scripts/detector_transfer.py",
    "scripts/detector_transfer_score.py",
    "scripts/detect_compare.py",
    "scripts/benched_vs_shipped.py",
    "scripts/gap_table.py",
    "scripts/summary_agrees.py",
    "scripts/round_lookup.py",
    "kaggle/build_and_push.sh",
]


def test_every_r99_instrument_exists_and_is_listed():
    """Each instrument is both ON DISK and NAMED on the round page.

    Expected feedback: a pass means a reader can re-run any measurement the round claims. A
    failure means either a script was deleted while the page still cites it, or one was added
    without a row — both leave a finding that cannot be re-checked.
    """
    text = PAGE.read_text()
    for script in INSTRUMENTS:
        assert Path(script).is_file(), f"{script} is cited but missing from the repo"
        assert script in text, f"{script} exists but is not listed on the round page"


def test_the_measurement_artefacts_are_committed():
    """The numbers reproduce without ssh access to the measurement box.

    Expected feedback: a pass means the card, ceiling and dispatch runs are in the repository.
    A failure means a quoted number can no longer be re-derived here.
    """
    for directory in ("scripts/rounds/SUBCAND1/games",
                      "scripts/rounds/CEILING1",
                      "scripts/rounds/SHIPPED1/games"):
        path = Path(directory)
        assert path.is_dir() and any(path.iterdir()), f"{directory} is empty or missing"
