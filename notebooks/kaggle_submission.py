# %% [markdown]
# # Admorphiq — ARC-AGI-3 Kaggle Submission (graph-frontier agent)
#
# Always-ready, valid submission notebook. It:
#  1. Installs the arc wheels offline (from the Kaggle Data tab).
#  2. Puts the official `agents` package on `sys.path`.
#  3. Registers our `KaggleUnifiedAgent` — the generic tool harness, zero adapters (the LLM-free
#     chained card, measured 0.2771 on the 25-game dev proxy (the chained card
#     alone measures 0.0566 on the same run; adapter ceiling 0.3296).
#     It loads NO weights: it learns each game's dynamics at test time, so the
#     submission needs only the `src` dataset (no weights upload).
#  4. Boots an OFFLINE `Arcade` over the bundled environment files and drives
#     the agent over every environment with a direct make()/agent.main() loop,
#     then writes `/kaggle/working/submission.json` from the closed scorecard.
#
# Why a direct loop and NOT `agents.swarm.Swarm` + `Arcade.listen_and_serve`:
# `Swarm.__init__` constructs its OWN `Arcade()` in NORMAL mode (which fetches
# an anonymous API key over HTTP) and runs the games through that internal
# Arcade — never through a locally-served OFFLINE one. With internet disabled
# that errors, and the `on_scorecard_close` callback that was meant to write
# the submission never fires. The direct OFFLINE loop below is fully offline,
# deterministic, and verified by `scripts/verify_offline_submission.py`.
#
# Every Kaggle-only path is guarded so this file also imports cleanly off
# Kaggle (e.g. during local lint / smoke tests).

# %%
import os
import subprocess
import sys

# Environment probe: which GPU does THIS run actually get? (validation runs
# measured P100 16GB on standalone CLI kernels; the competition rerun machine
# is documented as g4-standard-48 / RTX PRO 6000 96GB — verify, don't assume.)
try:
    _smi = subprocess.run(["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader"],
                          capture_output=True, text=True, timeout=30)
    print(f"[env-probe] GPU: {_smi.stdout.strip() or _smi.stderr.strip()}", flush=True)
except Exception as _e:  # CPU-only session is acceptable; the agent is CPU-based
    print(f"[env-probe] nvidia-smi unavailable: {_e}", flush=True)

# Kaggle mount points are NOT stable across attach methods (web-UI:
# /kaggle/input/<name>; CLI v2 run measured: /kaggle/input/competitions/... and
# /kaggle/input/datasets/...). Stop guessing: WALK /kaggle/input (depth-capped)
# and find each required directory by NAME wherever it mounts.


def _find_dir(name: str, root: str = "/kaggle/input", max_depth: int = 5) -> str:
    if not os.path.isdir(root):
        return os.path.join(root, name)  # off-Kaggle: return a non-existent stub
    root_depth = root.rstrip("/").count("/")
    for cur, dirs, _files in os.walk(root):
        if cur.rstrip("/").count("/") - root_depth >= max_depth:
            dirs[:] = []
            continue
        if name in dirs:
            return os.path.join(cur, name)
    return os.path.join(root, name)


KAGGLE_AGENTS_DIR = _find_dir("ARC-AGI-3-Agents")
KAGGLE_WHEELS_DIR = _find_dir("arc_agi_3_wheels")
KAGGLE_ENVS_DIR = _find_dir("environment_files")
KAGGLE_WORKING = "/kaggle/working"
SUBMISSION_PATH = os.path.join(KAGGLE_WORKING, "submission.json")

ON_KAGGLE = os.path.isdir("/kaggle/input")


# %%
def install_wheels_offline() -> None:
    """Install the arc wheels from the Kaggle Data tab (no internet)."""
    import glob
    import subprocess

    wheels = sorted(glob.glob(os.path.join(KAGGLE_WHEELS_DIR, "*.whl")))
    if not wheels:
        print(f"No wheels found under {KAGGLE_WHEELS_DIR}; assuming preinstalled.")
        return
    subprocess.check_call(
        [sys.executable, "-m", "pip", "install", "--no-index", "--no-deps", *wheels]
    )
    print(f"Installed {len(wheels)} wheel(s) offline.")


# %%
# Import the agent. Locally we import from the installed package; on Kaggle the
# `src` layout is added to the path so the same import works.
def _ensure_admorphiq_importable() -> None:
    try:
        import admorphiq  # noqa: F401

        return
    except ImportError:
        pass
    # Common local / Kaggle dataset src locations.
    # Wherever the dataset mounts, find the dir NAMED admorphiq that holds
    # __init__.py and put its PARENT on sys.path.
    if os.path.isdir("/kaggle/input"):
        for cur, dirs, _files in os.walk("/kaggle/input"):
            if cur.count("/") > 8:
                dirs[:] = []
                continue
            if "admorphiq" in dirs and os.path.isfile(
                os.path.join(cur, "admorphiq", "__init__.py")
            ):
                sys.path.insert(0, cur)
                try:
                    import admorphiq  # noqa: F401

                    return
                except ImportError:
                    pass
    for cand in (
        os.path.join(os.getcwd(), "src"),
        "/kaggle/input/admorphiq-src",       # CLI dataset (zip strips src/)
        "/kaggle/input/admorphiq-src/src",
        "/kaggle/input/admorphiq/src",
        os.path.join(KAGGLE_AGENTS_DIR, "src"),
    ):
        if os.path.isdir(os.path.join(cand, "admorphiq")) and cand not in sys.path:
            sys.path.insert(0, cand)


if ON_KAGGLE:
    install_wheels_offline()

if ON_KAGGLE:
    import glob as _glob

    print("/kaggle/input layout:", sorted(_glob.glob("/kaggle/input/*")))
    print("depth2:", sorted(_glob.glob("/kaggle/input/*/*"))[:20])
    print("resolved:", KAGGLE_AGENTS_DIR, "|", KAGGLE_WHEELS_DIR, "|", KAGGLE_ENVS_DIR)
# The shim consults ARC_AGENTS_DIR first — hand it the walk-resolved path so
# the official `agents` package imports regardless of the mount layout.
os.environ["ARC_AGENTS_DIR"] = KAGGLE_AGENTS_DIR
_ensure_admorphiq_importable()

# Importing the agent installs the `agents` package (real on Kaggle, light
# namespace shim in local dev) — see admorphiq._agents_shim. KaggleGraphFrontierAgent
# composes the graph-frontier agent (admorphiq.graph_frontier_agent): TRAINING-FREE
# region-masked state hashing -> exact observed transition graph -> frontier BFS ->
# segment click candidates. Nothing is learned from the public games, so it is
# transfer-honest by construction (measured: 9-subset 0.0055 vs online-RL from-scratch
# 0.0014; breaks L2 given budget — see .wiki/wiki/rounds/r36_graph-frontier-bfs.md).
# The online-RL card (KaggleOnlineRLAgent) remains available as an alternative.
from admorphiq.kaggle_unified_agent import KaggleUnifiedAgent  # noqa: E402

try:
    # On Kaggle the full package is present and provides the shared registry.
    from agents import AVAILABLE_AGENTS  # noqa: E402
except ImportError:
    # Local dev with the light shim: the registry only matters for the
    # Kaggle-only run path, so an empty dict is enough to import cleanly.
    AVAILABLE_AGENTS = {}

AGENT_KEY = "admorphiq"
# Deployed artifact (2026-08-28): THE GENERIC TOOLS ALONE — zero adapters, zero game ids.
#
# ⛔ This REPLACES detection dispatch, and the reason is measured rather than architectural.
# Full 25 on ceph-build, @4000, same tree, the same day:
#
#     kaggle_detect  (13 adapters + generic fallback)   0.5335
#     kaggle_unified (generic tools alone)              0.8874
#
# The adapters are worse on 23 of 25 games. They were written when the generic fallback scored
# 0.0566 and both routing guards were calibrated against THAT; neither can see that the fallback
# has since overtaken them. Nothing broke — a constant stopped being true.
#
# ⚠️ And the public number is not the argument. The eval is 110 PRIVATE games. An adapter fires on
# a mechanic recognised from the public 25, so a private game carrying none of them gets the
# fallback anyway — which is why raising the public card 5.6x moved the hidden score 0.20 -> 0.18.
# These tools read no game id, no title and no sprite tag; measured transfer across re-rendered
# games is 0.9981 with 13 of 14 IDENTICAL. That is weaker evidence than a different game, and the
# hidden score of this path is UNMEASURED — this notebook is how it gets measured.
#
# The two machines agree on all 25 games (mean 0.8874 both, zero differing), so the number is a
# property of the tools and not of the box. numpy-only on the deployed path: no weights, and the
# harness routes by frame signature whenever the LLM call raises. MEASURED on a Kaggle GPU run
# 2026-08-27 with a real gemma-4-31b behind vLLM: the LLM arm and the signature arm scored
# 0.853963 both, ZERO games differing — so the model changes nothing on these 25 and its absence
# costs nothing here.
AVAILABLE_AGENTS[AGENT_KEY] = KaggleUnifiedAgent
print(f"Registered agent '{AGENT_KEY}' -> {KaggleUnifiedAgent.__name__}")


# %%
def _wait_for_gateway(base_url: str, timeout_s: float = 600.0) -> None:
    """Poll the kaggle_evaluation gateway until it serves /api/games.

    In a REAL competition rerun the hidden games are served by a local gateway
    (which also generates submission.parquet from our actions); it boots
    asynchronously, so wait before asking for its game list. Protocol verified
    against the actively-submitting Duck v12 notebook (2026-07-13): the direct
    offline scorecard-JSON path is NOT a valid submission — the 400 error body
    says files must be submission.parquet generated by kaggle_evaluation.
    """
    import time
    from urllib.request import urlopen

    deadline = time.monotonic() + timeout_s
    last_error = ""
    while time.monotonic() < deadline:
        try:
            with urlopen(f"{base_url}api/games", timeout=10) as response:
                if response.status < 500:
                    return
        except Exception as exc:  # noqa: BLE001
            last_error = repr(exc)
        time.sleep(5)
    raise RuntimeError(f"Kaggle gateway did not become ready: {last_error}")


def run_offline_submission() -> None:
    """Drive the agent over every game — live gateway on a real rerun, bundled
    offline environments otherwise (free validation; writes submission.json as
    a diagnostic only)."""
    from arc_agi import Arcade, OperationMode

    true_submission = os.environ.get("KAGGLE_IS_COMPETITION_RERUN") is not None
    if true_submission:
        # Real rerun: play the HIDDEN games served by the kaggle_evaluation
        # gateway; it records actions and produces submission.parquet itself.
        os.environ.setdefault("ARC_API_KEY", "test-key-123")
        os.environ.setdefault("ARC_BASE_URL", "http://gateway:8001/")
        os.environ.setdefault(
            "RECORDINGS_DIR", os.path.join(KAGGLE_WORKING, "server_recording"))
        os.environ["OPERATION_MODE"] = "competition"
        _wait_for_gateway(os.environ["ARC_BASE_URL"])
        arc = Arcade(
            operation_mode=OperationMode.COMPETITION,
            arc_base_url=os.environ["ARC_BASE_URL"],
            environments_dir="",
        )
    else:
        # Interactive run: bundled environments, fully offline.
        os.environ["OPERATION_MODE"] = "offline"
        arc = Arcade(
            operation_mode=OperationMode.OFFLINE,
            environments_dir=KAGGLE_ENVS_DIR,
        )

    env_infos = getattr(arc, "available_environments", None) or arc.get_environments()
    games = [env.game_id for env in env_infos]
    print(f"Playing {len(games)} environment(s): {games}")

    card_id = arc.open_scorecard(tags=["admorphiq", "bc"])
    print(f"Opened scorecard: {card_id}")

    for game_id in games:
        env = arc.make(game_id, scorecard_id=card_id)
        if env is None:
            print(f"  {game_id}: make() returned None — skipping")
            continue
        agent = AVAILABLE_AGENTS[AGENT_KEY](
            card_id=card_id,
            game_id=game_id,
            agent_name=AGENT_KEY,
            ROOT_URL="",
            record=False,
            arc_env=env,
            tags=["admorphiq", "bc"],
        )
        agent.main()
        last = agent.frames[-1]
        print(
            f"  {game_id}: actions={agent.action_counter} "
            f"state={getattr(last.state, 'name', last.state)} "
            f"levels_completed={last.levels_completed}"
        )

    scorecard = arc.close_scorecard(card_id)
    os.makedirs(KAGGLE_WORKING, exist_ok=True)
    with open(SUBMISSION_PATH, "w") as f:
        f.write(scorecard.model_dump_json() if scorecard is not None else "{}")
    print(f"Wrote submission to {SUBMISSION_PATH}")

    if not true_submission:
        # An interactive run isn't scored, but the submit PRECONDITION checks
        # that the kernel output contains a file named submission.parquet
        # (measured: 400 "Did not find provided Notebook Output File"). The
        # REAL parquet is generated by the kaggle_evaluation gateway during
        # the competition rerun; this placeholder (same schema the actively-
        # submitting Duck v12 notebook writes) only satisfies the check.
        import pandas as pd

        pd.DataFrame(
            [["1_0", "1", True, 1]],
            columns=["row_id", "game_id", "end_of_game", "score"],
        ).to_parquet(os.path.join(KAGGLE_WORKING, "submission.parquet"), index=False)
        print("Wrote placeholder submission.parquet (interactive run).")


# %%
if ON_KAGGLE:
    run_offline_submission()
else:
    print("Off-Kaggle import: skipping offline submission run.")
    print("Use scripts/smoke_kaggle_agent.py for a local REMOTE-mode smoke test.")
