"""Drive one game with SluiceTool alone, and sweep its bid across every sample game.

Two modes, and they answer the two questions a tool owes the set:

    --rival <title> [cap]
                    play the game with this tool registered ALONGSIDE the whole default
                    registry, so the number is the one the harness would produce.
    <title> [cap]   play the game with this tool as the ONLY tool. Reports levels, the actions
                    each level cost, the human baseline beside it, and the RHAE score those two
                    make — because depth alone cannot be acted on: a level cleared at four times
                    the human count is worth a sixteenth of one cleared at parity.
    --full25 [par] [--baseline]
                    play ALL 25 sample games through the default registry, with this tool added
                    unless --baseline, and print each game's RHAE and the mean. ⛔ This is the
                    only measurement that can see a NET loss: a tool can be perfect on its own
                    board and take another game's turn away, which was paid for once already at
                    20x (lessons/tool_selectivity_20260827).
    --sweep [n]     run `detect` over a random-action rollout of n frames (default 1: the
                    starting frame) on every one of the 25 sample games, and report the highest
                    bid seen and what asking cost in seconds. A tool in a shared harness must bid
                    0.00 on every board it cannot solve — its mistake is not its own, it takes
                    the turn from the tool that could — and a board it never bids on at step 0
                    can still be a board it bids on at step 300.

⛔ This is a per-tool probe and it is NOT the number that counts. Use `scripts/harness_probe.py`
for that: the harness resets tools on a level-up, feeds `observe` only its own transitions, and
re-enters `propose` after every action, and a tool can be perfect here and score nothing there.
"""

from __future__ import annotations

import sys
import time

sys.path.insert(0, "src")


def _score(costs: list[int], human: list[int]) -> float:
    """RHAE: per level min(human/ours, 1) squared, weighted by the level's own 1-based index."""
    if not human:
        return 0.0
    total = sum(range(1, len(human) + 1))
    got = 0.0
    for i, base in enumerate(human):
        if i < len(costs) and costs[i] > 0:
            got += (i + 1) * min(base / costs[i], 1.0) ** 2
    return got / total


def _play(title: str, cap: int, rival: bool = False) -> None:
    from arc_agi import Arcade, OperationMode

    from admorphiq.harness.loop import UnifiedAgent
    from admorphiq.tools.sluice import SluiceTool

    def _no_llm(*_a, **_k):
        raise RuntimeError("LLM-free: the signature fallback is what this measures")

    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    info = next(i for i in arcade.get_environments()
                if (i.title or i.game_id).lower().startswith(title))
    human = list(getattr(info, "baseline_actions", None) or [])
    env = arcade.make(info.game_id)
    obs = env.reset()
    if rival:
        from admorphiq.harness.registry import default_tools
        tools = list(default_tools()) + [SluiceTool()]
    else:
        tools = [SluiceTool()]
    agent = UnifiedAgent(tools, _no_llm, giveup=cap, stall=80, ctx_budget=6000)
    picks: dict[str, int] = {}
    frames = [obs]
    costs: list[int] = []
    here = 0
    levels = 0
    start = time.time()
    step = 0
    for step in range(cap):
        if agent.is_done(frames, obs):
            break
        act = agent.choose_action(frames, obs)
        picks[str(agent._current)] = picks.get(str(agent._current), 0) + 1
        data = act.action_data.model_dump() if getattr(act, "action_data", None) else None
        obs = env.step(act, data=data) if data else env.step(act)
        frames.append(obs)
        here += 1
        now = int(getattr(obs, "levels_completed", levels) or 0)
        if now != levels:
            for _ in range(now - levels):
                costs.append(here)
                here = 0
            levels = now
    elapsed = time.time() - start
    print(f"{title}: {levels} levels in {step + 1} actions, {elapsed:.1f}s")
    if rival:
        print(f"   who acted: {dict(sorted(picks.items(), key=lambda kv: -kv[1])[:4])}")
    for i, base in enumerate(human):
        got = costs[i] if i < len(costs) else None
        mark = "-" if got is None else f"{got:>4}"
        rate = "" if got is None else f"  {base / got:5.2f}x human"
        print(f"   level {i + 1}: ours {mark}   human {base:>4}{rate}")
    print(f"   RHAE {_score(costs, human):.4f}")


def _sweep(frames: int) -> None:
    import random

    from arc_agi import Arcade, OperationMode
    from arcengine import GameAction

    from admorphiq.tools.sluice import SluiceTool

    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    rows = []
    for info in sorted(arcade.get_environments(), key=lambda i: (i.title or i.game_id)):
        title = (info.title or info.game_id).lower()
        env = arcade.make(info.game_id)
        obs = env.reset()
        tool = SluiceTool()
        rng = random.Random(7)
        top, cost, asked = 0.0, 0.0, 0
        for _ in range(frames):
            begin = time.time()
            try:
                top = max(top, tool.detect([obs], obs))
            except Exception as exc:  # noqa: BLE001
                print(f"{title:>12}  ERR {exc}")
                break
            cost += time.time() - begin
            asked += 1
            aid = rng.choice([1, 2, 3, 4, 5, 6])
            if aid == 6:
                spot = {"x": rng.randrange(64), "y": rng.randrange(64)}
                obs = env.step(GameAction.ACTION6, data=spot)
            else:
                obs = env.step(getattr(GameAction, f"ACTION{aid}"))
            if obs is None or obs.state.name in ("GAME_OVER", "WIN"):
                obs = env.reset()
        rows.append((title, top, asked, cost))
    for title, top, asked, cost in rows:
        flag = "  <== claims" if top > 0 else ""
        print(f"{title:>12}  top bid {top:.2f} over {asked:>4} frames, "
              f"{cost * 1000 / max(asked, 1):5.1f} ms/ask{flag}")
    claimed = [t for t, b, _, _ in rows if b > 0]
    print(f"\nclaims {len(claimed)} of {len(rows)}: {claimed}")


def _one_game(title: str, cap: int, rival: bool) -> tuple[str, int, float, float]:
    """One game in this process: (title, levels, RHAE, seconds). Used by --full25's pool."""
    from arc_agi import Arcade, OperationMode

    from admorphiq.harness.loop import UnifiedAgent
    from admorphiq.harness.registry import default_tools
    from admorphiq.tools.sluice import SluiceTool

    def _no_llm(*_a, **_k):
        raise RuntimeError("LLM-free: the signature fallback is what this measures")

    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    info = next(i for i in arcade.get_environments()
                if (i.title or i.game_id).lower().startswith(title))
    human = list(getattr(info, "baseline_actions", None) or [])
    env = arcade.make(info.game_id)
    obs = env.reset()
    tools = list(default_tools()) + ([SluiceTool()] if rival else [])
    agent = UnifiedAgent(tools, _no_llm, giveup=cap, stall=80, ctx_budget=6000)
    frames = [obs]
    costs: list[int] = []
    here = levels = 0
    start = time.time()
    for _ in range(cap):
        if agent.is_done(frames, obs):
            break
        act = agent.choose_action(frames, obs)
        data = act.action_data.model_dump() if getattr(act, "action_data", None) else None
        obs = env.step(act, data=data) if data else env.step(act)
        frames.append(obs)
        here += 1
        now = int(getattr(obs, "levels_completed", levels) or 0)
        if now != levels:
            for _ in range(now - levels):
                costs.append(here)
                here = 0
            levels = now
    return title, levels, _score(costs, human), time.time() - start


def _full25(par: int, rival: bool) -> None:
    import concurrent.futures as cf

    from arc_agi import Arcade, OperationMode

    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    titles = sorted({(i.title or i.game_id).lower() for i in arcade.get_environments()})
    out: dict[str, tuple[int, float, float]] = {}
    with cf.ProcessPoolExecutor(max_workers=par) as pool:
        futures = {pool.submit(_one_game, t, 1500, rival): t for t in titles}
        for fut in cf.as_completed(futures):
            title, levels, score, secs = fut.result()
            out[title] = (levels, score, secs)
            print(f"  {title:>6}  {levels:>2} levels  {score:.4f}  {secs:6.1f}s", flush=True)
    print(f"\n{'WITH sluice' if rival else 'BASELINE registry'}: "
          f"mean {sum(v[1] for v in out.values()) / len(out):.4f} over {len(out)} games")
    for title in sorted(out):
        print(f"{title} {out[title][1]:.4f}")


def main() -> None:
    args = sys.argv[1:]
    if args and args[0] == "--full25":
        base = "--baseline" in args
        rest = [a for a in args[1:] if a != "--baseline"]
        _full25(int(rest[0]) if rest else 5, rival=not base)
        return
    if args and args[0] == "--sweep":
        _sweep(int(args[1]) if len(args) > 1 else 1)
        return
    rival = bool(args) and args[0] == "--rival"
    if rival:
        args = args[1:]
    title = args[0] if args else "sp80"
    cap = int(args[1]) if len(args) > 1 else 1500
    _play(title, cap, rival=rival)


if __name__ == "__main__":
    main()
