"""Minimal, signature-targeted LLM-wiki context for the runtime model.

The runtime model has a bounded context window; feeding it the whole wiki
wastes budget and degrades an already-weak model. Instead we compute an
observable frame SIGNATURE and pull only the relevant slices of
``.wiki/wiki/tool_selector.md`` — the decision header plus the per-tool blocks
whose trigger the signature matches — capped at a char budget the bench can
sweep. This is context injection as retrieval, not few-shot prompting.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from admorphiq.tools.base import (
    availability,
    base_hash,
    changed_mask,
    diff_bbox,
)

_WIKI = Path(__file__).resolve().parents[3] / ".wiki" / "wiki" / "tool_selector.md"


@dataclass
class Signature:
    """Observable, game-agnostic frame signature used to target context + tools."""

    avatar_mobility: float  # fraction of simple-action changes that are small+local
    click_fraction: float   # fraction of available actions that are clicks (ACTION6)
    nondeterminism: float   # same (state, action) -> different next-state rate
    recolor_scale: float    # mean changed-cell count of observed transitions
    has_movement: bool      # any of simple ids 1-4 available

    def as_line(self) -> str:
        return (
            f"avatar_mobility={self.avatar_mobility:.2f}; "
            f"click_fraction={self.click_fraction:.2f}; "
            f"nondeterminism={self.nondeterminism:.2f}; "
            f"recolor_scale={self.recolor_scale:.0f}; "
            f"has_movement={self.has_movement}"
        )


def compute_signature(
    obs: object, transitions: list[tuple[np.ndarray, int, np.ndarray]]
) -> Signature:
    """Derive the observable signature from availability + observed transitions.

    ``transitions`` is a list of (prev_frame, action_id, next_frame) the agent
    has actually taken this game — the only evidence available offline.
    """
    simple_ids, action6 = availability(obs)
    avail = list(simple_ids) + ([6] if action6 else [])
    click_fraction = (sum(a >= 6 for a in avail) / len(avail)) if avail else 0.0
    has_movement = any(a in (1, 2, 3, 4) for a in simple_ids)

    small_local = simple_n = 0
    recolor: list[int] = []
    seen: dict[tuple[str, int], str] = {}
    nd = pairs = 0
    for prev, act, nxt in transitions:
        m = changed_mask(prev, nxt)
        changed = int(m.sum()) if m.size else 0
        recolor.append(changed)
        if act < 4 and changed > 0:
            simple_n += 1
            bb = diff_bbox(prev, nxt)
            if bb is not None:
                area = (bb[2] - bb[0] + 1) * (bb[3] - bb[1] + 1)
                if changed <= 40 and area <= 400:
                    small_local += 1
        key = (base_hash(prev), int(act))
        h = base_hash(nxt)
        if key in seen:
            pairs += 1
            nd += seen[key] != h
        else:
            seen[key] = h

    return Signature(
        avatar_mobility=small_local / simple_n if simple_n else 0.0,
        click_fraction=click_fraction,
        nondeterminism=nd / pairs if pairs else 0.0,
        recolor_scale=float(np.mean(recolor)) if recolor else 0.0,
        has_movement=has_movement,
    )


def _split_tool_blocks(text: str) -> tuple[str, dict[str, str]]:
    """Split tool_selector.md into (header-before-first-tool, {tool_name: block}).

    A tool block starts at a heading line that names a tool (case-insensitive
    match of a known tool name in the heading). Everything before the first
    such heading is the shared decision header.
    """
    lines = text.splitlines(keepends=True)
    tool_names = ["graph", "dealias", "deadsig", "paint", "world_model", "llm_goal", "code"]
    blocks: dict[str, str] = {}
    header: list[str] = []
    cur_name: str | None = None
    cur: list[str] = []

    def _flush() -> None:
        if cur_name is not None:
            blocks.setdefault(cur_name, "")
            blocks[cur_name] += "".join(cur)

    for ln in lines:
        heading = re.match(r"^#{2,4}\s+(.*)$", ln)
        matched = None
        if heading:
            low = heading.group(1).lower()
            for name in tool_names:
                if re.search(rf"\b{re.escape(name)}\b", low):
                    matched = name
                    break
        if matched is not None:
            _flush()
            cur_name = matched
            cur = [ln]
        elif cur_name is None:
            header.append(ln)
        else:
            cur.append(ln)
    _flush()
    return "".join(header), blocks


def _relevant_tools(sig: Signature) -> list[str]:
    """Order tool names by how well the signature matches their trigger."""
    scored: list[tuple[float, str]] = []
    scored.append((0.9 if sig.has_movement and sig.avatar_mobility >= 0.4 else 0.3, "graph"))
    scored.append((0.9 if sig.nondeterminism >= 0.2 else 0.1, "dealias"))
    scored.append((0.5, "deadsig"))  # efficiency aug — broadly useful
    scored.append((0.8 if sig.click_fraction >= 0.5 else 0.2, "paint"))
    scored.append((0.7 if sig.nondeterminism < 0.15 else 0.3, "world_model"))
    scored.append((0.8 if (not sig.has_movement and sig.recolor_scale >= 40) else 0.3, "llm_goal"))
    scored.append((0.6, "code"))  # the frontier fallback — always an option
    scored.sort(reverse=True)
    return [name for _, name in scored]


def build_context(sig: Signature, budget_chars: int = 6000) -> str:
    """Assemble the minimal wiki slice for this signature, within ``budget_chars``.

    Always includes the decision header, then appends the most-relevant tool
    blocks until the budget is hit. ``budget_chars`` is the lever the bench
    sweeps to find the context size that maximises runtime performance.
    """
    if not _WIKI.exists():
        return ""
    text = _strip_frontmatter(_WIKI.read_text(encoding="utf-8"))
    header, blocks = _split_tool_blocks(text)
    out = [header.strip()]
    used = len(out[0])
    for name in _relevant_tools(sig):
        blk = blocks.get(name)
        if not blk:
            continue
        if used + len(blk) > budget_chars:
            continue
        out.append(blk.rstrip())
        used += len(blk)
    assembled = "\n\n".join(p for p in out if p)
    # Hard cap: a tiny budget must win even over the always-included header, so
    # the runtime model's window is never blown by a large decision header.
    return assembled[:budget_chars]


def _strip_frontmatter(text: str) -> str:
    """Drop a leading YAML frontmatter block (the retriever strips it at runtime)."""
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            nl = text.find("\n", end + 1)
            return text[nl + 1:] if nl != -1 else ""
    return text
