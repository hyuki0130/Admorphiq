"""agent25 native tool-calling routing (R92 redesign).

Purpose: prove the staged tool-calling layer works — select_strategy routes to a
fixed tool or to the kernel-code path, the schemas carry rich descriptions, and
dealias/deadsig are NOT routable peers.

Expected feedback: pass = native function-calling routing is wired correctly (a
model tool_call maps to the right (mode, tool)); fail = the routing contract broke.
"""

from __future__ import annotations

import json

from admorphiq.harness.registry import default_tools
from admorphiq.harness.toolcall_agent import (
    _STRATEGY_DESCRIPTIONS,
    _WRITE_SOLVER_SCHEMA,
    ToolCallAgent,
    _select_schema,
)


class _Sig:
    def as_line(self) -> str:
        return "movement grid avatar"


def _agent(strategy: str) -> ToolCallAgent:
    def chat(messages, tools=None, tool_choice=None) -> dict:
        return {"content": "", "tool_calls": [
            {"function": {"name": "select_strategy",
                          "arguments": json.dumps({"strategy": strategy, "reason": "x"})}}]}
    return ToolCallAgent(default_tools(), lambda m: "{}", chat,
                         giveup=8000, stall=80, ctx_budget=6000)


def test_schemas_serialize_with_rich_descriptions() -> None:
    """Purpose: the tool schemas are valid and carry per-strategy usage docs.
    Expected: JSON-serializable; routing description names every strategy."""
    sel = _select_schema(list(_STRATEGY_DESCRIPTIONS))
    json.dumps(sel)
    json.dumps(_WRITE_SOLVER_SCHEMA)
    desc = sel["function"]["description"]
    assert all(s in desc for s in ("graph", "kernel_code", "world_model"))
    assert _WRITE_SOLVER_SCHEMA["function"]["parameters"]["properties"]["code"]["maxLength"] == 12000


def test_route_to_fixed_tool() -> None:
    """Purpose: a select_strategy tool_call naming a fixed tool routes to it.
    Expected: _decide -> ('tool','graph'); route_valid increments."""
    ag = _agent("graph")
    assert ag._decide(_Sig()) == ("tool", "graph")
    assert ag.route_valid == 1


def test_route_to_kernel_code() -> None:
    """Purpose: strategy 'kernel_code' routes to the code path.
    Expected: _decide -> ('code', None)."""
    assert _agent("kernel_code")._decide(_Sig()) == ("code", None)


def test_dealias_deadsig_not_routable() -> None:
    """Purpose: augmenter tools are always-on, never offered as peer strategies.
    Expected: they are absent from the routable enum."""
    ag = _agent("graph")
    assert "dealias" not in ag._routable
    assert "deadsig" not in ag._routable
    assert "kernel_code" in ag._routable


def test_bad_strategy_falls_back_to_signature_default() -> None:
    """Purpose: an invalid/failed strategy pick degrades to the signature tool.
    Expected: _decide returns a ('tool', <name>) with a real tool name, no crash."""
    ag = _agent("nonexistent_tool")
    mode, name = ag._decide(_Sig())
    assert mode == "tool" and name in ag.tools
