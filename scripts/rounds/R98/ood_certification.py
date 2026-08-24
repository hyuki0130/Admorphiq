"""R98 OOD certification — the control the pre-screen could not finish.

Purpose
-------
`near_ood_screen.py` ranked candidate games by the family's observable tell — a
single action exposing a scripted consequence as many frame layers at once — and
recorded that the FULL certification "needs the grounding service, which does not
exist yet". It exists now, so this runs the real control: point the flow harness
at a game that is NOT this family and watch what it says.

A control passes when the harness DECLINES. Two ways of declining are both fine
and mean different things:

* the grounding cannot assemble a board at all — the game does not present the
  entities this family is made of;
* it assembles one and the verifier does not PASS — a board was read but the
  claimed mechanics do not reproduce what the engine did.

A control FAILS when the harness reports PASS on a game from another family,
because a verifier that passes anything is not evidence about anything.

tu93 is the near control: it survived the pre-screen with an 8-layer burst against
the oracle's 22, so an agent could plausibly reach for this model and only then be
proven wrong. re86 is the far control at 1 layer — rejected on sight, and included
to show the difference between declining and never being tempted.

Expected feedback
-----------------
Per game: what the grounding could and could not read, and the verifier's verdict.
PASS on either control is a finding about the harness, not about the game.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from oracle_gate import ACTIONS, _open_arcade  # noqa: E402

from admorphiq.hypothesis_select import schema_flow as F  # noqa: E402
from admorphiq.hypothesis_select.grounding_flow import UNKNOWN, FlowGrounding  # noqa: E402
from admorphiq.hypothesis_select.schema import Verdict  # noqa: E402
from admorphiq.hypothesis_select.verifier_flow import verify_flow_instance  # noqa: E402

# sp80 is the POSITIVE control and it is not decoration: without it, "declines on every
# control" is indistinguishable from a harness that declines on everything, which would
# pass this certification while proving nothing.
CONTROLS = (("sp80", "positive"), ("tu93", "near"), ("re86", "far"))
DISCOVERY = (1, 1, 2, 3, 4)


def _play(prefix: str):
    """The same discovery the oracle gate spends on sp80, on another game."""
    arcade = _open_arcade()
    gid = next((e.game_id for e in arcade.get_environments()
                if e.game_id.startswith(prefix)), None)
    if gid is None:
        return None, f"no environment starting with {prefix!r}"
    env = arcade.make(gid)
    from arcengine import GameAction

    obs = env.step(GameAction.RESET)
    g = FlowGrounding()
    g.observe(0, None, obs.frame)

    def act(a):
        nonlocal obs
        obs = env.step(ACTIONS[a])
        g.observe(a, None, obs.frame)

    # The gate's discovery, not a shortened one. The first version of this control spent
    # five probes and a commit and every game "declined" — including sp80, which the
    # positive control caught at once. The alignment before the commit is what makes the
    # spill informative, and a control that skips it measures the discovery, not the game.
    for a in DISCOVERY:
        act(a)
    hint = g.flow_origin_hint()
    if hint is not UNKNOWN and g.tracked_region() is not UNKNOWN:
        target = max(c for _, c in hint.value)
        guard = 0
        while max(c for _, c in g.tracked_region().value) < target and guard < 12:
            act(4)
            guard += 1
    act(5)
    return g, gid


def main() -> int:
    failures = 0
    for prefix, kind in CONTROLS:
        g, gid = _play(prefix)
        if g is None:
            print(f"  {prefix} ({kind}): SKIP — {gid}")
            continue
        board = g.board()
        readable = board is not UNKNOWN
        detail = (f"board with {len(board.value.sinks)} target(s), "
                  f"{len(board.value.pieces)} piece(s)" if readable else "no board")
        positive = kind == "positive"
        if not readable:
            print(f"  {prefix} ({kind}): "
                  f"{'FAILS' if positive else 'DECLINES'} — the grounding cannot assemble "
                  f"a board")
            failures += 1 if positive else 0
            continue
        verdict = verify_flow_instance(F.sp80_oracle_instance(), g, False)
        passed = verdict.verdict is Verdict.PASS
        ok = passed if positive else not passed
        print(f"  {prefix} ({kind}): {'OK' if ok else 'FAILS'} — {detail}; "
              f"verifier {verdict.verdict.value}: {verdict.reason}")
        if not ok:
            failures += 1

    print(f"\n[ood certification] {'PASS' if not failures else 'FAIL'} — "
          + ("the harness reads its own family and declines the others"
             if not failures
             else f"{failures} control(s) came out the wrong way"))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
