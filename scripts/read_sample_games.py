"""Extract each sample game's MECHANIC from its own source, in one pass.

⛔ Why this exists, and the mistake it replaces: `OPERATING_RULES.md` rule 0 says stage one is
"read each sample game ... and write the code". The sources are RIGHT HERE in
`environment_files/`, obfuscated in their names but perfectly readable in their structure — and
a whole session was spent probing games as black boxes instead. One read of g50t's `step()`
answered in seconds what eight live probes could not: ACTION1-4 are up/down/left/right, an
action arriving while the avatar is mid-animation is SWALLOWED (which is why the probes
contradicted each other), and a timer sprite scrolls one cell every second action until it
leaves the screen and the game is lost.

⛔ The line this does NOT cross: what is read here is DEV-TIME understanding of what mechanic to
implement. The tools stay frame-only. A tool that reads game internals is an adapter, adapters
are quarantined precisely because they cannot transfer, and the eval is 110 games whose source
we will never see.

Prints, per game: the action dispatch, the win predicate, the lose predicate, and the level-setup
hook — the four things that decide what a generic tool has to be able to do.
"""

from __future__ import annotations

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent / "environment_files"


def _bodies(src: str, name: str, limit: int = 40) -> list[str]:
    """Every `def <name>` body in the file, each cut at the next same-indent `def`."""
    out = []
    for m in re.finditer(rf"\n(\s*)def {re.escape(name)}\s*\(", src):
        indent = m.group(1)
        rest = src[m.start() + 1:]
        end = re.search(rf"\n{indent}def ", rest[1:])
        body = rest[: end.start() + 1] if end else rest
        out.append("\n".join(ln for ln in body.splitlines() if ln.strip())[:6000])
    return [b for b in out if b]


def _method(src: str, name: str, limit: int = 40) -> str:
    """The GAME's `<name>`, not a sprite's.

    ⛔ A file carries several `def step`: animation helpers, tween drivers, and the one that
    dispatches the player's action. Taking the first found left six of the twenty-five games
    blank — including g50t, whose dispatch sits at line 2816 of 2855 and was found by hand
    minutes earlier. The game's own method is the one that reads `self.action`; failing that,
    the last one in the file.
    """
    bodies = _bodies(src, name, limit)
    if not bodies:
        return ""
    owning = [b for b in bodies if "self.action" in b]
    chosen = owning[-1] if owning else bodies[-1]
    return "\n".join(chosen.splitlines()[:limit])


def _called(src: str, body: str, depth: int = 1) -> str:
    """Inline the one-line predicates a body calls, so `win = self.xyz()` is legible."""
    if depth <= 0:
        return ""
    out = []
    for name in sorted(set(re.findall(r"self\.([a-z_][a-z0-9_]*)\(\)", body))):
        sub = _method(src, name, limit=6)
        if sub and len(sub.splitlines()) <= 6:
            out.append(sub)
    return "\n".join(out)


def main() -> None:
    only = sys.argv[1:] if len(sys.argv) > 1 else None
    for game_dir in sorted(ROOT.iterdir()):
        if not game_dir.is_dir() or (only and game_dir.name not in only):
            continue
        files = sorted(game_dir.rglob("*.py"))
        if not files:
            continue
        src = files[0].read_text(errors="replace")
        print("=" * 78)
        print(f"{game_dir.name}   ({files[0].relative_to(ROOT.parent)}, {len(src.splitlines())} lines)")
        print("=" * 78)
        step = _method(src, "step", limit=45)
        print("-- step() --")
        print(step or "  (no step method found)")
        extra = _called(src, step)
        if extra:
            print("-- predicates it calls --")
            print(extra)
        for hook in ("on_set_level", "on_level_complete", "reset"):
            body = _method(src, hook, limit=14)
            if body:
                print(f"-- {hook}() --")
                print(body)
        print()


if __name__ == "__main__":
    main()
