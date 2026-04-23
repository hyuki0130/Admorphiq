"""Round 18 focused diagnostic: FT09 only, instrumented.

Exposes per-level observation/goal/plan traces by monkey-patching
`_try_plan` in strat_inferential_agent. Helps diagnose why L2+
fails after R18's delta-chain clears L1.
"""

from __future__ import annotations

import time

from admorphiq.strategies import inferential as inf


def main() -> None:
    from arc_agi import Arcade, OperationMode

    arcade = Arcade(operation_mode=OperationMode.NORMAL)
    env_infos = arcade.get_environments()
    gid = None
    for info in env_infos:
        if (info.title or "").upper() == "FT09":
            gid = info.game_id
            break
    if gid is None:
        print("FT09 not found")
        return
    env = arcade.make(gid)
    if env is None:
        print("FT09 make failed")
        return
    print(f"FT09 game_id={gid}")

    # Monkey-patch observation_phase + _plan_lights_out so each call
    # logs a one-line summary.
    orig_obs = inf.observation_phase
    orig_plan = inf._plan_lights_out
    call_counter = {"obs": 0, "plan": 0}

    def traced_obs(env, stride=8, budget=200):
        call_counter["obs"] += 1
        profile, used = orig_obs(env, stride=stride, budget=budget)
        clicks = profile.get("click", [])
        responsive = [c for c in clicks if c.get("diff_magnitude", 0) >= 10]
        print(
            f"  [obs#{call_counter['obs']}] base_levels={profile['base_levels']} "
            f"clicks_probed={len(clicks)} responsive_ge10={len(responsive)} "
            f"obs_used={used}"
        )
        return profile, used

    def traced_plan(env, action_profile, entity_map, goal, budget):
        call_counter["plan"] += 1
        clicks = action_profile.get("click", [])
        responsive = [c for c in clicks if c.get("diff_magnitude", 0) >= 10]
        print(
            f"  [plan#{call_counter['plan']} lights_out] responsive={len(responsive)} "
            f"budget={budget}"
        )
        t0 = time.time()
        levels, used = orig_plan(env, action_profile, entity_map, goal, budget)
        stencil = inf._LAST_STENCIL
        if stencil is not None:
            A = stencil["A"]
            print(
                f"    stencil n={A.shape[0]} non_zero={int(A.sum())} "
                f"base_classes={stencil['base_classes']} "
                f"toggled_classes={stencil['toggled_classes']}"
            )
        print(
            f"    -> levels={levels} plan_used={used} prefix_len={len(inf._ACTIVE_PREFIX)} "
            f"elapsed={time.time() - t0:.1f}s"
        )
        return levels, used

    inf.observation_phase = traced_obs
    inf._plan_lights_out = traced_plan
    inf.PLAN_FNS["lights_out"] = traced_plan

    t0 = time.time()
    best, label, used = inf.strat_inferential_agent(env, 50000)
    elapsed = round(time.time() - t0, 1)
    print(
        f"\nFT09 final: levels={best}  actions={used}  label={label}  elapsed={elapsed}s"
    )


if __name__ == "__main__":
    main()
