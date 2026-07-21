# %% [markdown]
# # Admorphiq — agent25 kernel-bridge Kaggle bench (R92)
#
# Measures whether the R92 kernel bridge (HARNESS_KERNEL_API) lifts the offline
# code-agent (UnifiedAgent) on Kaggle. Reuses the R55 vLLM serving path:
#   1. offline-install arc wheels + vLLM (find-links from the attached mounts),
#   2. boot vllm.entrypoints.openai.api_server as a subprocess (served name "qwen"),
#   3. drive UnifiedAgent over a SMALL game subset in MATCHED arms — kernel bridge
#      OFF vs ON, both with code escalation ON — via score_efficiency.run_game,
#   4. a telemetry-wrapped llm counts code prompts / `K.` usage / latency; the run
#      FAILS if the ON arm never issued a code prompt (the bridge would be inert).
#
# Model-agnostic: serves whichever single HF model the kernel attaches (Qwen or
# gemma4), served-name auto-derived. Run the same notebook per model to compare.

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

# Small subset: tool-clearable (ls20/vc33/m0r0) + a transform game (cd82) where
# the code+kernel path is the only lever — enough to see the bridge fire.
BENCH_GAMES = ["ls20", "vc33", "m0r0", "cd82"]
MAX_ACTIONS = 300
VLLM_PORT = 8199
# served-model-name is derived from the mounted model dir (qwen / gemma4 / ...),
# so ONE notebook serves whichever model the kernel attaches.
VLLM_MODEL_NAME = os.environ.get("VLLM_MODEL_NAME", "served")
# Generous context; our prompts are only a few K tokens so this is not the binding
# limit, but raised to rule context out (gemma4 supports 256K, qwen 131072).
MAX_MODEL_LEN = int(os.environ.get("MAX_MODEL_LEN", "131072"))
BOOT_TIMEOUT_S = 1800.0


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


def _find_model_dir() -> tuple[str, str]:
    """The unique HF weights dir under /kaggle/input/models (config.json), plus a
    served-name tag derived from its path (qwen / gemma4 / ...). Model-agnostic so
    one notebook serves whichever single model the kernel attaches; asserts a
    single match so a stray mount can't select the wrong model."""
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
        print(f"[install] arc: {len(arc_wheels)} wheel(s)")
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


def _model_max_len(model_dir: str) -> int:
    """The model's OWN trained context (config.json max_position_embeddings),
    clamped to a memory-safe ceiling. Env MAX_MODEL_LEN overrides. This uses each
    model at its true max (gemma4 256K, qwen 131072) to rule context out, while
    _MAX_MODEL_LEN_CEIL guards KV-cache OOM on the 96GB card."""
    _MAX_MODEL_LEN_CEIL = 262144
    if os.environ.get("MAX_MODEL_LEN"):
        return int(os.environ["MAX_MODEL_LEN"])
    try:
        with open(os.path.join(model_dir, "config.json")) as f:
            cfg = json.load(f)
        for k in ("max_position_embeddings", "max_seq_len", "n_positions"):
            if isinstance(cfg.get(k), int):
                return min(cfg[k], _MAX_MODEL_LEN_CEIL)
        tc = cfg.get("text_config", {})
        if isinstance(tc.get("max_position_embeddings"), int):
            return min(tc["max_position_embeddings"], _MAX_MODEL_LEN_CEIL)
    except Exception as exc:  # noqa: BLE001
        print(f"[vllm] config max-len read failed ({exc}); default {MAX_MODEL_LEN}")
    return MAX_MODEL_LEN


def boot_vllm_server(model_dir: str, served_name: str) -> subprocess.Popen:
    """vLLM OpenAI api_server with the R55 measured-good offline config."""
    env = os.environ.copy()
    env["VLLM_ATTENTION_BACKEND"] = "TRITON_ATTN"
    env["VLLM_USE_FLASHINFER_SAMPLER"] = "0"
    env["VLLM_WORKER_MULTIPROC_METHOD"] = "spawn"
    max_len = _model_max_len(model_dir)
    print(f"[vllm] max-model-len={max_len} (model's own max, ceil-clamped)", flush=True)
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
    for cand in (os.path.join(os.getcwd(), "src"), "/kaggle/input/admorphiq-src",
                 "/kaggle/input/admorphiq-src/src"):
        if os.path.isdir(os.path.join(cand, "admorphiq")) and cand not in sys.path:
            sys.path.insert(0, cand)


def _ensure_score_efficiency_importable() -> None:
    """Put the dir holding scripts/score_efficiency.py on sys.path. The dataset
    mount layout varies (CLI vs competition-attached), so locate it by walk."""
    try:
        import score_efficiency  # noqa: F401
        return
    except ImportError:
        pass
    roots = ["/kaggle/input", os.getcwd()]
    for root in roots:
        if not os.path.isdir(root):
            continue
        for cur, dirs, files in os.walk(root):
            if cur.count("/") > 10:
                dirs[:] = []
                continue
            if "score_efficiency.py" in files and cur not in sys.path:
                sys.path.insert(0, cur)
                try:
                    import score_efficiency  # noqa: F401
                    return
                except ImportError:
                    continue


# %%
class _LLMTelemetry:
    """Wrap an llm(messages)->str callable to count calls, latency, and whether
    the code path fired (a code prompt carries the KERNEL TOOLBOX card when the
    bridge is on) and whether replies actually use ``K.`` kernels."""

    def __init__(self, inner):
        self.inner = inner
        self.calls = 0
        self.code_prompts = 0
        self.k_replies = 0
        self.py_replies = 0
        self.total_latency = 0.0
        self.errors = 0
        self.max_out_chars = 0
        # Full raw transcripts (prompt tail + the model's actual output) so we can
        # SEE the reasoning: is it producing code, using K., hitting the output cap?
        self.transcripts: list[dict] = []

    def __call__(self, messages: list[dict[str, str]]) -> str:
        self.calls += 1
        sys_content = messages[0].get("content", "") if messages else ""
        user_content = messages[-1].get("content", "") if messages else ""
        is_code_prompt = "KERNEL TOOLBOX" in sys_content
        if is_code_prompt:
            self.code_prompts += 1
        t0 = time.monotonic()
        try:
            out = self.inner(messages)
        except Exception as exc:  # noqa: BLE001 - telemetry only, re-raise
            self.errors += 1
            self.total_latency += time.monotonic() - t0
            raise exc
        self.total_latency += time.monotonic() - t0
        if "```python" in out:
            self.py_replies += 1
        if "K." in out:
            self.k_replies += 1
        self.max_out_chars = max(self.max_out_chars, len(out))
        self.transcripts.append({
            "call": self.calls,
            "code_prompt": is_code_prompt,
            "user_tail": user_content[-600:],   # goal/summary the model saw
            "output": out,                       # the model's FULL reply
            "out_chars": len(out),
            "used_K": "K." in out,
            "has_python": "```python" in out,
        })
        return out

    def summary(self) -> dict:
        return {
            "calls": self.calls, "code_prompts": self.code_prompts,
            "python_replies": self.py_replies, "kernel_replies": self.k_replies,
            "errors": self.errors, "max_out_chars": self.max_out_chars,
            "avg_latency_s": round(self.total_latency / max(self.calls, 1), 2),
        }


def _baseline_for(arcade, game_id: str) -> list[int] | None:
    for info in (getattr(arcade, "available_environments", None) or arcade.get_environments()):
        if info.game_id == game_id:
            return getattr(info, "baseline_actions", None)
    return None


def _run_arm(arcade, game_id: str, bridge_on: bool) -> dict:
    """One game under one arm. Sets the bridge flag, builds a telemetry-wrapped
    UnifiedAgent, and scores via the shared run_game (RHAE)."""
    from score_efficiency import run_game

    from admorphiq.harness.loop import UnifiedAgent
    from admorphiq.harness.registry import default_tools, openai_compat_llm

    os.environ["HARNESS_KERNEL_API"] = "1" if bridge_on else "0"

    # Output raised to 4096 so a full reason+code block is never truncated (the
    # transcript's out_chars vs this cap tells us if the model wanted more room).
    tele = _LLMTelemetry(openai_compat_llm(num_predict=4096))
    draw = openai_compat_llm(num_predict=1024)

    def factory():
        return UnifiedAgent(default_tools(), tele, draw_llm=draw,
                            giveup=8000, stall=80, ctx_budget=6000)

    base = _baseline_for(arcade, game_id)
    res = run_game(arcade, game_id, base, agent_name="unified",
                   max_actions=MAX_ACTIONS, adapter_factory=factory)
    res["arm"] = "on" if bridge_on else "off"
    res["telemetry"] = tele.summary()
    res["transcripts"] = tele.transcripts
    return res


# %%
def main() -> None:
    served = VLLM_MODEL_NAME
    if ON_KAGGLE:
        install_wheels_offline()
        model_dir, served = _find_model_dir()
        print(f"[model] {model_dir} served-name={served}")
        server = boot_vllm_server(model_dir, served)
        wait_for_server(VLLM_PORT, BOOT_TIMEOUT_S)
    else:
        server = None

    _ensure_admorphiq_importable()
    _ensure_score_efficiency_importable()

    # Backend wiring: harness llm -> local vLLM OpenAI server (served name auto-derived).
    os.environ["HARNESS_LLM_BACKEND"] = "openai"
    os.environ["HARNESS_LLM_BASE_URL"] = f"http://127.0.0.1:{VLLM_PORT}/v1"
    os.environ["HARNESS_LLM_MODEL"] = served
    os.environ["HARNESS_CODE_ESC"] = "1"  # let the model escalate to code (bridge lives there)

    from arc_agi import Arcade, OperationMode

    os.environ["OPERATION_MODE"] = "offline"
    envs_dir = _find_dir("environment_files")
    arcade = Arcade(operation_mode=OperationMode.OFFLINE, environments_dir=envs_dir)

    # Preflight: prove the kernel bridge is reachable in the sandbox before the run.
    os.environ["HARNESS_KERNEL_API"] = "1"
    import numpy as np

    from admorphiq.tools.code_agent import run_code
    pf = run_code("regs = K.find_regions(current_frame, background=0)\nprint('regs', len(regs))",
                  np.zeros((8, 8), dtype=int), [], ["ACTION1"])
    print(f"[preflight] kernel-bridge run_code: err={pf.error!r} printed={pf.printed!r}")
    assert pf.error == "", f"kernel bridge preflight failed: {pf.error}"

    target_ids = []
    for info in (getattr(arcade, "available_environments", None) or arcade.get_environments()):
        hay = f"{info.game_id} {getattr(info, 'title', '') or ''}".lower()
        if any(g in hay for g in BENCH_GAMES) and info.game_id not in target_ids:
            target_ids.append(info.game_id)

    results = []
    for gid in target_ids:
        for bridge_on in (False, True):
            arm = "on" if bridge_on else "off"
            print(f"\n=== {gid} [{arm}] ===", flush=True)
            try:
                res = _run_arm(arcade, gid, bridge_on)
            except Exception as exc:  # noqa: BLE001 - record, keep going
                res = {"game_id": gid, "arm": arm, "error": str(exc)[:300]}
            print(json.dumps({k: res.get(k) for k in
                              ("game_id", "arm", "levels_completed", "win_levels",
                               "game_score", "telemetry", "error")}), flush=True)
            results.append(res)

    # Full transcripts (prompt tail + model output) go to their own file so the
    # summary stays readable; this is the deep-debug artifact.
    transcripts = {
        f"{r.get('game_id')}:{r.get('arm')}": r.pop("transcripts", [])
        for r in results
    }
    with open(os.path.join(KAGGLE_WORKING, "agent25_transcripts.json"), "w") as f:
        json.dump({"model": served, "transcripts": transcripts}, f, indent=2)

    out = {
        "games": BENCH_GAMES, "max_actions": MAX_ACTIONS, "model": served,
        "results": results,
    }
    with open(os.path.join(KAGGLE_WORKING, "agent25_bench.json"), "w") as f:
        json.dump(out, f, indent=2)

    on_code_prompts = sum(
        r.get("telemetry", {}).get("code_prompts", 0)
        for r in results if r.get("arm") == "on")
    print(f"\n[bridge] ON-arm total code prompts: {on_code_prompts}")
    if on_code_prompts == 0:
        raise RuntimeError(
            "BRIDGE INERT: the ON arm never issued a code prompt — the kernel "
            "vocabulary was never exercised. Check HARNESS_CODE_ESC / stall.")

    if server is not None:
        server.terminate()


if __name__ == "__main__":
    main()
