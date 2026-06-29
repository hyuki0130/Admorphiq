# %% [markdown]
# # Admorphiq — ARC-AGI-3 Kaggle Submission (BC policy)
#
# Always-ready, valid submission notebook. It:
#  1. Installs the arc wheels offline (from the Kaggle Data tab).
#  2. Puts the official `agents` package on `sys.path`.
#  3. Registers our `KaggleBCAgent` — the trained behaviour-cloning policy
#     (`models/bc_policy.pt`, auto-updated to the best checkpoint at submit
#     time; override with the `BC_WEIGHTS` env var).
#  4. Boots an OFFLINE `Arcade` over the bundled environment files and serves
#     it locally, runs the agent swarm against every environment, and writes
#     `/kaggle/working/submission.json` from the closed scorecard.
#
# Every Kaggle-only path is guarded so this file also imports cleanly off
# Kaggle (e.g. during local lint / smoke tests).

# %%
import os
import sys

# Kaggle Data-tab mount points (see competition spec).
KAGGLE_AGENTS_DIR = "/kaggle/input/ARC-AGI-3-Agents"
KAGGLE_WHEELS_DIR = "/kaggle/input/arc_agi_3_wheels"
KAGGLE_ENVS_DIR = "/kaggle/input/environment_files"
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
    for cand in (
        os.path.join(os.getcwd(), "src"),
        "/kaggle/input/admorphiq/src",
        os.path.join(KAGGLE_AGENTS_DIR, "src"),
    ):
        if os.path.isdir(os.path.join(cand, "admorphiq")) and cand not in sys.path:
            sys.path.insert(0, cand)


if ON_KAGGLE:
    install_wheels_offline()

_ensure_admorphiq_importable()

# Importing the agent installs the `agents` package (real on Kaggle, light
# namespace shim in local dev) — see admorphiq._agents_shim. KaggleBCAgent
# composes the trained BC policy (admorphiq.bc_agent.BCPolicyAgent).
from admorphiq.kaggle_bc_agent import KaggleBCAgent  # noqa: E402

try:
    # On Kaggle the full package is present and provides the shared registry.
    from agents import AVAILABLE_AGENTS  # noqa: E402
except ImportError:
    # Local dev with the light shim: the registry only matters for the
    # Kaggle-only run path, so an empty dict is enough to import cleanly.
    AVAILABLE_AGENTS = {}

AGENT_KEY = "admorphiq"
AVAILABLE_AGENTS[AGENT_KEY] = KaggleBCAgent
print(f"Registered agent '{AGENT_KEY}' -> {KaggleBCAgent.__name__}")


# %%
def run_offline_submission() -> None:
    """Boot OFFLINE Arcade, serve it, run the swarm, write submission.json."""
    import threading

    from agents.swarm import Swarm
    from arc_agi import Arcade, OperationMode

    host, port = "localhost", 8001
    root_url = f"http://{host}:{port}"

    arc = Arcade(
        operation_mode=OperationMode.OFFLINE,
        environments_dir=KAGGLE_ENVS_DIR,
    )

    def _on_scorecard_close(scorecard) -> None:
        os.makedirs(KAGGLE_WORKING, exist_ok=True)
        with open(SUBMISSION_PATH, "w") as f:
            f.write(scorecard.model_dump_json())
        print(f"Wrote submission to {SUBMISSION_PATH}")

    # Serve the offline environments in a background thread.
    server = threading.Thread(
        target=arc.listen_and_serve,
        kwargs=dict(
            host=host,
            port=port,
            competition_mode=True,
            on_scorecard_close=_on_scorecard_close,
        ),
        daemon=True,
    )
    server.start()

    # Discover every environment the offline Arcade exposes.
    games = [env.game_id for env in arc.get_environments()]
    print(f"Playing {len(games)} environment(s): {games}")

    swarm = Swarm(AGENT_KEY, root_url, games, tags=["admorphiq", "bc"])
    swarm.main()


# %%
if ON_KAGGLE:
    run_offline_submission()
else:
    print("Off-Kaggle import: skipping offline submission run.")
    print("Use scripts/smoke_kaggle_agent.py for a local REMOTE-mode smoke test.")
