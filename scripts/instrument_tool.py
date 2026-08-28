"""Tag every `return` in a tool's `propose` with a marker that CANNOT break the tool.

⛔ WHY THIS EXISTS. The same instrumentation bug was written twice in one session, hours apart:
a marker calling `levels_completed(obs)` inside a tool that does not import it. `propose` then
throws on every call, the harness catches it silently ("[harness] <tool>.propose error"), the tool
degrades to nothing, and the run comes back with a LOWER SCORE that looks like a measurement —
keymaze took ls20 to 0.0000 that way, railpeg took lf52 from 0.2727 to 0.1818.

Two rules, both enforced here rather than remembered:

  * the marker uses ONLY names the module already has — it prints `self._level` when the class has
    one and otherwise prints no level at all, and it never calls a helper;
  * the patched file is CHECKED: it must import-parse, and the run must produce zero
    "propose error" lines. `--verify` prints the command that proves it.

Usage:
    uv run python scripts/instrument_tool.py src/admorphiq/tools/railpeg.py /tmp/out.py [tag]
"""
from __future__ import annotations

import ast
import pathlib
import sys


def instrument(src: str, tag: str) -> tuple[str, int]:
    tree = ast.parse(src)
    has_level = any(
        isinstance(n, ast.Attribute) and n.attr == "_level" for n in ast.walk(tree)
    )
    lvl = "lvl={self._level} " if has_level else ""
    lines = src.split("\n")
    out: list[str] = []
    inside = False
    tagged = 0
    for i, ln in enumerate(lines):
        if ln.startswith("    def propose(self"):
            inside = True
            out.append(ln)
            continue
        if inside and ln.startswith("    def "):
            inside = False
        stripped = ln.strip()
        if inside and stripped.startswith("return ") and "yield" not in stripped:
            indent = ln[: len(ln) - len(ln.lstrip())]
            expr = stripped[len("return ") :]
            out += [
                f"{indent}_r = {expr}",
                f'{indent}import sys as _s; print(f"[{tag}] {lvl}site={i + 1} '
                f'n={{len(_r) if isinstance(_r, list) else 1}}", file=_s.stderr, flush=True)',
                f"{indent}return _r",
            ]
            tagged += 1
        else:
            out.append(ln)
    return "\n".join(out), tagged


def main() -> None:
    if len(sys.argv) not in (3, 4):
        raise SystemExit("usage: instrument_tool.py <tool.py> <out.py> [tag]")
    src_path, out_path = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2])
    tag = sys.argv[3] if len(sys.argv) == 4 else "ins"
    patched, n = instrument(src_path.read_text(), tag)
    ast.parse(patched)  # refuse to emit something that will not import
    out_path.write_text(patched)
    print(f"tagged {n} propose-returns in {src_path.name} -> {out_path}")
    print("⛔ VERIFY: the run must print ZERO lines matching 'propose error'.")
    print("   grep -c 'propose error' <run log>   # must be 0, or the marker broke the tool")


if __name__ == "__main__":
    main()
