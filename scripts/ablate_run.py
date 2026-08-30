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
import hashlib
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

    def __init__(self, inner: Any, telemetry: bool = False) -> None:
        self.inner = inner
        self.by_tool: Counter[str] = Counter()
        self.by_level: dict[int, Counter[str]] = {}
        self.picks: list[tuple[int, int, str, bool]] = []  # (action, level, tool, primary_owns)
        self._n = 0
        # --- per-action telemetry (optional; the "can the harness tell it is lost" arm) ---
        # ⛔ RAW frame, every layer, hashed by this recorder — NOT `frame_2d`, which takes
        # layer 0 and is known to read a STALE layer at level transitions (rule 7o). A
        # novelty signal computed off a stale layer would fire spuriously at exactly the
        # moment the label changes, which is the one place it must not.
        self.telemetry = telemetry
        self.tool_names: list[str] = []
        self.tel: dict[str, list[Any]] = {k: [] for k in
                                          ("level", "tool", "since_progress", "n_seen",
                                           "nchanged", "cx", "cy")}
        self.novel_raw: list[str] = []
        self._seen_raw: set[str] = set()
        self._prev_raw: Any = None
        self._prev_level = -1

    def __getattr__(self, item: str) -> Any:
        return getattr(self.inner, item)

    def is_done(self, frames: list[Any], obs: Any) -> bool:
        return self.inner.is_done(frames, obs)

    def _record(self, obs: Any, level: int, who: str) -> None:
        """Append one action's frame-derived telemetry. Costs one md5 and one compare.

        Purpose: make the candidate "does the run itself know it is lost" signals
        computable OFFLINE, from quantities available at runtime and nothing else.
        Expected feedback: `novel_raw` and `nchanged` are the tool-INDEPENDENT twins of
        the harness's own `_since_progress`, which is measured with the ACTIVE tool's
        state identity and therefore not comparable across tools.
        """
        import numpy as _np  # noqa: PLC0415

        raw = getattr(obs, "frame", None)
        grid = None
        if raw is not None:
            try:
                grid = _np.asarray(raw)
            except Exception:  # noqa: BLE001
                grid = None
        if level != self._prev_level:
            self._seen_raw.clear()      # novelty is PER LEVEL, as the harness's own is
            self._prev_raw = None
            self._prev_level = level
        nchanged, cx, cy = -1, -1, -1
        if grid is not None:
            h = hashlib.md5(_np.ascontiguousarray(grid).tobytes()).hexdigest()[:12]
            self.novel_raw.append("0" if h in self._seen_raw else "1")
            self._seen_raw.add(h)
            if self._prev_raw is not None and self._prev_raw.shape == grid.shape:
                diff = self._prev_raw != grid
                nchanged = int(diff.sum())
                if nchanged:
                    idx = _np.argwhere(diff)[:, -2:]
                    cy, cx = (int(idx[:, 0].mean()), int(idx[:, 1].mean()))
            self._prev_raw = grid
        else:
            self.novel_raw.append("0")
        if who not in self.tool_names:
            self.tool_names.append(who)
        self.tel["level"].append(level)
        self.tel["tool"].append(self.tool_names.index(who))
        self.tel["since_progress"].append(int(getattr(self.inner, "_since_progress", -1)))
        self.tel["n_seen"].append(len(getattr(self.inner, "_seen_states", ()) or ()))
        self.tel["nchanged"].append(nchanged)
        self.tel["cx"].append(cx)
        self.tel["cy"].append(cy)

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
        if self.telemetry:
            self._record(obs, level, who)
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

    def telemetry_report(self) -> dict[str, Any]:
        """Columnar per-action telemetry, or {} when telemetry was not requested."""
        if not self.telemetry:
            return {}
        return {"tool_names": self.tool_names, "novel_raw": "".join(self.novel_raw), **self.tel}


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--titles", required=True)
    p.add_argument("--drop", required=True,
                   help="comma-separated tool names to remove, or 'none' for the control arm")
    p.add_argument("--only", default="",
                   help="KEEP only this tool (forced-alone). Mutually exclusive with --drop.")
    p.add_argument("--agent", default="unified")
    p.add_argument("--max-actions", type=int, default=4000)
    p.add_argument("--out", required=True)
    p.add_argument("--telemetry", action="store_true",
                   help="record per-action frame telemetry (novelty, change size, centroid)")
    args = p.parse_args()

    full = [t.name for t in _UNPATCHED()]
    drop = args.drop.strip()

    # --- forced-alone: keep exactly one tool -------------------------------------------
    # ⛔ WHY THIS LIVES HERE AND NOT IN `scripts/_solo_tool.py`. That script hand-rolls its
    # own env loop — it passes an ACCUMULATING frames list where `run_game` passes `[]`,
    # honours no `restart_on_game_over`, and reports levels but never a game_score. Rule 7aj
    # clause 1 exists because a hand-rolled loop clears FOUR bp35 boards where the scorer
    # clears five, so its numbers cannot be compared with an arm measured through the
    # scorer. Forcing the registry to one tool inside THIS runner reuses `run_game`
    # unchanged, so the solo number and the harness number are the same measurement.
    only = args.only.strip()
    if only:
        if drop != "none":
            print("⛔ REFUSING: --only and --drop are mutually exclusive.", flush=True)
            return 1
        if only not in full:
            print(f"⛔ REFUSING: '{only}' is not in the registry. Names: {sorted(full)}",
                  flush=True)
            return 1

        def keep_one() -> list[Any]:
            return [t for t in _UNPATCHED() if t.name == only]

        registry.default_tools = keep_one
        after = [t.name for t in registry.default_tools()]
        if after != [only]:
            print(f"⛔ REFUSING: the registry is {after}, not exactly ['{only}']", flush=True)
            return 1
        drop = f"!only:{only}"
    elif drop != "none":
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
            rec = OwnershipRecorder(_make_agent(args.agent, game_id=env_info.game_id),
                                    telemetry=args.telemetry)
            holder["rec"] = rec
            return rec

        result = run_game(arcade, env_info.game_id, env_info.baseline_actions,
                          agent_name=args.agent, max_actions=args.max_actions,
                          adapter_factory=factory)
        result["title"] = env_info.title or env_info.game_id
        result["ownership"] = holder["rec"].report()
        if args.telemetry:
            result["telemetry"] = holder["rec"].telemetry_report()
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
