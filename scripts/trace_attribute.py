"""Attribute trace events to levels ONLY when the event says which level it belongs to.

⛔ WHY THIS EXISTS. Every instrumented dive on 2026-08-28 used the same pattern: a tool prints a
marker, the runner prints one line per action, and a script assigns each event to the most recent
level seen. That is valid only when the marker fires once per action. When it fires on a subset —
a branch reached on refills, a function called once per level — the last marker is carried across
every action until the next one, and a handful of events is reported as hundreds.

It produced three false findings in one session, each of which had to be withdrawn:

  * "499 of 500 dc22 actions come from one read failure"   -> the failure fires TEN times
  * "s5i5 level 7 has riders=2 places=2"                   -> that was level 6's model
  * "swivel's replan fails on level 7"                     -> attributed by proximity, not measured

and it was committed twice AFTER being written up as the sixth entry of
`.wiki/wiki/lessons/instrument_validity_20260825.md`. A rule that is only prose gets broken; this
turns it into an exception.

USE IT LIKE THIS. Print the level ON THE EVENT LINE, from inside the code that fires:

    print(f"[rp] lvl={levels_completed(obs)} pairings={n}", file=sys.stderr, flush=True)

then

    uv run python scripts/trace_attribute.py /tmp/run.trace rp

⛔ If an event line has no `lvl=`, this REFUSES to guess. That refusal is the whole point.
"""
from __future__ import annotations

import collections
import pathlib
import sys


def parse(lines: list[str], tag: str) -> dict[int, collections.Counter]:
    """Group `[tag]` events by the level THEY name. Raises if any event omits `lvl=`."""
    per: dict[int, collections.Counter] = collections.defaultdict(collections.Counter)
    naked = 0
    for ln in lines:
        if not ln.startswith(f"[{tag}]"):
            continue
        fields = ln.split()[1:]
        kv = dict(f.split("=", 1) for f in fields if "=" in f)
        if "lvl" not in kv:
            naked += 1
            continue
        rest = " ".join(f for f in fields if not f.startswith("lvl="))
        per[int(kv["lvl"])][rest] += 1
    if naked:
        raise SystemExit(
            f"⛔ {naked} '[{tag}]' event(s) carry no lvl= field. Attribution by proximity is what "
            f"produced three withdrawn findings on 2026-08-28 — print the level from inside the "
            f"code that fires the marker instead of inferring it from the nearest action line."
        )
    return per


def main() -> None:
    if len(sys.argv) != 3:
        raise SystemExit("usage: trace_attribute.py <trace file> <tag>")
    lines = pathlib.Path(sys.argv[1]).read_text().splitlines()
    per = parse(lines, sys.argv[2])
    if not per:
        print(f"no '[{sys.argv[2]}]' events in {sys.argv[1]}")
        return
    for level in sorted(per):
        top = per[level].most_common(3)
        body = "  |  ".join(f"{what} x{n}" for what, n in top)
        print(f"  level {level + 1}: {body}")


if __name__ == "__main__":
    main()
