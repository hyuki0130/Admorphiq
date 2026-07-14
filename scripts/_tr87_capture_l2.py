"""DISPOSABLE, DEV-ONLY, SOURCE-ASSISTED capture script. NOT shipped, NOT a
solver, NOT wired into any test/agent. Extends scripts/_tr87_capture_l1.py
one more level: per Codex's source read (docs/r56_codex_tr87_review_20260715.md),
level index 2 ("Level 3") has multi-token LHS runs in addition to level 1's
multi-token RHS runs -- the hardest segmentation case captured so far. This
script clears level 0 then level 1 (chained, same oracle-assisted approach)
and saves level 2's settled reset frame.

Generalizes level 1's capture script's per-column clearing loop to handle a
bar2 whose length is NOT 1:1 with bar1 (level 0: 5 bar1 glyphs, 5 bar2
glyphs, each rule 1-token both sides; level 1: 4 bar1 glyphs, 7 bar2 glyphs,
because some rules' RHS is 2-3 tokens) -- the target for bar2 is the
FLATTENED concatenation of every matched rule's full RHS token list, in
bar1 order, and the bracket cycles over `len(ztgmtnnufb)` positions
directly (measured true for both level 0 and level 1), so the same
per-position "move bracket, dial to target digit" loop works for any
no-flags level regardless of the LHS/RHS token-count shape.
"""
from __future__ import annotations

import numpy as np
from arc_agi import Arcade, OperationMode
from arcengine import GameAction

A1, A2, A3, A4 = GameAction.ACTION1, GameAction.ACTION2, GameAction.ACTION3, GameAction.ACTION4
DIAL_STATES = 7
# MEASURED (scripts/_tr87_capture_l1.py, tr87.py:1006): ACTION1 = -1 (backward),
# ACTION2 = +1 (forward) -- the wiki's original "ACTION1 is forward" claim was
# wrong (corrected in .wiki/wiki/games/TR87.md, commit a3a6644).
DIAL_FORWARD_ACTION = A2


def forward_steps(current_digit: int, target_digit: int) -> int:
    """How many DIAL_FORWARD_ACTION presses to cycle current_digit -> target_digit (1..7, wraps)."""
    return (target_digit - current_digit) % DIAL_STATES


def clear_current_level(env, game, budget_actions: int = 400) -> tuple[int, object]:
    """Satisfy the current level's bar1->bar2 derivation and flush to the next level.

    Generalized: builds the FULL target token sequence for bar2 by
    flattening every matched rule's complete RHS (not just its first
    token) in bar1 order, so this works for any no-flags level (single- or
    multi-token LHS/RHS) as long as the player edits bar2 directly
    (alter_rules absent/False -- verified via get_data() before calling).
    Returns ``(actions_taken, obs)`` -- callers MUST use the returned
    ``obs`` for anything post-transition (e.g. saving the next level's
    frame), not a stale ``obs`` captured before this function ran; a first
    version of this script (BUG, fixed 2026-07-15) returned only
    ``actions_taken`` and `main()` kept using its OWN original RESET
    ``obs``, silently saving level 0's frame under a "level 2" filename
    (caught because it was byte-identical to `data/traces/tr87.npz`'s
    frame[0] -- always sanity-check a capture against known-different
    prior captures, not just against measured widths that could coincide).
    Asserts the level actually advances.
    """
    flags = (
        game.current_level.get_data("alter_rules"),
        game.current_level.get_data("tree_translation"),
        game.current_level.get_data("double_translation"),
    )
    assert flags == (None, None, None), (
        f"clear_current_level only handles no-flags levels (got {flags}) -- "
        "alter_rules/tree_translation/double_translation need their own logic"
    )
    start_level = game._current_level_index

    rule_target = {lhs[0].name: [s.name for s in rhs] for lhs, rhs in game.cifzvbcuwqe}
    bar1_names = [s.name for s in game.zvojhrjxxm]
    target_names: list[str] = []
    for name in bar1_names:
        target_names.extend(rule_target[name])
    bar2_names_now = [s.name for s in game.ztgmtnnufb]
    assert len(target_names) == len(bar2_names_now), (
        f"target sequence length {len(target_names)} != bar2 length {len(bar2_names_now)} "
        "-- rule_target mapping or bar1 order is wrong"
    )
    print(f"  level {start_level}: bar1={bar1_names}")
    print(f"  level {start_level}: bar2 current={bar2_names_now}")
    print(f"  level {start_level}: bar2 target ={target_names}")

    cur_bracket = 0
    actions_taken = 0
    obs = None
    for pos in range(len(target_names)):
        while cur_bracket != pos:
            obs = env.step(A4)
            actions_taken += 1
            cur_bracket = (cur_bracket + 1) % len(target_names)
        cur_digit = int(bar2_names_now[pos][-1])
        target_digit = int(target_names[pos][-1])
        n_steps = forward_steps(cur_digit, target_digit)
        for _ in range(n_steps):
            obs = env.step(DIAL_FORWARD_ACTION)
            actions_taken += 1
        assert actions_taken <= budget_actions, f"exceeded action budget mid-level {start_level}"

    # Flush the win-animation until the level index advances.
    for _ in range(40):
        if game._current_level_index != start_level:
            break
        obs = env.step(DIAL_FORWARD_ACTION)
        actions_taken += 1

    assert game._current_level_index == start_level + 1, (
        f"failed to advance past level {start_level} (still at {game._current_level_index}) "
        f"after {actions_taken} actions"
    )
    print(f"  level {start_level} cleared in {actions_taken} actions -> now level {game._current_level_index}")
    return actions_taken, obs


def main() -> None:
    arcade = Arcade(operation_mode=OperationMode.NORMAL)
    env = arcade.make("tr87")
    obs = env.step(GameAction.RESET)
    game = env._game  # noqa: SLF001 -- verification-only, disposable script
    assert game._current_level_index == 0

    actions0, obs = clear_current_level(env, game)  # level 0 -> 1
    actions1, obs = clear_current_level(env, game)  # level 1 -> 2
    total = actions0 + actions1
    print(f"total actions across both levels: {total}")
    assert game._current_level_index == 2

    # Same transient-multilayer settle as level 1's capture (measured there:
    # 37 layers, frame[0] stale / frame[-1] settled) -- read frame[-1].
    n_layers = len(obs.frame)
    print(f"n_layers right after the level-2 transition: {n_layers} (using frame[-1])")
    l2_frame = np.array(obs.frame[-1], dtype=np.uint8)
    out_path = "data/traces/tr87_l2_reset.npz"
    np.savez(out_path, frame=l2_frame, level_index=game._current_level_index)
    print(f"saved level-2 reset frame to {out_path}")


if __name__ == "__main__":
    main()
