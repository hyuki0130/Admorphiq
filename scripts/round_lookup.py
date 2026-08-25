"""Every round-log mention of a game, in DATE ORDER, so the newest is unmistakable.

Purpose: the round pages carry several entries per game written months apart, and grep
returns them in file order. Finding one is not finding the CURRENT one — measured twice in a
single session: su15 was quoted as reopenable on a "lag-compensating predictor" (r59s10)
when a later entry (R75) had superseded it with a sub-pixel-perception wall, and a depth
axis was chosen from entries that a later scan had already settled with proofs.

Expected feedback: one line per mention, oldest first, each tagged with the dated section it
sits in. The LAST line is the current record. A game with no dated section shows its entries
under "(undated)" — those cannot be ordered and have to be read.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROUNDS = Path(".wiki/wiki/rounds")
DATED = re.compile(r"^##+\s+(.*?)\((\d{4}-\d{2}-\d{2})[^)]*\)", re.MULTILINE)


def sections(text: str) -> list[tuple[str, str, int, int]]:
    """(title, date, start, end) for each dated section, in file order."""
    marks = [(m.group(1).strip(), m.group(2), m.start()) for m in DATED.finditer(text)]
    out = []
    for i, (title, date, start) in enumerate(marks):
        end = marks[i + 1][2] if i + 1 < len(marks) else len(text)
        out.append((title, date, start, end))
    return out


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: round_lookup.py <game-or-keyword> [more…]")
        return 1
    needles = [n.lower() for n in sys.argv[1:]]

    hits: list[tuple[str, str, str, str]] = []   # (date, page, section, line)
    undated: list[tuple[str, str]] = []
    for page in sorted(ROUNDS.glob("*.md")):
        text = page.read_text()
        marks = sections(text)
        for lineno, line in enumerate(text.splitlines()):
            if not all(n in line.lower() for n in needles):
                continue
            offset = sum(len(x) + 1 for x in text.splitlines()[:lineno])
            here = [(t, d) for t, d, s, e in marks if s <= offset < e]
            if here:
                title, date = here[-1]
                hits.append((date, page.stem, title, line.strip()))
            else:
                undated.append((page.stem, line.strip()))

    for date, page, title, line in sorted(hits):
        print(f"{date}  {page:26s} {title[:34]:34s} {line[:110]}")
    for page, line in undated:
        print(f"(undated)   {page:26s} {'':34s} {line[:110]}")
    if hits:
        print(f"\n^ {len(hits)} dated mention(s); THE LAST LINE IS THE CURRENT RECORD")
    if undated:
        print(f"  plus {len(undated)} undated mention(s) — read them, they cannot be ordered")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
