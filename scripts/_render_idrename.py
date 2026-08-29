"""Rename every obfuscated identifier in a game's source and ask whether it RENDERS the same.

This is the mutation the real world already performs: the ARC Prize API rotates a game's
version hash and every sprite key, `name=`, game-specific tag and attribute name changes.
That rotation broke twelve brittle solvers in April 2026 (CLAUDE.md's v1-vs-v2 table), so
it is the transfer question with the longest history in this repository.

⭐ WHAT IT MEASURES, AND WHY IT IS NOT A FULL-25 RUN. The generic tools are frame-only —
grepped and confirmed: nothing under `src/admorphiq/tools/` or `src/admorphiq/harness/`
reads a sprite name, a tag or a game attribute. So if the renamed game RENDERS THE SAME
FRAMES under the same action sequence, the rename is provably inert for any frame-only
agent, and a full-25 scoring run would be a slower way of learning nothing. The frame
comparison IS the result. Byte-equality of every frame over a fixed action sequence is a
stronger statement than one identical score, not a weaker one.

⛔ AND IT IS ALSO THE VALIDITY CHECK. A rename that broke the game would crash or render
differently; both show up here. Frames that differ are reported as such and are NOT
claimed as a transfer failure — this probe cannot separate "my rename is broken" from
"the engine's draw order depends on the name", and saying so is the honest output.

⛔ ONLY A PRIVATE COPY IS EVER TOUCHED. `environment_files/` in the shared tree is the
ground truth; the rename runs against a copy under /tmp selected by ENVIRONMENTS_DIR.

    bash scripts/pfan.sh idrename scripts/_render_idrename.py 25 "" 6
"""

from __future__ import annotations

import ast
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))

# An obfuscated token as the generator emits them: lowercase runs, optionally
# hyphen-joined, optionally with a trailing size digit ("bodekplurlf16", "gayktr-grwjuk").
TOKEN = re.compile(r"^[0-9a-z]*[a-z]{3}[0-9a-z-]*$")
STEPS = 60


def engine_vocabulary() -> set[str]:
    """Every word the ENGINE knows, which must therefore never be renamed.

    ``sys_click`` is the load-bearing example: it survives the real re-render because the
    engine reads it. Renaming an engine-meaningful string would change the game's
    behaviour, not its rendering, and every number after that would be void.
    """
    words: set[str] = set()
    for pkg in ("arcengine", "arc_agi"):
        root = REPO / ".venv" / "lib" / "python3.12" / "site-packages" / pkg
        for path in root.rglob("*.py"):
            words.update(re.findall(r"[A-Za-z_][A-Za-z_0-9]*", path.read_text(
                encoding="utf-8", errors="ignore")))
    return words


class _Rename(ast.NodeTransformer):
    """Rewrite exactly the string constants in the mapping. Nothing else moves."""

    def __init__(self, mapping: dict[str, str]) -> None:
        self.mapping = mapping
        self.hits = 0

    def visit_Constant(self, node: ast.Constant) -> ast.Constant:
        if isinstance(node.value, str) and node.value in self.mapping:
            self.hits += 1
            return ast.copy_location(ast.Constant(value=self.mapping[node.value]), node)
        return node


def sprite_strings(tree: ast.AST, engine: set[str]) -> tuple[list[str], str | None]:
    """The strings a version rotation rotates: the sprite dict's keys, names and tags.

    ⛔ TWO WRONG VERSIONS PRECEDED THIS ONE AND BOTH FAILED THE SAME WAY — by renaming
    PART of what had to move together.

    (1) The first also renamed attribute ACCESSES without their definitions, so
        ``self.foo()`` lost its ``def foo`` and every game diverged on frame ZERO. A
        column of 25 DIFFERENTs that reads as a spectacular transfer failure and is a bug
        in the instrument.
    (2) The second selected keys by a name PATTERN, which matched 7 of cd82's 13 sprite
        keys and 26 of sc25's 50. A partially renamed board breaks any prefix grouping the
        game does (`clcbko-1`, `clcbko-2` are one family) — cd82, sb26 and sc25 came back
        DIFFERENT for that reason and not for a reason about the tools.

    So the rule here is ALL OR NOTHING: take the module-level ``sprites`` dict's keys
    entire, and REFUSE the game if any key is engine vocabulary or if any other string in
    the module contains, or is contained by, a key — that is prefix logic, and renaming
    under it is renaming half a thing.
    """
    keys: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Dict) \
                and any(isinstance(t, ast.Name) and t.id == "sprites" for t in node.targets):
            for key in node.value.keys:
                if not (isinstance(key, ast.Constant) and isinstance(key.value, str)):
                    return [], "a sprite key is not a plain string constant"
                keys.append(key.value)
    if not keys:
        return [], "no module-level `sprites` dict of string keys"
    clash = [k for k in keys if k in engine]
    if clash:
        return [], f"sprite key(s) {clash[:3]} are engine vocabulary — renaming changes behaviour"

    names: list[str] = list(keys)
    for node in ast.walk(tree):
        if isinstance(node, ast.keyword) and node.arg in ("name", "tags"):
            for sub in ast.walk(node):
                if isinstance(sub, ast.Constant) and isinstance(sub.value, str) \
                        and sub.value not in names and sub.value not in engine \
                        and TOKEN.match(sub.value):
                    names.append(sub.value)

    chosen = set(names)
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Constant) and isinstance(node.value, str)):
            continue
        other = node.value
        if other in chosen or len(other) < 3:
            continue
        for tok in chosen:
            if other in tok or tok in other:
                return [], (f"string {other!r} overlaps sprite name {tok!r} — the module "
                            f"groups sprites by prefix, so a rename would split a family")
    return names, None


def dynamic_name_risk(tree: ast.AST, candidates: list[str]) -> str | None:
    """Refuse when a candidate name could be BUILT from pieces rather than written out.

    A sprite key assembled in an f-string exists in the source only as a FRAGMENT, so
    renaming whole tokens leaves the fragment behind and the lookup fails. Only f-strings
    whose literal parts actually overlap a candidate matter.
    """
    for node in ast.walk(tree):
        if not isinstance(node, ast.JoinedStr):
            continue
        for part in node.values:
            if not (isinstance(part, ast.Constant) and isinstance(part.value, str)):
                continue
            frag = part.value
            if len(frag) < 3:
                continue
            for cand in candidates:
                if frag in cand:
                    return f"an f-string literal {frag!r} is a fragment of {cand!r}"
    return None


def rename_source(src: str) -> tuple[str | None, dict[str, str], str | None]:
    tree = ast.parse(src)
    candidates, why = sprite_strings(tree, engine_vocabulary())
    if why:
        return None, {}, why
    risk = dynamic_name_risk(tree, candidates)
    if risk:
        return None, {}, risk
    mapping = {tok: f"q{i:04d}zz" for i, tok in enumerate(sorted(candidates))}
    walker = _Rename(mapping)
    out = ast.unparse(ast.fix_missing_locations(walker.visit(tree)))
    if walker.hits < len(mapping):
        return None, {}, "the rewriter touched fewer strings than it selected"
    return out, mapping, None


class _Poison(ast.NodeTransformer):
    """Recolour every sprite pixel: the probe's own NEGATIVE control.

    Purpose: an all-"same-frames" column is indistinguishable from a comparison that
    cannot see anything at all — the fail-toward-absence shape that has cost this
    campaign eight instruments. A deliberately recoloured copy MUST come back
    DIFFERENT; where it does not, the rename result for that game says nothing and is
    reported as unmeasurable rather than as agreement.
    """

    def __init__(self) -> None:
        self.inside = 0
        self.hits = 0

    def visit_keyword(self, node: ast.keyword) -> ast.keyword:
        if node.arg == "pixels":
            self.inside += 1
            self.generic_visit(node)
            self.inside -= 1
            return node
        return self.generic_visit(node) or node

    def visit_Constant(self, node: ast.Constant) -> ast.Constant:
        if self.inside and isinstance(node.value, int) and node.value >= 0:
            self.hits += 1
            return ast.copy_location(
                ast.Constant(value=(node.value + 1) % 16), node)
        return node


def frames_of(env_dir: str, game_id: str, steps: int) -> list[bytes]:
    """Render a fixed action sequence in a SUBPROCESS and return every frame's bytes.

    A subprocess because the game module is imported by name and two versions of the
    same module cannot coexist in one interpreter — a cached import would compare a
    game against itself and report perfect agreement over no measurement at all.
    """
    code = (
        "import os,sys,hashlib,json\n"
        f"sys.path.insert(0,{str(REPO / 'src')!r})\n"
        f"os.environ['ENVIRONMENTS_DIR']={env_dir!r}\n"
        "from arc_agi import Arcade, OperationMode\n"
        "from arcengine import GameAction\n"
        "a=Arcade(operation_mode=OperationMode.OFFLINE)\n"
        f"e=a.make({game_id!r})\n"
        "o=e.observation_space; out=[]\n"
        "simple=[x for x in GameAction if x.is_simple() and x is not GameAction.RESET]\n"
        f"for i in range({steps}):\n"
        "    out.append(hashlib.md5(b''.join(bytes(f.astype('int16')) for f in o.frame)).hexdigest())\n"
        "    av=set(o.available_actions or [])\n"
        "    pool=[x for x in simple if x.value in av]\n"
        "    if 6 in av and i%3==0:\n"
        "        act=GameAction.ACTION6; act.set_data({'game_id':'','x':(i*7)%64,'y':(i*11)%64})\n"
        "        o=e.step(act,data=act.action_data.model_dump())\n"
        "    elif pool:\n"
        "        o=e.step(pool[i%len(pool)])\n"
        "    else:\n"
        "        break\n"
        "    if o is None or not o.frame: break\n"
        "print(json.dumps(out))\n"
    )
    proc = subprocess.run([sys.executable, "-c", code], capture_output=True,
                          text=True, timeout=900, cwd=str(REPO))
    if proc.returncode != 0:
        return ["CRASH:" + proc.stderr.strip()[-300:]]
    return json.loads(proc.stdout.strip().splitlines()[-1])


def main() -> int:
    idx = int(sys.argv[1]) - 1
    src_root = Path(os.environ.get("ENVIRONMENTS_DIR", "environment_files")).resolve()
    games = sorted(p.name for p in src_root.iterdir() if p.is_dir())
    # A second argument names ONE game, so a single result can be re-examined without
    # re-running the whole fan.
    if len(sys.argv) > 2 and sys.argv[2]:
        games = [sys.argv[2]]
    if idx >= len(games):
        return 0
    game = games[idx]

    work = Path(tempfile.mkdtemp(prefix=f"idren_{game}_"))
    try:
        plain = work / "plain"
        renamed = work / "renamed"
        shutil.copytree(src_root / game, plain / game)
        shutil.copytree(src_root / game, renamed / game)
        for cache in renamed.rglob("__pycache__"):
            shutil.rmtree(cache, ignore_errors=True)
        target = next(renamed.rglob(f"{game}.py"))
        out, mapping, why = rename_source(target.read_text(encoding="utf-8"))
        if out is None:
            print(json.dumps({"game": game, "status": "not-constructible", "why": why}))
            return 0
        target.write_text(out, encoding="utf-8")
        game_id = json.loads(next(plain.rglob("metadata.json")).read_text())["game_id"]

        poisoned = work / "poisoned"
        shutil.copytree(src_root / game, poisoned / game)
        for cache in poisoned.rglob("__pycache__"):
            shutil.rmtree(cache, ignore_errors=True)
        ptarget = next(poisoned.rglob(f"{game}.py"))
        ptree = ast.parse(ptarget.read_text(encoding="utf-8"))
        poison = _Poison()
        ptarget.write_text(
            ast.unparse(ast.fix_missing_locations(poison.visit(ptree))),
            encoding="utf-8")

        a = frames_of(str(plain), game_id, STEPS)
        b = frames_of(str(renamed), game_id, STEPS)
        c = frames_of(str(poisoned), game_id, STEPS)
        same = a == b
        print(json.dumps({
            "game": game, "status": "same-frames" if same else "DIFFERENT",
            "poison_detected": a != c, "poisoned_pixels": poison.hits,
            "renamed_tokens": len(mapping), "frames": len(a),
            "first_divergence": next((i for i, (x, y) in enumerate(zip(a, b)) if x != y),
                                     None) if not same else None,
            "len_plain": len(a), "len_renamed": len(b),
            "detail": (a[-1:] + b[-1:]) if not same else None,
        }))
    finally:
        shutil.rmtree(work, ignore_errors=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
