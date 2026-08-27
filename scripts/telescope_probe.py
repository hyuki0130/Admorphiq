"""Diagnose the telescope tool on one game: what it reads, what it bids, what it clears.

⛔ This is a DIAGNOSTIC, not a measurement. The number that counts comes from
`scripts/harness_probe.py`, which drives the real loop — a tool's own probe cannot see that it
never got a turn, or that the harness took the board off it on a transitional frame.

    uv run python scripts/telescope_probe.py <title> [max-actions]
    uv run python scripts/telescope_probe.py --bids            # first-frame bid on all games
"""

from __future__ import annotations

import sys

sys.path.insert(0, "src")


def _arcade():
    from arc_agi import Arcade, OperationMode
    return Arcade(operation_mode=OperationMode.OFFLINE)


def bids() -> None:
    """What this tool bids on the FIRST frame of every sample game.

    ⛔ The selectivity gate: anything but zero away from its own mechanic is a bid that steals a
    turn from the tool that could solve that board, which is the most expensive mistake
    available here.
    """
    from admorphiq.tools.telescope import TelescopeArmTool
    arcade = _arcade()
    for info in sorted(arcade.get_environments(), key=lambda i: (i.title or i.game_id)):
        env = arcade.make(info.game_id)
        obs = env.reset()
        bid = TelescopeArmTool().detect([obs], obs)
        flag = "  <-- CLAIMS" if bid > 0 else ""
        print(f"{(info.title or info.game_id):>10}  {bid:.2f}{flag}")


def scan() -> None:
    """The frame test, on EVERY level of every sample game — statically, no engine, no actions.

    ⛔ A first-frame audit is not a selectivity audit. A tool that is silent on twenty-four
    opening boards can still wake up on level six of one of them and spend that game's budget.
    Each game ships its own sprites and level literals, so every board in the set can be drawn
    and asked without stepping the environment once.
    """
    import importlib.util
    import pathlib

    import numpy as np

    from admorphiq.tools.telescope import anchored_bars as T_anchored
    from admorphiq.tools.telescope import marker_colour, read_markers, read_widgets

    where = sys.argv[2] if len(sys.argv) > 2 else "environment_files"
    root = pathlib.Path(__file__).resolve().parent.parent / where
    claims = 0
    for game_dir in sorted(p for p in root.iterdir() if p.is_dir()):
        src = next(iter(sorted(game_dir.rglob("*.py"))), None)
        if src is None:
            continue
        spec = importlib.util.spec_from_file_location(f"_scan_{game_dir.name}", src)
        if spec is None or spec.loader is None:
            continue
        mod = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = mod
        try:
            spec.loader.exec_module(mod)
            levels = list(getattr(mod, "levels", []))
        except Exception as exc:  # noqa: BLE001
            print(f"{game_dir.name}: unreadable ({type(exc).__name__})")
            continue
        hits = []
        for n, level in enumerate(levels, 1):
            g = _draw(level, np)
            widgets = read_widgets(g)
            two = [wd for wd in widgets if wd.two_way]
            if not two or len(two) != len(widgets):
                continue
            boxes = [wd.box for wd in widgets]
            banned = {int(v) for wd in boxes
                      for v in g[wd[0]:wd[2] + 1, wd[1]:wd[3] + 1].ravel()}
            colour = marker_colour(g, banned)
            if colour is None:
                continue
            m = read_markers(g, colour)
            if m is None or all(q in set(m.movers) for q in m.places):
                continue
            if len(T_anchored(g, colour, boxes)) < len(m.places):
                continue
            hits.append(n)
            claims += 1
        print(f"{game_dir.name:>6}  {len(levels)} levels   claims {hits or 'none'}")
    print(f"total boards claimed: {claims}")


def _draw(level, np):
    """The board this level's own data describes, painted the way the engine paints it."""
    out = np.full((64, 64), 5, dtype=int)
    for sp in level.get_sprites():
        px = np.array(sp.pixels)
        for r in range(px.shape[0]):
            for c in range(px.shape[1]):
                v = int(px[r, c])
                y, x = int(sp.y) + r, int(sp.x) + c
                if v >= 0 and 0 <= y < 64 and 0 <= x < 64:
                    out[y, x] = v
    return out


def play(title: str, cap: int) -> None:
    from admorphiq.tools.telescope import TelescopeArmTool, _layers, read_widgets
    arcade = _arcade()
    info = next(i for i in arcade.get_environments()
                if (i.title or i.game_id).lower().startswith(title))
    env = arcade.make(info.game_id)
    obs = env.reset()
    tool = TelescopeArmTool()
    g = _layers(obs)[-1]
    wds = read_widgets(g)
    print(f"widgets: {len(wds)} ({sum(w.two_way for w in wds)} two-way)  bid={tool.detect([obs], obs):.2f}")
    levels = 0
    marks: list[tuple[int, int]] = []
    for step in range(cap):
        steps = tool.propose([obs], obs)
        if not steps:
            print(f"stopped at action {step}: dead={tool._dead} level={levels}")
            break
        act, xy = steps[0]
        obs = _apply(env, act, xy)
        now = int(getattr(obs, "levels_completed", levels) or 0)
        if now != levels:
            marks.append((now, step + 1))
            levels = now
        if str(getattr(obs, "state", "")).endswith("WIN"):
            break
    print(f"{title} TOOL-ONLY: {levels} levels, clears at {marks}")


def _apply(env, act: int, xy):
    """Same conversion the harness uses, so the probe and the loop drive the engine alike."""
    from admorphiq.adapter import AdmorphiqAdapter
    from admorphiq.types import ActionType, GameAction
    if xy is None:
        action = AdmorphiqAdapter._convert_action(GameAction.simple(ActionType(act)))
        return env.step(action)
    action = AdmorphiqAdapter._convert_action(
        GameAction.coordinate(int(xy[0]), int(xy[1])))
    data = action.action_data.model_dump() if getattr(action, "action_data", None) else None
    return env.step(action, data=data) if data else env.step(action)


def harness(title: str, cap: int) -> None:
    """The REAL loop, with this tool registered alongside the deployed set.

    ⛔ This, not `play`, is the number that counts. A tool's own driver cannot see the three
    ways the harness disagrees with it: the tool never gets a turn because it bid too low, the
    board is taken off it on the frame a level ends, or it holds every step and still clears
    less because the loop re-enters propose() after every single action.

    It builds the registered set and appends this tool rather than editing the registry, so the
    comparison is the deployed tree plus exactly one difference.
    """
    from admorphiq.harness.loop import UnifiedAgent
    from admorphiq.harness.registry import default_tools
    from admorphiq.tools.telescope import TelescopeArmTool

    def _no_llm(*_a, **_k):
        raise RuntimeError("LLM-free: the signature fallback is what this measures")

    arcade = _arcade()
    info = next(i for i in arcade.get_environments()
                if (i.title or i.game_id).lower().startswith(title))
    env = arcade.make(info.game_id)
    obs = env.reset()
    tools = default_tools()
    # Registered by the integrator, so it is already in the set; `--with` only adds it when it
    # is not, and `--without` measures the same tree with it taken out.
    if "--without" in sys.argv:
        tools = [t for t in tools if getattr(t, "name", "") != TelescopeArmTool.name]
    elif "--with" in sys.argv and not any(
            getattr(t, "name", "") == TelescopeArmTool.name for t in tools):
        tools = tools + [TelescopeArmTool()]
    agent = UnifiedAgent(tools, _no_llm, giveup=cap, stall=80, ctx_budget=6000)
    frames = [obs]
    picks: dict[str, int] = {}
    marks: list[tuple[int, int]] = []
    levels = 0
    step = 0
    for step in range(cap):
        if agent.is_done(frames, obs):
            break
        act = agent.choose_action(frames, obs)
        picks[str(agent._current)] = picks.get(str(agent._current), 0) + 1
        data = act.action_data.model_dump() if getattr(act, "action_data", None) else None
        obs = env.step(act, data=data) if data else env.step(act)
        frames.append(obs)
        now = int(getattr(obs, "levels_completed", levels) or 0)
        if now != levels:
            marks.append((now, step + 1))
            levels = now
    top = sorted(picks.items(), key=lambda kv: -kv[1])[:4]
    print(f"{title} HARNESS: {levels} levels in {step + 1} actions   clears at {marks}")
    print(f"   who acted: {dict(top)}")


if __name__ == "__main__":
    if sys.argv[1] == "--bids":
        bids()
    elif sys.argv[1] == "--scan":
        scan()
    elif sys.argv[1] == "--harness":
        harness(sys.argv[2], int(sys.argv[3]) if len(sys.argv) > 3 else 800)
    else:
        play(sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 400)
