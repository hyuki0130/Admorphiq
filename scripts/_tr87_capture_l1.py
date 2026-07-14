"""DISPOSABLE, DEV-ONLY, SOURCE-ASSISTED capture script. NOT shipped, NOT a
solver, NOT wired into any test/agent. Exists for exactly one purpose per
docs/r56_codex_tr87_review_20260715.md's "cheapest next step": no captured
frames exist for TR87 level index 1 (data/traces + data/transitions only
have level 0), so the gap-window segmentation claims in
docs/tr87_frame_only_grammar_design_20260715.md are untested on a level
with multi-token (1-to-2, 1-to-3) rules. This script runs ONE local episode
(via arc_agi.Arcade, the same offline dev harness scripts/test_tr87_*.py
already use -- environment_files/tr87/cd924810/tr87.py executes in-process,
no Kaggle submission involved) and reads the running game object's OWN
internal rule table (`env._game.cifzvbcuwqe`, `.zvojhrjxxm`, `.ztgmtnnufb`)
ONLY to compute which buttons clear level 0 fast -- exactly the
"verification-only internal read" pattern already established in this repo
(see the design doc's "Sources read" section), applied here to ADVANCE the
game rather than to build a solver. The resulting level-1 reset frame is
saved to data/traces/tr87_l1_reset.npz for the actual (frame-only) gap
probe to consume -- nothing in the probe itself reads game internals.
"""
from __future__ import annotations

import numpy as np
from arc_agi import Arcade, OperationMode
from arcengine import GameAction

A1, A2, A3, A4 = GameAction.ACTION1, GameAction.ACTION2, GameAction.ACTION3, GameAction.ACTION4
DIAL_STATES = 7
# MEASURED directly against the running game object below (step()'s own
# `pxdsteijos = -1 if self.action.id == GameAction.ACTION1 else 1` for the
# ACTION1/ACTION2 branch): ACTION1 is the -1 (backward) dial step, ACTION2
# is +1 (forward) -- the OPPOSITE of .wiki/wiki/games/TR87.md's "ACTION1 is
# the forward step" claim. Flagging for a follow-up wiki correction; this
# script uses the source-verified direction, not the wiki's.
DIAL_FORWARD_ACTION = A2


def forward_steps(current_digit: int, target_digit: int) -> int:
    """How many DIAL_FORWARD_ACTION presses to cycle current_digit -> target_digit (1..7, wraps)."""
    return (target_digit - current_digit) % DIAL_STATES


def main() -> None:
    arcade = Arcade(operation_mode=OperationMode.NORMAL)
    env = arcade.make("tr87")
    obs = env.step(GameAction.RESET)
    game = env._game  # noqa: SLF001 -- verification-only, disposable script

    assert game._current_level_index == 0, f"expected to start at level 0, got {game._current_level_index}"

    # Build LHS-name -> RHS-name map from the level's own rule table (oracle read).
    rule_target = {lhs[0].name: rhs[0].name for lhs, rhs in game.cifzvbcuwqe}
    bar1_names = [s.name for s in game.zvojhrjxxm]
    bar2_names_now = [s.name for s in game.ztgmtnnufb]
    target_names = [rule_target[name] for name in bar1_names]
    print(f"bar1 (target) glyph names: {bar1_names}")
    print(f"bar2 (current) glyph names: {bar2_names_now}")
    print(f"bar2 (required) glyph names: {target_names}")

    cur_bracket = 0  # qvtymdcqear_index starts at 0 per on_set_level
    actions_taken = 0
    for col in range(len(target_names)):
        while cur_bracket != col:
            obs = env.step(A4)
            actions_taken += 1
            cur_bracket = (cur_bracket + 1) % len(target_names)
        cur_digit = int(bar2_names_now[col][-1])
        target_digit = int(target_names[col][-1])
        n_steps = forward_steps(cur_digit, target_digit)
        for _ in range(n_steps):
            obs = env.step(DIAL_FORWARD_ACTION)
            actions_taken += 1
        print(f"  column {col}: {bar2_names_now[col]} -> {target_names[col]} "
              f"({n_steps} forward presses)")

    print(f"actions taken to satisfy the derivation: {actions_taken}")
    print(f"levels_completed after the final press: {obs.levels_completed}")

    # Flush the win-animation (yfetxjexviz counts up over several step() calls
    # before next_level() actually fires) until level_index advances or we
    # give up -- generous cap, level 0's own budget is 128 actions.
    for _ in range(40):
        if game._current_level_index != 0 or obs.levels_completed >= 1:
            break
        obs = env.step(DIAL_FORWARD_ACTION)
        actions_taken += 1

    print(f"final level_index: {game._current_level_index}, "
          f"levels_completed: {obs.levels_completed}, total actions: {actions_taken}")
    assert game._current_level_index == 1, (
        f"failed to advance to level 1 (still at {game._current_level_index}) -- "
        "the derivation target computation is wrong, inspect above"
    )

    # `obs.frame` is a frame-history stack that carries MULTIPLE layers for a
    # few steps right after a level clears (measured here: 37 layers on the
    # very step level_index becomes 1); frame[0] is a STALE pre-transition
    # frame during that window (row-63's move counter still shows the prior
    # level's partial usage instead of a fresh full bar) while frame[-1] is
    # the settled CURRENT frame -- this is the exact transient documented in
    # .wiki/wiki/rounds/r53_unified-harness.md's SB26 "canonical_layer"
    # finding, now independently reproduced for TR87. Use frame[-1].
    print(f"n_layers right after the level-1 transition: {len(obs.frame)} "
          f"(frame[0] would be STALE if this is > 1; using frame[-1])")
    l1_frame = np.array(obs.frame[-1], dtype=np.uint8)
    out_path = "data/traces/tr87_l1_reset.npz"
    np.savez(out_path, frame=l1_frame, level_index=game._current_level_index)
    print(f"saved level-1 reset frame to {out_path}")


if __name__ == "__main__":
    main()
