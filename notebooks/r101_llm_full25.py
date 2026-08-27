# %% [markdown]
# # R101 — the generic tool set driven by the OFFLINE MODEL, all 25 games
#
# Every generic-path number in round R101 was measured on the LLM-FREE fallback:
# `harness/loop.py` drops to signature routing when the llm call raises, and the
# ceph round runners set no `HARNESS_MODEL`. The fallback reached **0.6711** with
# twelve games conquered. What ships asks a MODEL to name the tool, and that path
# was never measured at width — ceph-build has no GPU and one 26B model on its
# shared CPUs takes ~37 cores.
#
# This kernel measures it. It reuses the R55/R92 serving path verbatim: install the
# arc wheels and vLLM offline from mounted wheel dirs, boot the OpenAI-compatible
# server on whichever HF model the kernel attaches, point the harness at it with
# `HARNESS_LLM_BACKEND=openai`, and run all 25 games through `score_efficiency`.
#
# ⛔ What to compare against. The fallback's per-game scores are in the repo at
# `scripts/rounds/WF/games/*.json`. A game where the model scores LESS than the
# fallback is a routing loss, not a tool weakness — three such losses in R101 were
# caused by the model being unable to NAME the right tool (its menu and its ranking
# were both hardcoded to eight literal names) and a fourth by the prompt handing it
# ranked fit scores without telling it to use them.

# %%
from __future__ import annotations

import glob
import json
import os
import subprocess
import sys
import time
from urllib.request import urlopen

ON_KAGGLE = os.path.isdir("/kaggle/input")
KAGGLE_WORKING = "/kaggle/working"
VLLM_PORT = 8199
GAMES = [
    "ar25", "bp35", "cd82", "cn04", "dc22", "ft09", "g50t", "ka59", "lf52",
    "lp85", "ls20", "m0r0", "r11l", "re86", "s5i5", "sb26", "sc25", "sk48",
    "sp80", "su15", "tn36", "tr87", "tu93", "vc33", "wa30",
]
MAX_ACTIONS = int(os.environ.get("MAX_ACTIONS", "500"))
# A subset for smoke-testing the plumbing off-Kaggle. Empty means all 25, which is what
# the kernel runs. The plumbing is validated on one game locally before a push, because
# every failure this kernel can have — a mount path, a stale dataset, a missing framework
# dir — costs a full GPU session to discover remotely.
BENCH_TITLES = os.environ.get("BENCH_TITLES", "")
_MAX_MODEL_LEN_CEIL = 200000


def find_dir(name: str) -> str:
    for root, dirs, _ in os.walk("/kaggle/input"):
        if os.path.basename(root) == name:
            return root
        for d in dirs:
            if d == name:
                return os.path.join(root, d)
    raise FileNotFoundError(f"no mounted directory named {name}")


def find_file(name: str) -> str:
    """Locate a file anywhere under the mounts.

    The runner is found by SEARCH, not by joining a path. `--dir-mode zip` strips the
    top level of each staged directory, so `scripts/score_efficiency.py` arrives beside
    the package rather than under a `scripts/` dir — a joined path would miss it.
    """
    for root, _, files in os.walk("/kaggle/input"):
        if name in files:
            return os.path.join(root, name)
    raise FileNotFoundError(f"no mounted file named {name}")


def find_model() -> str:
    """The one HF weights directory (a dir holding config.json) under the model mounts.

    Kaggle mounts a model at owner/framework/variation/version, so it sits several levels
    deeper than the dataset mounts and a shallow glob misses it entirely.
    """
    hits = []
    for base in ("/kaggle/input/models", "/kaggle/input"):
        if not os.path.isdir(base):
            continue
        for root, _, files in os.walk(base):
            if "config.json" in files and glob.glob(os.path.join(root, "*.safetensors")):
                hits.append(root)
        if hits:
            break
    if not hits:
        raise FileNotFoundError("no HF weights directory under /kaggle/input")
    return sorted(hits)[0]


def install_offline() -> None:
    arc = sorted(glob.glob(os.path.join(find_dir("arc_agi_3_wheels"), "*.whl")))
    if arc:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "--no-index", "--no-deps", *arc])
        print(f"[install] arc: {len(arc)} wheel(s)", flush=True)
    vllm = glob.glob("/kaggle/input/**/vllm*.whl", recursive=True)
    links = sorted({os.path.dirname(w) for w in vllm})
    if links:
        args = []
        for d in links:
            args += ["--find-links", d]
        subprocess.check_call([sys.executable, "-m", "pip", "install", "--no-index", *args, "vllm"])
        print(f"[install] vLLM from {len(links)} link dir(s)", flush=True)


def model_max_len(model_dir: str) -> int:
    """The model's own trained context, clamped so the KV cache fits the card.

    Measured 2026-07-21 on this hardware: a 31B model at 262144 needs 27.04 GiB of
    KV against 24.36 GiB available and the engine OOMs. Prompts here are a few K
    tokens, so context is never the binding limit.
    """
    if os.environ.get("MAX_MODEL_LEN"):
        return int(os.environ["MAX_MODEL_LEN"])
    try:
        with open(os.path.join(model_dir, "config.json")) as f:
            cfg = json.load(f)
        for key in ("max_position_embeddings", "max_seq_len", "n_positions"):
            if isinstance(cfg.get(key), int):
                return min(cfg[key], _MAX_MODEL_LEN_CEIL)
        text_cfg = cfg.get("text_config", {})
        if isinstance(text_cfg.get("max_position_embeddings"), int):
            return min(text_cfg["max_position_embeddings"], _MAX_MODEL_LEN_CEIL)
    except Exception as exc:  # noqa: BLE001
        print(f"[vllm] max-len read failed ({exc})", flush=True)
    return 32768


def boot(model_dir: str, served: str) -> subprocess.Popen:
    env = os.environ.copy()
    env["VLLM_ATTENTION_BACKEND"] = "TRITON_ATTN"
    env["VLLM_USE_FLASHINFER_SAMPLER"] = "0"
    env["VLLM_WORKER_MULTIPROC_METHOD"] = "spawn"
    cmd = [
        sys.executable, "-m", "vllm.entrypoints.openai.api_server",
        "--model", model_dir, "--served-model-name", served,
        "--max-model-len", str(model_max_len(model_dir)),
        "--enforce-eager", "--gpu-memory-utilization", "0.92",
        "--port", str(VLLM_PORT),
    ]
    print(f"[vllm] {' '.join(cmd)}", flush=True)
    log = open(os.path.join(KAGGLE_WORKING, "vllm.log"), "w")  # noqa: SIM115
    return subprocess.Popen(cmd, env=env, stdout=log, stderr=subprocess.STDOUT)


def wait_healthy(port: int, timeout_s: float = 1800) -> None:
    url = f"http://127.0.0.1:{port}/v1/models"
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        try:
            with urlopen(url, timeout=10) as r:
                if r.status == 200:
                    print("[vllm] healthy", flush=True)
                    return
        except Exception:  # noqa: BLE001
            time.sleep(10)
    raise TimeoutError("vLLM never became healthy — see vllm.log")


# %%
if ON_KAGGLE:
    install_offline()
    src = find_dir("admorphiq")
    sys.path.insert(0, os.path.dirname(src))
    model_dir = find_model()
    served = "gemma4" if "gemma" in model_dir.lower() else os.path.basename(model_dir).lower()
    print(f"[model] {model_dir} served as {served}", flush=True)
    proc = boot(model_dir, served)
    wait_healthy(VLLM_PORT)
    # The LLM env vars are deliberately NOT set here. Setting them globally leaks them
    # into the fallback arm's environment copy, and the runner switches to the openai
    # backend on a bare `HARNESS_LLM_BASE_URL` — so both arms would be the LLM arm and
    # the comparison would measure nothing while looking perfectly healthy. run_arm owns
    # these three variables and nothing else touches them.

# %% [markdown]
# ## The measurement
#
# The runner is invoked as a SUBPROCESS, exactly as the ceph rounds invoke it, so
# the two arms differ in one thing only: whether `HARNESS_MODEL` names a served
# model. Calling `run_game` in-process here would be a second driver, and a driver
# written for one arm is the classic way to measure the driver instead of the arm.
#
# `ENVIRONMENTS_DIR` is set explicitly — that is the name the Arcade reads. Getting it
# wrong is a MEASURED trap that has now fired twice: a GPU session boots a healthy model
# server, scores 0/0 games, and prints a clean 0.00% that reads exactly like a broken
# agent. The first run of THIS kernel set only `ARC_ENVIRONMENTS_DIR`, which is a
# convention of the probe scripts and which this runner never reads.

if ON_KAGGLE:
    repo = os.path.dirname(find_dir("admorphiq"))
    runner = find_file("score_efficiency.py")
    envs_dir = find_dir("environment_files")
else:
    repo = os.path.join(os.getcwd(), "src")
    runner = os.path.join(os.getcwd(), "scripts", "score_efficiency.py")
    envs_dir = os.path.join(os.getcwd(), "environment_files")

n_envs = len(glob.glob(os.path.join(envs_dir, "*")))
print(f"[envs] {envs_dir}: {n_envs} entries", flush=True)
if n_envs == 0:
    raise FileNotFoundError(f"no game environments under {envs_dir}")

out_path = os.path.join(KAGGLE_WORKING if ON_KAGGLE else ".", "r101_llm_full25.json")


def run_arm(label: str, model: str | None) -> dict:
    """One full-25 pass. `model=None` is the LLM-FREE fallback (signature routing)."""
    env = os.environ.copy()
    # ENVIRONMENTS_DIR is the name the arc_agi Arcade actually reads. ARC_ENVIRONMENTS_DIR
    # is a convention of the R97/R98 PROBE scripts, which read it themselves and pass it to
    # Arcade(environments_dir=...); this runner does not, so it falls back to a cwd-relative
    # "environment_files" and finds nothing. Both failures print the same thing — a healthy
    # model server and "0/0 games scored" — which is why setting only the ARC_ name looks
    # like a fix and is not. MEASURED: from a foreign cwd, unset scores 0 games, set scores
    # 1.0000 on the same game. RECORDINGS_DIR is redirected because the mounts are read-only.
    env["ENVIRONMENTS_DIR"] = envs_dir
    env["ARC_ENVIRONMENTS_DIR"] = envs_dir
    env["RECORDINGS_DIR"] = os.path.join(KAGGLE_WORKING if ON_KAGGLE else ".", "recordings")
    env["PYTHONPATH"] = repo
    for var in ("HARNESS_LLM_BACKEND", "HARNESS_LLM_BASE_URL", "HARNESS_LLM_MODEL"):
        env.pop(var, None)
    if model:
        env["HARNESS_LLM_BACKEND"] = "openai"
        env["HARNESS_LLM_BASE_URL"] = f"http://127.0.0.1:{VLLM_PORT}/v1"
        # HARNESS_LLM_MODEL, not HARNESS_MODEL: the latter names the OLLAMA model and is
        # ignored by the openai path, which raises on an empty model — so the wrong name
        # produces a run where every LLM call fails and the harness silently falls back
        # to signature routing, i.e. the LLM arm quietly becomes the fallback arm.
        env["HARNESS_LLM_MODEL"] = model
    out = os.path.join(KAGGLE_WORKING if ON_KAGGLE else ".", f"arm_{label}.json")
    cmd = [
        sys.executable, runner,
        "--agent", "unified",
        *(["--titles", BENCH_TITLES] if BENCH_TITLES else ["--games", "all"]),
        "--max-actions", str(MAX_ACTIONS), "--out", out,
    ]
    print(f"\n=== arm {label} (model={model or 'NONE — fallback'}) ===", flush=True)
    started = time.monotonic()
    subprocess.run(cmd, env=env, cwd=KAGGLE_WORKING if ON_KAGGLE else ".", check=False)
    print(f"[arm {label}] {time.monotonic() - started:.0f}s", flush=True)
    with open(out) as f:
        data = json.load(f)
    if not data.get("games"):
        raise RuntimeError(
            f"arm {label} scored 0 games — the arcade saw no environments under {envs_dir}. "
            "This prints as a clean 0.00% and is not a result."
        )
    return data


def preflight_llm(model: str) -> None:
    """Prove the LLM arm can actually reach the model BEFORE 25 games are spent.

    `harness/loop.py` catches a failing llm call and drops to signature routing. That is
    the right runtime behaviour and the wrong measurement behaviour: an LLM arm whose every
    call raises silently becomes a second fallback arm, and the comparison then prints two
    near-identical columns that look like "the model routes as well as the signature does".
    A wrong env-var name alone produces exactly that. So the wiring is proven with one call,
    and a failure stops the kernel instead of being averaged into a verdict.
    """
    os.environ["HARNESS_LLM_BASE_URL"] = f"http://127.0.0.1:{VLLM_PORT}/v1"
    os.environ["HARNESS_LLM_MODEL"] = model
    sys.path.insert(0, repo)
    from admorphiq.harness.registry import openai_compat_llm

    reply = openai_compat_llm(num_predict=32)([
        {"role": "user", "content": "Reply with the single word: ready"},
    ])
    for var in ("HARNESS_LLM_BASE_URL", "HARNESS_LLM_MODEL"):
        os.environ.pop(var, None)
    if not (reply or "").strip():
        raise RuntimeError("the served model returned an empty reply — the LLM arm would be inert")
    print(f"[preflight] model replied: {reply.strip()[:60]!r}", flush=True)


if ON_KAGGLE:
    preflight_llm(served)

arms: dict[str, dict] = {}
arms["llm"] = run_arm("llm", served if ON_KAGGLE else None)
if os.environ.get("RUN_FALLBACK_ARM", "1") == "1":
    arms["fallback"] = run_arm("fallback", None)

with open(out_path, "w") as f:
    json.dump(arms, f, indent=1)

# %% [markdown]
# ## Read it per game, not as a mean
#
# A mean hides the only failure this kernel exists to catch: the model routing a
# board to the wrong tool. That shows up as ONE game collapsing to zero while the
# rest hold, which a 25-game mean barely moves.


# %%
def per_game(arm: dict) -> dict[str, float]:
    """Per-game scores, keyed by title.

    A game with no human baseline is DROPPED, not zeroed. The runner excludes it
    from its own total, so zeroing it here would make this cell disagree with the
    number the runner printed — a discrepancy that reads as a regression.
    """
    rows = arm.get("games", arm) if isinstance(arm, dict) else {}
    if isinstance(rows, list):
        return {
            r.get("title", r.get("game_id", "?")): r["game_score"]
            for r in rows
            if r.get("game_score") is not None
        }
    return {
        k: v["game_score"]
        for k, v in rows.items()
        if isinstance(v, dict) and v.get("game_score") is not None
    }


llm = per_game(arms["llm"])
fb = per_game(arms.get("fallback", {}))
names = sorted(set(llm) | set(fb))
# An arm that did not run prints as "—", never as 0.0000. A missing measurement rendered
# as a zero is indistinguishable from a game that scored nothing, and this repository has
# already published one conclusion built on exactly that confusion.
print(f"{'game':<8}{'llm':>9}{'fallback':>11}   verdict")
losses = 0
for name in names:
    a = llm.get(name)
    b = fb.get(name) if fb else None
    verdict = ""
    if b is not None and a is not None:
        if a < b - 1e-9:
            verdict, losses = "ROUTING LOSS", losses + 1
        elif a > b + 1e-9:
            verdict = "llm ahead"
    cell_a = f"{a:>9.4f}" if a is not None else f"{'—':>9}"
    cell_b = f"{b:>11.4f}" if b is not None else f"{'—':>11}"
    print(f"{name:<8}{cell_a}{cell_b}   {verdict}")

print(f"\nmean  llm={sum(llm.values()) / max(1, len(llm)):.4f}  over {len(llm)} game(s)")
if fb:
    print(f"mean  fallback={sum(fb.values()) / max(1, len(fb)):.4f}  over {len(fb)} game(s)")
    print(f"routing losses: {losses}")
else:
    print("fallback arm not run — no comparison made")
