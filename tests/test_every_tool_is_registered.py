"""A tool file that is committed but not registered has never run, and measures like an absent one.

Purpose: pin that every `src/admorphiq/tools/*.py` defining a `*Tool` class is either in
`default_tools()` or listed here with the measurement that retired it.

Expected feedback: a FAIL means someone added a tool and forgot the registry — the tool does not
bid, does not propose, and any measurement of it is a measurement of nothing.

⛔ WHY THIS EXISTS, MEASURED. `fogscout.py` was committed 2026-08-27 and never registered. It was
then measured, found "inert", and set aside — because an unregistered tool scores exactly like an
absent one. Registering it on 2026-08-28 took ls20 from 0.7500 to 0.8442 (7/7) and the full-25 mean
from 0.8892 to 0.8929, with no game regressing. The tool was right the whole time; the measurement
was of nothing.
"""
from __future__ import annotations

import pathlib
import re

from admorphiq.harness.registry import default_tools

#: Tool files deliberately NOT registered, each with the measurement that retired it.
#: ⛔ Adding a name here requires a measurement, not an opinion.
RETIRED = {
    # Replaced by `crag`, which clears everything it cleared and one level more.
    "ledge",
    "shaft",
    # Registered alongside `crag` in a snapshot and measured 2026-08-28: bp35 0.2078 and
    # lf52 0.2727, i.e. IDENTICAL to the tree without it on both games it targets.
}


def _tool_files() -> list[str]:
    root = pathlib.Path(__file__).resolve().parent.parent / "src" / "admorphiq" / "tools"
    out = []
    for p in sorted(root.glob("*.py")):
        if p.stem in ("__init__", "base"):
            continue
        if re.search(r"^class \w+Tool\b", p.read_text(), re.M):
            out.append(p.stem)
    return out


def _registered_names() -> set[str]:
    names = set()
    for t in default_tools():
        names.add(getattr(t, "name", ""))
        names.add(type(t).__name__)
    return names


def test_every_tool_file_is_registered_or_explicitly_retired() -> None:
    """Every committed tool either runs or is retired ON THE RECORD.

    Purpose: proves no tool is silently absent from the agent.

    Expected feedback: the failure message names the files that define a Tool class and do not
    appear in `default_tools()`. Either register them, or add them to RETIRED with the
    measurement that justifies it.
    """
    live = _registered_names()
    missing = []
    for stem in _tool_files():
        src = (pathlib.Path(__file__).resolve().parent.parent
               / "src" / "admorphiq" / "tools" / f"{stem}.py").read_text()
        m = re.search(r'name\s*=\s*["\'](\w+)["\']', src)
        declared = m.group(1) if m else stem
        if stem in RETIRED:
            continue
        if declared not in live and stem not in live:
            missing.append(stem)
    assert not missing, (
        "committed but NOT registered — these have never run and measure like absent tools: "
        f"{sorted(missing)}"
    )


def test_retired_list_names_only_real_files() -> None:
    """RETIRED must not accumulate names of files that no longer exist.

    Purpose: a stale exemption silently re-opens the hole this suite closes.

    Expected feedback: a FAIL means a retired tool was deleted; drop it from RETIRED too.
    """
    stems = set(_tool_files())
    stale = sorted(RETIRED - stems)
    assert not stale, f"RETIRED names files that no longer define a Tool class: {stale}"
