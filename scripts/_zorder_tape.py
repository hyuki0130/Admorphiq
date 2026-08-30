"""Is the z-order mutation render-only? Replay a game's OWN action tape under it.

Why this probe exists
---------------------
Rule 7ck measured that fourteen of 25 games depend on paint order, and that two of them —
g50t and tu93 — fall from 1.0000 to **0.0000**. It also says plainly that g50t is NOT
CLASSIFIABLE: *"what is missing is whether their levels stay solvable with the one hidden
sprite."* A game that loses everything is exactly where a mutation is most likely to have
changed the MECHANIC rather than the picture, and that is the cheapest hypothesis on the
table — if it holds, the 0.0000 says nothing about the tools.

`zorder_mutation.py` argues render-only STRUCTURALLY: `Camera.render` has one caller,
game logic reads `_raw_render`, click resolution reads `Level._sprites`. ⛔ Rule 7g: the
source says what is POSSIBLE. This measures it.

The test
--------
1. RECORD — play the game clean and keep every action the agent sent, in order.
2. REPLAY-CLEAN — feed that tape back through `score_efficiency.run_game` with a tape
   adapter. Must reproduce the recording exactly.
3. REPLAY-MUTATED — feed the SAME tape through the SAME loop with the paint-order patch
   installed.

If the mutation is render-only the state trajectory is a function of the action sequence
alone, so arm 3 must clear the same levels at the same action indices as arm 1. Any
divergence is the mutation reaching the game's LOGIC, and the game's 0.0000 under the
z-order arm is then an artefact of a broken mutation, not a transfer failure.

⛔ IT REUSES `run_game` VIA `adapter_factory` RATHER THAN STEPPING THE ENGINE ITSELF
(rule 7aj#1): the restart policy, the BREAK-on-WIN and the level accounting are the
scorer's own, and a hand-rolled replay loop would be describing a different run.
`restart_on_game_over` is copied off the real agent so the loop shape is identical.

Both controls
-------------
POSITIVE — arm 2 (replay clean) must equal arm 1 (record) on levels and per-level action
counts. If a game cannot even replay its own tape it is nondeterministic under replay and
NOTHING else in its row is interpretable; the probe says so rather than reporting arm 3.
POSITIVE, cross-game — run it on **s5i5**, where the mutation is KNOWN to be real and
render-only (rule 7cd proved the archived board clears every level, just slower). Its tape
MUST still clear under mutation. A probe that calls s5i5 broken has measured nothing.

    bash scripts/pfan.sh ztape scripts/_zorder_tape.py 4 "" 4      # arm i -> GAMES[i-1]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT / "src"))
sys.path.insert(0, str(_ROOT / "scripts"))

BUDGET = 4000

# g50t and tu93 are the two that fall to zero. s5i5 is the cross-game positive control (the
# mutation is real there and provably render-only). r11l is the negative: 7ck measured it
# identical action-for-action under the arm, so its tape must replay unchanged in both.
GAMES = ["g50t", "tu93", "s5i5", "r11l"]


class Tape:
    """Replays a recorded action list through the scorer's own loop.

    ⛔ THE TAPE STORES COORDINATES, NOT JUST THE ACTION. `AdmorphiqAdapter._convert_action`
    returns `OfficialGameAction.from_id(id)` — an ENUM MEMBER, a singleton — and then calls
    `set_data({x, y})` on it. Keeping the returned object is therefore keeping ONE object for
    every click in the run, all of them showing the LAST coordinates by the time the tape is
    replayed. Measured: the first version of this probe replayed g50t and tu93 (movement games,
    no coordinates) perfectly and scored s5i5 and r11l at ZERO LEVELS on the CLEAN engine — which
    reads exactly like "those games are not deterministic" and is a bug in the recorder. The
    clean-replay control is what caught it.
    """

    def __init__(self, actions: list, restart: bool) -> None:
        self._a = actions
        self._i = 0
        self.restart_on_game_over = restart

    def is_done(self, frames, obs) -> bool:  # noqa: ANN001
        return self._i >= len(self._a)

    def choose_action(self, frames, obs):  # noqa: ANN001, ANN202
        act, data = self._a[self._i]
        self._i += 1
        if data is not None:
            act.set_data(data)
        return act


def main() -> None:
    import score_efficiency as se
    from arc_agi import Arcade, OperationMode

    from admorphiq.zorder_mutation import ZOrderPatch, build

    arm = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    pick = sys.argv[2].strip().lower() if len(sys.argv) > 2 and sys.argv[2].strip() else ""
    title = pick if pick else GAMES[(arm - 1) % len(GAMES)]
    mutation = "zrevall"

    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    envs = [e for e in arcade.get_environments()
            if title in f"{e.game_id} {e.title or ''}".lower()]
    if not envs:
        print(json.dumps({"game": title, "error": "no such env"}))
        return
    info = envs[0]

    # -- arm 1: record --------------------------------------------------------
    tape: list = []
    orig_make = se._make_agent

    def make(*a, **k):  # noqa: ANN002, ANN003
        adapter = orig_make(*a, **k)
        inner = adapter.choose_action

        def choose(frames, obs):  # noqa: ANN001
            act = inner(frames, obs)
            data = None
            if act.is_complex():
                d = act.action_data.model_dump()
                data = {"x": int(d["x"]), "y": int(d["y"])}
            tape.append((act, data))
            return act

        adapter.choose_action = choose
        make.restart = bool(getattr(adapter, "restart_on_game_over", False))
        return adapter

    make.restart = False
    se._make_agent = make
    rec = se.run_game(arcade, info.game_id, info.baseline_actions,
                      agent_name="unified", max_actions=BUDGET)
    se._make_agent = orig_make
    restart = bool(make.restart)

    def replay(mutated: bool) -> dict:
        patch = ZOrderPatch(build(mutation)).install() if mutated else None
        try:
            return se.run_game(arcade, info.game_id, info.baseline_actions,
                               agent_name="unified", max_actions=BUDGET,
                               adapter_factory=lambda: Tape(tape, restart))
        finally:
            if patch is not None:
                patch.remove()

    clean = replay(False)
    muted = replay(True)

    def sig(r: dict) -> dict:
        return {
            "levels": r.get("levels_completed"),
            "win_levels": r.get("win_levels"),
            "score": round(float(r.get("game_score", 0.0)), 6),
            "per_level": [p.get("agent_actions") for p in r.get("per_level", [])],
        }

    rs, cs, ms = sig(rec), sig(clean), sig(muted)
    replayable = cs["levels"] == rs["levels"] and cs["per_level"] == rs["per_level"]
    print(json.dumps({
        "game": title,
        "mutation": mutation,
        "tape_len": len(tape),
        "record": rs,
        "replay_clean": cs,
        "replay_mutated": ms,
        "REPLAYABLE": replayable,
        # Only meaningful when REPLAYABLE. True => the same actions reach the same levels
        # under the mutation => the mutation is RENDER-ONLY on this game and the arm's
        # score loss is the tool's, not the instrument's.
        "RENDER_ONLY": (replayable
                        and ms["levels"] == rs["levels"]
                        and ms["per_level"] == rs["per_level"]),
    }, sort_keys=True))


if __name__ == "__main__":
    main()
