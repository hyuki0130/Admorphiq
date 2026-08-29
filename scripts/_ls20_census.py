"""ls20 level 7: WHAT is the tool doing for the 107 ticks between sighting the mover and pressing it?

Purpose. The ordering axis is closed in both directions (six ways of exploring less, ten ways of
pressing more/sooner, ~76 runs, every one a loss or exactly inert). The remaining question the
previous round left is whether there is a DIFFERENT way to meet a moving changer under fog. This
probe answers the two sub-questions that must precede any design, and it answers them with GROUND
TRUTH read out of the engine beside the tool's own belief, so a claim about the mover cannot be a
claim about our perception of it.

It changes NO decision: `fogscout` is subclassed for recording only, and the loop mirrors
`score_efficiency.run_game` (empty frames list, `restart_on_game_over`, break on WIN), so the banked
[17,101,63,66,67,100,231] must come back or nothing below is about the shipped tool.

Per tick on level 7 it records the tool's reason tag, the avatar cell, whether the move was ACCEPTED
(engine-side), the engine's own mover position and heading, the engine token, the drawn budget, and
the tool's belief state (marks seen, sighted, learned, win-route length). At level-7 entry it dumps
the static geometry: the mover's track region, every changer/refill/wall/goal cell, and each goal's
demanded token.

Expected feedback. `per_level` must read [17,101,63,66,67,100,231]. The census then says where the
231 go; the `blocked` column says whether a refused move advances the mover (the source says it is
UNDONE, which would make every `wait` tick a strict no-op); and the mover trace says whether its
patrol is a deterministic function of the accepted-move count, which is what an interception plan
would have to assume.
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))


def _mk():
    from collections import deque

    from admorphiq.tools.fogscout import _MOVE_IDS, FogScoutTool

    class V(FogScoutTool):
        """FogScoutTool with a recorder bolted on; every decision is the shipped one."""

        def __init__(self) -> None:
            self.rows: list[dict[str, Any]] = []
            super().__init__()

        def _win_len(self, shape) -> int | None:
            if self.pos is None or self.tok is None or self.goal is None or self.target is None:
                return None
            q: deque = deque([(self.pos, self.tok, 0)])
            seen = {(self.pos, self.tok)}
            acts = [a for a in self.dirs if a in _MOVE_IDS]
            while q:
                c, t, d = q.popleft()
                for a in acts:
                    nb = self._step_to(c, a)
                    if nb == self.goal:
                        if t == self.target:
                            return d + 1
                        continue
                    if not self._passable(nb, shape):
                        continue
                    nt = self._tok_after(nb, t)
                    if nt is None or (nb, nt) in seen:
                        continue
                    seen.add((nb, nt))
                    q.append((nb, nt, d + 1))
            return None

        def propose(self, frames, obs):
            out = super().propose(frames, obs)
            self.rows.append({
                "t": self.tick,
                "why": str(self.reason),
                "pos": list(self.pos) if self.pos else None,
                "win": self._win_len((64, 64)) if self.pos is not None else None,
                "left": self.moves_left(),
                "stood": len(self.stood),
                "seen": len(self.seen),
                "marks": len(self.mark),
                "kind": len(self.kind),
                "inert": len(self.inert),
                "refill": len(self.refill_marks),
                "sighted": len(self.sighted),
                "goal": self.goal is not None,
                "tgt": self.target is not None,
            })
            return out

    return V()


def _geom(g) -> dict[str, Any]:
    lv = g.current_level
    out: dict[str, Any] = {}
    for tag in ("ihdgageizm", "ttfwljgohq", "soyhouuebz", "rhsxkxzdjz", "npxgalaybz",
                "rjlbuycveu", "xfmluydglp", "gbvqrjtaqo"):
        try:
            out[tag] = [[s.x, s.y, s.width, s.height] for s in lv.get_sprites_by_tag(tag)]
        except Exception:
            out[tag] = []
    out["movers"] = [[m._sprite.x, m._sprite.y, m._dir,
                      m.bfdcztirdu.x, m.bfdcztirdu.y,
                      m.bfdcztirdu.width, m.bfdcztirdu.height] for m in g.wsoslqeku]
    out["mover_tags"] = [sorted(m._sprite.tags or []) for m in g.wsoslqeku]
    out["track_pixels"] = [
        [[int(v) for v in row] for row in m.bfdcztirdu.pixels.tolist()] for m in g.wsoslqeku]
    out["goals"] = [[s.x, s.y, g.ldxlnycps[i], g.yjdexjsoa[i], g.ehwheiwsk[i]]
                    for i, s in enumerate(g.plrpelhym)]
    out["avatar"] = [g.gudziatsk.x, g.gudziatsk.y, g.gisrhqpee, g.tbwnoxqgc]
    out["token"] = [g.fwckfzsyc, g.hiaauhahz, g.cklxociuu]
    out["nshape"] = len(g.ijessuuig)
    out["ncolor"] = len(g.tnkekoeuk)
    out["budget"] = g._step_counter_ui.osgviligwp
    out["steps"] = g._step_counter_ui.current_steps
    out["lives"] = g.aqygnziho
    return out


def main() -> None:
    from arc_agi import Arcade, OperationMode
    from arcengine import GameAction, GameState

    from admorphiq.harness.loop import UnifiedAgent
    from admorphiq.harness.registry import default_tools

    def _no_llm(*_a, **_k):
        raise RuntimeError("LLM-free: the signature fallback is what this measures")

    fog = _mk()
    tools = [fog if t.name == "fogscout" else t for t in default_tools()]

    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    info = next(i for i in arcade.get_environments()
                if (i.title or i.game_id).lower().startswith("ls20"))
    env = arcade.make(info.game_id)
    obs = env.observation_space
    g = env._game
    agent = UnifiedAgent(tools, _no_llm, giveup=4000, stall=80, ctx_budget=6000)
    human = list(getattr(info, "baseline_actions", []) or [])

    prev_levels = int(obs.levels_completed)
    total = 0
    this = 0
    per: list[int] = []
    trace: list[list[Any]] = []
    geom: dict[str, Any] = {}
    restart = bool(getattr(agent, "restart_on_game_over", False))

    while total < 4000:
        if agent.is_done([], obs):
            break
        act = agent.choose_action([], obs)
        if not isinstance(act, GameAction):
            break
        if prev_levels == 6 and not geom:
            geom = _geom(g)
        px, py = g.gudziatsk.x, g.gudziatsk.y
        mv0 = [[m._sprite.x, m._sprite.y, m._dir] for m in g.wsoslqeku]
        obs = env.step(act, data=act.action_data.model_dump()) if act.is_complex() else env.step(act)
        if obs is None:
            break
        total += 1
        this += 1
        if prev_levels == 6:
            mv1 = [[m._sprite.x, m._sprite.y, m._dir] for m in g.wsoslqeku]
            trace.append([
                this, str(getattr(act, "name", act)),
                px, py, g.gudziatsk.x, g.gudziatsk.y,
                mv0, mv1,
                [g.fwckfzsyc, g.hiaauhahz, g.cklxociuu],
                g._step_counter_ui.current_steps, g.aqygnziho,
            ])
        cur = int(obs.levels_completed)
        if cur > prev_levels:
            for _ in range(cur - prev_levels):
                per.append(this)
                this = 0
            prev_levels = cur
        if obs.state == GameState.WIN:
            break
        if obs.state == GameState.GAME_OVER:
            if not restart:
                break
            obs = env.step(GameAction.RESET)
            total += 1
            this += 1
            if obs is None:
                break

    weight = sum(range(1, len(human) + 1))
    got = 0.0
    rows = []
    for i, h in enumerate(human, start=1):
        mine = per[i - 1] if i - 1 < len(per) else 0
        s = min(h / mine, 1.0) ** 2 if mine else 0.0
        got += i * s
        rows.append([i, mine, h, round(s, 4)])
    why7 = Counter(r["why"].split("[")[0] for r in fog.rows if r["t"] >= 0)
    print(json.dumps({
        "levels": prev_levels, "total": total, "per_level": rows,
        "game_score": round(got / weight, 6),
        "why_all": dict(why7.most_common(20)),
        "geom": geom,
        "trace": trace,
        "belief": fog.rows,
    }, default=str), flush=True)


if __name__ == "__main__":
    main()
