# %% [markdown]
# # Admorphiq — R55 code-REPL bench kernel (ReplAgent + real Qwen3.6-27B-FP8)
#
# Round-1-second-half bench: gives `ReplAgent` its first real-LLM run and writes
# full observability diagnostics. It:
#  1. Probes the GPU + installs the arc wheels and vLLM offline (from mounts).
#  2. Boots a vLLM OpenAI api_server SUBPROCESS in the background with the
#     measured-good config (TRITON_ATTN, no fp8 KV, enforce-eager) and health-
#     polls it.
#  3. Imports our package (walk-resolver + ARC_AGENTS_DIR shim), builds an
#     OFFLINE Arcade over the bundled environment_files.
#  4. Runs `ReplAgent` (OpenAI-compat client -> local vLLM) on five games —
#     su15, ls20 (sanity) + bp35, dc22, g50t (walls) — each capped at 150
#     actions AND 600s wall-clock, sequentially, with per-game try/except.
#  5. Writes per-game diagnostics JSON + the FULL transcript JSONL, prints a
#     one-line summary per game, and ends with a grep-able REPL_BENCH_SUMMARY.
#
# The serving config is the measured PREFLIGHT result (round page r55, 2026-07-14):
# --kv-cache-dtype fp8 forces the broken offline flashinfer path, so we serve
# bf16 KV + TRITON_ATTN + FLASHINFER_SAMPLER off. Every Kaggle-only path is
# guarded so this file also imports cleanly off Kaggle (local lint / tests).

# %%
import glob
import json
import os
import subprocess
import sys
import time
from urllib.request import urlopen

ON_KAGGLE = os.path.isdir("/kaggle/input")
KAGGLE_WORKING = "/kaggle/working"

# Bench parameters.
BENCH_GAMES = ["su15", "ls20", "bp35", "dc22", "g50t"]
MAX_ACTIONS = 150
WALL_S = 600.0
VLLM_PORT = 8199
VLLM_MODEL_NAME = "qwen"
SERVER_BOOT_TIMEOUT_S = 1200.0


# %%
def env_probe() -> None:
    """Print the actual GPU (the 27B needs the RTX PRO 6000, not the P100)."""
    try:
        smi = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader"],
            capture_output=True, text=True, timeout=30,
        )
        print(f"[env-probe] GPU: {smi.stdout.strip() or smi.stderr.strip()}", flush=True)
    except Exception as exc:  # noqa: BLE001
        print(f"[env-probe] nvidia-smi unavailable: {exc}", flush=True)


def _find_dir(name: str, root: str = "/kaggle/input", max_depth: int = 6) -> str:
    """Walk /kaggle/input (depth-capped) for a directory NAMED `name`."""
    if not os.path.isdir(root):
        return os.path.join(root, name)
    root_depth = root.rstrip("/").count("/")
    for cur, dirs, _files in os.walk(root):
        if cur.rstrip("/").count("/") - root_depth >= max_depth:
            dirs[:] = []
            continue
        if name in dirs:
            return os.path.join(cur, name)
    return os.path.join(root, name)


def _find_model_dir() -> str:
    """Locate the Qwen weights: a dir under /kaggle/input holding config.json
    whose path mentions qwen."""
    for cur, _dirs, files in os.walk("/kaggle/input"):
        if "config.json" in files and "qwen" in cur.lower():
            return cur
    raise RuntimeError("Qwen model dir (config.json) not found under /kaggle/input")


def install_wheels_offline() -> None:
    """Install the arc wheels + vLLM from the attached mounts (no internet)."""
    wheels_dir = _find_dir("arc_agi_3_wheels")
    arc_wheels = sorted(glob.glob(os.path.join(wheels_dir, "*.whl")))
    if arc_wheels:
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "--no-index", "--no-deps", *arc_wheels])
        print(f"[install] arc: {len(arc_wheels)} wheel(s)")
    else:
        print(f"[install] no arc wheels under {wheels_dir}; assuming preinstalled")

    # vLLM: gather every dir that holds a vllm*.whl and use them as find-links.
    vllm_wheels = glob.glob("/kaggle/input/**/vllm*.whl", recursive=True)
    link_dirs = sorted({os.path.dirname(w) for w in vllm_wheels})
    if link_dirs:
        find_link_args = []
        for d in link_dirs:
            find_link_args += ["--find-links", d]
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "--no-index", *find_link_args, "vllm"])
        print(f"[install] vLLM from {len(link_dirs)} link dir(s)")
    else:
        print("[install] no vLLM wheels found; assuming preinstalled")


# %%
def boot_vllm_server(model_dir: str) -> subprocess.Popen:
    """Start the vLLM OpenAI api_server subprocess with the measured-good config.

    bf16 KV cache (NOT fp8 — that forces the broken offline flashinfer prefill),
    TRITON_ATTN, flashinfer sampler off, spawn multiproc. enforce-eager keeps the
    boot inside budget (CUDA-graph capture is slow).
    """
    env = os.environ.copy()
    env["VLLM_ATTENTION_BACKEND"] = "TRITON_ATTN"
    env["VLLM_USE_FLASHINFER_SAMPLER"] = "0"
    env["VLLM_WORKER_MULTIPROC_METHOD"] = "spawn"
    cmd = [
        sys.executable, "-m", "vllm.entrypoints.openai.api_server",
        "--model", model_dir,
        "--served-model-name", VLLM_MODEL_NAME,
        "--max-model-len", "131072",
        "--enforce-eager",
        "--gpu-memory-utilization", "0.92",
        "--port", str(VLLM_PORT),
    ]
    print(f"[vllm] launching: {' '.join(cmd)}", flush=True)
    log = open(os.path.join(KAGGLE_WORKING, "vllm_server.log"), "w")  # noqa: SIM115
    return subprocess.Popen(cmd, env=env, stdout=log, stderr=subprocess.STDOUT)


def wait_for_server(port: int, timeout_s: float) -> None:
    """Poll /v1/models until the server answers (or raise after timeout)."""
    url = f"http://127.0.0.1:{port}/v1/models"
    deadline = time.monotonic() + timeout_s
    last = ""
    while time.monotonic() < deadline:
        try:
            with urlopen(url, timeout=10) as r:
                if r.status == 200:
                    print(f"[vllm] healthy after {time.monotonic() - (deadline - timeout_s):.0f}s",
                          flush=True)
                    return
        except Exception as exc:  # noqa: BLE001
            last = repr(exc)
        time.sleep(5)
    raise RuntimeError(f"vLLM server not healthy within {timeout_s}s: {last}")


# %%
def _ensure_admorphiq_importable() -> None:
    try:
        import admorphiq  # noqa: F401
        return
    except ImportError:
        pass
    if os.path.isdir("/kaggle/input"):
        for cur, dirs, _files in os.walk("/kaggle/input"):
            if cur.count("/") > 8:
                dirs[:] = []
                continue
            if "admorphiq" in dirs and os.path.isfile(
                    os.path.join(cur, "admorphiq", "__init__.py")):
                sys.path.insert(0, cur)
                try:
                    import admorphiq  # noqa: F401
                    return
                except ImportError:
                    pass


def _target_game_ids(arcade) -> list[str]:
    """Filter the offline environments down to the five bench titles."""
    env_infos = getattr(arcade, "available_environments", None) or arcade.get_environments()
    out: list[str] = []
    for info in env_infos:
        hay = f"{info.game_id} {getattr(info, 'title', '') or ''}".lower()
        if any(t in hay for t in BENCH_GAMES):
            out.append(info.game_id)
    return out


def run_bench() -> dict:
    """Run ReplAgent on the five bench games; write diagnostics + transcripts."""
    from arc_agi import Arcade, GameAction, OperationMode

    from admorphiq.repl_agent.agent import OpenAICompatClient, ReplAgent
    from admorphiq.repl_agent.bench import run_game
    from admorphiq.repl_agent.transcript import TranscriptRecorder

    os.environ["REPL_LLM_BASE_URL"] = f"http://127.0.0.1:{VLLM_PORT}/v1"
    os.environ["REPL_LLM_MODEL"] = VLLM_MODEL_NAME
    os.environ.setdefault("REPL_SANDBOX_TIMEOUT", "30")

    diag_dir = os.path.join(KAGGLE_WORKING, "diagnostics")
    tr_dir = os.path.join(KAGGLE_WORKING, "transcripts")
    os.makedirs(diag_dir, exist_ok=True)
    os.makedirs(tr_dir, exist_ok=True)

    envs_dir = _find_dir("environment_files")
    arcade = Arcade(operation_mode=OperationMode.OFFLINE, environments_dir=envs_dir)
    game_ids = _target_game_ids(arcade)
    print(f"[bench] games: {game_ids}", flush=True)

    summary: dict[str, dict] = {}
    for game_id in game_ids:
        try:
            env = arcade.make(game_id)
            if env is None:
                print(f"[bench] {game_id}: make() -> None; skipping", flush=True)
                continue
            recorder = TranscriptRecorder(os.path.join(tr_dir, f"{game_id}.jsonl"))
            agent = ReplAgent(OpenAICompatClient(), recorder=recorder)
            diag = run_game(env, agent, max_actions=MAX_ACTIONS, wall_s=WALL_S,
                            reset_action=GameAction.RESET)
            recorder.close()
        except Exception as exc:  # noqa: BLE001 — one game never kills the bench
            from admorphiq.repl_agent.bench import GameDiagnostics
            diag = GameDiagnostics(game_id=game_id, terminal_reason="error",
                                   error=f"{type(exc).__name__}: {exc}")
        with open(os.path.join(diag_dir, f"{game_id}.json"), "w") as f:
            json.dump(diag.to_dict(), f, indent=2)
        summary[game_id] = {
            "levels": diag.levels, "actions": diag.actions, "wall_s": diag.wall_s,
            "llm_calls": diag.llm_calls, "terminal": diag.terminal_reason,
            "parse_failures": diag.parse_failures,
            "governor_rejections": diag.governor_rejections,
            "sandbox_errors": diag.sandbox_errors, "error": diag.error,
        }
        print(f"[bench] {game_id}: levels={diag.levels} actions={diag.actions} "
              f"wall={diag.wall_s}s llm={diag.llm_calls} term={diag.terminal_reason} "
              f"parse_fail={diag.parse_failures} gov_rej={diag.governor_rejections} "
              f"sbx_err={diag.sandbox_errors}", flush=True)
    return summary


# %%
def main() -> None:
    env_probe()
    install_wheels_offline()
    _ensure_admorphiq_importable()
    os.environ["ARC_AGENTS_DIR"] = _find_dir("ARC-AGI-3-Agents")
    server = boot_vllm_server(_find_model_dir())
    try:
        wait_for_server(VLLM_PORT, SERVER_BOOT_TIMEOUT_S)
        summary = run_bench()
    finally:
        server.terminate()
        try:
            server.wait(timeout=30)
        except Exception:  # noqa: BLE001
            server.kill()
    print("REPL_BENCH_SUMMARY " + json.dumps(summary, sort_keys=True), flush=True)


# %%
if ON_KAGGLE:
    main()
else:
    print("Off-Kaggle import: skipping the repl bench run.")
