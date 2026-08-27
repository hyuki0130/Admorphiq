"""Drive a proximity-fog board with FogScoutTool and report per-level COST.

Two modes, because a tool for a LAST level cannot be measured from action zero:

  harness (default)  the real `UnifiedAgent` with `fogscout` registered locally,
                     from the first action of the game. This is the number that
                     counts — the tool has to WIN the pick, survive the level-up
                     contract and share the board. See scripts/harness_probe.py.
  solo               the real harness drives until the fogged level begins, then
                     FogScoutTool takes every remaining action. Diagnostic only:
                     it says whether the SOLVER works, never whether the tool
                     helps, and the two have disagreed three times on this file's
                     own game ([[lessons/tool_selectivity_20260827]]).

Usage:
    uv run python scripts/fogscout_probe.py <game> [budget] [--solo] [--trace]
    uv run python scripts/fogscout_probe.py <game> [budget] --sweep [--dump=DIR]

The game named is the tool's OWN board: in --sweep every other board must read
0.00, and that is the line the sweep prints last.
"""

from __future__ import annotations

import sys
from collections import Counter

sys.path.insert(0, "src")


def _window() -> dict:
    """Honour `HARNESS_NOPROGRESS` the way score_efficiency.py does.

    ⛔ Without this the probe silently pinned the run to the built-in default,
    so asking for the longer diagnostic window changed nothing and the two
    measurements came back identical — which reads as "the window is not the
    constraint" and is an artefact of the instrument, not a finding.
    """
    import os
    val = os.environ.get("HARNESS_NOPROGRESS")
    return {"no_progress": int(val)} if val else {}


def _no_llm(*_a, **_k):
    raise RuntimeError("LLM-free: the signature fallback is what this measures")


def _env(title: str):
    from arc_agi import Arcade, OperationMode
    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    info = next(i for i in arcade.get_environments()
                if (i.title or i.game_id).lower().startswith(title))
    return arcade.make(info.game_id), info


def _report(title: str, marks: list[tuple[int, int]], total: int, info) -> None:
    base = list(getattr(info, "baseline_actions", None) or [])
    cost = [marks[0][1]] + [marks[i][1] - marks[i - 1][1] for i in range(1, len(marks))]
    rows, wsum, wtot = [], 0.0, 0.0
    # ⛔ The game's level count is the BASELINE's length, never the number of
    # level-up events seen. A won game reports one more completion than it has
    # levels, and taking the max put an eighth weight in the denominator of a
    # seven-level game — which read as a SCORE DROP on the run that first
    # cleared the last level.
    nlev = len(base)
    for i in range(nlev):
        w = i + 1
        wtot += w
        if i < len(cost) and i < len(base):
            s = min(base[i] / cost[i], 1.0) ** 2
            wsum += w * s
            rows.append(f"  L{i+1}: {cost[i]:>4} actions vs human {base[i]:>4}  score {s:.4f}")
        elif i < len(base):
            rows.append(f"  L{i+1}: not reached      human {base[i]:>4}  score 0.0000")
    print(f"{title}: {len(marks)} levels in {total} actions")
    print("\n".join(rows))
    print(f"  GAME SCORE {wsum / wtot:.4f}" if wtot else "  no baseline")


def run_harness(title: str, cap: int, trace: bool, first: bool = False) -> None:
    from admorphiq.harness.loop import UnifiedAgent
    from admorphiq.harness.registry import default_tools
    from admorphiq.tools.fogscout import FogScoutTool

    env, info = _env(title)
    obs = env.reset()
    # ⛔ Registration ORDER decides ties, and this tool ties the general searcher
    # at 0.80 on its own board, so where it sits in the list decides whether it
    # is ever asked. Default is LAST — the honest position for a new tool, and
    # the one that shows it cannot displace anything. `--first` measures the
    # other order, which is the integrator's call to make, not this file's.
    mine = FogScoutTool()
    tools = [mine, *default_tools()] if first else [*default_tools(), mine]
    agent = UnifiedAgent(tools, _no_llm, giveup=cap, stall=80, ctx_budget=6000, **_window())
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
    _report(title + " HARNESS", marks, step + 1, info)
    print(f"  who acted: {dict(sorted(picks.items(), key=lambda kv: -kv[1]))}")
    if mine.census:
        print("  census while it held the board: "
              + ", ".join(f"{k} {v}" for k, v in mine.census.most_common(8)))
        print(f"  belief at hand-back: mapped {len(mine.seen)}, marks {len(mine.kind)}, "
              f"goal {mine.goal}, target known {mine.target is not None}")


def run_solo(title: str, cap: int, trace: bool, after: int = 0) -> None:
    import numpy as np

    from admorphiq.harness.loop import UnifiedAgent
    from admorphiq.harness.registry import default_tools
    from admorphiq.tools.fogscout import FogScoutTool, fog_view
    from admorphiq.types import ActionType, GameAction

    env, info = _env(title)
    obs = env.reset()
    agent = UnifiedAgent(default_tools(), _no_llm, giveup=cap, stall=80, ctx_budget=6000, **_window())
    frames = [obs]
    marks: list[tuple[int, int]] = []
    levels = 0
    n = 0
    while n < cap:
        g = np.asarray(obs.frame[0], dtype=np.int16)
        if fog_view(g) is not None:
            break
        act = agent.choose_action(frames, obs)
        data = act.action_data.model_dump() if getattr(act, "action_data", None) else None
        obs = env.step(act, data=data) if data else env.step(act)
        frames.append(obs)
        n += 1
        now = int(getattr(obs, "levels_completed", levels) or 0)
        if now != levels:
            marks.append((now, n))
            levels = now
    # ⛔ `--after=N` hands over N actions INTO the claimed level instead of at
    # its first frame. That is not a detail: inside the harness the incumbent
    # keeps the board across a level-up and only gives it up on a stall, so the
    # earliest this tool can be asked is ~150 actions in — with the level's
    # drawn budget and its lives already spent by someone else. Handing over at
    # action 0 measures the SOLVER; handing over at 150 measures what the tool
    # is actually given, and the two answers differ.
    for _ in range(after):
        if n >= cap or agent.is_done(frames, obs):
            break
        act = agent.choose_action(frames, obs)
        data = act.action_data.model_dump() if getattr(act, "action_data", None) else None
        obs = env.step(act, data=data) if data else env.step(act)
        frames.append(obs)
        n += 1
        now = int(getattr(obs, "levels_completed", levels) or 0)
        if now != levels:
            marks.append((now, n))
            levels = now
    print(f"  [solo] handover at action {n}, level {levels}", file=sys.stderr)

    tool = FogScoutTool()
    prev = None
    prev_step = None
    while n < cap:
        cur = np.asarray(obs.frame[0], dtype=np.int16) if obs.frame else None
        if prev is not None and prev_step is not None and cur is not None:
            tool.observe(prev, prev_step, bool((prev != cur).any()))
        steps = tool.propose(frames, obs)
        if not steps:
            break
        aid, _xy = steps[0]
        prev, prev_step = cur, steps[0]
        obs = env.step(agent._convert(GameAction.simple(ActionType(aid))))
        frames.append(obs)
        n += 1
        if trace and n % 1 == 0:
            print(f"    n={n} a={aid} pos={tool.pos} why={tool.reason} "
                  f"tok={None if not tool.tok else tool.tok[1]} goal={tool.goal} "
                  f"tgt={None if not tool.target else tool.target[1]} "
                  f"kinds={[len(v) for v in tool.kind.values()]} mapped={len(tool.seen)} "
                  f"bar={tool.bar_len}/{tool.bar_full}", file=sys.stderr)
        now = int(getattr(obs, "levels_completed", levels) or 0)
        if now != levels:
            marks.append((now, n))
            levels = now
        if str(getattr(obs, "state", "")).endswith("GAME_OVER"):
            obs = env.step(agent._convert(GameAction.reset()))
            frames.append(obs)
            n += 1
            prev = prev_step = None
    _report(title + " SOLO", marks, n, info)


def run_bids(title: str, cap: int) -> None:
    """Max fogscout bid PER LEVEL while the real harness plays the whole game.

    ⛔ This exists because the harness's `step=` counter is PER LEVEL — it is
    zeroed in `_reset_level`, which runs on every level-up — so a pick logged at
    `step=146` is 146 actions into whichever level is current, not action 146 of
    the game. Reading it as cumulative puts the pick at level 3 or 4 of a game
    whose first six levels cost 414 actions. This mode answers the question the
    counter cannot: on which levels does the tool actually bid?
    """
    import numpy as np

    from admorphiq.harness.loop import UnifiedAgent
    from admorphiq.harness.registry import default_tools
    from admorphiq.tools.fogscout import FogScoutTool

    env, info = _env(title)
    obs = env.reset()
    agent = UnifiedAgent(default_tools(), _no_llm, giveup=cap, stall=80, ctx_budget=6000, **_window())
    probe = FogScoutTool()
    frames = [obs]
    per_level: dict[int, float] = {}
    seen_at: dict[int, int] = {}
    levels = 0
    for n in range(cap):
        if not getattr(obs, "frame", None):
            break
        try:
            fit = float(probe.detect([np.asarray(f) for f in frames[-4:]], obs))
        except Exception:  # noqa: BLE001
            fit = 0.0
        per_level[levels] = max(per_level.get(levels, 0.0), fit)
        seen_at.setdefault(levels, n)
        if agent.is_done(frames, obs):
            break
        act = agent.choose_action(frames, obs)
        data = act.action_data.model_dump() if getattr(act, "action_data", None) else None
        obs = env.step(act, data=data) if data else env.step(act)
        frames.append(obs)
        levels = int(getattr(obs, "levels_completed", levels) or 0)
    print(f"{title}: max fogscout bid per level (cumulative action where the level began)")
    for lv in sorted(per_level):
        print(f"  level {lv + 1}: bid {per_level[lv]:.3f}   began at cumulative action {seen_at[lv]}")


def run_census(title: str, cap: int, after: int = 0) -> None:
    """One attempt at the claimed level, then the CENSUS.

    ⛔ Prints counts, not a narrative. The harness retires a tool that reaches no
    new state for N actions; when that happens the question "why did the planner
    stop producing useful actions" has exactly as many answers as the planner has
    branches, and the only cheap way to find the live one is to count them. Also
    prints whether the tool's BELIEF grew during the run, because a stall while
    the belief grows and a stall while it does not are different defects.
    """
    import numpy as np

    from admorphiq.harness.loop import UnifiedAgent
    from admorphiq.harness.registry import default_tools
    from admorphiq.tools.fogscout import FogScoutTool, fog_view
    from admorphiq.types import ActionType, GameAction

    env, info = _env(title)
    obs = env.reset()
    agent = UnifiedAgent(default_tools(), _no_llm, giveup=cap, stall=80, ctx_budget=6000, **_window())
    frames = [obs]
    n = 0
    while n < cap:
        g = np.asarray(obs.frame[0], dtype=np.int16)
        if fog_view(g) is not None:
            break
        act = agent.choose_action(frames, obs)
        data = act.action_data.model_dump() if getattr(act, "action_data", None) else None
        obs = env.step(act, data=data) if data else env.step(act)
        frames.append(obs)
        n += 1
    for _ in range(after):
        if n >= cap or agent.is_done(frames, obs):
            break
        act = agent.choose_action(frames, obs)
        data = act.action_data.model_dump() if getattr(act, "action_data", None) else None
        obs = env.step(act, data=data) if data else env.step(act)
        frames.append(obs)
        n += 1
    print(f"  handover at action {n}", file=sys.stderr)

    tool = FogScoutTool()
    prev = prev_step = None
    belief: list[tuple[int, str]] = []
    stalls = Counter()
    last_key = None
    run = 0
    start = n
    while n < cap:
        cur = np.asarray(obs.frame[0], dtype=np.int16) if obs.frame else None
        if prev is not None and prev_step is not None and cur is not None:
            tool.observe(prev, prev_step, bool((prev != cur).any()))
        steps = tool.propose(frames, obs)
        if not steps:
            break
        key = tool.state_key(cur) if cur is not None else ""
        run = run + 1 if key == last_key else 0
        stalls[min(run, 40)] += 1
        last_key = key
        belief.append((len(tool.seen), tool.reason.split("[")[0]))
        aid, _xy = steps[0]
        prev, prev_step = cur, steps[0]
        obs = env.step(agent._convert(GameAction.simple(ActionType(aid))))
        frames.append(obs)
        n += 1
        if str(getattr(obs, "state", "")).endswith("GAME_OVER"):
            obs = env.step(agent._convert(GameAction.reset()))
            frames.append(obs)
            n += 1
            prev = prev_step = None
    total = n - start
    print(f"\nCENSUS over {total} actions on the claimed level")
    for why, cnt in tool.census.most_common():
        print(f"  {why:22s} {cnt:5d}  {100.0 * cnt / max(1, total):5.1f}%")
    print(f"\nbelief: mapped cells {belief[0][0] if belief else 0} -> {len(tool.seen)}, "
          f"marks understood {len(tool.kind)}, transitions "
          f"{sum(len(v) for v in tool.kind.values())}")
    # ⛔ Is the target token REACHABLE in the learned tables at all? "The plan
    # never fires" has two completely different causes — the tool does not know
    # enough changer transitions to construct the demanded token, or it knows
    # them and cannot route to the cell. One closure answers which.
    # ⛔ Close over what the PLANNER sees, not over the raw tables. The tool
    # generalises each mark to a rule on one attribute, so a closure taken from
    # the stored pairs understates it — measured 27 where the planner had more,
    # which would have sent the next fix at the wrong half of the problem.
    reach = {tool.tok} if tool.tok else set()
    frontier = list(reach)
    while frontier:
        t = frontier.pop()
        for sig, table in tool.kind.items():
            nt = tool._factored(sig, t) or table.get(t)
            if nt is not None and nt not in reach:
                reach.add(nt)
                frontier.append(nt)
    if tool.target is None:
        print("\ntarget token: NEVER IDENTIFIED")
    else:
        hit = tool.target in reach
        print(f"\ntarget token reachable through the learned tables: {hit}"
              f"   (closure of {len(reach)} tokens from the one held)")
        if not hit:
            miss = {c for _, c in reach}
            print(f"   colours reachable {sorted(miss)}; target colour {tool.target[1]}")
            print(f"   masks reachable {len({m for m, _ in reach})}; "
                  f"target mask size {len(tool.target[0])}")
    rules = tool._rules()
    print("marks as rules:")
    for i, (sig, table) in enumerate(tool.kind.items()):
        got = rules.get(sig)
        axis = "MIXED (no rule derived)" if got is None else f"{got[0]} permutation over {len(got[1])}"
        print(f"   mark {i}: {len(table):3d} observed pairs -> {axis}")
    phase = None
    if tool.anchor and tool.pitch:
        phase = (tool.anchor[0] % tool.pitch, tool.anchor[1] % tool.pitch)
    icon_sigs = {tool.mark.get(c) for c in tool.icon_seen} - {None}
    dead = [c for c, k in tool.icon_seen.items()
            if any(s in tool.inert for s in {tool.mark.get(c)} - {None})]
    print(f"icon cells ever seen {len(tool.icon_seen)}; of their marks, "
          f"{len([s for s in icon_sigs if s in tool.inert])} written off as INERT")
    print(f"   icon cells whose mark is now inert: {dead}")
    print(f"   icon cells: {sorted(tool.icon_seen)}")
    print(f"   of those, currently in the live mark map: "
          f"{sorted(c for c in tool.icon_seen if c in tool.mark)}")
    print(f"   of those, ever stood on: {sorted(c for c in tool.icon_seen if c in tool.stood)}")
    print(f"struck off (never reconsidered): {sorted(tool.give_up)}")
    print(f"self-loop edges recorded: {sum(1 for k, v in tool.edges.items() if v == k[0])}")
    print(f"what the walks aimed at: {dict(tool.aimed)}")
    print(f"walks: ARRIVED {tool.arrived}, ABANDONED before arriving {tool.abandoned}")
    print(f"lattice: pitch {tool.pitch}, anchor {tool.anchor}, phase {phase}, "
          f"avatar template {None if tool.tpl is None else tool.tpl.shape}")
    print(f"wall colours learned {sorted(tool.wall_colors)}, floor {sorted(tool.floor_colors)}, "
          f"walls {len(tool.walls)}, icons ever seen {len(tool.icon_seen)}")
    print(f"goal cell known: {tool.goal}, avatar at {tool.pos}")
    # ⛔ "The token is reachable" and "the win is reachable" are different
    # claims. Separate them: can the avatar even stand next to the target cell,
    # and does the joint search return a route when asked directly?
    reach_cells = tool._reach((64, 64))
    if tool.goal is not None:
        nb = [(tool.goal[0] + d[0], tool.goal[1] + d[1])
              for d in ((1, 0), (-1, 0), (0, 1), (0, -1))]
        print(f"   neighbours of the target cell that are reachable: "
              f"{[c for c in nb if c in reach_cells]} of {nb}")
    win = tool._search((64, 64), lambda c, t: c == tool.goal and t == tool.target, False)
    print(f"   joint (cell, token) search for the win returns: {win}")
    longest = max((r for r in stalls), default=0)
    print(f"longest run with NO change to the tool's own state key: {longest} actions")
    print(f"deaths seen: {tool.census.get('lost', 0)} lost-avatar frames")
    _kind_report(tool)


def _kind_report(tool) -> None:
    """What the model believes every element kind it has SEEN actually is.

    ⛔ The point is to be refutable. A tool can be silently blind to a kind of
    furniture, and no amount of planning refinement reaches a mechanic that is
    not modelled — so the honest check is not "does the plan look right" but
    "name every distinct thing on this board and say what you think it does".
    Anything landing in UNLEARNED after a full attempt is a gap.
    """
    rules = tool._rules()
    by_sig: dict = {}
    for cell, sig in tool.mark.items():
        by_sig.setdefault(sig, []).append(cell)
    for sig in tool.sighted:
        by_sig.setdefault(sig, [])
    print("\nELEMENT KINDS THE MODEL HAS SEEN, and what it believes each one is")
    for sig, cells in sorted(by_sig.items(), key=lambda kv: -len(kv[1])):
        ys = [p[0] for p in sig] or [0]
        xs = [p[1] for p in sig] or [0]
        cols = sorted({p[2] for p in sig})
        shape = f"{max(ys) - min(ys) + 1}x{max(xs) - min(xs) + 1}"
        span = len(tool.lane.get(sig, ()))
        if sig in tool.refill_marks:
            belief = "REFILL — entering it refills the drawn budget"
        elif sig in rules:
            axis, table = rules[sig]
            belief = (f"CHANGER — {axis} rule over {len(table)} values"
                      + (", and it PATROLS" if span > 1 else ", static"))
        elif sig in tool.inert:
            belief = "INERT — stood on it, the token did not change"
        else:
            belief = "UNLEARNED — never stood on one"
        goal = " <-- the TARGET" if tool.goal in cells else ""
        print(f"  {shape:>5} colours {cols!s:<12} on {len(cells)} cell(s), "
              f"seen across {max(span, 1)} position(s): {belief}{goal}")
    print(f"  (walls are not marks: {len(tool.walls)} cells refused entry; "
          f"wall colours {sorted(tool.wall_colors)}, floor {sorted(tool.floor_colors)})")


def run_sweep(cap: int, own: str, dump: str | None = None) -> None:
    """⛔ SELECTIVITY, over all 25 boards. A tool in a shared harness is judged
    on where it does NOT bid: a loosened detector took one game from 0.4762 to
    0.0476 while staying perfect on its own board
    ([[lessons/tool_selectivity_20260827]]). Every line but the claimed one has
    to read 0.00."""
    import numpy as np
    from arc_agi import Arcade, OperationMode

    from admorphiq.harness.loop import UnifiedAgent
    from admorphiq.harness.registry import default_tools
    from admorphiq.tools.fogscout import FogScoutTool

    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    worst = 0.0
    for info in sorted(arcade.get_environments(), key=lambda i: (i.title or i.game_id)):
        title = (info.title or info.game_id).lower()
        env = arcade.make(info.game_id)
        obs = env.reset()
        agent = UnifiedAgent(default_tools(), _no_llm, giveup=cap, stall=80, ctx_budget=6000, **_window())
        probe = FogScoutTool()
        frames = [obs]
        best = 0.0
        frames_seen = 0
        for _ in range(cap):
            if not getattr(obs, "frame", None):
                break
            frames_seen += 1
            try:
                fit = float(probe.detect([np.asarray(f) for f in frames[-4:]], obs))
            except Exception as exc:  # noqa: BLE001
                print(f"  {title}: detect raised {exc}")
                break
            if dump is not None:
                g = np.asarray(obs.frame[0], dtype=np.int16)
                if fit > 0 or frames_seen % 7 == 0:
                    np.save(f"{dump}/{title}_{frames_seen:05d}_{'hit' if fit > 0 else 'neg'}.npy", g)
            best = max(best, fit)
            if agent.is_done(frames, obs):
                break
            act = agent.choose_action(frames, obs)
            data = act.action_data.model_dump() if getattr(act, "action_data", None) else None
            obs = env.step(act, data=data) if data else env.step(act)
            frames.append(obs)
        flag = "  <-- CLAIMS" if best > 0 else ""
        print(f"{title:8s} max fit {best:.2f} over {frames_seen} frames{flag}", flush=True)
        if not title.startswith(own):
            worst = max(worst, best)
    print(f"\nworst false-positive fit on the other boards: {worst:.2f}")


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    flags = {a for a in sys.argv[1:] if a.startswith("--")}
    if not args:
        raise SystemExit(__doc__)
    title = args[0]
    cap = int(args[1]) if len(args) > 1 else 1600
    if "--bids" in flags:
        run_bids(title, cap)
    elif "--census" in flags:
        after = next((int(a.split("=", 1)[1]) for a in flags if a.startswith("--after=")), 0)
        run_census(title, cap, after)
    elif "--sweep" in flags:
        dump = next((a.split("=", 1)[1] for a in flags if a.startswith("--dump=")), None)
        if dump:
            import os
            os.makedirs(dump, exist_ok=True)
        run_sweep(cap, title, dump)
    elif "--solo" in flags:
        after = next((int(a.split("=", 1)[1]) for a in flags if a.startswith("--after=")), 0)
        run_solo(title, cap, "--trace" in flags, after)
    else:
        run_harness(title, cap, "--trace" in flags, "--first" in flags)


if __name__ == "__main__":
    main()
