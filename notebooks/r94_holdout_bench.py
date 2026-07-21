# %% [markdown]
# # R94 D5 paired-holdout bench (Kaggle, offline)
#
# THE R94 measurement: hand the offline LLM a CONQUERED per-game solution as an
# editable TEMPLATE and, on a HELD-OUT game, measure whether the model can ADAPT
# it. Two pre-registered arms (frozen in .wiki/wiki/rounds/r94_adapter-template.md,
# "D5 PRE-REGISTRATION"), both on sk48:
#   simdfs x sk48  (FAMILY-MATCHED — sb26 conquest template, faithful-sim + DFS)
#   toggle x sk48  (FAMILY-MISMATCHED — the R93-proven generic-core template)
# The family-specific-vs-generic asymmetry IS the experiment's variable.
#
# Flow per arm (scripts/probe_template_holdout.py): template baseline (verbatim
# card through the sandbox) -> ONE adaptation ask (card + core trace + baseline
# summary -> full adapted core) -> validate (1 error-feedback retry) -> adaptation
# replay -> select-on-adaptation-replay (levels > distinct states > distinct
# transitions; noop tie-break) -> score the selected variant once on a FRESH env.
# sk48's own adapter/card/wiki/traces never enter any prompt (the holdout rule).
#
# Boot: vLLM api_server on the mounted model (gemma4-31b-it), PLAIN completion
# (the adaptation ask is a single completion), then subprocess the runner per arm
# so its [live] lines stream straight into the kernel log.

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
BUDGET = int(os.environ.get("R94_BUDGET", "2000"))
# The two pre-registered arms, both on the sk48 holdout (frozen D5 protocol).
CASES = [("simdfs", "sk48"), ("toggle", "sk48")]


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
    parser — the adaptation ask is a plain completion."""
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

    probe = (_find_file("probe_template_holdout.py") if ON_KAGGLE
             else "scripts/probe_template_holdout.py")
    pkg_dir = os.path.dirname(_find_dir("admorphiq")) if ON_KAGGLE else "src"
    envs_dir = _find_dir("environment_files")

    env = os.environ.copy()
    env.update({
        "HARNESS_LLM_BACKEND": "openai",
        "HARNESS_LLM_BASE_URL": f"http://127.0.0.1:{VLLM_PORT}/v1",
        "HARNESS_LLM_MODEL": served,
        "HARNESS_KERNEL_API": "1",
        "OPERATION_MODE": "offline",
        "ARC_ENVIRONMENTS_DIR": envs_dir,
        "PYTHONPATH": pkg_dir + os.pathsep + env.get("PYTHONPATH", ""),
        "PYTHONUNBUFFERED": "1",
    })
    if served == "gptoss":
        # gpt-oss is a REASONING model: high effort + a bigger completion budget
        # (reasoning tokens count against max_tokens in vLLM/harmony).
        env["HARNESS_REASONING_EFFORT"] = "high"
        env["HARNESS_PATCH_NUM_PREDICT"] = "20000"

    results = []
    for arm, game in CASES:
        out = os.path.join(KAGGLE_WORKING, f"r94_holdout_{arm}_{game}.json")
        print(f"\n=== R94 HOLDOUT {arm} x {game} @ {BUDGET} ===", flush=True)
        try:
            rc = subprocess.call(
                [sys.executable, "-u", probe, "--arm", arm, "--game", game,
                 "--budget", str(BUDGET), "--out", out],
                env=env, timeout=BOOT_TIMEOUT_S)  # one stuck arm must not eat the kernel
        except subprocess.TimeoutExpired:
            rc = -9
            print(f"[case] {arm} x {game} TIMEOUT ({BOOT_TIMEOUT_S}s)", flush=True)
        print(f"[case] {arm} x {game} rc={rc}", flush=True)
        if os.path.exists(out):
            with open(out) as f:
                results.append(json.load(f))
        else:
            results.append({"arm": arm, "game": game, "error": f"probe rc={rc}, no output"})

    summary = {
        "model": served, "budget": BUDGET,
        "selected": {f"{r.get('arm')}:{r.get('game')}": r.get("selected", "ERROR")
                     for r in results},
        "fresh_levels": {f"{r.get('arm')}:{r.get('game')}":
                         (r.get("fresh_score") or {}).get("levels", "ERROR")
                         for r in results},
        "results": results,
    }
    with open(os.path.join(KAGGLE_WORKING, "r94_holdout_bench.json"), "w") as f:
        json.dump(summary, f, indent=2)
    print("\n=== R94 HOLDOUT SUMMARY ===", flush=True)
    print(json.dumps({"selected": summary["selected"],
                      "fresh_levels": summary["fresh_levels"]}, indent=1), flush=True)

    if server is not None:
        server.terminate()


main()
