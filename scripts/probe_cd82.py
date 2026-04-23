"""Round 20 focused diagnostic: CD82 only, instrumented.

Instruments observation_phase and each plan fn to see what the
inferential agent does on CD82 (paint-game). Measures per-level
progress, responsive-cell counts, plan choices.
"""

from __future__ import annotations

import time

from admorphiq.strategies import inferential as inf


def main() -> None:
    from arc_agi import Arcade, OperationMode

    arcade = Arcade(operation_mode=OperationMode.NORMAL)
    gid = None
    for info in arcade.get_environments():
        if (info.title or "").upper() == "CD82":
            gid = info.game_id
            break
    env = arcade.make(gid)
    print(f"CD82 game_id={gid}")

    orig_obs = inf.observation_phase
    orig_goal = inf.goal_phase
    counters: dict[str, int] = {}
    plan_calls: list[str] = []

    def traced_obs(env, stride=8, budget=200):
        counters["obs"] = counters.get("obs", 0) + 1
        profile, used = orig_obs(env, stride=stride, budget=budget)
        clicks = profile.get("click", [])
        responsive = [c for c in clicks if c.get("diff_magnitude", 0) >= 10]
        big = [c for c in clicks if c.get("diff_magnitude", 0) >= 100]
        print(
            f"  [obs#{counters['obs']}] base_levels={profile['base_levels']} "
            f"responsive>=10={len(responsive)} big>=100={len(big)} used={used}"
        )
        if big:
            print(f"    top-big centroids: {[(c['x'], c['y'], c['diff_magnitude']) for c in big[:5]]}")
        return profile, used

    def traced_goal(action_profile, entity_map):
        counters["goal"] = counters.get("goal", 0) + 1
        goal = orig_goal(action_profile, entity_map)
        print(
            f"  [goal#{counters['goal']}] kind={goal['kind']} "
            f"conf={goal['confidence']:.2f} source={goal['source']} "
            f"players={'found' if entity_map.get('player') else 'none'} "
            f"merge_items={len(entity_map.get('merge_items', []))} "
            f"executors={len(entity_map.get('executors', []))} "
            f"palettes={len(entity_map.get('palettes', []))}"
        )
        return goal

    inf.observation_phase = traced_obs
    inf.goal_phase = traced_goal

    for name in list(inf.PLAN_FNS.keys()):
        orig_fn = inf.PLAN_FNS[name]

        def wrap(fn, kind):
            def _traced(env, profile, emap, goal, budget):
                plan_calls.append(kind)
                t0 = time.time()
                r = fn(env, profile, emap, goal, budget)
                print(
                    f"    [plan={kind}] levels={r[0]} used={r[1]} "
                    f"elapsed={time.time()-t0:.1f}s"
                )
                return r
            return _traced

        inf.PLAN_FNS[name] = wrap(orig_fn, name)

    t0 = time.time()
    best, label, used = inf.strat_inferential_agent(env, 50000)
    print(
        f"\nCD82 final: levels={best}  actions={used}  label={label}  "
        f"elapsed={time.time()-t0:.1f}s  plan_sequence={plan_calls}"
    )


if __name__ == "__main__":
    main()
