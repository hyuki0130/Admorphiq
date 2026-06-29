# %% [markdown]
# # Admorphiq — ARC-AGI-3 Kaggle Submission (online world-model agent)
#
# Always-ready, valid submission notebook. It:
#  1. Installs the arc wheels offline (from the Kaggle Data tab).
#  2. Puts the official `agents` package on `sys.path`.
#  3. Registers our `KaggleWorldModelAgent` — the online world-model agent.
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
# namespace shim in local dev) — see admorphiq._agents_shim. KaggleWorldModelAgent
# composes the online world-model agent (admorphiq.world_model_agent.WorldModelAgent):
# it loads NO weights — it learns each game's dynamics at test time, so it
# transfers to the private games. (KaggleBCAgent remains available for the BC
# policy, but the world-model is the deployed card per the R27 transfer finding.)
from admorphiq.kaggle_world_model_agent import KaggleWorldModelAgent  # noqa: E402

try:
    # On Kaggle the full package is present and provides the shared registry.
    from agents import AVAILABLE_AGENTS  # noqa: E402
except ImportError:
    # Local dev with the light shim: the registry only matters for the
    # Kaggle-only run path, so an empty dict is enough to import cleanly.
    AVAILABLE_AGENTS = {}

AGENT_KEY = "admorphiq"
AVAILABLE_AGENTS[AGENT_KEY] = KaggleWorldModelAgent
print(f"Registered agent '{AGENT_KEY}' -> {KaggleWorldModelAgent.__name__}")


# %%
def run_offline_submission() -> None:
    """Boot OFFLINE Arcade, drive the agent over every game, write submission.json."""
    from arc_agi import Arcade, OperationMode

    # Force OFFLINE deterministically. The Arcade constructor lets an
    # OPERATION_MODE=competition env var override the constructor arg, and
    # competition mode needs the network — impossible with internet disabled.
    os.environ["OPERATION_MODE"] = "offline"

    arc = Arcade(
        operation_mode=OperationMode.OFFLINE,
        environments_dir=KAGGLE_ENVS_DIR,
    )

    games = [env.game_id for env in arc.get_environments()]
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


# %%
if ON_KAGGLE:
    run_offline_submission()
else:
    print("Off-Kaggle import: skipping offline submission run.")
    print("Use scripts/smoke_kaggle_agent.py for a local REMOTE-mode smoke test.")
