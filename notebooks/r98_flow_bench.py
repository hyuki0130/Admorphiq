# %% [markdown]
# # R98 FlowDeflectionDynamics MODEL bench (Kaggle, offline)
#
# The paired model measurement for the third hypothesis family. Per run a fresh
# live env is probed for evidence, the offline model supplies the hypothesis, the
# VERIFIER gates it (UNKNOWN/CONTRADICTED never executes, so a wrong hypothesis
# costs zero actions), and a PASSing hypothesis is compiled and live-executed
# exactly like the oracle gate.
#
# Two modes, both run in this kernel:
#   select — pick among neutrally serialized candidates (the truth + the
#            distinguishable mutants; the inert-slot mutants are excluded because
#            they serialize identically once neutralised)
#   fill   — variant-first: the objective variant, then the gated response-table
#            slots. own_flow and boundary are NEVER asked: both were measured
#            inert, and forcing a choice from absent evidence manufactures a
#            false result.
#
# Contract (FROZEN 2026-08-22, docs/design_r98_family_expansion.md): sp80 idx0
# criterion-level ONLY, one cumulative cap of 20 actions and 3 commits over a
# 9-action certified path, per-model success >= 2 of 3 runs, CONFIRMED = both
# models. Prerequisite already PASSED: the live oracle gate 3/3
# (scripts/rounds/R98/oracle.txt).
#
# Two-model rule: run this kernel TWICE, once per mounted model
# (admorphiq-r98-flow-{gemma4,gptoss}). No one-shot verdicts.
#
# Boot: vLLM api_server on the mounted model, plain completions. This DRIVES the
# live arc env, so the competition environment_files are located and passed via
# ARC_ENVIRONMENTS_DIR. Ship scripts/probe_r98_model_bench.py and the admorphiq
# package in the same working tree.

# %%
import glob
import json
import os
import subprocess
import sys
import time
from urllib.request import urlopen

ON_KAGGLE = os.path.isdir("/kaggle/input")
KAGGLE_WORKING = "/kaggle/working" if ON_KAGGLE else "."
VLLM_PORT = 8199
BOOT_TIMEOUT_S = 2400
MAX_MODEL_LEN = 131072
_MAX_MODEL_LEN_CEIL = 200000
RUNS = int(os.environ.get("R98_RUNS", "3"))

# %%
def _find_dir(name: str, root: str = "/kaggle/input", max_depth: int = 6) -> str:
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


def _find_file(name: str, root: str = "/kaggle/input") -> str:
    for cur, _dirs, files in os.walk(root):
        if name in files:
            return os.path.join(cur, name)
    raise RuntimeError(f"{name} not found under {root}")


def _find_model_dir() -> tuple[str, str]:
    roots = ["/kaggle/input/models", "/kaggle/input"]
    hits: list[str] = []
    for root in roots:
        if not os.path.isdir(root):
            continue
        for cur, _dirs, files in os.walk(root):
            if "config.json" in files and "/models/" in cur:
                hits.append(cur)
        if hits:
            break
    hits = sorted(set(hits))
    if not hits:
        raise RuntimeError("no HF model dir (config.json) under /kaggle/input/models")
    if len(hits) > 1:
        raise RuntimeError(f"ambiguous model dirs: {hits}")
    d = hits[0]
    low = d.lower()
    if "gemma" in low:
        tag = "gemma4"
    elif "qwen" in low:
        tag = "qwen"
    elif "gpt-oss" in low or "gptoss" in low or "gpt_oss" in low:
        tag = "gptoss"
    else:
        tag = "served"
    return d, tag


def install_wheels_offline() -> None:
    wheels_dir = _find_dir("arc_agi_3_wheels")
    arc_wheels = sorted(glob.glob(os.path.join(wheels_dir, "*.whl")))
    if arc_wheels:
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "--no-index", "--no-deps", *arc_wheels])
        print(f"[install] arc: {len(arc_wheels)} wheel(s)", flush=True)
    vllm_wheels = glob.glob("/kaggle/input/**/vllm*.whl", recursive=True)
    link_dirs = sorted({os.path.dirname(w) for w in vllm_wheels})
    if link_dirs:
        find_link_args = []
        for d in link_dirs:
            find_link_args += ["--find-links", d]
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "--no-index", *find_link_args, "vllm"])
        print(f"[install] vLLM from {len(link_dirs)} link dir(s)", flush=True)
    else:
        print("[install] no vLLM wheels found; assuming preinstalled", flush=True)


def _model_max_len(model_dir: str) -> int:
    try:
        with open(os.path.join(model_dir, "config.json")) as f:
            cfg = json.load(f)
        mpe = int(cfg.get("max_position_embeddings") or MAX_MODEL_LEN)
        return min(mpe, _MAX_MODEL_LEN_CEIL)
    except Exception as exc:  # noqa: BLE001
        print(f"[vllm] config max-len read failed ({exc}); default {MAX_MODEL_LEN}", flush=True)
        return MAX_MODEL_LEN


def boot_vllm_server(model_dir: str, served_name: str) -> subprocess.Popen:
    """vLLM OpenAI api_server, R55 measured-good offline config. NO tool-call
    parser — the selection ask is a plain guided-json completion."""
    env = os.environ.copy()
    env["VLLM_ATTENTION_BACKEND"] = "TRITON_ATTN"
    env["VLLM_USE_FLASHINFER_SAMPLER"] = "0"
    env["VLLM_WORKER_MULTIPROC_METHOD"] = "spawn"
    max_len = _model_max_len(model_dir)
    print(f"[vllm] max-model-len={max_len}", flush=True)
    cmd = [
        sys.executable, "-m", "vllm.entrypoints.openai.api_server",
        "--model", model_dir,
        "--served-model-name", served_name,
        "--max-model-len", str(max_len),
        "--enforce-eager",
        "--gpu-memory-utilization", "0.92",
        "--port", str(VLLM_PORT),
    ]
    print(f"[vllm] launching: {' '.join(cmd)}", flush=True)
    log = open(os.path.join(KAGGLE_WORKING, "vllm_server.log"), "w")  # noqa: SIM115
    return subprocess.Popen(cmd, env=env, stdout=log, stderr=subprocess.STDOUT)


def wait_for_server(port: int, timeout_s: float) -> None:
    url = f"http://127.0.0.1:{port}/v1/models"
    deadline = time.monotonic() + timeout_s
    last = ""
    while time.monotonic() < deadline:
        try:
            with urlopen(url, timeout=10) as r:
                if r.status == 200:
                    print("[vllm] healthy", flush=True)
                    return
        except Exception as exc:  # noqa: BLE001
            last = repr(exc)
        time.sleep(5)
    raise RuntimeError(f"vLLM server not healthy within {timeout_s}s: {last}")


# %%
def _gptoss_offline_env() -> None:
    """gpt-oss offline vocab fix (verified with network blocked): openai_harmony
    loads o200k_base/cl100k_base from TIKTOKEN_ENCODINGS_BASE (plain filenames)
    instead of fetching openaipublic.blob.core.windows.net."""
    for root, _dirs, files in os.walk("/kaggle/input"):
        if "o200k_base.tiktoken" in files:
            os.environ["TIKTOKEN_ENCODINGS_BASE"] = root
            break
    else:
        raise RuntimeError("o200k_base.tiktoken not found — attach tiktoken-encodings-offline")
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    from openai_harmony import HarmonyEncodingName, load_harmony_encoding
    enc = load_harmony_encoding(HarmonyEncodingName.HARMONY_GPT_OSS)
    print(f"[preflight] harmony offline OK from {os.environ['TIKTOKEN_ENCODINGS_BASE']} "
          f"tokens={enc.encode('preflight', allowed_special='all')[:3]}", flush=True)


def main() -> None:
    if ON_KAGGLE:
        install_wheels_offline()
        model_dir, served = _find_model_dir()
        print(f"[model] {model_dir} served-name={served}", flush=True)
        if served == "gptoss":
            _gptoss_offline_env()  # BEFORE vLLM boots (env inherited)
        server = boot_vllm_server(model_dir, served)
        wait_for_server(VLLM_PORT, BOOT_TIMEOUT_S)
    else:
        served = os.environ.get("HARNESS_LLM_MODEL", "gemma4")
        server = None

    if ON_KAGGLE:
        probe = _find_file("probe_r98_model_bench.py")
        pkg_dir = os.path.dirname(_find_dir("admorphiq"))
        envs_dir = _find_dir("environment_files")
    else:
        probe = "scripts/probe_r98_model_bench.py"
        pkg_dir = "src"
        envs_dir = "environment_files"

    env = os.environ.copy()
    env.update({
        "HARNESS_LLM_BACKEND": "openai",
        "HARNESS_LLM_BASE_URL": f"http://127.0.0.1:{VLLM_PORT}/v1",
        "HARNESS_LLM_MODEL": served,
        "OPERATION_MODE": "offline",
        "ARC_ENVIRONMENTS_DIR": envs_dir,
        "PYTHONPATH": pkg_dir + os.pathsep + env.get("PYTHONPATH", ""),
        "PYTHONUNBUFFERED": "1",
    })
    if served == "gptoss":
        # gpt-oss is a REASONING model: high effort + a bigger completion budget.
        env["HARNESS_REASONING_EFFORT"] = "high"
        env["HARNESS_PATCH_NUM_PREDICT"] = "20000"

    results = {}
    for mode in ("select", "fill"):
        out = os.path.join(KAGGLE_WORKING, f"r98_flow_{mode}_{served}.json")
        print(f"\n=== R98 FLOW {mode} x{RUNS} ({served}) ===", flush=True)
        try:
            rc = subprocess.call(
                [sys.executable, "-u", probe, "--mode", mode,
                 "--runs", str(RUNS), "--out", out],
                env=env, timeout=7200)  # a run drives the live env AND asks the model
        except subprocess.TimeoutExpired:
            rc = -9
            print(f"[mode] {mode} TIMEOUT (7200s)", flush=True)
        print(f"[mode] {mode} rc={rc}", flush=True)
        if os.path.exists(out):
            with open(out) as f:
                results[mode] = json.load(f)
        else:
            results[mode] = {"mode": mode, "error": f"probe rc={rc}, no output"}

    summary = {
        "model": served,
        "runs": RUNS,
        "verdict": {mode: r.get("verdict", "ERROR") for mode, r in results.items()},
        "per_run": {
            mode: [
                {
                    "pick": run.get("pick"),
                    "picked_truth": run.get("picked_truth"),
                    "variant": run.get("variant"),
                    "slots": run.get("slots"),
                    "equivalent_to_truth": run.get("equivalent_to_truth"),
                    "verdict": run.get("verdict"),
                    "plan_status": run.get("plan_status"),
                    "executed_actions": run.get("executed_actions"),
                    "total_actions": run.get("total_actions"),
                    "commits": run.get("commits"),
                    "outcome": run.get("outcome"),
                }
                for run in r.get("runs", [])
            ]
            for mode, r in results.items()
        },
        "results": results,
    }
    with open(os.path.join(KAGGLE_WORKING, f"r98_flow_bench_{served}.json"), "w") as f:
        json.dump(summary, f, indent=2)
    print("\n=== R98 FLOW SUMMARY ===", flush=True)
    print(json.dumps({"model": served, "verdict": summary["verdict"]}, indent=1), flush=True)

    if server is not None:
        server.terminate()


main()
