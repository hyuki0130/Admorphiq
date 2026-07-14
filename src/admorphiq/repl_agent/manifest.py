"""Run manifest for the bench (R55 observability, item 3).

A `run_manifest.json` written at bench START pins everything needed to interpret
and reproduce a run: a run id, the git commit + dirty-tree flag, the model, the
prompt version, relevant config/env, package versions, the game list, the
accelerator, and the start time. Gathering is defensive (works off-Kaggle, never
raises) so it can be unit-tested without a git repo or Kaggle mounts.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "1"
# Bump when the model-facing prompt contract (_SYSTEM_PROMPT / packet) changes,
# so runs are comparable only within a prompt version.
PROMPT_VERSION = "v4"

_ENV_PREFIXES = ("REPL_", "VLLM_", "HARNESS_", "VLM_")


def _git_info() -> dict[str, Any]:
    def _run(args: list[str]) -> str:
        try:
            return subprocess.run(["git", *args], capture_output=True, text=True,
                                  timeout=10).stdout.strip()
        except Exception:  # noqa: BLE001 — off-repo / no git is fine
            return ""
    commit = _run(["rev-parse", "HEAD"])
    dirty = bool(_run(["status", "--porcelain"]))
    return {"commit": commit, "dirty": dirty}


def _pkg_versions() -> dict[str, str]:
    out: dict[str, str] = {}
    for name in ("admorphiq", "arc_agi", "arcengine", "vllm", "numpy"):
        try:
            mod = __import__(name)
            out[name] = str(getattr(mod, "__version__", "?"))
        except Exception:  # noqa: BLE001 — optional deps off-Kaggle
            out[name] = "absent"
    return out


def _config_env() -> dict[str, str]:
    return {k: v for k, v in os.environ.items() if k.startswith(_ENV_PREFIXES)}


def build_manifest(
    *,
    run_id: str | None = None,
    model: str = "",
    baseline: str = "",
    game_list: list[str] | None = None,
    accelerator: str = "",
    max_actions: int = 0,
    wall_s: float = 0.0,
    expected_artifacts: list[str] | None = None,
    clock: Any = time.time,
) -> dict[str, Any]:
    """Assemble the manifest dict (defensive; never raises)."""
    ts = clock()
    return {
        "run_id": run_id or f"repl-{int(ts)}",
        "schema_version": SCHEMA_VERSION,
        "prompt_version": PROMPT_VERSION,
        "baseline": baseline,
        "git": _git_info(),
        "model": model,
        "python": sys.version.split()[0],
        "config_env": _config_env(),
        "versions": _pkg_versions(),
        "game_list": list(game_list or []),
        "accelerator": accelerator,
        "budget": {"max_actions": max_actions, "wall_s": wall_s},
        "start_time": ts,
        "expected_artifacts": expected_artifacts or [
            "diagnostics/{game}.json", "transcripts/{game}.jsonl",
            "events/{game}.events.jsonl",
        ],
    }


def write_manifest(path: str | Path, **kwargs: Any) -> dict[str, Any]:
    """Build + write run_manifest.json; return the manifest dict."""
    manifest = build_manifest(**kwargs)
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    return manifest
