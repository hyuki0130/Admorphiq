"""Diagnose the swivel tool: what it bids, what it claims, and what the real loop clears.

⛔ A DIAGNOSTIC, not a measurement. The number that counts comes from the real loop — a tool's
own driver cannot see that it never got a turn, or that the board was taken off it on the frame
a level ended. `--harness` drives the registered set so the comparison is the deployed tree plus
exactly one difference.

    uv run python scripts/swivel_probe.py --harness <title> [cap] [--with|--without]
    uv run python scripts/swivel_probe.py --bids
    uv run python scripts/swivel_probe.py --scan [environment_files|environment_files_archive]

Both serializations are measured on every change; set ENVIRONMENTS_DIR for the archived one.
"""

from __future__ import annotations

import sys

sys.path.insert(0, "src")


def _arcade():
    from arc_agi import Arcade, OperationMode
    return Arcade(operation_mode=OperationMode.OFFLINE)


def bids() -> None:
    """What this tool bids on the FIRST frame of every sample game — the selectivity gate."""
    from admorphiq.tools.swivel import SwivelArmTool
    arcade = _arcade()
    for info in sorted(arcade.get_environments(), key=lambda i: (i.title or i.game_id)):
        env = arcade.make(info.game_id)
        obs = env.reset()
        bid = SwivelArmTool().detect([obs], obs)
        print(f"{(info.title or info.game_id):>10}  {bid:.2f}{'  <-- CLAIMS' if bid else ''}")


def scan() -> None:
    """The frame test on EVERY level of every sample game — statically, no engine, no actions."""
    import importlib.util
    import pathlib

    import numpy as np

    from admorphiq.tools.telescope import (
        _widget_colours,
        anchored_bars,
        marker_colour,
        read_markers,
        read_widgets,
    )

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
            if not any(not w.two_way for w in widgets) or not any(w.two_way for w in widgets):
                continue
            colour = marker_colour(g, _widget_colours(g, widgets))
            if colour is None:
                continue
            marks = read_markers(g, colour)
            if marks is None:
                continue
            if len(anchored_bars(g, colour, [w.box for w in widgets])) < len(marks.places):
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


def harness(title: str, cap: int) -> None:
    from admorphiq.harness.loop import UnifiedAgent
    from admorphiq.harness.registry import default_tools
    from admorphiq.tools.swivel import SwivelArmTool

    def _no_llm(*_a, **_k):
        raise RuntimeError("LLM-free: the signature fallback is what this measures")

    arcade = _arcade()
    info = next(i for i in arcade.get_environments()
                if (i.title or i.game_id).lower().startswith(title))
    env = arcade.make(info.game_id)
    obs = env.reset()
    tools = default_tools()
    if "--without" in sys.argv:
        tools = [t for t in tools if getattr(t, "name", "") != SwivelArmTool.name]
    elif not any(getattr(t, "name", "") == SwivelArmTool.name for t in tools):
        tools = tools + [SwivelArmTool()]
    agent = UnifiedAgent(tools, _no_llm, giveup=cap, stall=80, ctx_budget=6000)
    frames = [obs]
    picks: dict[str, int] = {}
    marks: list[tuple[int, int]] = []
    levels = step = 0
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
    else:
        harness(sys.argv[2], int(sys.argv[3]) if len(sys.argv) > 3 else 900)
