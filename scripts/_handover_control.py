"""Is the level-transition tax a TAX, or the tool's ordinary inert rate wearing a window?

⛔ THIS IS THE CONTROL HALF, and it exists because a peer's `scripts/_handover_tax.py` —
measuring the same thing, well, and in flight as this was written — has no baseline to
compare its window against. "Of the first six actions after a rise, N changed nothing" is
a restatement of "the tool was searching" until you know what N is AWAY from a rise. Two
findings this round were exactly that shape, and the brief that commissioned this warns
about it by name.

⚠️ It also fixes an attribution the peer probe cannot make. Its `filled` counter is
`tool is None`, and `_current` only goes None after `_EMPTY_TOLERANCE` consecutive empty
proposes — so the COMMON case, a NAMED tool proposing nothing and the harness filling the
turn under its name, is invisible to it. That case is 83 of lf52's level-6 actions and all
8 of ls20's. This tags at the source, inside `UnifiedAgent._probe`.

⛔ READ RULE 7o FIRST. The obvious fix here has already been tried and gated: `frame_2d` reading
the LAST layer instead of the first took the full 25 from 0.8962 to 0.6525, fourteen games
regressed, and the measurement behind it was TRUE the whole time (layer 0 is stale at 100% of
level transitions in all 21 games measured). A measurement of a MECHANISM does not license a
change of BEHAVIOUR. So this file MEASURES and proposes nothing.

Two independent sightings started this. On ls20 the incumbent tool keeps the board across a
level-up and spends 9 actions on the new level before handing over. On re86 a peer found the
transition frame carrying the old board in layer 0, the tool proposing nothing, and the harness
filling the turn with the lowest-numbered key — 2 actions per level, push plus undo. Both are
"the first actions of a new level are wasted", and neither has ever been priced across the set.

WHAT IS RECORDED, per action, faithfully to the scored configuration (`choose_action([], obs)`,
giveup 8000, stall 80, ctx 6000, LLM raising so the signature fallback runs — that is what
`--agent unified` does on a box with no models pulled):

  changed   `tools.segment.board_changed(prev, cur)` — NOT `(prev != cur).any()`. Rule 7c: an
            edge-pinned counter makes the naive test true for every action including refusals,
            and a guard built on it was inert while looking like a measured negative.
  fill      the harness had NO plan and filled the turn itself (`UnifiedAgent._probe`). Tagged
            at the source, because the loop tags nothing and attributing waste to a tool that
            did not issue it has already cost this project a session.
  tool      `agent._current` at the moment the action was issued.

WHAT IS COMPUTED:

  tax[i]      actions from the first action of level i+1 up to the first BOARD-CHANGING action
  tax_fill[i] how many of those the harness issued because no tool had a plan
  swap[i]     did the active tool change between the transition and the first change
  ⭐ CONTROL: the same statistic away from a transition — the mean and the distribution of
            maximal inert runs MID-LEVEL. Without it "N actions before the board moved" is a
            restatement of "the tool was searching", not a transition tax. A tax exists only
            where the level-start prefix is LONGER than the ordinary inert run on that game.

  layers    the layer count of every observation, and whether the transition observation's
            layer 0 differs from the board handed back next. Recorded because it is the
            mechanism under suspicion — NOT because a layer choice is being proposed.

Expected feedback: per game, `tax` against `ctrl_mean`. A game whose level-starts cost no more
than its ordinary inert runs has NO handover tax however many actions it spends. Summed over the
games that clear many levels, the excess is what any fix could be worth — and it is an upper
bound, since some of those actions are a tool legitimately re-probing a board it has never seen.
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

WINDOW = 6  # actions after a rise attributed to the handover — the peer probe's window, kept
            # identical so the two measurements are directly comparable

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

GAMES = ("ar25 bp35 cd82 cn04 dc22 ft09 g50t ka59 lf52 lp85 ls20 m0r0 r11l re86 s5i5 "
         "sb26 sc25 sk48 sp80 su15 tn36 tr87 tu93 vc33 wa30").split()


def main() -> None:
    import numpy as np
    from arc_agi import Arcade, OperationMode
    from arcengine import GameAction

    from admorphiq.harness.loop import UnifiedAgent, frame_2d, has_frame, levels_completed
    from admorphiq.harness.registry import default_tools
    from admorphiq.tools.segment import board_changed

    # Accept a title or a 1-based index, so the same probe drops into a per-game fan or a
    # numbered one without a wrapper deciding which.
    a1 = sys.argv[1] if len(sys.argv) > 1 else "1"
    cap = int(sys.argv[2]) if len(sys.argv) > 2 else 4000
    title = GAMES[(int(a1) - 1) % len(GAMES)] if a1.isdigit() else a1.strip().lower()

    def _no_llm(*_a, **_k):
        raise RuntimeError("LLM-free: the signature fallback is what the scorer measures here")

    agent = UnifiedAgent(default_tools(), _no_llm, giveup=8000, stall=80, ctx_budget=6000)
    # ⛔ A BOOLEAN READ IMMEDIATELY AFTER THE CALL, not an index match. The first version tagged
    # `agent._steps` and compared it to the loop counter; they DRIFT, because the harness's
    # GAME_OVER / no-frame branch returns a RESET without incrementing `_steps`. Measured: 8 fills
    # tagged, 0 matched, and `fills_total` read a clean ZERO on a game that had fills — a
    # finding-shaped null of exactly the kind rule 7b warns about, caught only because
    # `fills_named` disagreed with it.
    fill_flag = {"hit": False, "named": 0, "none": 0}
    orig_probe = agent._probe

    def _tagged_probe(simple_ids, action6):
        # `_steps` is incremented AFTER the queue pop, so it is the index of the action this
        # fill is about to produce. A fill always yields exactly one step and the queue is
        # empty when `_fill_from_current` runs, so the tag cannot slide onto a planned action.
        fill_flag["hit"] = True
        # ⛔ `_current` is already updated when `_probe` runs: `_fill_from_current` clears it only
        # after `_EMPTY_TOLERANCE` = 8 CONSECUTIVE empty proposes, and the fill happens on every
        # one of them. So a proxy that counts "the harness filled it" as `_current is None` sees at
        # most one fill in eight — the common case is a NAMED tool proposing nothing and the
        # harness filling under its name. This records both so the undercount can be priced.
        if agent._current is not None:
            fill_flag["named"] += 1
        else:
            fill_flag["none"] += 1
        return orig_probe(simple_ids, action6)

    agent._probe = _tagged_probe  # type: ignore[method-assign]

    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    info = next(i for i in arcade.get_environments()
                if (i.title or i.game_id).lower().startswith(title))
    env = arcade.make(info.game_id)
    obs = env.observation_space
    human = list(getattr(info, "baseline_actions", []) or [])

    lvl = levels_completed(obs)
    prev_board = frame_2d(obs).astype(np.int16) if has_frame(obs) else None
    # per action: (level, changed, fill, tool)
    stream: list[tuple[int, int, int, str]] = []
    layers: Counter[int] = Counter()
    trans_layers: list[int] = []
    trans_stale0: list[int] = []
    level_start_step: list[int] = [0]
    print(f"{title} start", flush=True)

    stop = "budget"
    deaths = 0
    for _step_i in range(cap):
        if agent.is_done([], obs):
            stop = "is_done"
            break
        fill_flag["hit"] = False
        act = agent.choose_action([], obs)
        tool = str(agent._current)
        data = act.action_data.model_dump() if getattr(act, "action_data", None) else None
        obs = env.step(act, data=data) if data else env.step(act)
        if obs is None:
            stop = "obs_none"
            break
        nl = len(getattr(obs, "frame", []) or [])
        layers[nl] += 1
        board = frame_2d(obs).astype(np.int16) if has_frame(obs) else None
        ch = 0
        if prev_board is not None and board is not None and prev_board.shape == board.shape:
            ch = int(board_changed(prev_board, board))
        stream.append((lvl, ch, int(fill_flag["hit"]), tool))
        now = levels_completed(obs)
        # ⛔ `> lvl`, never `!=` — a collapse and a clear are the same boolean (rule 7f).
        if now > lvl:
            trans_layers.append(nl)
            # Is layer 0 of the TRANSITION observation the board that comes next? Measurement
            # only — rule 7o: this establishes the mechanism, not that changing it is right.
            raw = getattr(obs, "frame", None)
            if raw is not None and nl >= 2:
                a0 = np.asarray(raw[0], dtype=np.int16)
                a1 = np.asarray(raw[-1], dtype=np.int16)
                trans_stale0.append(int(a0.shape == a1.shape and bool((a0 != a1).any())))
            lvl = now
            level_start_step.append(len(stream))
        prev_board = board
        st = str(getattr(obs, "state", ""))
        # ⛔ THE SCORER DOES NOT STOP ON GAME_OVER — `UnifiedAgent.restart_on_game_over` is True
        # (loop.py:138), so `score_efficiency.py` revives the env and KEEPS COUNTING. The first
        # version of this probe broke here instead, and it truncated ls20 at 6 levels / 481 actions
        # where the gated run clears 7 in 651: the level-7 fuel game loses three lives and restarts,
        # and everything after the first restart was simply missing. Caught by running a probe with
        # a KNOWN-GOOD output (`_ls20_verify.py`, 231 on level 7) out of the same snapshot and
        # finding they disagreed — the disagreement was mine.
        if st.endswith("GAME_OVER"):
            deaths += 1
            # ⛔ `GameAction.RESET`, the ENUM MEMBER, exactly as score_efficiency.py does.
            # `arcengine.GameAction` is an Enum; `.reset()` is `admorphiq.types.GameAction`'s API
            # and raises AttributeError here. It fires ONLY on a death, so lf52 and dc22 (no
            # deaths) ran clean while ls20 and bp35 died silently — the runner was discarding
            # stderr, so both looked like games that ended early rather than a probe that crashed.
            obs = env.step(GameAction.RESET)
            if obs is None:
                stop = "obs_none_after_reset"
                break
            # The revive costs an action in the scorer's count, so it costs one here too.
            stream.append((lvl, 0, 0, "RESET"))
            prev_board = frame_2d(obs).astype(np.int16) if has_frame(obs) else None
            continue
        if st.endswith("WIN"):
            stop = "win"
            break
        if len(stream) % 500 == 0:
            print(f"{title} n={len(stream)} lvl={lvl}", flush=True)

    # -- the tax as an OFFSET PROFILE, against a control that excludes the windows ------------
    #
    # ⛔ The first version defined the tax as "actions after a rise until the board next changes".
    # It is worthless on a game where the board changes on nearly every action: re86 measured ZERO
    # inert actions in 696, so the prefix is 0 by construction and the instrument reports "no tax"
    # on a game that is one of the two the tax was SIGHTED on. A metric that cannot fire is not a
    # negative.
    #
    # What replaces it compares like with like. For each offset 0..WINDOW-1 after a rise, the rate
    # of inert actions and of harness fills; and the SAME two rates over every action that is NOT
    # in a post-rise window. A tax exists only where the window rate exceeds the control rate, and
    # `excess_*` prices it in actions per game rather than in a ratio.
    starts = level_start_step[1:]
    inwin = set()
    for s0 in starts:
        for k in range(WINDOW):
            if s0 + k < len(stream):
                inwin.add(s0 + k)
    prof_inert = [0] * WINDOW
    prof_fill = [0] * WINDOW
    prof_n = [0] * WINDOW
    prof_tools: list[Counter] = [Counter() for _ in range(WINDOW)]
    for s0 in starts:
        for k in range(WINDOW):
            if s0 + k >= len(stream):
                continue
            lv, ch, fl, tl = stream[s0 + k]
            prof_n[k] += 1
            prof_inert[k] += 1 - ch
            prof_fill[k] += fl
            prof_tools[k][tl] += 1
    out_win = [r for i, r in enumerate(stream) if i not in inwin]
    ctrl_inert = round(sum(1 - r[1] for r in out_win) / len(out_win), 4) if out_win else 0.0
    ctrl_fill = round(sum(r[2] for r in out_win) / len(out_win), 4) if out_win else 0.0
    win_inert = sum(prof_inert)
    win_fill = sum(prof_fill)
    win_n = sum(prof_n)

    # Which tool cleared the level, and which held the board straight after it
    cleared_by = [stream[s0 - 1][3] for s0 in starts if s0 - 1 < len(stream)]
    held_after = [stream[s0][3] for s0 in starts if s0 < len(stream)]
    swaps = sum(1 for a, b in zip(cleared_by, held_after) if a != b)

    # -- WHO ISSUED THE INERT ACTIONS ---------------------------------------------------------
    #
    # The question the handover profile could not reach and the wall measurement cannot either:
    # lf52 spends 359 of 500 actions changing nothing, against 2-6% on a game that scores 1.0.
    # An inert action has three possible authors and they want opposite work:
    #
    #   fill_named   the harness filled the turn because the ACTIVE tool proposed nothing. The
    #                tool is blind here, and `_current` still carries its name — which is why the
    #                `tool is None` proxy reports zero and this one does not.
    #   fill_none    the harness filled after `_EMPTY_TOLERANCE` = 8 consecutive empties retired
    #                the tool. The only case the proxy can see.
    #   proposed     a tool HAD a plan, issued it, and the board did not move. That is a wrong
    #                model, not a blind one, and no fill-side change can touch it.
    by_tool: dict[str, list[int]] = {}
    for _lv, ch, fl, tl in stream:
        r = by_tool.setdefault(tl, [0, 0, 0, 0])   # actions, inert, fills, inert_and_fill
        r[0] += 1
        r[1] += 1 - ch
        r[2] += fl
        r[3] += (1 - ch) * fl
    by_level: dict[int, list[int]] = {}
    for lv, ch, fl, _tl in stream:
        r = by_level.setdefault(lv, [0, 0, 0])
        r[0] += 1
        r[1] += 1 - ch
        r[2] += fl
    inert_filled = sum((1 - r[1]) * r[2] for r in stream)
    inert_proposed = sum((1 - r[1]) * (1 - r[2]) for r in stream)

    # ⚠️ Instrument validity (rule 7b, and the peer probe's own advice): the per-level action
    # counts must reproduce numbers already known for the game. ls20 is 17/101/63/66/67/100/231.
    bounds = level_start_step + [len(stream)]
    per_level = [bounds[i + 1] - bounds[i] for i in range(len(bounds) - 1)]

    out = {
        "game": title, "levels": lvl, "actions": len(stream), "per_level": per_level,
        "human": human[:len(per_level)],
        "stop": stop, "deaths": deaths, "window": WINDOW, "transitions": len(starts),
        "prof_inert": prof_inert, "prof_fill": prof_fill, "prof_n": prof_n,
        "prof_tools": [dict(c.most_common(3)) for c in prof_tools],
        "ctrl_inert_rate": ctrl_inert, "ctrl_fill_rate": ctrl_fill,
        "win_inert": win_inert, "win_fill": win_fill, "win_n": win_n,
        "excess_inert": round(win_inert - ctrl_inert * win_n, 2),
        "excess_fill": round(win_fill - ctrl_fill * win_n, 2),
        "cleared_by": cleared_by, "held_after": held_after, "swaps": swaps,
        "by_tool": {k: v for k, v in sorted(by_tool.items(), key=lambda kv: -kv[1][0])},
        "by_level": {str(k): v for k, v in sorted(by_level.items())},
        "inert_filled": inert_filled, "inert_proposed": inert_proposed,
        "fills_total": sum(r[2] for r in stream),
        "fills_named": fill_flag["named"],
        "fills_none_visible_to_proxy": fill_flag["none"],
        "inert_total": sum(1 for r in stream if not r[1]),
        "layers": dict(layers), "trans_layers": trans_layers,
        "trans_layer0_stale": trans_stale0,
    }
    with open(f"/tmp/hctrl_{title}.json", "w") as fh:
        json.dump({"stream": stream, **out}, fh)
    print(json.dumps(out), flush=True)


if __name__ == "__main__":
    main()
