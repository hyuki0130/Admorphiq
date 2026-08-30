#!/usr/bin/env python3
"""Static census of the 7cd shape: a candidate set FILTERED by a predicate, with a FALLBACK to the
unfiltered set.

Purpose
-------
Rule 7cd named a defect class — a frame-only tool that identifies an object by whether it is DRAWN
is reading PAINT ORDER, not mechanics — from ONE exemplar (`telescope.py:1179`). The class has no
known population. This script enumerates every site in the tool set that has the STRUCTURE, so a
runtime instrument (`scripts/_viscensus_run.py`) can then measure which of them actually fire.

⛔ THIS IS A GREP, AND A GREP IS NOT THE DELIVERABLE (rule 7g). The source says what is POSSIBLE.
Only `_viscensus_run.py` on a real 25-game run says what HAPPENS.

The three shapes it looks for
----------------------------
A  `sel = [x for x in CANDS if P(x)]` then `sel if <cond> else CANDS`      (ternary fallback)
B  `sel = [x for x in CANDS if P(x)]` then `if <cond>: sel = CANDS`        (statement fallback)
C  `sel = [x for x in CANDS if P(x)] or CANDS`                            (or-fallback)

The predicate `P` is then CLASSIFIED, because the structure alone is not the defect:
  visibility  — membership in a set of cells/colours read off the CURRENT frame
                (`in drawn`, `in lit`, `g[r, c] == col`), i.e. 7cd's shape
  colour      — orders or selects by a colour INDEX (rule 7ce measured this harmless)
  other       — geometry, feasibility, arity, budget: not a visibility read

Expected feedback
-----------------
Prints one line per site with file:line, the candidate expression, the predicate source and the
class. A site whose class is `visibility` is a 7cd candidate and MUST be measured on a run.
"""

from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TOOLS = ROOT / "src" / "admorphiq" / "tools"
HARNESS = ROOT / "src" / "admorphiq" / "harness"

# Names that, when a predicate tests membership in them or compares against them, mean "is this
# thing currently PAINTED like that". Derived from the exemplar (`drawn = set(m.movers)`) and
# widened by reading the tool set's own vocabulary.
VIS_WORDS = (
    "drawn", "draw", "lit", "shown", "visible", "paint", "painted", "render",
    "onscreen", "showing", "seen_cells", "marker", "markers", "mover", "movers",
    "pip", "pips", "glyph", "colour", "color", "shade", "tint",
)


def _src(node: ast.AST, lines: list[str]) -> str:
    try:
        return ast.get_source_segment("\n".join(lines), node) or ast.dump(node)[:80]
    except Exception:  # pragma: no cover - defensive on odd nodes
        return ast.dump(node)[:80]


def _norm(s: str) -> str:
    """Strip whitespace and the container wrappers that make two spellings of the SAME candidate
    set compare unequal.

    ⛔ The first version compared raw source text and MISSED `swivel.py:734`, whose comprehension
    iterates `range(len(reading.bars))` while its fallback is `list(range(len(reading.bars)))` —
    a site the campaign already knew about by name. An exact-match instrument scores its own known
    positive at zero for the tool it was not transcribed from.
    """
    s = "".join(s.split())
    for _ in range(4):
        for w in ("list(", "set(", "tuple(", "sorted(", "frozenset("):
            if s.startswith(w) and s.endswith(")"):
                s = s[len(w):-1]
                break
        else:
            break
    return s


def _classify(pred_src: str) -> str:
    low = pred_src.lower()
    hits = [w for w in VIS_WORDS if w in low]
    if not hits:
        return "other"
    # A comparison against a colour INDEX is rule 7ce's class, measured harmless. A membership
    # test against a set of CELLS is 7cd's.
    if " in " in low or ".issubset" in low or "&" in low:
        return "visibility"
    if any(w in low for w in ("colour", "color", "tint", "shade")):
        return "colour"
    return "visibility"


class Census(ast.NodeVisitor):
    def __init__(self, path: Path, lines: list[str]):
        self.path = path
        self.lines = lines
        self.hits: list[dict] = []
        # name -> (iter_src, pred_src, lineno) for comprehensions assigned to a bare name
        self.comps: dict[str, tuple[str, str, int]] = {}

    # -- collecting comprehension assignments ------------------------------
    def visit_Assign(self, node: ast.Assign) -> None:
        if len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            name = node.targets[0].id
            comp = self._as_filtered_comp(node.value)
            if comp is not None:
                self.comps[name] = comp
        self.generic_visit(node)

    # -- shape C: `<filtered> or CANDS`, wherever it appears ----------------
    # ⛔ This lives on BoolOp rather than on Assign because `tube.py:777` spells it
    # `return out or list(range(len(board.tubes)))` and `tether.py:413` spells it
    # `options.append(near if near else ...)`. An instrument anchored to the assignment statement
    # sees neither, and both are real sites.
    def visit_BoolOp(self, node: ast.BoolOp) -> None:
        if isinstance(node.op, ast.Or) and len(node.values) == 2:
            left, right = node.values
            right_src = _src(right, self.lines)
            c = self._as_filtered_comp(left) or self.comps.get(_src(left, self.lines))
            if c is not None and _norm(c[0]) == _norm(right_src):
                self._record("C-or", node, c[0], c[1], _src(left, self.lines))
            elif c is not None:
                self._record("C-near", node, f"{c[0]} -> else {right_src}", c[1],
                             _src(left, self.lines))
        self.generic_visit(node)

    def _as_filtered_comp(self, v: ast.AST) -> tuple[str, str, int] | None:
        if not isinstance(v, (ast.ListComp, ast.SetComp, ast.GeneratorExp)):
            return None
        if len(v.generators) != 1 or not v.generators[0].ifs:
            return None
        gen = v.generators[0]
        return (
            _src(gen.iter, self.lines),
            " and ".join(_src(i, self.lines) for i in gen.ifs),
            v.lineno,
        )

    # -- shape A: ternary fallback ----------------------------------------
    def visit_IfExp(self, node: ast.IfExp) -> None:
        body_src = _src(node.body, self.lines)
        else_src = _src(node.orelse, self.lines)
        c = self.comps.get(body_src)
        if c is not None:
            if _norm(c[0]) == _norm(else_src):
                self._record("A-ternary", node, c[0], c[1], body_src)
            else:
                # ⚠️ NEAR MISS, reported rather than dropped. The fallback is some OTHER expression,
                # so it may still be a superset spelled differently. These are read by hand; the
                # alternative is an instrument that decides silently what it did not match.
                self._record("A-near", node, f"{c[0]} -> else {else_src}", c[1], body_src)
        # inline form: `[x for x in C if P] if cond else C`
        inline = self._as_filtered_comp(node.body)
        if inline is not None and _norm(inline[0]) == _norm(else_src):
            self._record("A-ternary", node, inline[0], inline[1], "<inline>")
        self.generic_visit(node)

    # -- shape B: statement fallback --------------------------------------
    def visit_If(self, node: ast.If) -> None:
        for stmt in node.body:
            if (
                isinstance(stmt, ast.Assign)
                and len(stmt.targets) == 1
                and isinstance(stmt.targets[0], ast.Name)
            ):
                name = stmt.targets[0].id
                c = self.comps.get(name)
                if c is not None and _norm(_src(stmt.value, self.lines)) == _norm(c[0]):
                    self._record("B-stmt", stmt, c[0], c[1], name)
        self.generic_visit(node)

    def _record(self, shape: str, node: ast.AST, cands: str, pred: str, name: str) -> None:
        self.hits.append(
            {
                "file": self.path.name,
                "line": node.lineno,
                "col": node.col_offset,
                "shape": shape,
                "name": name,
                "cands": cands.replace("\n", " ")[:70],
                "pred": pred.replace("\n", " ")[:110],
                "cls": _classify(pred),
            }
        )


# ⛔ BOTH CONTROLS, BUILT INTO THE INSTRUMENT (rule 7aj#3). The first pass of this scanner returned
# ZERO sites over the whole tool set — indistinguishable from "the population is one" and from "the
# detector is broken". It was the latter. The positive is 7cd's exemplar transcribed verbatim; the
# negative is the same function with the fallback removed.
POSITIVE = '''
def _begin(self, g):
    bars = anchored_bars(g, self._marker, boxes, self._pieces)
    drawn = set(m.movers)
    pinned = [b for b in bars if tip_centre(self._pieces[b[0]].box, b[1]) in drawn]
    riders = pinned if len(pinned) >= len(m.places) else bars
    return riders
'''
# A SECOND positive, transcribed from a DIFFERENT tool (`swivel.py:734`), whose fallback is spelled
# `list(range(...))` against an iter of `range(...)`. It is the control that caught `_norm`.
POSITIVE2 = '''
def _read(self, g):
    drawn = set(marks.movers) if marks else set()
    pinned = [i for i in range(len(reading.bars))
              if rider_at(self._cfg, i) in drawn]
    riders = pinned if len(pinned) >= len(reading.places) else list(range(len(reading.bars)))
    return riders
'''
NEGATIVE = '''
def _begin(self, g):
    bars = anchored_bars(g, self._marker, boxes, self._pieces)
    drawn = set(m.movers)
    pinned = [b for b in bars if tip_centre(self._pieces[b[0]].box, b[1]) in drawn]
    return pinned
'''


def scan_text(text: str, name: str) -> list[dict]:
    lines = text.splitlines()
    tree = ast.parse(text)
    out: list[dict] = []
    for fn in [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]:
        c = Census(Path(name), lines)
        for stmt in fn.body:
            c.visit(stmt)
        out.extend(c.hits)
    return out


def selftest() -> int:
    pos = scan_text(POSITIVE, "positive_control.py")
    pos2 = scan_text(POSITIVE2, "positive_control2.py")
    neg = scan_text(NEGATIVE, "negative_control.py")
    ok = (
        len(pos) == 1 and pos[0]["cls"] == "visibility" and pos[0]["shape"] == "A-ternary"
        and len(pos2) == 1 and pos2[0]["cls"] == "visibility" and pos2[0]["shape"] == "A-ternary"
        and len(neg) == 0
    )
    print(json.dumps({"SELFTEST": "PASS" if ok else "FAIL", "pos": pos, "pos2": pos2, "neg": neg},
                     sort_keys=True))
    return 0 if ok else 1


def scan(path: Path) -> list[dict]:
    text = path.read_text()
    lines = text.splitlines()
    tree = ast.parse(text)
    # Per-FUNCTION scope, so a comprehension in one function cannot pair with a fallback in another.
    out: list[dict] = []
    funcs = [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
    for fn in funcs:
        c = Census(path, lines)
        for stmt in fn.body:
            c.visit(stmt)
        out.extend(c.hits)
    return out


def main() -> None:
    # pfan passes a seed as argv[1]; the real selector is argv[2].
    args = [a for a in sys.argv[1:] if not a.isdigit()]
    only = args[0] if args else ""
    rc = selftest()
    if rc:
        print(json.dumps({"TOTAL": -1, "note": "selftest failed — census refused"}))
        sys.exit(1)
    files = sorted(TOOLS.glob("*.py")) + sorted(HARNESS.glob("*.py"))
    allhits: list[dict] = []
    for f in files:
        if only and only not in f.name:
            continue
        allhits.extend(scan(f))
    by_cls: dict[str, int] = {}
    for h in allhits:
        by_cls[h["cls"]] = by_cls.get(h["cls"], 0) + 1
    # ⛔ ONE JSON LINE PER SITE — `pfan.sh` keeps only lines beginning with `{`, so a human-readable
    # table would come back EMPTY and read as "there is nothing here" (rule 7aj#3).
    for h in allhits:
        print(json.dumps(h, sort_keys=True))
    print(json.dumps({"TOTAL": len(allhits), "by_cls": by_cls}, sort_keys=True))


if __name__ == "__main__":
    main()
