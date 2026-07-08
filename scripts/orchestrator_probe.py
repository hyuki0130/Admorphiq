"""Runtime-brain validation: can the local model pick the right FIRST tool?

Tests the KNOWLEDGE->BRAIN link of the self-improving harness
(.wiki/wiki/architecture_self_improving_agent.md): given a game's observable
signals + the tool_selector decision table, does the offline model choose a
sensible first tool? This is the cheapest check of whether a weak local model
can orchestrate the tools Claude builds — before wiring the full loop.

Game-agnostic: the model sees the first frame (hex grid) + available actions +
a small auto-derived signature (movement? click-responsive? palette). No game
ids. Run on the VM against ollama (gemma4-31b / gpt-oss-120b).
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))

# The tool menu the model must choose from (mirrors tool_selector.md rows).
TOOL_MENU = """Available tools (pick the FIRST to run):
- graph_frontier: HIGH avatar_mobility (small object translates under directional actions) =>
  navigation/state-space; walls block. Prefer over paint_flood when avatar_mobility is high even
  if avg_changed_cells is large.
- paint_flood: an ACTION6 click fills a connected region with one color; goal is a coloring.
- dealias_graph: same frame+action gives DIFFERENT results (hidden timer/off-screen) -> de-alias then graph.
- world_model_plan: transitions learnable + a monotone progress measure (count/order/fill).
- cnn_rl: reactive/timing game, dense small changes, steering under pressure.
- dead_signature: always-on efficiency prior (stop re-probing inert action classes)."""

SYS = (
    "You are the orchestrator brain of an ARC-AGI-3 agent. Given a game's observable signals "
    "and the tool menu, choose the single best FIRST tool to run. Output ONLY JSON: "
    '{"tool": "<name>", "why": "<short>"}.'
)


def _first_frame(game: str) -> np.ndarray:
    d = np.load(REPO / "data" / "transitions" / "train" / f"{game}.npz", allow_pickle=True)
    return np.asarray(d["frames"][0], dtype=np.int16)


def _signature(game: str) -> str:
    """Auto-derive a compact observable signature from the transitions (generic)."""
    d = np.load(REPO / "data" / "transitions" / "train" / f"{game}.npz", allow_pickle=True)
    fr, ac, nf = d["frames"], d["actions"], d["next_frames"]
    n = len(ac)
    changed = np.array([int((fr[i] != nf[i]).sum()) for i in range(n)])
    # nondeterminism: same (state,action) -> different next?
    import hashlib
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
    click_heavy = float(np.mean([a >= 5 for a in ac]))  # ACTION6 index >= 5
    # Movement discriminator (fixes ar25 mis-route): does a SMALL object TRANSLATE
    # under simple directional actions (navigation) vs a big repaint? For each
    # simple-action (idx 0-3) changed transition, is the changed region a small,
    # spatially-compact bbox (an object moved a step)?
    simple_small = simple_n = 0
    for i in range(n):
        if int(ac[i]) < 4 and changed[i] > 0:
            simple_n += 1
            ys, xs = np.where(fr[i] != nf[i])
            bbox = (ys.max() - ys.min() + 1) * (xs.max() - xs.min() + 1)
            # compact + small changed set => object translation, not a repaint
            if changed[i] <= 40 and bbox <= 400:
                simple_small += 1
    mobility = simple_small / simple_n if simple_n else 0.0
    return (
        f"avg_changed_cells={changed[changed > 0].mean():.0f}; "
        f"click_action_fraction={click_heavy:.2f}; "
        f"avatar_mobility={mobility:.2f} (small object translates under directional actions); "
        f"nondeterminism={nd / max(1, pairs):.2f}; "
        f"palette={sorted(set(np.unique(_first_frame(game)).tolist()))}"
    )


def ask(model: str, game: str, host: str) -> dict:
    from admorphiq.ewm.core import serialize_grid
    grid = serialize_grid(_first_frame(game))
    user = (
        f"{TOOL_MENU}\n\nGAME SIGNALS: {_signature(game)}\n\n"
        f"FIRST_FRAME (hex, 64 rows):\n{grid}\n\nPick the first tool."
    )
    body = {
        "model": model,
        "messages": [{"role": "system", "content": SYS}, {"role": "user", "content": user}],
        "stream": False,
        "think": ("low" if "gpt-oss" in model else False),
        "options": {"temperature": 0.0, "num_ctx": 16384, "num_predict": 300},
    }
    req = urllib.request.Request(
        f"{host}/api/chat", data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"}, method="POST",
    )
    with urllib.request.urlopen(req, timeout=300) as r:
        text = json.loads(r.read())["message"]["content"]
    import re
    m = re.search(r"\{.*\}", text, re.DOTALL)
    return json.loads(m.group(0)) if m else {"tool": "?", "why": text[:80]}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="gemma4:31b-it-q8_0")
    ap.add_argument("--games", default="ft09,dc22,su15,ka59,ar25")
    ap.add_argument("--host", default="http://localhost:11434")
    a = ap.parse_args()
    print(f"model={a.model}", flush=True)
    for g in a.games.split(","):
        try:
            pick = ask(a.model, g, a.host)
            print(f"  {g:6s} sig=[{_signature(g)}]", flush=True)
            print(f"         -> {pick.get('tool')}: {pick.get('why', '')[:90]}", flush=True)
        except Exception as exc:  # noqa: BLE001
            print(f"  {g}: ERROR {exc}", flush=True)


if __name__ == "__main__":
    main()
