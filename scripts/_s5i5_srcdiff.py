"""What actually differs between the two s5i5 serializations, with the names taken away.

⛔ The raw `diff` of the two `s5i5.py` files is 3,719 lines and almost all of it is RENAMING —
every sprite is called something else and the level lists are ordered by the new names. That diff
cannot answer the only question worth asking: is the BOARD the same? So both files are canonicalised
— each sprite is replaced by a signature of its own pixels and flags, and each level by the multiset
of (signature, position) it places — and the canonical forms are compared.

⛔ It also prints the PAINT ORDER, because that is the render fact this family's tools are most
exposed to. `arcengine.Camera.render` sorts by `layer` with a STABLE sort, so within one layer the
list order IS the z-order: a sprite later in the list is drawn over an earlier one at the same
layer. Two serializations that place identical sprites at identical positions can therefore still
render differently if they list them in a different order.

Run it on ceph-build (the archive lives beside the shared tree, not in the repo):

    .venv/bin/python scripts/_s5i5_srcdiff.py <live_s5i5.py> <archived_s5i5.py>
"""

from __future__ import annotations

import ast
import hashlib
import sys
from collections import Counter


def _sprite_table(tree: ast.Module) -> dict[str, str]:
    """name -> a signature of everything about the sprite EXCEPT its name."""
    out: dict[str, str] = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.Dict):
            continue
        for k, v in zip(node.keys, node.values):
            if not isinstance(k, ast.Constant) or not isinstance(k.value, str):
                continue
            if not isinstance(v, ast.Call) or getattr(v.func, "id", "") != "Sprite":
                continue
            parts = []
            for kw in v.keywords:
                if kw.arg in ("name", "tags"):
                    continue          # the two things a re-render is free to change
                try:
                    parts.append(f"{kw.arg}={ast.literal_eval(kw.value)!r}")
                except Exception:  # noqa: BLE001
                    parts.append(f"{kw.arg}=?")
            out[k.value] = hashlib.md5("|".join(sorted(parts)).encode()).hexdigest()[:10]
    return out


def _levels(tree: ast.Module, table: dict[str, str]) -> list[list[tuple[str, tuple]]]:
    """Per level, the sprites IN LIST ORDER as (signature, position)."""
    levels: list[list[tuple[str, tuple]]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        if not any(getattr(t, "id", "") == "levels" for t in node.targets):
            continue
        for lv in node.value.elts:                       # type: ignore[attr-defined]
            placed: list[tuple[str, tuple]] = []
            for kw in lv.keywords:                       # type: ignore[attr-defined]
                if kw.arg != "sprites":
                    continue
                for call in kw.value.elts:               # type: ignore[attr-defined]
                    pos = ast.literal_eval(ast.Tuple(elts=list(call.args), ctx=ast.Load()))
                    inner = call.func.value               # .clone()
                    key = inner.func.value.slice.value    # sprites["<name>"]
                    placed.append((table[key], pos))
            levels.append(placed)
        break
    return levels


def main() -> None:
    a_src, b_src = sys.argv[1], sys.argv[2]
    a = ast.parse(open(a_src).read())
    b = ast.parse(open(b_src).read())
    ta, tb = _sprite_table(a), _sprite_table(b)
    print(f"sprites: live {len(ta)}  arch {len(tb)}")
    print(f"art signatures identical as a SET: {sorted(Counter(ta.values())) == sorted(Counter(tb.values()))}")
    la, lb = _levels(a, ta), _levels(b, tb)
    print(f"levels: live {len(la)}  arch {len(lb)}")
    for i, (x, y) in enumerate(zip(la, lb), start=1):
        same_set = Counter(x) == Counter(y)
        same_order = x == y
        print(f"  L{i}: n={len(x)}/{len(y)}  same_placements={same_set}  same_LIST_ORDER={same_order}")
        if same_set and not same_order:
            # Which pairs swapped relative order — the only thing that can change the picture.
            ia = {v: n for n, v in enumerate(x)}
            ib = {v: n for n, v in enumerate(y)}
            flips = [v for v in x if any(
                (ia[v] < ia[w]) != (ib[v] < ib[w]) for w in x if w != v and w[1] == v[1])]
            if flips:
                print(f"       z-order FLIPPED at a shared position for: {sorted({f[1] for f in flips})}")
        if not same_set:
            print(f"       live-only {sorted(Counter(x) - Counter(y))}")
            print(f"       arch-only {sorted(Counter(y) - Counter(x))}")


if __name__ == "__main__":
    main()
