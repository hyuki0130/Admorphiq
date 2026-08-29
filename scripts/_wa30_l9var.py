"""wa30 level 9 — three candidate mechanisms for the missing ninth piece, each measured whole-game.

MEASURED FIRST, by `_wa30_l9diag.py` on the shipped tool (commit under test, full 25 baseline
0.8962): level 9 is entered at action 584 and the harness gets EIGHT attempts at it, because the
board's declared 70-action counter restarts the level rather than ending the game.

    attempt 1   covered 8 of 9 by action 63, seven actions to spare
    attempts 2-7  covered 7, IDENTICAL to each other action for action
    attempt 8   cut off by the run's budget

So six of the eight attempts are the same attempt. The tool never learns that it died, because a
restart does not change `levels_completed` and nothing else in it is watching. Three consequences
are testable, and this probe tests them separately rather than as one lump:

  R  RESTART-AWARE. A restart redraws every piece and puts the carrier back where it started, so
     any plan in hand is a plan for a board that no longer exists, and the walker sweep is
     comparing one attempt's last frame with the next attempt's first. Detected from the frame:
     the cargo set and the carrier cell both equal the ones this level opened with.
  B  BUDGET GUARD. The FIRST death measures the allowance — no source, no drawn counter needed,
     just the length of the attempt that died. From attempt two on, refuse to begin a haul longer
     than the actions left, and put down a piece that cannot be delivered in time: a piece held by
     the carrier is a piece the field is FORBIDDEN to take (`ynmgxjqkgh` skips anything already in
     `zmqreragji`), so holding one it cannot deliver is strictly worse than not holding it.
  O  OPENING SHIFT. Six identical retries are six wasted attempts. Take the k-th candidate rather
     than the best one on attempt k, so the retries differ. Deterministic — no RNG, so a clear is
     reproducible.

⛔ Variants are SUBCLASSES here, not edits to the tool: `pfan.sh` ships `scripts/` only, and a
measurement of src that was never shipped is a measurement of the old code.

⛔ `levels_completed` is printed as a NUMBER and tested `> start`. Level 9 is the last, so a real
clear may never increment the level index, and a collapse to level 0 is indistinguishable from a
clear to anything that tests `!=`. The engine's own win predicate — nine pieces resting in a bay,
held by nobody — is reported alongside it.
"""
from __future__ import annotations

import json
import sys

sys.path.insert(0, "src")

C = 4
Cell = tuple[int, int]

# name -> (restart-aware, budget guard, opening shift, route-distance mover bias)
VARIANTS = [
    ("control", False, False, False, False),
    ("R", True, False, False, False),
    ("R+B", True, True, False, False),
    ("R+O", True, False, True, False),
    ("R+B+O", True, True, True, False),
    ("Rt", False, False, False, True),
    ("R+Rt", True, False, False, True),
    ("R+B+Rt", True, True, False, True),
    ("R+O+Rt", True, False, True, True),
    ("R+B+O+Rt", True, True, True, True),
]


def build(kind):
    from admorphiq.tools.base import frame_2d, has_frame, levels_completed
    from admorphiq.tools.haul import _DELTA, _LATCH, _MOVES
    from admorphiq.tools.shepherd import ShepherdRelayTool, _reach, _spread

    _, restart_aware, budget_guard, opening_shift, by_route = kind

    class Variant(ShepherdRelayTool):
        def __init__(self) -> None:
            super().__init__()
            self._last: tuple = (None, None)
            self._acted = 0
            self._attempt = 1
            self._allowance: int | None = None
            self.calls = 0
            self.restarts = 0
            self.hauls: list[str] = []      # one line per haul chosen, for the first attempts
            self.declined = 0
            self.dropped = 0

        def reset(self) -> None:
            super().reset()
            self._last = (None, None)
            self._acted = 0
            self._attempt = 1
            self._allowance = None

        # -- restart -----------------------------------------------------
        def _restarted(self, board) -> bool:
            """A restart is a TELEPORT plus pieces reappearing outside the bays.

            ⛔ Both halves are needed and neither is a threshold. The carrier moves at most one
            cell per action, so a jump is not something play produces; and a thief takes at most
            one piece out of a bay per turn, so two pieces reappearing loose in one action is not
            something the field produces either.
            """
            loose = sum(1 for c in board.cargo if c not in board.bays)
            prev_loose, prev_carrier = self._last
            self._last = (loose, board.carrier)
            if prev_carrier is None or board.carrier is None:
                return False
            jump = (abs(board.carrier[0] - prev_carrier[0])
                    + abs(board.carrier[1] - prev_carrier[1]))
            return jump > 1 and loose - prev_loose >= 2

        def propose(self, frames, obs):
            self.calls += 1
            if restart_aware and has_frame(obs) and levels_completed(obs) == self._level:
                board = self._eyes._read(frame_2d(obs))
                if board is not None and board.carrier is not None:
                    self._acted += 1
                    if self._restarted(board):
                        self.restarts += 1
                        if self._allowance is None:
                            self._allowance = self._acted - 1
                        self._attempt += 1
                        self._acted = 1
                        # ⛔ Everything that says WHERE things are is void; what the game taught
                        # about which colour walks and which can be removed is not.
                        self._plan = []
                        self._offset = None
                        self._promise = None
                        self._camp = None
                        self._camped = 0
                        self._chase = 0
                        self._pending = None
                        self._fresh = True
                        self._flat = {}
                        self._actors = {}
            return super().propose(frames, obs)

        def _left(self):
            if self._allowance is None:
                return None
            return self._allowance - self._acted

        # -- put a piece down that cannot be delivered in time -------------
        def _deliver(self, board, carrier, offset):
            if budget_guard:
                left = self._left()
                ride = (carrier[0] + offset[0], carrier[1] + offset[1])
                bays = self._open_bays(board, ride)
                if left is not None and ride not in bays:
                    paths = self._eyes._tow(board, carrier, offset)
                    aim = [len(p) for q, p in paths.items()
                           if (q[0] + offset[0], q[1] + offset[1]) in bays]
                    if aim and min(aim) + 1 > left:
                        self.dropped += 1
                        self._plan = []
                        self._promise = None
                        return _LATCH
            return super()._deliver(board, carrier, offset)

        # -- which piece to take ------------------------------------------
        def _start_haul(self, board, carrier):
            if not (budget_guard or opening_shift or by_route):
                return super()._start_haul(board, carrier)
            bays = self._open_bays(board, None)
            loose = [c for c in board.cargo if c not in board.bays]
            if not loose or not bays:
                return self._hold(board, carrier)
            walk = self._eyes._walk(board, carrier)
            movers = sorted(c for c, kind in self._actors.items()
                            if kind not in self._removable)
            left = self._left() if budget_guard else None
            # ⛔ ROUTE, NOT PICTURE — the rule `_police` already states for a thief and
            # `_start_haul` does not state for a mover. On this game's last board one of the two
            # helpers is sealed above a hazard band and moves zero cells in seventy actions, and a
            # straight line puts it four cells from a piece it can never reach, so the three
            # pieces on that side rank as already-taken-care-of and the carrier walks away.
            field = _spread(board, movers) if by_route else {}
            far = board.rows + board.cols
            ranked = []
            for piece in loose:
                if by_route:
                    got = _reach(field, piece)
                    alone = far if got is None else got
                else:
                    alone = min([abs(piece[0] - m[0]) + abs(piece[1] - m[1]) for m in movers],
                                default=0)
                for act in _MOVES:
                    d = _DELTA[act]
                    stance = (piece[0] - d[0], piece[1] - d[1])
                    if stance == carrier:
                        approach = []
                    elif stance in walk:
                        approach = list(walk[stance])
                    else:
                        continue
                    tow = self._eyes._tow(board, stance, d)
                    drop = sorted((len(p), q) for q, p in tow.items()
                                  if (q[0] + d[0], q[1] + d[1]) in bays)
                    if not drop:
                        continue
                    turn = [] if (not approach and board.facing == act) else [act]
                    plan = approach + turn + [_LATCH] + list(tow[drop[0][1]]) + [_LATCH]
                    if left is not None and len(plan) > left:
                        continue
                    ranked.append((alone, len(plan), piece, plan))
            if not ranked:
                self.declined += 1
                return self._hold(board, carrier)
            ranked.sort(key=lambda t: (-t[0], t[1]))
            # One candidate per PIECE, so a shift moves to a different piece rather than to
            # another face of the same one.
            seen = set()
            distinct = []
            for alone, cost, piece, plan in ranked:
                if piece in seen:
                    continue
                seen.add(piece)
                distinct.append((alone, cost, piece, plan))
            idx = min(self._attempt - 1, len(distinct) - 1) if opening_shift else 0
            if len(self.hauls) < 40:
                self.hauls.append(
                    f"a{self._attempt}/t{self._acted} left={left} take={distinct[idx][2]} "
                    f"cost={distinct[idx][1]} alone={[(d[2], d[0]) for d in distinct[:4]]}")
            self._plan = list(distinct[idx][3])
            return self._plan.pop(0)

    return Variant


def main() -> None:
    from arc_agi import Arcade, OperationMode

    from admorphiq.harness.loop import UnifiedAgent
    from admorphiq.harness.registry import default_tools
    from admorphiq.tools.shepherd import ShepherdRelayTool

    job = int(sys.argv[1])
    cap = int(sys.argv[2]) if len(sys.argv) > 2 else 1400
    kind = VARIANTS[(job - 1) % len(VARIANTS)]

    def _no_llm(*_a, **_k):
        raise RuntimeError("LLM-free: the signature fallback is what the harness scores")

    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    info = next(i for i in arcade.get_environments()
                if (i.title or i.game_id).lower().startswith("wa30"))
    env = arcade.make(info.game_id)
    obs = env.reset()
    game = getattr(env, "_game", None) or getattr(env, "game", None)

    tools = default_tools()
    probe = None
    if kind[0] != "control":
        cls = build(kind)
        tools = [(probe := cls()) if isinstance(t, ShepherdRelayTool) else t for t in tools]
    agent = UnifiedAgent(tools, _no_llm, giveup=cap, stall=80, ctx_budget=6000)

    def pieces():
        return game.current_level.get_sprites_by_tag("geezpjgiyd")

    def covered():
        return sum(1 for s in pieces()
                   if (s.x, s.y) in game.wyzquhjerd and s not in game.zmqreragji)

    start_done = int(getattr(obs, "levels_completed", 0) or 0)
    frames = [obs]
    levels = start_done
    per_level: list[list[int]] = []
    last_mark = 0
    step = 0
    win_seen = False
    win_at = None
    prev_steps = None
    attempts: list[int] = []          # best covered per attempt at level 9
    best = 0

    for step in range(cap):
        if agent.is_done(frames, obs):
            break
        act = agent.choose_action(frames, obs)
        data = act.action_data.model_dump() if getattr(act, "action_data", None) else None
        obs = env.step(act, data=data) if data else env.step(act)
        frames.append(obs)
        now = int(getattr(obs, "levels_completed", levels) or 0)
        if now > levels:
            per_level.append([now, step + 1 - last_mark])
            last_mark = step + 1
            levels = now
        if levels != 8:
            continue
        steps_left = game.kuncbnslnm.current_steps
        if prev_steps is None or steps_left > prev_steps:
            attempts.append(best)
            best = 0
        prev_steps = steps_left
        cov = covered()
        best = max(best, cov)
        if cov == len(pieces()) and not win_seen:
            win_seen = True
            win_at = step + 1
    attempts.append(best)

    end_done = int(getattr(obs, "levels_completed", 0) or 0)
    print(json.dumps({
        "job": job, "variant": kind[0],
        "levels_completed_start": start_done,
        "levels_completed_end": end_done,
        "greater_than_start": end_done > start_done,
        "engine_win_seen": win_seen, "win_at_action": win_at,
        "actions_total": step + 1,
        "per_level_actions": per_level,
        "level9_attempts": attempts[1:],
        "level9_best": max(attempts) if attempts else 0,
        "fired": None if probe is None else {
            "propose_calls": probe.calls, "restarts_seen": probe.restarts,
            "allowance_learnt": probe._allowance, "attempt_final": probe._attempt,
            "hauls_declined": probe.declined, "pieces_put_down": probe.dropped},
        "hauls": [] if probe is None else probe.hauls,
    }))


if __name__ == "__main__":
    main()
