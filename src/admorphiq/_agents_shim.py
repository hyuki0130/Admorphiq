"""Make ``agents.agent`` / ``agents.swarm`` importable without the heavy init.

The official ARC-AGI-3 ``agents`` package eagerly imports every template
agent in its ``__init__.py`` (langgraph / smolagents / Pillow-version-
sensitive vision code). We only need ``agents.agent.Agent`` and
``agents.swarm.Swarm``, which depend solely on ``arc_agi`` / ``arcengine``.

This module registers a *namespace-style* ``agents`` package in
``sys.modules`` pointing at the real framework directory's ``__path__`` but
with an empty ``__init__`` body, so submodule imports resolve to the real
files while the heavy template imports never run.

On Kaggle the wheels for the templates are installed, so the real
``__init__`` would work too — but bypassing it is harmless and keeps the
local dev path fast and dependency-light. Call :func:`ensure_agents_package`
before importing anything from ``agents``.
"""

from __future__ import annotations

import importlib.util
import os
import sys
import types

# Candidate locations of the official framework directory (contains ``agents/``).
_FRAMEWORK_CANDIDATES = (
    "/kaggle/input/ARC-AGI-3-Agents",
    os.path.join(os.getcwd(), "ARC-AGI-3-Agents"),
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "ARC-AGI-3-Agents"),
)


def _find_framework_dir() -> str | None:
    for cand in _FRAMEWORK_CANDIDATES:
        cand = os.path.abspath(cand)
        if os.path.isdir(os.path.join(cand, "agents")):
            return cand
    return None


def ensure_agents_package() -> None:
    """Make the ``agents`` package importable, preferring the real one.

    Strategy:
      1. If ``agents`` is already in ``sys.modules``, do nothing.
      2. Add the framework dir to ``sys.path`` and try a real import — on
         Kaggle (all template wheels present) this gives the full package
         including ``AVAILABLE_AGENTS``.
      3. If the real import fails (local dev without langgraph/smolagents/
         matching Pillow), fall back to a light namespace package exposing
         only the submodules we need.

    Idempotent.
    """
    if "agents" in sys.modules:
        return
    framework = _find_framework_dir()
    if framework is None:
        return
    if framework not in sys.path:
        sys.path.insert(0, framework)
    try:
        importlib.import_module("agents")
        return
    except Exception:
        # Real package init failed (missing heavy template deps locally).
        sys.modules.pop("agents", None)
    agents_dir = os.path.join(framework, "agents")
    pkg = types.ModuleType("agents")
    pkg.__path__ = [agents_dir]  # type: ignore[attr-defined]
    pkg.__package__ = "agents"
    sys.modules["agents"] = pkg


def load_agent_class():
    """Return the official ``agents.agent.Agent`` base class."""
    ensure_agents_package()
    spec = importlib.util.find_spec("agents.agent")
    if spec is None or spec.loader is None:  # pragma: no cover - defensive
        raise ImportError("Could not locate agents.agent")
    module = importlib.util.module_from_spec(spec)
    sys.modules.setdefault("agents.agent", module)
    spec.loader.exec_module(module)
    return module.Agent
