"""Round 21 focused diagnostic: SU15 only, instrumented."""

from __future__ import annotations

import time

from admorphiq.strategies import inferential as inf


def main() -> None:
    from arc_agi import Arcade, OperationMode

    arcade = Arcade(operation_mode=OperationMode.NORMAL)
    gid = None
    for info in arcade.get_environments():
        if (info.title or "").upper() == "SU15":
            gid = info.game_id
            break
    env = arcade.make(gid)
    print(f"SU15 game_id={gid}")

    orig_obs = inf.observation_phase
    orig_goal = inf.goal_phase
    orig_merge = inf._plan_merge
    counters: dict[str, int] = {}

    def traced_obs(env, stride=8, budget=200):
        counters["obs"] = counters.get("obs", 0) + 1
        profile, used = orig_obs(env, stride=stride, budget=budget)
        clicks = profile.get("click", [])
        r10 = [c for c in clicks if c.get("diff_magnitude", 0) >= 10]
        print(
            f"  [obs#{counters['obs']}] base_levels={profile['base_levels']} "
            f"responsive>=10={len(r10)} used={used}"
        )
        return profile, used

    def traced_goal(action_profile, entity_map):
        counters["goal"] = counters.get("goal", 0) + 1
        goal = orig_goal(action_profile, entity_map)
        print(
            f"  [goal#{counters['goal']}] kind={goal['kind']} "
            f"conf={goal['confidence']:.2f} "
            f"merge_items={len(entity_map.get('merge_items', []))} "
            f"player={'y' if entity_map.get('player') else 'n'} "
            f"goal_regions={len(entity_map.get('goal_regions', []))}"
        )
        return goal

    def traced_merge(env, ap, em, g, b):
        counters["merge"] = counters.get("merge", 0) + 1
        t0 = time.time()
        r = orig_merge(env, ap, em, g, b)
        print(f"  [merge#{counters['merge']}] levels={r[0]} used={r[1]} elapsed={time.time()-t0:.1f}s")
        return r

    inf.observation_phase = traced_obs
    inf.goal_phase = traced_goal
    inf._plan_merge = traced_merge
    inf.PLAN_FNS["merge"] = traced_merge

    t0 = time.time()
    best, label, used = inf.strat_inferential_agent(env, 50000)
    print(
        f"\nSU15 final: levels={best}  actions={used}  label={label}  "
        f"elapsed={time.time()-t0:.1f}s"
    )


if __name__ == "__main__":
    main()
