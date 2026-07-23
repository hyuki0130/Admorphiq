# %% [markdown]
# # R97 tier-2 self-extension MODEL bench (Kaggle, offline)
#
# The 4-case model measurement over the R97 vocabulary-HOLE test — run AFTER the
# pre-model oracle-certification gate PASSED (scripts/probe_r97_oracle_gate.py):
#
#   1. HOLE (ft09 idx4 k>=3 evidence): vocab minus ordered_cycle + the extend
#      escape hatch. Success = extend proposed AND the authored update passes
#      TRAIN fit + held-out exactness. >=2/3 = hole recall.
#   2. NO-HOLE (idx0 2-state evidence): full vocab. Success = correct SELECT; any
#      extend = false positive. >=2/3 = no-hole specificity.
#   3. EVIDENCE-BLIND (1 run): transitions withheld — a passing extend = LEAKAGE.
#   4. INSUFFICIENT (1 run): one transition — expected abstain (non-gating).
#
# SEED-PASS per model = hole recall >=2/3 AND no-hole specificity >=2/3. The
# two-model rule applies: run gemma4-31b-q8 AND gpt-oss-120b (separate kernels
# admorphiq-r97-ext-{gemma4,gptoss}); no one-shot verdicts.
#
# Boot: vLLM api_server on the mounted model, a PLAIN guided-json completion (the
# select/extend/abstain ask). The driver (probe_r97_model_bench.py) sources its
# colour-transition evidence from the committed certification.json — the oracle
# gate's captured live runs — so the paired bench needs NO env for detection; the
# optional --gold-gate live clear (env-driven) is off by default. Ship the sibling
# scripts (probe_r97_oracle_gate.py, probe_hypothesis_model.py, probe_hypothesis_live.py)
# and scripts/rounds/R97/certification.json in the same working tree.

# %%
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
GOLD_GATE = os.environ.get("R97_GOLD_GATE", "0") == "1"  # off by default (detection scoring)


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
    elif "gpt-oss" in low or "gptoss" in low or "gpt_oss" in low:
        tag = "gptoss"
    else:
        tag = "served"
    return d, tag


def install_wheels_offline() -> None:
    import glob

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


def _gptoss_offline_env() -> None:
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


# %%
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
        driver = _find_file("probe_r97_model_bench.py")
        pkg_dir = os.path.dirname(_find_dir("admorphiq"))
        cert = _find_file("certification.json")
        envs_dir = _find_dir("environment_files")
    else:
        driver = "scripts/probe_r97_model_bench.py"
        pkg_dir = "src"
        cert = "scripts/rounds/R97/certification.json"
        envs_dir = "environment_files"

    env = os.environ.copy()
    env.update({
        "HARNESS_LLM_BACKEND": "openai",
        "HARNESS_LLM_BASE_URL": f"http://127.0.0.1:{VLLM_PORT}/v1",
        "HARNESS_LLM_MODEL": served,
        "OPERATION_MODE": "offline",
        "ARC_ENVIRONMENTS_DIR": envs_dir,  # only used if --gold-gate is set
        "PYTHONPATH": pkg_dir + os.pathsep + env.get("PYTHONPATH", ""),
        "PYTHONUNBUFFERED": "1",
    })
    if served == "gptoss":
        env["HARNESS_REASONING_EFFORT"] = "high"
        env["HARNESS_PATCH_NUM_PREDICT"] = "20000"

    out = os.path.join(KAGGLE_WORKING, f"r97_ext_bench_{served}.json")
    cmd = [sys.executable, "-u", driver, "--evidence", cert, "--out", out]
    if GOLD_GATE:
        cmd.append("--gold-gate")
    print(f"\n=== R97 EXT BENCH ({served}) gold_gate={GOLD_GATE} ===", flush=True)
    try:
        rc = subprocess.call(cmd, env=env, timeout=7200)
    except subprocess.TimeoutExpired:
        rc = -9
        print("[bench] TIMEOUT (7200s)", flush=True)
    print(f"[bench] rc={rc}", flush=True)

    report = {}
    if os.path.exists(out):
        with open(out) as f:
            report = json.load(f)
    summary = {
        "model": served,
        "seed_pass": report.get("seed_pass"),
        "hole_recall": report.get("hole_recall"),
        "no_hole_specificity": report.get("no_hole_specificity"),
    }
    with open(os.path.join(KAGGLE_WORKING, f"r97_ext_summary_{served}.json"), "w") as f:
        json.dump(summary, f, indent=2)
    print("\n=== R97 EXT SUMMARY ===", flush=True)
    print(json.dumps(summary, indent=1), flush=True)

    if server is not None:
        server.terminate()


main()
