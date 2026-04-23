"""Round 19 focused diagnostic: KA59 only, instrumented.

Probes what the inferential agent currently does on KA59 (2-player
sokoban). Delegation chain: navigation plan → strat_bfs_state_space.
Measures per-level progress and which plan kind is selected.
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
        if (info.title or "").upper() == "KA59":
            gid = info.game_id
            break
    if gid is None:
        print("KA59 not found")
        return
    env = arcade.make(gid)
    if env is None:
        print("KA59 make failed")
        return
    print(f"KA59 game_id={gid}")

    orig_obs = inf.observation_phase
    orig_goal = inf.goal_phase
    orig_nav = inf._plan_navigation
    call_counter = {"obs": 0, "goal": 0, "nav": 0}

    def traced_obs(env, stride=8, budget=200):
        call_counter["obs"] += 1
        profile, used = orig_obs(env, stride=stride, budget=budget)
        dir_counts = {
            a: len([t for t in profile["observed_transitions"] if t["action"] == a])
            for a in (1, 2, 3, 4)
        }
        print(
            f"  [obs#{call_counter['obs']}] base_levels={profile['base_levels']} "
            f"dir_transitions={dir_counts} obs_used={used}"
        )
        return profile, used

    def traced_goal(action_profile, entity_map):
        call_counter["goal"] += 1
        goal = orig_goal(action_profile, entity_map)
        players = entity_map.get("player")
        ngoals = len(entity_map.get("goal_regions", []))
        nmerge = len(entity_map.get("merge_items", []))
        print(
            f"  [goal#{call_counter['goal']}] kind={goal['kind']} "
            f"conf={goal['confidence']:.2f} source={goal['source']} "
            f"players={'found' if players else 'none'} "
            f"goal_regions={ngoals} merge_items={nmerge}"
        )
        return goal

    def traced_nav(env, action_profile, entity_map, goal, budget):
        call_counter["nav"] += 1
        print(f"  [nav#{call_counter['nav']}] budget={budget}")
        t0 = time.time()
        levels, used = orig_nav(env, action_profile, entity_map, goal, budget)
        print(
            f"    -> levels={levels} used={used} prefix_len={len(inf._ACTIVE_PREFIX)} "
            f"elapsed={time.time() - t0:.1f}s"
        )
        return levels, used

    inf.observation_phase = traced_obs
    inf.goal_phase = traced_goal
    inf._plan_navigation = traced_nav
    inf.PLAN_FNS["navigation"] = traced_nav

    t0 = time.time()
    best, label, used = inf.strat_inferential_agent(env, 50000)
    elapsed = round(time.time() - t0, 1)
    print(
        f"\nKA59 final: levels={best}  actions={used}  label={label}  elapsed={elapsed}s"
    )


if __name__ == "__main__":
    main()
