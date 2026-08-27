"""Measure the rail-cart peg tool: what it SEES, and what it SOLVES.

Two modes, and both are needed — a board read correctly can still be planned wrongly, and a plan
that works in a simulator can still lose to the engine's animation lag.

  read   render every level of the sample game straight from its own module (no engine, no
         actions, nothing stepped) and compare the tool's reading of each opening frame against
         the board the game's data declares. Ground truth here is DEV-TIME only: the tool never
         sees any of it.
  solve  drive the live engine with this tool alone and report levels and actions.
  bids   the highest bid this tool makes on EVERY sample game while the standard tool set plays
         them. Selectivity is a property of the tool SET, not of one tool: a tool that bids on a
         board it cannot solve takes the turn from the tool that can. Anything but 0.00 away from
         this tool's own game is a defect.

⛔ Neither replaces `scripts/harness_probe.py`. The harness is what is scored; this is what says
WHY a number is what it is.
"""

from __future__ import annotations

import importlib.util
import pathlib
import sys

sys.path.insert(0, "src")

import numpy as np

ROOT = pathlib.Path(__file__).resolve().parent.parent
GAME = "lf52"

# Ground-truth reading of a level's own layout literal. The game declares each cell as a list of
# component names; these two predicates are the engine's own legality rules, transcribed.
_PIECE = "fozwvlovdui"
_BLOCK = "dgxfozncuiz"
_HOLE = "hupkpseyuim"
_DECK = "hupkpseyuim2"
_RAIL = "kraubslpehi"


def _load(path: pathlib.Path):
    spec = importlib.util.spec_from_file_location(f"_game_{path.stem}", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def truth(mod, level: int) -> dict[str, set]:
    """Cells of each kind, in (row, col), as the level's own data declares them."""
    g = mod.kciatvszkc[f"grid{level}"]
    out = {k: set() for k in ("sockets", "rails", "carts", "cargo", "obstacles", "pieces")}
    for r, line in enumerate(g.ojilieuwrah):
        for c, ch in enumerate(line):
            if ch == " ":
                continue
            names = g.vyebgdxovnm[ch]
            cell = (r, c)
            if any(n.startswith(_RAIL) for n in names) or _DECK in names:
                out["rails"].add(cell)
            if _DECK in names:
                out["carts"].add(cell)
                if _BLOCK in names:
                    out["cargo"].add(cell)
            elif _BLOCK in names:
                out["obstacles"].add(cell)
            elif any(n == _HOLE for n in names):
                out["sockets"].add(cell)
            for n in names:
                if n.startswith(_PIECE):
                    out["pieces"].add(cell)
    return out


def read_mode() -> None:
    from admorphiq.tools.railpeg import read_board

    src = next(iter(sorted((ROOT / "environment_files" / GAME).rglob("*.py"))))
    mod = _load(src)
    bad = 0
    for level in range(1, 11):
        st = mod.equnaohchtj()
        st.whtqurkphir = level
        st.qjwmwkhrml()
        st.vpanmnowjy()
        frame = np.asarray(st.vclswpkbjs()).astype(np.int16)
        ox, oy = st.hncnfaqaddg.cdpcbbnfdp
        board = read_board(frame)
        if board is None:
            print(f"L{level}: NO BOARD")
            bad += 1
            continue
        # The tool's cell (0,0) is wherever its lattice phase landed; map it onto the game's.
        dr = (board.oy - (oy + 1)) // board.pitch
        dc = (board.ox - (ox + 1)) // board.pitch
        def w(cells):
            return {(r + dr, c + dc) for r, c in cells}
        t = truth(mod, level)
        vis = w(board.window)
        got = {"sockets": w(board.sockets) - w(board.pieces),
               "rails": w(board.rails), "carts": w(board.carts),
               "cargo": w(board.cargo), "obstacles": w(board.obstacles),
               "pieces": w(board.pieces)}
        # A socket holding a piece is declared as a socket by the game and as both here.
        want = {k: (v & vis) for k, v in t.items()}
        want["sockets"] = want["sockets"] - want["pieces"]
        line = [f"L{level} pitch={board.pitch}"]
        for k in ("sockets", "rails", "carts", "cargo", "obstacles", "pieces"):
            miss = sorted(want[k] - got[k])
            extra = sorted(got[k] - want[k])
            mark = "ok" if not miss and not extra else f"MISS{miss}/EXTRA{extra}"
            if mark != "ok":
                bad += 1
            line.append(f"{k}={len(got[k])}/{len(want[k])} {mark}")
        print("  ".join(line))
    print("PERCEPTION:", "clean" if not bad else f"{bad} disagreements")


def solve_mode(cap: int) -> None:
    from arc_agi import Arcade, OperationMode

    from admorphiq.harness.loop import UnifiedAgent
    from admorphiq.tools.railpeg import RailPegTool

    def _no_llm(*_a, **_k):
        raise RuntimeError("LLM-free")

    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    info = next(i for i in arcade.get_environments()
                if (i.title or i.game_id).lower().startswith(GAME))
    env = arcade.make(info.game_id)
    obs = env.reset()
    agent = UnifiedAgent([RailPegTool()], _no_llm, giveup=cap, stall=80, ctx_budget=6000)
    frames = [obs]
    levels = 0
    marks: list[tuple[int, int]] = []
    step = 0
    for step in range(cap):
        if agent.is_done(frames, obs):
            break
        act = agent.choose_action(frames, obs)
        data = act.action_data.model_dump() if getattr(act, "action_data", None) else None
        obs = env.step(act, data=data) if data else env.step(act)
        frames.append(obs)
        now = int(getattr(obs, "levels_completed", levels) or 0)
        if now != levels:
            marks.append((now, step + 1))
            levels = now
    print(f"ALONE: {levels} levels in {step + 1} actions   clears at {marks}")


def bids_mode(steps: int) -> None:
    from arc_agi import Arcade, OperationMode

    from admorphiq.harness.loop import UnifiedAgent
    from admorphiq.harness.registry import default_tools
    from admorphiq.tools.railpeg import RailPegTool

    def _no_llm(*_a, **_k):
        raise RuntimeError("LLM-free")

    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    seen: set[str] = set()
    envs: list[tuple[str, str]] = []
    for info in arcade.get_environments():
        title = (info.title or info.game_id).split("-")[0].lower()
        if title not in seen:
            seen.add(title)
            envs.append((title, info.game_id))
    worst = 0.0
    for title, game_id in sorted(envs):
        env = arcade.make(game_id)
        obs = env.reset()
        probe = RailPegTool()
        agent = UnifiedAgent(default_tools(), _no_llm, giveup=steps, stall=80, ctx_budget=6000)
        frames = [obs]
        top = 0.0
        for _ in range(steps):
            top = max(top, float(probe.detect([], obs)))
            if agent.is_done(frames, obs):
                break
            act = agent.choose_action(frames, obs)
            data = act.action_data.model_dump() if getattr(act, "action_data", None) else None
            obs = env.step(act, data=data) if data else env.step(act)
            frames.append(obs)
        flag = "" if (top == 0.0 or title == GAME) else "   <-- BIDS ELSEWHERE"
        if title != GAME:
            worst = max(worst, top)
        print(f"{title}  max bid {top:.2f}{flag}")
    print(f"SELECTIVITY: highest bid away from {GAME} = {worst:.2f}")


def main() -> None:
    mode = sys.argv[1] if len(sys.argv) > 1 else "read"
    if mode == "read":
        read_mode()
    elif mode == "bids":
        bids_mode(int(sys.argv[2]) if len(sys.argv) > 2 else 80)
    else:
        solve_mode(int(sys.argv[2]) if len(sys.argv) > 2 else 1500)


if __name__ == "__main__":
    main()
