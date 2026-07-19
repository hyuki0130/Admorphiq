"""DISPOSABLE: trace the collect-match controller on L5 — does it detect/assign,
does the body move toward goals, does it absorb the right pieces? env._game read
for ground-truth absorbed/colour-set progress only."""
from __future__ import annotations

import numpy as np
from arc_agi import Arcade, OperationMode
from arcengine import GameAction

from admorphiq.adapters25.r11l import Adapter


def body_colsets(game):
    out = {}
    for cname in game.bulmhgivatv:
        sprs = game.current_level.get_sprites_by_name(cname)
        if sprs:
            out[cname] = sorted({int(c) for c in np.unique(sprs[0].pixels) if c > 0})
    return out


def main() -> None:
    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    env = arcade.make("r11l")
    obs = env.step(GameAction.RESET)
    game = env._game  # noqa: SLF001
    ad = Adapter()
    steps = 0
    while steps < 6000:
        if ad.is_done([], obs):
            break
        a = ad.choose_action([], obs)
        obs = env.step(a, data=a.action_data.model_dump()) if a.is_complex() else env.step(a)
        if obs is None:
            break
        steps += 1
        if obs.state.name == "GAME_OVER":
            obs = env.step(GameAction.RESET)
            steps += 1
            continue
        if int(getattr(obs, "levels_completed", 0) or 0) >= 4:
            break

    print(f"reached L5 in {steps} steps")
    reset_count = 0
    for t in range(120):
        if ad.is_done([], obs):
            print("adapter done")
            break
        a = ad.choose_action([], obs)
        obs = env.step(a, data=a.action_data.model_dump()) if a.is_complex() else env.step(a)
        if obs is None:
            break
        st = obs.state.name
        lv = int(getattr(obs, "levels_completed", 0) or 0)
        if t < 8 or t % 15 == 0 or st in ("WIN", "GAME_OVER") or lv >= 5:
            print(f"  t={t} act=({a.action_data.x if a.is_complex() else '-'},"
                  f"{a.action_data.y if a.is_complex() else '-'}) st={st} lv={lv} "
                  f"cm_active={ad._cm_active} ci={ad._cm_ci} moves={ad._cm_moves_done} "
                  f"assign={[sorted(c) for c, _cc, _b in ad._cm_assign]} "
                  f"absorbed={ {k: v for k, v in game.bulmhgivatv.items()} } "
                  f"colsets={body_colsets(game)}")
        if lv >= 5:
            print("  *** L5 CLEARED ***")
            break
        if st == "GAME_OVER":
            obs = env.step(GameAction.RESET)
            reset_count += 1
            if reset_count > 3:
                break
    print(f"final: state={obs.state.name} levels={int(getattr(obs,'levels_completed',0) or 0)}")


if __name__ == "__main__":
    main()
