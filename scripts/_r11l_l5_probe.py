"""DISPOSABLE, DEV-ONLY, SOURCE-ASSISTED perception probe for r11l Level 5.

Drives the SHIPPED quarantined adapter (adapters25.r11l.Adapter) through
L0-L3 (its 4/6 floor), then at ``levels_completed == 4`` (Level 5 reached)
reads the running game object PASSIVELY (env._game, verification-only,
never shipped) to establish the ground-truth collect-match structure:
collectors (whkxtx bodies + legs), collectible puukul pieces + colours,
target colour-sets. Cross-references each against the FRAME to confirm the
colour-set win is frame-observable (the Pass-1 deliverable). No solver, no
build; nothing here is imported by any agent/test.
"""
from __future__ import annotations

import numpy as np
from arc_agi import Arcade, OperationMode
from arcengine import GameAction

from admorphiq.adapters25.r11l import Adapter


def pos_colours(sprite) -> set[int]:
    """Positive colour set of a sprite's pixel array (the win-check semantics:
    ``{int(c) for c in np.unique(pixels) if c > 0}``)."""
    return {int(c) for c in np.unique(sprite.pixels) if c > 0}


def sprite_box(sprite) -> tuple[int, int, int, int]:
    return (sprite.x, sprite.y, sprite.x + sprite.width, sprite.y + sprite.height)


def main() -> None:
    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    env = arcade.make("r11l")
    obs = env.step(GameAction.RESET)
    game = env._game  # noqa: SLF001 -- verification-only, disposable

    adapter = Adapter()
    steps = 0
    reached = False
    while steps < 6000:
        if adapter.is_done([], obs):
            break
        action = adapter.choose_action([], obs)
        if not isinstance(action, GameAction):
            break
        if action.is_complex():
            obs = env.step(action, data=action.action_data.model_dump())
        else:
            obs = env.step(action)
        if obs is None:
            break
        steps += 1
        lv = int(getattr(obs, "levels_completed", 0) or 0)
        if obs.state.name == "GAME_OVER":
            obs = env.step(GameAction.RESET)
            steps += 1
            continue
        if lv >= 4:
            # Let the entry animation settle a few frames.
            reached = True
            break

    print(f"reached L5={reached} after {steps} adapter steps; "
          f"levels_completed={int(getattr(obs, 'levels_completed', 0) or 0)} "
          f"state={obs.state.name}")
    if not reached:
        print("DID NOT REACH L5 -- abort.")
        return

    print("\n=== GROUND TRUTH (env._game passive read) ===")
    print(f"current_level_index = {getattr(game, '_current_level_index', '?')}")
    kac = game.kacotwgjcyq
    print(f"\ncreatures (kacotwgjcyq) -- {len(kac)} entries:")
    for name, data in kac.items():
        body = data["roduyfsmiznvg"]
        legs = data["lecfirgqbwunn"]
        tgt = data["gosubdcyegamj"]
        bstr = f"{body.name}@{sprite_box(body)} col={pos_colours(body)}" if body else "None"
        tstr = f"{tgt.name}@{sprite_box(tgt)} col={pos_colours(tgt)}" if tgt else "None"
        lstr = [f"{lg.name}@({lg.x},{lg.y}) col={pos_colours(lg)}" for lg in legs]
        print(f"  [{name!r}] dirwzt={'dirwzt' in name}")
        print(f"      body(collector)={bstr}")
        print(f"      target={tstr}")
        print(f"      legs({len(legs)})={lstr}")

    print(f"\ncollectors (bulmhgivatv keys): {list(game.bulmhgivatv.keys())}")
    for cname, absorbed in game.bulmhgivatv.items():
        sprs = game.current_level.get_sprites_by_name(cname)
        s = sprs[0] if sprs else None
        cstr = f"@{sprite_box(s)} col={pos_colours(s)}" if s else "missing"
        print(f"  {cname}: absorbed={absorbed} now {cstr}")

    print(f"\ncollectibles (owuypsqbino) -- {len(game.owuypsqbino)}:")
    for c in game.owuypsqbino:
        print(f"  {c.name}@{sprite_box(c)} col={pos_colours(c)}")

    print("\n=== TARGET REQUIREMENTS (non-dirwzt, body-less collect-match) ===")
    for name, data in kac.items():
        tgt = data["gosubdcyegamj"]
        body = data["roduyfsmiznvg"]
        if tgt is None or "dirwzt" in name or body is not None:
            continue
        print(f"  target {name}: needs a collector overlapping "
              f"{sprite_box(tgt)} with colour set == {pos_colours(tgt)}")

    # Frame-observability cross-check.
    print("\n=== FRAME OBSERVABILITY ===")
    frame = np.array(obs.frame[-1]) if hasattr(obs, "frame") else None
    if frame is not None:
        print(f"frame shape={frame.shape}, colours present={sorted(set(int(x) for x in np.unique(frame)))}")
        # Which target/collectible colours are visible on the frame?
        present = set(int(x) for x in np.unique(frame))
        for name, data in kac.items():
            tgt = data["gosubdcyegamj"]
            if tgt is None or "dirwzt" in name:
                continue
            tc = pos_colours(tgt)
            print(f"  target {name} col={tc} -> visible on frame: {tc & present} "
                  f"(missing {tc - present})")
        for c in game.owuypsqbino:
            cc = pos_colours(c)
            print(f"  collectible {c.name} col={cc} -> visible: {cc & present}")


if __name__ == "__main__":
    main()
