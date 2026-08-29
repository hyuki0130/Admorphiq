"""How close does s5i5 get on level 7 — how many targets are covered, and does it improve?

s5i5's win is the game's own predicate: every sprite tagged `0087vvmblxkzdi` (a target) must have a
`0064ocqkuqacti` (a mover) at the same x,y. The harness clears 6 of 8 and stalls on level 7. Counting
targets and covered targets over the run says whether the tool gets close and stops, or never gets
near — a different repair in each case.

⛔ Rule 7g: this is the RUN side. The source said what the predicate is; this shows what happens.
⛔ Rule 7f: level numbers are reported with their direction.
"""
from __future__ import annotations


def main() -> None:
    from arc_agi import Arcade, OperationMode

    from admorphiq.harness.loop import UnifiedAgent
    from admorphiq.harness.registry import default_tools

    def _no_llm(*_a, **_k):
        raise RuntimeError("LLM-free")

    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    info = next(i for i in arcade.get_environments()
                if (i.title or i.game_id).lower().startswith("s5i5"))
    env = arcade.make(info.game_id)
    obs = env.reset()
    agent = UnifiedAgent(default_tools(), _no_llm, giveup=4000, stall=80, ctx_budget=6000)
    frames = [obs]

    game = getattr(env, "_game", None) or getattr(env, "game", None)

    def cover():
        if game is None:
            return None
        lvl = getattr(game, "current_level", None)
        if lvl is None:
            return None
        tgt = lvl.get_sprites_by_tag("0087vvmblxkzdi")
        mov = lvl.get_sprites_by_tag("0064ocqkuqacti")
        on = sum(1 for t in tgt if any(m.x == t.x and m.y == t.y for m in mov))
        return on, len(tgt)

    lvl = 0
    best = None
    n = 0
    for _ in range(4000):
        if agent.is_done(frames, obs):
            break
        act = agent.choose_action(frames, obs)
        data = act.action_data.model_dump() if getattr(act, "action_data", None) else None
        obs = env.step(act, data=data) if data else env.step(act)
        frames.append(obs)
        now = int(getattr(obs, "levels_completed", lvl) or 0)
        if now != lvl:
            print(f"  level {lvl + 1} -> {now + 1} after {n} actions", flush=True)
            lvl, n, best = now, 0, None
        n += 1
        if lvl == 6:
            c = cover()
            if c and (best is None or c[0] > best[0]):
                best = c
                print(f"    level 7: {c[0]}/{c[1]} targets covered at action {n}", flush=True)
    print(f"stopped on level {lvl + 1} after {n} actions; best coverage {best}", flush=True)


if __name__ == "__main__":
    main()
