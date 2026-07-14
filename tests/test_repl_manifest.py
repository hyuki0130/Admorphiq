"""Tests for the bench run manifest (R55 observability, item 3).

These lock that the manifest pins the reproducibility fields (run id, git commit
+ dirty flag, model, prompt version, game list, config env) defensively — it must
build and serialize off-Kaggle without a repo or optional deps.
"""

from __future__ import annotations

import json

from admorphiq.repl_agent.manifest import (
    PROMPT_VERSION,
    build_manifest,
    write_manifest,
)


def test_build_manifest_has_reproducibility_fields():
    """Purpose: the manifest carries run_id, git, model, prompt version, budget,
    and the game list.

    Feedback: failure means a run can't be reproduced or compared to a baseline.
    """
    m = build_manifest(model="qwen", baseline="chained-card",
                       game_list=["su15", "ls20"], accelerator="RTX PRO 6000",
                       max_actions=150, wall_s=600.0, clock=lambda: 1000.0)
    assert m["run_id"] == "repl-1000"
    assert m["prompt_version"] == PROMPT_VERSION
    assert set(m["git"]) == {"commit", "dirty"}
    assert m["model"] == "qwen"
    assert m["game_list"] == ["su15", "ls20"]
    assert m["budget"] == {"max_actions": 150, "wall_s": 600.0}
    json.dumps(m)  # serializable


def test_config_env_filtered(monkeypatch):
    """Purpose: only REPL_/VLLM_-prefixed env vars are captured (no secrets/noise).

    Feedback: failure means the manifest leaks unrelated env or misses config.
    """
    monkeypatch.setenv("REPL_LLM_MODEL", "qwen")
    monkeypatch.setenv("VLLM_ATTENTION_BACKEND", "TRITON_ATTN")
    monkeypatch.setenv("UNRELATED_SECRET", "nope")
    m = build_manifest()
    assert m["config_env"].get("REPL_LLM_MODEL") == "qwen"
    assert m["config_env"].get("VLLM_ATTENTION_BACKEND") == "TRITON_ATTN"
    assert "UNRELATED_SECRET" not in m["config_env"]


def test_write_manifest_roundtrips(tmp_path):
    """Purpose: write_manifest persists a reloadable JSON manifest.

    Feedback: failure means run_manifest.json can't be written/read.
    """
    path = tmp_path / "run_manifest.json"
    written = write_manifest(path, model="qwen", game_list=["su15"])
    reloaded = json.loads(path.read_text())
    assert reloaded["model"] == "qwen"
    assert reloaded["run_id"] == written["run_id"]
