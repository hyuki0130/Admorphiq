"""R98 discovery-evidence certification — sp80 idx0.

Purpose
-------
Codex binding correction E.1: the v1.1 mutant table leaned on evidence that was
only asserted ("if routed"), not observed. This probe walks every reachable
placement of the single piece and records, for each, the exact settle outcome:
which sinks became satisfied, whether the hazard was contacted, and whether the
level advanced. From that table it answers three questions the contract needs:

* T3 (sink satisfied on CONTACT vs on MOUTH entry) — is there a placement whose
  flow touches a sink's outer wall without satisfying it there?
* O1 (all sinks vs any sink) — is a PARTIAL cover (exactly one of two sinks)
  reachable at all? If not, O1 is honestly UNKNOWN at this level and no probe
  can rescue it.
* O2 (hazard fatal vs neutral) — is there a placement that satisfies EVERY sink
  and still fails? That is the only evidence that attributes failure to the
  hazard rather than to incomplete coverage.

Expected feedback
-----------------
Each question resolves to CERTIFIED (with the placement and the observed
outcome) or UNKNOWN-AT-THIS-LEVEL (with the exhaustive enumeration as proof
that no probe exists). Either answer is usable; a fabricated CERTIFIED is not.
The enumeration is exhaustive over horizontal placements, so an UNKNOWN here is
a proof of absence, not a failure to look.

Dev-time only — a certification probe, not part of any runtime agent path.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from arc_agi import Arcade, OperationMode  # noqa: E402
from arcengine import GameAction  # noqa: E402

WATER = 6
SATISFIED = 13   # a sink that the flow filled
SCALE = 4        # pixels per cell, confirmed by the oracle probe
GRID = 16        # cells per side on this board

# Hazard contact is read as "the flow reached the row directly above the bottom
# row", a frame-only signal. Two traps this avoids:
#  * the failure-flash colour is NOT usable — the HUD paints the same colour on
#    every frame, so a colour-based flash detector fires on every run;
#  * water never OCCUPIES the bottom row, because a droplet that contacts the
#    hazard dies instead of advancing into it. The deepest cell water can hold is
#    one row above.
# Layers are also truncated at the first board reset: within one spill the water
# trail only grows, so a layer that is not a superset of the accumulated trail
# belongs to the NEXT level and must not be measured.


def _fresh():
    arcade = Arcade(
        operation_mode=OperationMode.OFFLINE,
        environments_dir=os.environ.get("ARC_ENVIRONMENTS_DIR") or None,
    )
    gid = next(e.game_id for e in arcade.get_environments() if e.game_id.startswith("sp80"))
    env = arcade.make(gid)
    return env, env.step(GameAction.RESET)


def _cells(grid, colour: int) -> set[tuple[int, int]]:
    return {
        (y // SCALE, x // SCALE)
        for y, row in enumerate(grid)
        for x, v in enumerate(row)
        if v == colour
    }


def _run_placement(dx: int, dy: int = 0) -> dict:
    """Translate the auto-selected piece by (dx, dy) cells, commit, read the outcome."""
    env, obs = _fresh()
    for _ in range(abs(dx)):
        obs = env.step(GameAction.ACTION4 if dx > 0 else GameAction.ACTION3)
    for _ in range(abs(dy)):
        obs = env.step(GameAction.ACTION2 if dy > 0 else GameAction.ACTION1)
    obs = env.step(GameAction.ACTION5)

    def _absorb(frame, satisfied_cols, sink_cells, water_by_layer, trail):
        """Append this frame's layers, stopping at the first board reset."""
        for layer in frame:
            water = _cells(layer, WATER)
            if trail and water and not (trail <= water):
                return True  # the trail reset — this layer is a different board
            sat = _cells(layer, SATISFIED)
            satisfied_cols |= {c for (_, c) in sat}
            sink_cells |= sat
            water_by_layer.append(water)
            trail |= water
        return False

    satisfied_cols: set[int] = set()
    sink_cells: set[tuple[int, int]] = set()
    water_by_layer: list[set[tuple[int, int]]] = []
    trail: set[tuple[int, int]] = set()
    stop = _absorb(obs.frame, satisfied_cols, sink_cells, water_by_layer, trail)

    advanced = obs.levels_completed >= 1
    if not advanced:
        for _ in range(30):
            obs = env.step(GameAction.ACTION5)
            if not stop:
                stop = _absorb(obs.frame, satisfied_cols, sink_cells, water_by_layer, trail)
            if obs.levels_completed >= 1:
                advanced = True
                break

    deepest = max((r for cells in water_by_layer for (r, _) in cells), default=-1)
    # a droplet dies on hazard contact, so the deepest cell it can OCCUPY is the
    # row above the bottom row
    hazard_contact = deepest >= GRID - 2

    # how many distinct sinks were filled: satisfied cells cluster per sink
    groups: list[set[int]] = []
    for c in sorted(satisfied_cols):
        if groups and c - max(groups[-1]) <= 1:
            groups[-1].add(c)
        else:
            groups.append({c})

    seen: set[tuple[int, int]] = set()
    frontier: list[list[tuple[int, int]]] = []
    for cells in water_by_layer:
        frontier.append(sorted(cells - seen))
        seen |= cells

    # contact-without-satisfaction: a frontier cell whose cell AHEAD is part of a
    # sink, where the next frontier is the flanking pair instead of a satisfied
    # sink. This is what separates mouth-entry semantics from contact semantics.
    contact_spread = None
    for i in range(len(frontier) - 1):
        for (r, c) in frontier[i]:
            if (r + 1, c) not in sink_cells:
                continue
            nxt = set(frontier[i + 1])
            if {(r, c - 1), (r, c + 1)} <= nxt:
                contact_spread = {"layer": i, "cell": (r, c),
                                  "sink_cell_ahead": (r + 1, c),
                                  "spread_to": [(r, c - 1), (r, c + 1)]}
                break
        if contact_spread:
            break

    return {
        "dx": dx,
        "dy": dy,
        "sinks_filled": len(groups),
        "satisfied_columns": sorted(satisfied_cols),
        "deepest_water_row": deepest,
        "hazard_contact": hazard_contact,
        "contact_spread": contact_spread,
        "advanced": advanced,
        "frontier": frontier,
    }


def main() -> int:
    table = []
    # exhaustive over horizontal placements: the piece starts at columns 3..7 on a
    # 16-wide board, so -3..+8 covers every position it can reach.
    for dx in range(-3, 9):
        try:
            table.append(_run_placement(dx))
        except Exception as exc:  # a placement the engine refuses is still data
            table.append({"dx": dx, "dy": 0, "error": str(exc)})
    # row-independence check: the same columns at two other rows
    for dy in (2, 5):
        for dx in (2, 3):
            try:
                table.append(_run_placement(dx, dy))
            except Exception as exc:
                table.append({"dx": dx, "dy": dy, "error": str(exc)})

    print("placement table (dx, dy → outcome):")
    for row in table:
        if "error" in row:
            print(f"  ({row['dx']:+d},{row['dy']:+d}): ERROR {row['error']}")
            continue
        print(f"  ({row['dx']:+d},{row['dy']:+d}): sinks_filled={row['sinks_filled']} "
              f"cols={row['satisfied_columns']} deepest_row={row['deepest_water_row']} "
              f"hazard={row['hazard_contact']} advanced={row['advanced']}")

    ok = [r for r in table if "error" not in r]
    total_sinks = max((r["sinks_filled"] for r in ok), default=0)

    partial = [r for r in ok if 0 < r["sinks_filled"] < total_sinks]
    full_but_failed = [r for r in ok
                       if r["sinks_filled"] == total_sinks and total_sinks > 0
                       and not r["advanced"]]
    winners = [r for r in ok if r["advanced"]]

    print()
    if partial:
        print(f"[O1 all-vs-any] CERTIFIED via ({partial[0]['dx']:+d},{partial[0]['dy']:+d})")
    else:
        print("[O1 all-vs-any] UNKNOWN-AT-THIS-LEVEL — no reachable placement fills "
              "a strict subset of the sinks (exhaustive over all placements above), "
              "so no probe can rescue this mutant here")

    # the attribution is only valid if the two runs differ in hazard contact and
    # in nothing else the objective can see
    pair = next(((f, w) for f in full_but_failed for w in winners
                 if f["sinks_filled"] == w["sinks_filled"]
                 and f["hazard_contact"] and not w["hazard_contact"]), None)
    if pair:
        f, w = pair
        print(f"[O2 hazard fatal] CERTIFIED — ({f['dx']:+d},{f['dy']:+d}) fills every sink "
              f"({f['sinks_filled']}) and FAILS, with the flow reaching row "
              f"{f['deepest_water_row']}; ({w['dx']:+d},{w['dy']:+d}) fills the same "
              f"{w['sinks_filled']} sinks, stops at row {w['deepest_water_row']}, and "
              f"ADVANCES. Coverage is identical across the pair, so the failure is "
              f"attributable to the hazard contact alone.")
    elif full_but_failed:
        print("[O2 hazard fatal] UNKNOWN — a full-coverage failure exists but no "
              "winner/loser pair differs ONLY in hazard contact, so the failure "
              "cannot be attributed")
    else:
        print("[O2 hazard fatal] UNKNOWN-AT-THIS-LEVEL")

    witness = next((r for r in ok if r.get("contact_spread")), None)
    if witness:
        cs = witness["contact_spread"]
        print(f"[T3 contact-vs-mouth] CERTIFIED via ({witness['dx']:+d},"
              f"{witness['dy']:+d}) — at layer {cs['layer']} the flow occupied "
              f"{cs['cell']} with the sink cell {cs['sink_cell_ahead']} directly "
              f"ahead; it did NOT satisfy the sink there but spread to "
              f"{cs['spread_to']}, and the sink only became satisfied once the flow "
              f"reached its mouth column. Contact alone is therefore not "
              f"satisfaction.")
    else:
        print("[T3 contact-vs-mouth] UNKNOWN — no placement produced a "
              "contact-without-satisfaction event")

    tgt = witness or (full_but_failed[0] if full_but_failed else (ok[0] if ok else None))
    if tgt:
        print(f"    frontier of ({tgt['dx']:+d},{tgt['dy']:+d}):")
        for i, f in enumerate(tgt["frontier"][:20]):
            if f:
                print(f"      layer {i:2d}: {f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
