# %% [markdown]
# # R95a part-2 selection bench (Kaggle, offline)
#
# THE R95a part-2 measurement: can the offline model, shown only NEUTRAL mechanic
# descriptions + TRAIN observations (no names, no oracle hint, no held-out data),
# SELECT the correct hypothesis template? Pre-registration frozen in
# docs/design_hypothesis_dsl_r95.md ("R95a part-2 PRE-REGISTRATION").
#
# Per game (scripts/probe_hypothesis_select.py --ask): assemble the five neutral
# candidate rules under a deterministic T1..T5 shuffle + a TRAIN-only observation
# summary -> ONE guided-json completion {choice, confidence, evidence} -> map the
# choice back and score PASS iff it lands in part-1's oracle EQUIVALENCE CLASS
# (oracle + templates tied with it). 3 repetitions per game (sampling variance).
# The exhaustive-ranking winner (no-LLM control) is reported alongside.
#
# ft09 is the PRIMARY case (random PASS = 2/5 = 0.40); sc25 is a WEAK case
# (random PASS = 3/5 = 0.60, cannot carry the verdict alone).
#
# Boot: vLLM api_server on the mounted model (gemma4-31b-it OR gpt-oss-120b), a
# PLAIN completion (the ask is a single JSON answer), then subprocess the runner
# per game so its printed JSON streams into the kernel log. No arc environment is
# needed — the ask reads recorded traces (data/traces/*.npz), located and passed
# via R95A_TRACES_DIR.

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
REPS = int(os.environ.get("R95A_REPS", "3"))
# The two pre-registered games (frozen R95a part-2 protocol). ft09 primary.
CASES = [("ft09",), ("sc25",)]


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
    instead of fetching openaipublic.blob.core.windows.net. Files ship in the
    jaehyukhyun/tiktoken-encodings-offline dataset."""
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

    probe = (_find_file("probe_hypothesis_select.py") if ON_KAGGLE
             else "scripts/probe_hypothesis_select.py")
    pkg_dir = os.path.dirname(_find_dir("admorphiq")) if ON_KAGGLE else "src"
    traces_dir = os.path.dirname(_find_file("ft09.npz")) if ON_KAGGLE else "data/traces"

    env = os.environ.copy()
    env.update({
        "HARNESS_LLM_BACKEND": "openai",
        "HARNESS_LLM_BASE_URL": f"http://127.0.0.1:{VLLM_PORT}/v1",
        "HARNESS_LLM_MODEL": served,
        "OPERATION_MODE": "offline",
        "R95A_TRACES_DIR": traces_dir,
        "PYTHONPATH": pkg_dir + os.pathsep + env.get("PYTHONPATH", ""),
        "PYTHONUNBUFFERED": "1",
    })
    if served == "gptoss":
        # gpt-oss is a REASONING model: high effort + a bigger completion budget
        # (reasoning tokens count against max_tokens in vLLM/harmony).
        env["HARNESS_REASONING_EFFORT"] = "high"
        env["HARNESS_PATCH_NUM_PREDICT"] = "20000"

    results = []
    for (game,) in CASES:
        out = os.path.join(KAGGLE_WORKING, f"r95a_select_{game}.json")
        print(f"\n=== R95a SELECT {game} x{REPS} ({served}) ===", flush=True)
        try:
            rc = subprocess.call(
                [sys.executable, "-u", probe, "--game", game, "--ask",
                 "--reps", str(REPS), "--out", out],
                env=env, timeout=3600)  # each ask may retry; reasoning models are slow
        except subprocess.TimeoutExpired:
            rc = -9
            print(f"[case] {game} TIMEOUT (3600s)", flush=True)
        print(f"[case] {game} rc={rc}", flush=True)
        if os.path.exists(out):
            with open(out) as f:
                results.append(json.load(f))
        else:
            results.append({"game": game, "error": f"probe rc={rc}, no output"})

    summary = {
        "model": served, "reps": REPS,
        "pass_rate": {r.get("game"): r.get("pass_rate", "ERROR") for r in results},
        "equivalence_class": {r.get("game"): r.get("equivalence_class") for r in results},
        "exhaustive_winner_control": {
            r.get("game"): r.get("exhaustive_winner_control") for r in results},
        "ask_results": {r.get("game"): r.get("ask_results") for r in results},
        "results": results,
    }
    with open(os.path.join(KAGGLE_WORKING, "r95a_select_bench.json"), "w") as f:
        json.dump(summary, f, indent=2)
    print("\n=== R95a SELECT SUMMARY ===", flush=True)
    print(json.dumps({"model": served, "pass_rate": summary["pass_rate"],
                      "exhaustive_winner_control": summary["exhaustive_winner_control"]},
                     indent=1), flush=True)

    if server is not None:
        server.terminate()


main()
