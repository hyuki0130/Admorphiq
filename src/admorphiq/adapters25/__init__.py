"""Quarantine zone: game-specific script25 adapters (R56).

****************************************************************************
* MODEL-NEVER-VISIBLE. See ``admorphiq.adapters25.base``'s module          *
* docstring for the full quarantine rationale. The runtime LLM/harness     *
* agent (``admorphiq.harness``) must never import this package.           *
****************************************************************************

An adapter module living directly under this package (e.g.
``admorphiq/adapters25/m0r0.py``) MAY assign roles ("this region is the
goal"), declare a mechanic hypothesis, and derive thresholds from live
observations. It MUST NOT:

  - import anything outside the standard library, ``admorphiq.kernels``
    (any submodule), and ``admorphiq.adapters25.base``;
  - contain its own BFS/search/pixel-processing algorithm — call a kernel
    instead;
  - hardcode coordinate constants for actions — coordinates must come from
    kernel outputs computed over observed frames.

Enforced mechanically, best-effort, by ``scripts/adapters25_lint.py``.

Discovery contract: each adapter module defines two module-level names —
``GAME_ID: str`` (a lowercase substring matched against ``"<game_id>
<title>"`` to select which live environments the adapter targets) and
``Adapter: type[GameAdapter]``. :func:`discover_adapters` walks this
package's direct submodules (excluding ``base``) and collects them.
"""

from __future__ import annotations

import importlib
import pkgutil

from admorphiq.adapters25.base import GameAdapter

_EXCLUDED_MODULES = {"base"}


def discover_adapters() -> dict[str, type[GameAdapter]]:
    """Map ``GAME_ID -> Adapter class`` for every adapter module in this package.

    A submodule missing either ``GAME_ID`` or ``Adapter`` is silently
    skipped (not every future file under this package need be a complete
    adapter — e.g. shared test fixtures).
    """
    out: dict[str, type[GameAdapter]] = {}
    package = importlib.import_module(__name__)
    for info in pkgutil.iter_modules(package.__path__):
        if info.name in _EXCLUDED_MODULES or info.name.startswith("_"):
            continue
        module = importlib.import_module(f"{__name__}.{info.name}")
        game_id = getattr(module, "GAME_ID", None)
        adapter_cls = getattr(module, "Adapter", None)
        if not game_id or adapter_cls is None:
            continue
        out[game_id] = adapter_cls
    return out


__all__ = ["GameAdapter", "discover_adapters"]
