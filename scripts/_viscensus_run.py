#!/usr/bin/env python3
"""RUN-TIME census of the 7cd shape: does each candidate site actually change the candidate set?

Purpose
-------
`scripts/_viscensus_ast.py` lists every site in the tool set with the STRUCTURE rule 7cd named — a
candidate set filtered by a predicate, with a fallback to the unfiltered set. That is a grep, and
rule **7g** says the source only says what is POSSIBLE. This script says what HAPPENS: it rewrites
each of those expressions at IMPORT TIME into a logging call, plays one of the 25 sample games
through `score_efficiency.run_game` — the scorer's own loop, not a hand-rolled one (rule 7aj#1) —
and reports, per site, how often it was evaluated, which branch was taken, and whether the filter
CHANGED the candidate set.

Usage
-----
    bash scripts/pfan.sh viscrun scripts/_viscensus_run.py 25 "" 8

Arm `i` (1-based) plays the i'th of the 25 games. Arm 26, if asked for, is the CONTROL arm: the same
game with the rewriting installed but disabled, so its score can be compared against the instrumented
arm to show the rewrite is behaviour-neutral.

Both controls (rule 7aj#3)
--------------------------
POSITIVE — `telescope.py`'s site on s5i5 must report `narrowed > 0`: rule 7cd measured the live
board pinning the rider at every level while the archived one falls back to all nine bars. An
instrument that reports s5i5 clean has measured nothing.
NEGATIVE — `stamppaint.py:197` filters a region's cells by `g[c] == fill` where `fill` IS that
region's modal colour, so the filtered list can never be empty and the `or cells` fallback is
structurally dead. It must report `fallback == 0`. A site that never fires must come back clean.

⛔ SIDE EFFECTS. The instrument evaluates BOTH branches to learn the counterfactual length, so it
refuses to do that when the un-taken branch is not a pure read (a Name/Attribute/Subscript, or a
`list`/`set`/`sorted`/`range`/`enumerate` over one). `harness/loop.py:569`'s fallback is
`self._probe(...)` — a call — and is logged with `other=null` rather than being run early.

Expected feedback
-----------------
One JSON line per game, `sites` mapping `file:line` to counts. `narrowed > 0` on a site means the
visibility read is doing real work on that game and its absence would widen the search; `eval == 0`
means the site never ran and the static hit is inert HERE (not everywhere — say which game).
"""

from __future__ import annotations

import ast
import importlib.abc
import importlib.util
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import _viscensus_ast as census  # noqa: E402

# --- the log ----------------------------------------------------------------

LOG: dict[str, dict[str, int]] = {}


def _size(v: object) -> int:
    try:
        return len(v)  # type: ignore[arg-type]
    except Exception:
        return -1


def _note(sid: str, took_filter: bool, chosen: object, other: object, have_other: bool) -> None:
    d = LOG.setdefault(sid, {"eval": 0, "filter": 0, "fallback": 0, "narrowed": 0,
                             "same": 0, "unknown": 0, "min_f": 10**9, "max_o": -1})
    d["eval"] += 1
    d["filter" if took_filter else "fallback"] += 1
    if not have_other:
        d["unknown"] += 1
        return
    a, b = _size(chosen), _size(other)
    if a < 0 or b < 0:
        d["unknown"] += 1
    elif a != b:
        d["narrowed"] += 1
        d["min_f"] = min(d["min_f"], a)
        d["max_o"] = max(d["max_o"], b)
    else:
        d["same"] += 1


def _VIS(sid: str, ftest, fbody, forelse, pa: bool, pb: bool):
    """`A if C else B`. The TAKEN branch is evaluated once; the other only when it is a pure read.

    ⛔ Each branch is evaluated at most once. An earlier draft called `forelse()` twice on the
    impure path, which would have issued `loop.py`'s probe an extra time — an instrument that
    changes the run it is observing.
    """
    test = bool(ftest())
    if test:
        chosen = fbody()
        other, have = (forelse(), True) if pb else (None, False)
    else:
        chosen = forelse()
        other, have = (fbody(), True) if pa else (None, False)
    _note(sid, test, chosen, other, have)
    return chosen


def _VISOR(sid: str, fleft, fright, pa: bool, pb: bool):
    """`A or B`, same accounting."""
    left = fleft()
    if left:
        other, have = (fright(), True) if pb else (None, False)
        _note(sid, True, left, other, have)
        return left
    right = fright()
    _note(sid, False, right, left, True)
    return right


# --- purity ------------------------------------------------------------------

_PURE_CALLS = {"list", "set", "tuple", "sorted", "frozenset", "range", "enumerate", "len", "dict"}


def _is_pure(node: ast.AST) -> bool:
    """May this expression be evaluated EARLY, purely to learn its length?

    ⛔ Only reads. A call to anything the tool defines may act on the board — `loop.py:569`'s
    fallback issues a probe — and an instrument that runs it early has changed the run it claims to
    be observing.
    """
    if isinstance(node, (ast.Name, ast.Constant, ast.Attribute)):
        return True
    if isinstance(node, ast.Subscript):
        return _is_pure(node.value)
    if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
        return all(_is_pure(e) for e in node.elts)
    if isinstance(node, ast.Call):
        if isinstance(node.func, ast.Name) and node.func.id in _PURE_CALLS:
            return all(_is_pure(a) for a in node.args) and not node.keywords
        if isinstance(node.func, ast.Attribute) and node.func.attr in ("values", "keys", "items"):
            return _is_pure(node.func.value)
        return False
    if isinstance(node, (ast.ListComp, ast.SetComp, ast.GeneratorExp)):
        return True
    return False


def _lam(node: ast.AST) -> ast.Lambda:
    return ast.Lambda(
        args=ast.arguments(posonlyargs=[], args=[], vararg=None, kwonlyargs=[],
                           kw_defaults=[], kwarg=None, defaults=[]),
        body=node,
    )


class _Rewriter(ast.NodeTransformer):
    def __init__(self, targets: set[tuple[int, int]], fname: str):
        self.targets = targets
        self.fname = fname
        self.done: list[str] = []

    def visit_IfExp(self, node: ast.IfExp) -> ast.AST:
        self.generic_visit(node)
        key = (node.lineno, node.col_offset)
        if key not in self.targets:
            return node
        sid = f"{self.fname}:{node.lineno}"
        self.done.append(sid)
        return ast.Call(
            func=ast.Name(id="_VIS", ctx=ast.Load()),
            args=[ast.Constant(sid), _lam(node.test), _lam(node.body), _lam(node.orelse),
                  ast.Constant(_is_pure(node.body)), ast.Constant(_is_pure(node.orelse))],
            keywords=[],
        )

    def visit_BoolOp(self, node: ast.BoolOp) -> ast.AST:
        self.generic_visit(node)
        key = (node.lineno, node.col_offset)
        if key not in self.targets or not isinstance(node.op, ast.Or) or len(node.values) != 2:
            return node
        sid = f"{self.fname}:{node.lineno}"
        self.done.append(sid)
        return ast.Call(
            func=ast.Name(id="_VISOR", ctx=ast.Load()),
            args=[ast.Constant(sid), _lam(node.values[0]), _lam(node.values[1]),
                  ast.Constant(_is_pure(node.values[0])), ast.Constant(_is_pure(node.values[1]))],
            keywords=[],
        )


# --- the import hook ---------------------------------------------------------

class VisFinder(importlib.abc.MetaPathFinder, importlib.abc.Loader):
    """Serve the census's modules from REWRITTEN source.

    ⛔ A meta-path finder rather than pre-importing each module by hand: `swivel` imports from
    `telescope`, so any hand-ordered install can pull an UNINSTRUMENTED copy of a target in first
    and the site then reports zero for a reason that has nothing to do with the tools.
    """

    def __init__(self, mods: dict[str, tuple[Path, set[tuple[int, int]]]]):
        self.mods = mods
        self.installed: dict[str, list[str]] = {}

    def find_spec(self, fullname, path=None, target=None):
        if fullname not in self.mods:
            return None
        origin = str(self.mods[fullname][0])
        return importlib.util.spec_from_file_location(fullname, origin, loader=self)

    def create_module(self, spec):
        return None

    def exec_module(self, module):
        name = module.__spec__.name
        path, targets = self.mods[name]
        tree = ast.parse(path.read_text(), filename=str(path))
        rw = _Rewriter(targets, path.name)
        tree = rw.visit(tree)
        ast.fix_missing_locations(tree)
        self.installed[name] = rw.done
        module.__dict__["_VIS"] = _VIS
        module.__dict__["_VISOR"] = _VISOR
        exec(compile(tree, str(path), "exec"), module.__dict__)


def _targets() -> dict[str, tuple[Path, set[tuple[int, int]]]]:
    out: dict[str, tuple[Path, set[tuple[int, int]]]] = {}
    for d, pkg in ((census.TOOLS, "admorphiq.tools"), (census.HARNESS, "admorphiq.harness")):
        for f in sorted(d.glob("*.py")):
            hits = [h for h in census.scan(f) if h["shape"] in ("A-ternary", "A-near",
                                                                "C-or", "C-near")]
            if hits:
                out[f"{pkg}.{f.stem}"] = (f, {(h["line"], h["col"]) for h in hits})
    return out


# --- the run -----------------------------------------------------------------

GAMES = ["ar25", "bp35", "cd82", "cn04", "dc22", "ft09", "g50t", "ka59", "lf52", "lp85",
         "ls20", "m0r0", "r11l", "re86", "s5i5", "sb26", "sc25", "sk48", "sp80", "su15",
         "tn36", "tr87", "tu93", "vc33", "wa30"]


def main() -> None:
    arm = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    budget = int(os.environ.get("VIS_BUDGET", "4000"))
    # `pfan.sh` fans arms 1..N and passes its 4th argument through to every arm. Naming a game
    # there runs that ONE game per arm, which is how the s5i5 positive control is checked without
    # paying for the other twenty-four.
    pick = sys.argv[2].strip().lower() if len(sys.argv) > 2 and sys.argv[2].strip() else ""
    control = pick.endswith("+control") or arm > len(GAMES)
    pick = pick.replace("+control", "")
    title = pick if pick else GAMES[(arm - 1) % len(GAMES)]

    tgts = _targets()
    finder = VisFinder({} if control else tgts)
    sys.meta_path.insert(0, finder)

    import score_efficiency as se  # noqa: E402  (after the hook, so tools import rewritten)
    from arc_agi import Arcade, OperationMode  # noqa: E402

    # ⛔ A site that logs ZERO is ambiguous between "the branch is inert" and "the tool never got
    # this board", and those are different findings. Count `propose` calls per tool class so the
    # two can be told apart. Patched on the CLASS, because the agent builds its own instances.
    from admorphiq.harness import registry  # noqa: E402
    used: dict[str, int] = {}

    def _wrap(cls: type) -> None:
        if cls.__dict__.get("_vis_wrapped"):
            return
        orig = cls.propose
        nm = cls.__name__

        def prop(self, *a, **k):  # noqa: ANN001, ANN002, ANN003
            used[nm] = used.get(nm, 0) + 1
            return orig(self, *a, **k)

        cls.propose = prop
        cls._vis_wrapped = True

    for t in registry.default_tools():
        _wrap(type(t))

    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    envs = [e for e in arcade.get_environments()
            if title in f"{e.game_id} {e.title or ''}".lower()]
    if not envs:
        print(json.dumps({"game": title, "error": "no such env"}))
        return
    env_info = envs[0]

    t0 = time.time()
    res = se.run_game(arcade, env_info.game_id, env_info.baseline_actions,
                      agent_name="unified", max_actions=budget)
    for d in LOG.values():
        if d["min_f"] == 10**9:
            d["min_f"] = -1
    print(json.dumps({
        "game": title,
        "arm": "control" if control else "instrumented",
        "score": round(float(res.get("game_score", 0.0)), 6),
        "levels": res.get("levels_completed"),
        "per_level": [p.get("agent_actions") for p in res.get("per_level", [])],
        "secs": round(time.time() - t0, 1),
        "n_static_sites": sum(len(v[1]) for v in tgts.values()),
        "rewritten": sorted({s for v in finder.installed.values() for s in v}),
        "proposed": used,
        "sites": LOG,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
