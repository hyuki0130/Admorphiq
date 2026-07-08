"""Composed orchestration loop: the LLM picks a tool config, runs it, adapts.

The runtime story (single offline model orchestrating Claude-built tools): for a
game, gemma4-31b reads the observable signature + the tool menu, picks a tool
CONFIG, the harness RUNS it (scripts/score_efficiency.py as a subprocess),
reports the score back, and the model picks the NEXT config with that feedback —
up to K rounds, keeping the best. Game-agnostic (no game ids); the tools are the
generic primitives Claude built. Run on the Kaggle-matched VM.

Tool configs = runnable agent+flag combinations:
  graph            : --agent graph_frontier
  graph_dealias    : graph_frontier + GF_DEALIAS=1   (hidden-state)
  graph_deadsig    : graph_frontier + GF_DEAD_SIG=1  (efficiency)
  paint_flood      : --agent paint_flood             (click-fills-region)
  world_model      : --agent worldmodel              (learnable + goal)
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import urllib.request
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))

CONFIGS = {
    "graph": ("graph_frontier", {}),
    "graph_dealias": ("graph_frontier", {"GF_DEALIAS": "1"}),
    "graph_deadsig": ("graph_frontier", {"GF_DEAD_SIG": "1"}),
    "paint_flood": ("paint_flood", {}),
    "world_model": ("worldmodel", {}),
}

MENU = """Tool configs (pick ONE to run next):
- graph: navigation/state-space via transition-graph frontier BFS (high avatar_mobility).
- graph_dealias: graph + hidden-state de-aliasing (use when nondeterminism is high).
- graph_deadsig: graph + skip inert action classes (efficiency).
- paint_flood: click fills a background region with one color (verify it's really a fill game).
- world_model: learn transitions + plan toward a progress measure (deterministic, learnable)."""

SYS = (
    "You orchestrate an ARC-AGI-3 agent by choosing tool configs. Given the game's observable "
    "signature, the menu, and results of configs already tried, choose the next config to run. "
    'Output ONLY JSON: {"config": "<name>", "why": "<short>"}.'
)


def _signature(game: str) -> str:
    import hashlib
    d = np.load(REPO / "data" / "transitions" / "train" / f"{game}.npz", allow_pickle=True)
    fr, ac, nf = d["frames"], d["actions"], d["next_frames"]
    n = len(ac)
    changed = np.array([int((fr[i] != nf[i]).sum()) for i in range(n)])
    seen: dict = {}
    nd = pairs = 0
    for i in range(n):
        k = (hashlib.md5(fr[i].tobytes()).hexdigest()[:8], int(ac[i]))
        h = hashlib.md5(nf[i].tobytes()).hexdigest()[:8]
        if k in seen:
            pairs += 1
            nd += seen[k] != h
        else:
            seen[k] = h
    simple_small = simple_n = 0
    for i in range(n):
        if int(ac[i]) < 4 and changed[i] > 0:
            simple_n += 1
            ys, xs = np.where(fr[i] != nf[i])
            if changed[i] <= 40 and (ys.max()-ys.min()+1)*(xs.max()-xs.min()+1) <= 400:
                simple_small += 1
    return (
        f"avg_changed_cells={changed[changed>0].mean():.0f}; "
        f"click_action_fraction={float(np.mean([a>=5 for a in ac])):.2f}; "
        f"avatar_mobility={simple_small/simple_n if simple_n else 0:.2f}; "
        f"nondeterminism={nd/max(1,pairs):.2f}"
    )


def _pick(model: str, host: str, sig: str, tried: list[dict]) -> str:
    tried_str = "; ".join(f"{t['config']}->lvl{t['levels']}(score {t['score']:.4f})" for t in tried) or "none yet"
    user = f"{MENU}\n\nSIGNATURE: {sig}\nALREADY TRIED: {tried_str}\n\nNext config?"
    body = {
        "model": model, "stream": False, "think": False,
        "messages": [{"role": "system", "content": SYS}, {"role": "user", "content": user}],
        "options": {"temperature": 0.0, "num_ctx": 8192, "num_predict": 200},
    }
    req = urllib.request.Request(f"{host}/api/chat", data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"}, method="POST")
    import re
    with urllib.request.urlopen(req, timeout=300) as r:
        txt = json.loads(r.read())["message"]["content"]
    m = re.search(r'"config"\s*:\s*"(\w+)"', txt)
    return m.group(1) if m and m.group(1) in CONFIGS else "graph"


def _run(game: str, config: str, budget: int) -> tuple[int, float]:
    import os
    agent, env_extra = CONFIGS[config]
    env = {**os.environ, "GF_GIVEUP": str(budget), **env_extra}
    out = f"/tmp/orch_{game}_{config}.json"
    subprocess.run(
        [sys.executable, str(REPO / "scripts" / "score_efficiency.py"),
         "--agent", agent, "--titles", game, "--max-actions", str(budget), "--out", out],
        env=env, capture_output=True, timeout=3600,
    )
    try:
        g = json.load(open(out))["games"][0]
        return int(g["levels_completed"]), float(g["game_score"])
    except Exception:
        return 0, 0.0


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="gemma4:31b-it-q8_0")
    ap.add_argument("--game", required=True)
    ap.add_argument("--host", default="http://localhost:11434")
    ap.add_argument("--rounds", type=int, default=3)
    ap.add_argument("--budget", type=int, default=8000)
    a = ap.parse_args()
    sig = _signature(a.game)
    print(f"game={a.game} sig=[{sig}]", flush=True)
    tried: list[dict] = []
    best = (0, 0.0, None)
    for r in range(a.rounds):
        cfg = _pick(a.model, a.host, sig, tried)
        if any(t["config"] == cfg for t in tried):  # avoid repeats
            cfg = next((c for c in CONFIGS if not any(t["config"] == c for t in tried)), cfg)
        lvl, score = _run(a.game, cfg, a.budget)
        tried.append({"config": cfg, "levels": lvl, "score": score})
        print(f"  round {r}: {cfg} -> levels={lvl} score={score:.4f}", flush=True)
        if (lvl, score) > (best[0], best[1]):
            best = (lvl, score, cfg)
        if lvl > 0:
            break
    print(f"BEST: config={best[2]} levels={best[0]} score={best[1]:.4f}", flush=True)


if __name__ == "__main__":
    main()
