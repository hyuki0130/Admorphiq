"""Score ONE game with ONE tool removed from the registry — and record who plays it.

⭐ WHAT THIS MEASURES. The closest available proxy to an UNSEEN game. Every transfer
instrument this repository has — the archived re-render (rule 7by), the colour permutation
and identifier rename (7ce), the z-order arm — perturbs the RENDERING of a game whose
mechanic one of our tools already implements. None of them perturbs the MECHANIC. But the
private-110 condition, for most of those games, is exactly: *a board whose mechanic no tool
in the registry implements.* We cannot obtain a new mechanic; we can obtain the CONDITION,
by removing the tool that owns a game and scoring it again.

⛔ OWNERSHIP COMES FROM WHAT THE HARNESS PICKS, NOT FROM `detect()` (rule 7g). A tool's bid
says what is POSSIBLE; only the run says what HAPPENS. So the recorder reads
`UnifiedAgent._current` after every single action and attributes that action — and the
level it was spent on — to whichever tool actually held the board.

⛔ THE ABLATION IS A MEASUREMENT, NOT A CHANGE (rule 7o). It monkeypatches
`admorphiq.harness.registry.default_tools` for the lifetime of this process only, inside a
private snapshot. Nothing is edited in the shared tree, and
`tests/test_every_tool_is_registered.py` exists precisely because an unregistered tool
measures like an absent one — which here is the point rather than the hazard.

⛔ AND IT REFUSES RATHER THAN REPORTING ABSENCE. A `--drop` naming a tool that is not in the
registry would ablate nothing and score identically, which reads exactly like "the harness
copes fine without it". That is the fail-toward-nothing shape this campaign has paid for
eight times. The runner checks the registry actually shrank by one and exits non-zero if it
did not.

    uv run python scripts/ablate_run.py --titles bp35 --drop none  --out c.json
    uv run python scripts/ablate_run.py --titles bp35 --drop crag  --out a.json
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from arc_agi import Arcade, OperationMode  # noqa: E402

import admorphiq.harness.registry as registry  # noqa: E402

_UNPATCHED = registry.default_tools


class OwnershipRecorder:
    """Wrap the agent and attribute every ACTION to the tool that held the board.

    Purpose: turn "which tool owns this game" from a guess into a count. Rule 7bq measured
    that 20 of 25 games are played start to finish by ONE tool, so ownership is usually
    unambiguous — but "usually" is not "here", and the ablation's whole meaning depends on
    having removed the right tool.

    Expected feedback: ``by_tool`` is the action census. If the game's actions are spread
    over several tools, the single-tool ablation answers a narrower question than the round
    is asking, and the round page must say so rather than average over it.
    """

    def __init__(self, inner: Any) -> None:
        self.inner = inner
        self.by_tool: Counter[str] = Counter()
        self.by_level: dict[int, Counter[str]] = {}
        self.picks: list[tuple[int, int, str, bool]] = []  # (action, level, tool, primary_owns)
        self._n = 0

    def __getattr__(self, item: str) -> Any:
        return getattr(self.inner, item)

    def is_done(self, frames: list[Any], obs: Any) -> bool:
        return self.inner.is_done(frames, obs)

    def choose_action(self, frames: list[Any], obs: Any) -> Any:
        level = int(getattr(obs, "levels_completed", 0) or 0)
        action = self.inner.choose_action(frames, obs)
        self._n += 1
        who = str(getattr(self.inner, "_current", None) or "none")
        self.by_tool[who] += 1
        self.by_level.setdefault(level, Counter())[who] += 1
        if not self.picks or self.picks[-1][2] != who:
            # ⛔ `_primary_owns` is WHY a tenure does or does not end. A tool whose detect()
            # cleared `_PRIMARY_CONF` is exempt from stall retirement, so a wrong tool that
            # bids high holds the board until the outer no-progress guard abandons the game.
            # Recording it here turns "it was never displaced" into "it COULD not be".
            self.picks.append((self._n, level, who,
                               bool(getattr(self.inner, "_primary_owns", False))))
        return action

    def report(self) -> dict[str, Any]:
        return {
            "actions": self._n,
            "by_tool": dict(self.by_tool.most_common()),
            "owner": self.by_tool.most_common(1)[0][0] if self.by_tool else None,
            "owner_share": (round(self.by_tool.most_common(1)[0][1] / self._n, 4)
                            if self._n else None),
            "n_tools_used": len(self.by_tool),
            "by_level": {str(k): dict(v.most_common()) for k, v in sorted(self.by_level.items())},
            "tenures": len(self.picks),
            "picks": [{"action": a, "level": lv, "tool": t, "primary_owns": p}
                      for a, lv, t, p in self.picks[:80]],
        }


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--titles", required=True)
    p.add_argument("--drop", required=True,
                   help="comma-separated tool names to remove, or 'none' for the control arm")
    p.add_argument("--agent", default="unified")
    p.add_argument("--max-actions", type=int, default=4000)
    p.add_argument("--out", required=True)
    args = p.parse_args()

    full = [t.name for t in _UNPATCHED()]
    drop = args.drop.strip()
    if drop != "none":
        # A multi-drop arm is how the LATCH is tested causally: removing a game's owner AND
        # the tool that then seizes the board says whether the seizure was the cause of the
        # collapse or merely its accompaniment.
        names = [d.strip() for d in drop.split(",") if d.strip()]
        if len(set(names)) != len(names):
            print(f"⛔ REFUSING: '{drop}' names a tool twice — the shrink check would pass "
                  f"for the wrong reason.", flush=True)
            return 1
        missing = [d for d in names if d not in full]
        if missing:
            print(f"⛔ REFUSING: {missing} not in the registry. Ablating a tool that is "
                  f"not there removes nothing and scores identically, which reads exactly "
                  f"like 'the harness copes without it'. Names are: {sorted(full)}",
                  flush=True)
            return 1

        def patched() -> list[Any]:
            return [t for t in _UNPATCHED() if t.name not in names]

        registry.default_tools = patched
        after = [t.name for t in registry.default_tools()]
        if len(after) != len(full) - len(names) or any(d in after for d in names):
            print(f"⛔ REFUSING: the registry did not shrink by exactly {len(names)} "
                  f"({len(full)} -> {len(after)})", flush=True)
            return 1
    else:
        after = list(full)

    # Imported AFTER the patch so `_make_agent`'s own `from ... import default_tools`
    # (which happens at call time, inside the function) resolves to the patched attribute.
    from score_efficiency import _make_agent, run_game, total_score  # noqa: PLC0415

    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    wanted = [t.strip().lower() for t in args.titles.split(",") if t.strip()]
    seen: set[str] = set()
    envs = []
    for e in arcade.get_environments():
        hay = f"{e.game_id} {e.title or ''}".lower()
        if any(w in hay for w in wanted) and e.game_id not in seen:
            seen.add(e.game_id)
            envs.append(e)
    if not envs:
        print(f"⛔ REFUSING: no environment matched {args.titles!r}", flush=True)
        return 1

    results: list[dict[str, Any]] = []
    scored: list[float] = []
    for env_info in envs:
        holder: dict[str, OwnershipRecorder] = {}

        def factory() -> OwnershipRecorder:
            rec = OwnershipRecorder(_make_agent(args.agent, game_id=env_info.game_id))
            holder["rec"] = rec
            return rec

        result = run_game(arcade, env_info.game_id, env_info.baseline_actions,
                          agent_name=args.agent, max_actions=args.max_actions,
                          adapter_factory=factory)
        result["title"] = env_info.title or env_info.game_id
        result["ownership"] = holder["rec"].report()
        results.append(result)
        if result.get("has_baseline"):
            scored.append(result["game_score"])
        own = result["ownership"]
        print(f"{env_info.game_id} drop={drop} score={result.get('game_score')} "
              f"levels={result.get('levels_completed')}/{result.get('win_levels')} "
              f"owner={own['owner']}({own['owner_share']}) tools={own['n_tools_used']} "
              f"tenures={own['tenures']} actions={own['actions']}", flush=True)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({
        "agent": args.agent,
        "dropped": drop,
        "registry_size": len(after),
        "registry_size_full": len(full),
        "n_games_run": len(envs),
        "n_games_scored": len(scored),
        "total_score": round(total_score(scored), 6),
        "games": results,
    }, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
