"""Census: which tools decide an object's IDENTITY from whether it is currently DRAWN?

⛔ WHAT THIS IS FOR. Rule 7cd named a defect CLASS — *a frame-only tool that identifies an object
by whether it is DRAWN is reading PAINT ORDER, not mechanics* — from one site,
`telescope._begin:1182`. A named class with an unknown population is not a doctrine; it is an
anecdote. A grep gives a list of SITES, and rule 7g says the source is what is POSSIBLE. This probe
measures what HAPPENS: for every site of the shape, on every one of the 25 games, does the
visibility filter fire, and does it change the candidate set?

**THE SHAPE** (`telescope.py:1182` is the exemplar): a set of candidate objects filtered by whether
some cell of theirs currently shows a particular colour, with a FALLBACK to the unfiltered set.

    pinned = [b for b in bars if tip_centre(...) in drawn]
    riders = pinned if len(pinned) >= len(m.places) else bars

The four sites carrying it, found by grep and each read in full:

    telescope.TelescopeArmTool._begin   pinned -> bars                    (the 7cd exemplar)
    swivel.SwivelArmTool._begin         pinned -> every bar               (the identical two lines)
    tether._partition                   near   -> every body              (`near if near else all`)
    ledge.LedgeTool._avatar             two branches, both visibility     (see below)

⚠️ `ledge._avatar` is the same class in a second guise and is counted separately by branch: once an
ink is learned it returns **the cell wearing that ink right now**, and `None` when nothing does —
which is what an occluded body looks like; before that it takes the cell drawn exactly ONCE, and
falls back to whichever singular cell sits nearest the frame's middle.

⚠️ NOT COUNTED, and deliberately: `keymaze.py:416` is `[a for a in order if a in unknown] or
list(unknown)` — the same *filter-with-fallback* shape over ACTIONS, which no render can hide. And
the eight index-ordered colour sites rule 7ce measured are colour ORDER, not visibility; a colour
permutation is a bijection and preserves what is drawn.

For each site the probe separates three outcomes, because they are not the same finding:

    fires     the branch executed at all                (a site that never runs costs nothing)
    narrows   the filtered set was used AND was smaller (the visibility evidence did work)
    fallback  the unfiltered set was used               (the evidence was absent — 7cd's case)

  bash scripts/pfan.sh viscensus scripts/_visibility_census.py 25 "" 12
      one arm per game, in the order `Arcade.get_environments()` yields them.

⛔ RUN IT ON BOTH BOARDS. A census on the LIVE 25 alone UNDERSTATES the class by construction, and
this is measured, not argued: `lattice_maze._locate` reaches its ambiguous branch **zero** times in
187 reads on the live tu93 and was decisive enough on the ARCHIVED copy to cost that game 9 levels
in 188 actions -> 4 in 1288. A site is only known to be free once the render that removes its
evidence has been tried. `arm=arch` substitutes every archived re-render, exactly as
`scripts/xfergate.sh` does.

  bash scripts/pfan.sh viscensus  scripts/_visibility_census.py 25 ""     12
  bash scripts/pfan.sh viscensusA scripts/_visibility_census.py 25 arch   12
"""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
from collections import Counter
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT / "src"))
sys.path.insert(0, str(_ROOT / "scripts"))

BUDGET = 4000
_LIVE = _ROOT / "environment_files"
# ⚠️ Not in the repo and not linked into a pfan snapshot; it sits beside the shared tree on the box.
_ARCH = Path.home() / "admorphiq" / "environment_files_archive"


def env_dir(arm: str) -> str | None:
    """None = the runner's own default. 'arch' = every archived re-render SUBSTITUTED.

    ⛔ SUBSTITUTE, NEVER ADD. Two version dirs under one game share a `game_id` and the loader
    keeps whichever `rglob` yields first (rule 7bu), so adding the archive would score an
    unpredictable mixture and look like a clean run.
    """
    if arm != "arch":
        return None
    tmp = Path(tempfile.mkdtemp(prefix="census_arch_"))
    for game in sorted(p.name for p in _LIVE.iterdir() if p.is_dir()):
        src = _ARCH / game if (_ARCH / game).is_dir() else _LIVE / game
        shutil.copytree(src, tmp / game)
    return str(tmp)


def _install(tally: Counter, state: dict) -> None:
    """Wrap the four sites. Every wrapper calls the original and only READS after it."""
    from admorphiq.tools import ledge as ld
    from admorphiq.tools import swivel as sw
    from admorphiq.tools import telescope as te
    from admorphiq.tools import tether as tt

    def note(site: str, outcome: str) -> None:
        tally[f"{site}.{outcome}"] += 1

    # --- 1. telescope: pinned riders, else every anchored bar ------------------
    te_begin = te.TelescopeArmTool._begin

    def te_wrap(self, g):  # noqa: ANN001, ANN202
        ok = te_begin(self, g)
        if ok and self._model is not None:
            m = te.read_markers(g, self._marker or 0)
            widgets = te.read_widgets(g)
            bars = te.anchored_bars(g, self._marker or 0, [w.box for w in widgets], self._pieces)
            drawn = set(m.movers) if m else set()
            pinned = [b for b in bars
                      if te.tip_centre(self._pieces[b[0]].box, b[1]) in drawn]
            places = len(m.places) if m else 0
            note("telescope._begin", "fires")
            if len(pinned) >= places:
                note("telescope._begin", "narrows" if len(pinned) < len(bars) else "no_effect")
            else:
                note("telescope._begin", "fallback")
            state["te"].append((len(drawn), len(pinned), len(bars), places))
        return ok

    te.TelescopeArmTool._begin = te_wrap

    # --- 2. swivel: the identical two lines -----------------------------------
    sw_begin = sw.SwivelArmTool._begin

    def sw_wrap(self, g):  # noqa: ANN001, ANN202
        ok = sw_begin(self, g)
        if ok and self._model is not None and self._cfg is not None:
            marks = sw.read_markers(g, self._marker or 0)
            drawn = set(marks.movers) if marks else set()
            n = len(self._cfg.bars)
            pinned = [i for i in range(n) if sw.rider_at(self._cfg, i) in drawn]
            places = len(self._model.places)
            note("swivel._begin", "fires")
            if len(pinned) >= places:
                note("swivel._begin", "narrows" if len(pinned) < n else "no_effect")
            else:
                note("swivel._begin", "fallback")
            state["sw"].append((len(drawn), len(pinned), n, places))
        return ok

    sw.SwivelArmTool._begin = sw_wrap

    # --- 3. tether: a weight's pip names its body, else EVERY body ------------
    tt_part = tt._partition

    def tt_wrap(board):  # noqa: ANN001, ANN202
        out = tt_part(board)
        note("tether._partition", "fires")
        bodies = len(board.disks)
        for w in board.weights:
            near = [i for i, b in enumerate(board.disks) if w["pip"] in b["colours"]]
            if not near:
                note("tether._partition", "fallback")
            elif len(near) < bodies:
                note("tether._partition", "narrows")
            else:
                note("tether._partition", "no_effect")
        return out

    tt._partition = tt_wrap

    # --- 4. ledge: the avatar is whatever wears its ink right now -------------
    ld_av = ld.LedgeTool._avatar

    def ld_wrap(self, board, inks):  # noqa: ANN001, ANN202
        tracked = bool(self._avatar_ink)
        got = ld_av(self, board, inks)
        note("ledge._avatar", "fires")
        if tracked:
            hits = [c for c, ink in inks.items() if ink & self._avatar_ink]
            # ⭐ No hit = nothing on the board wears the body's ink. That is what an occluded
            # avatar looks like, and the tool answers None — the identity is simply lost.
            note("ledge._avatar", "tracked_lost" if not hits else
                 ("tracked_unique" if len(hits) == 1 else "tracked_ambiguous"))
        else:
            cand = sorted(self._singular(inks))
            note("ledge._avatar", "boot_none" if not cand else
                 ("boot_unique" if len(cand) == 1 else "boot_fallback"))
        if got is None:
            note("ledge._avatar", "returned_none")
        return got

    ld.LedgeTool._avatar = ld_wrap


def main() -> None:
    seed = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    arm = sys.argv[2] if len(sys.argv) > 2 and sys.argv[2] else "live"

    from arc_agi import Arcade, OperationMode

    tally: Counter = Counter()
    state: dict = {"te": [], "sw": []}
    _install(tally, state)

    from score_efficiency import run_game

    where = env_dir(arm)
    arcade = (Arcade(operation_mode=OperationMode.OFFLINE, environments_dir=where)
              if where else Arcade(operation_mode=OperationMode.OFFLINE))
    envs = arcade.get_environments()
    seen: set[str] = set()
    uniq = []
    for e in envs:
        if e.game_id not in seen:
            seen.add(e.game_id)
            uniq.append(e)
    if seed > len(uniq):
        print(json.dumps({"seed": seed, "arm": arm, "skipped": True, "n_games": len(uniq)}))
        return
    info = uniq[seed - 1]
    res = run_game(arcade, info.game_id, info.baseline_actions,
                   agent_name="unified", max_actions=BUDGET)
    print(json.dumps({
        "seed": seed,
        "arm": arm,
        "game": info.game_id,
        "game_score": res.get("game_score"),
        "levels": res.get("levels_completed"),
        "tally": dict(sorted(tally.items())),
        # (drawn, pinned, candidates, destinations) per level, so a fallback can be told from a
        # filter that ran and changed nothing.
        "telescope_reads": state["te"],
        "swivel_reads": state["sw"],
    }))


if __name__ == "__main__":
    main()
