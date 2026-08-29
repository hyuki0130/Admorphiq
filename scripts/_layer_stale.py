"""How much does `frame_2d` reading LAYER 0 cost, across all 25 games?

Measured on re86: the level-transition frame carries the OLD level's board in layer 0 and the NEW
level's board in layer 1. `frame_2d` returns the first layer, so the tool reads a board that is one
level out of date, finds nothing it recognises, proposes nothing, and `UnifiedAgent._probe` fills
the turn with `simple_ids[0]` — which pushed a piece the wrong way and cost two actions (the push
and the undo) on every level of the game.

That is a HARNESS fact, not a tool fact, so the question is how many of the other twenty-four games
pay it. This probe answers, per game and without changing anything:

  layers        how many layers the game emits, and how often more than one
  stale0        frames where a later layer showed something layer 0 did not AND the NEXT
                frame's layer 0 is exactly that — layer 0 was one frame BEHIND the board
  trans_stale   the same, restricted to the frame right after `levels_completed` rises
  fills         actions the active tool did not propose, so the harness probe filled them
  trans_fills   fills on the frame right after a level rose (the re86 case exactly)
  fill_inert    of those fills, how many changed nothing on the board at all

    uv run python scripts/_layer_stale.py <index 1..25> [cap]

⛔ Level changes are tested as `> previous` and the resulting level is printed, never `!=`
(rule 7f). Progress goes to stderr from the first action (rule 7e). One json line on stdout.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))


def _log(*a):
    print(*a, file=sys.stderr, flush=True)


def _layers(obs):
    import numpy as np
    fr = getattr(obs, "frame", None)
    if fr is None:
        return []
    if isinstance(fr, list):
        return [np.asarray(x) for x in fr]
    return [np.asarray(fr)]


def main() -> None:
    idx = int(sys.argv[1]) - 1
    cap = int(sys.argv[2]) if len(sys.argv) > 2 else 4000
    from arc_agi import Arcade, OperationMode

    from admorphiq.harness.loop import UnifiedAgent
    from admorphiq.harness.registry import default_tools
    from admorphiq.tools.segment import board_changed

    def _no_llm(*_a, **_k):
        raise RuntimeError("LLM-free: the signature fallback is what this measures")

    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    infos = sorted(arcade.get_environments(), key=lambda i: (i.title or i.game_id).lower())
    if idx >= len(infos):
        print(json.dumps({"skip": idx}))
        return
    info = infos[idx]
    title = (info.title or info.game_id).lower()
    _log(f"[layer] {title} cap={cap}")
    env = arcade.make(info.game_id)
    obs = env.reset()
    agent = UnifiedAgent(default_tools(), _no_llm, giveup=cap, stall=80, ctx_budget=6000)

    filled = {"n": 0}
    real_probe = agent._probe

    def _probe(simple_ids, action6):
        filled["n"] += 1
        return real_probe(simple_ids, action6)

    agent._probe = _probe                                    # type: ignore[method-assign]

    frames = [obs]
    done = 0
    seen_layers: dict[int, int] = {}
    stale0 = trans_stale = trans_fills = fill_inert = 0
    at_transition = True          # the very first frame of the game counts as one
    was_transition = False        # whether the frame BEING judged for staleness was one
    prev = _layers(obs)
    n = 0
    for n in range(cap):
        if agent.is_done(frames, obs):
            break
        before = filled["n"]
        act = agent.choose_action(frames, obs)
        data = act.action_data.model_dump() if getattr(act, "action_data", None) else None
        was_fill = filled["n"] > before
        board = _layers(obs)
        seen_layers[len(board)] = seen_layers.get(len(board), 0) + 1
        # ⛔ "Layer 0 is BEHIND" is only demonstrated by the layer 0 that CATCHES UP. The first
        # version of this test asked whether layer 0 held still while a later layer moved
        # SINCE THE LAST FRAME — and it scored re86, the board it was written from, at zero,
        # because re86's frames carry one layer until the transition, so there is no previous
        # later layer to compare against. An instrument that cannot see its own known positive
        # measures nothing (rule 7b). The test now spans two frames and is decisive: this frame
        # shows something in a later layer that layer 0 does not, and the NEXT frame's layer 0
        # is exactly that. An overlay or an animation cannot satisfy the second half.
        if prev and len(prev) > 1 and prev[0].shape == prev[-1].shape \
                and (prev[0] != prev[-1]).any() and board \
                and board[0].shape == prev[-1].shape \
                and (board[0] == prev[-1]).all():
            stale0 += 1
            if was_transition:
                trans_stale += 1
        if was_fill and at_transition:
            trans_fills += 1
        was_transition = at_transition
        prev = board
        obs = env.step(act, data=data) if data else env.step(act)
        frames.append(obs)
        after = _layers(obs)
        if was_fill and board and after and board[0].shape == after[0].shape \
                and not board_changed(board[0], after[0]):
            fill_inert += 1
        now = int(getattr(obs, "levels_completed", done) or 0)
        at_transition = now > done
        if at_transition:
            _log(f"  {title} level {now} at action {n + 1}")
            done = now
        if n % 200 == 0:
            _log(f"  {title} step={n} level={done} fills={filled['n']}")
    print(json.dumps({
        "game": title, "actions": n + 1, "levels": done,
        "layers": seen_layers, "stale0": stale0, "trans_stale": trans_stale,
        "fills": filled["n"], "trans_fills": trans_fills, "fill_inert": fill_inert,
    }))


if __name__ == "__main__":
    main()
