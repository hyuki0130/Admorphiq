"""Pure rewrite-derivation kernel.

Given a source token string and a set of (LHS, RHS) production rules, derive
the strings reachable within a depth bound, each with a step-by-step proof.
This is the generic computation behind production-grammar win rules (e.g. the
TR87 class: an editable bar must be a valid derivation of a static bar) —
but the kernel knows nothing about bars, frames, or games. The caller supplies
tokens and rules; the kernel only computes.

Strategies
----------
- ``all_matches``: branch on every rule at every match position (one
  substitution per step). Complete single-step rewriting search.
- ``leftmost``: per rule, substitute only at its leftmost match.
- ``parallel``: per rule, substitute all non-overlapping matches
  simultaneously (greedy left-to-right), L-system style.

The search is breadth-first and deterministic: states expand in insertion
order, rules in index order, positions left to right. ``max_states`` bounds
the explored set; hitting it stops expansion (the return is then the
complete set of derivations found up to that point, not of the full space).
"""

from __future__ import annotations

from collections import deque
from collections.abc import Sequence
from typing import Any

Tokens = tuple[Any, ...]
Rule = tuple[Tokens, Tokens]

_STRATEGIES = ("all_matches", "leftmost", "parallel")


def _normalize_rules(rules: Sequence[Sequence[Sequence[Any]]]) -> list[Rule]:
    normalized: list[Rule] = []
    for i, rule in enumerate(rules):
        lhs, rhs = rule
        lhs_t, rhs_t = tuple(lhs), tuple(rhs)
        if not lhs_t:
            raise ValueError(f"rule {i}: empty LHS is not a valid production")
        normalized.append((lhs_t, rhs_t))
    return normalized


def _match_positions(tokens: Tokens, lhs: Tokens) -> list[int]:
    m = len(lhs)
    if m > len(tokens):
        return []
    return [i for i in range(len(tokens) - m + 1) if tokens[i : i + m] == lhs]


def _substitute(tokens: Tokens, positions: Sequence[int], lhs_len: int, rhs: Tokens) -> Tokens:
    out: list[Any] = []
    cursor = 0
    for pos in positions:
        out.extend(tokens[cursor:pos])
        out.extend(rhs)
        cursor = pos + lhs_len
    out.extend(tokens[cursor:])
    return tuple(out)


def _non_overlapping(positions: list[int], lhs_len: int) -> list[int]:
    picked: list[int] = []
    next_free = 0
    for pos in positions:
        if pos >= next_free:
            picked.append(pos)
            next_free = pos + lhs_len
    return picked


def _successors(tokens: Tokens, rules: list[Rule], strategy: str) -> list[tuple[Tokens, dict[str, Any]]]:
    succ: list[tuple[Tokens, dict[str, Any]]] = []
    for rule_index, (lhs, rhs) in enumerate(rules):
        positions = _match_positions(tokens, lhs)
        if not positions:
            continue
        if strategy == "all_matches":
            applied = [[p] for p in positions]
        elif strategy == "leftmost":
            applied = [[positions[0]]]
        else:  # parallel
            applied = [_non_overlapping(positions, len(lhs))]
        for pos_group in applied:
            result = _substitute(tokens, pos_group, len(lhs), rhs)
            step = {
                "rule": rule_index,
                "positions": list(pos_group),
                "before": tokens,
                "after": result,
            }
            succ.append((result, step))
    return succ


def derive_rewrites(
    source_tokens: Sequence[Any],
    rules: Sequence[Sequence[Sequence[Any]]],
    max_depth: int,
    strategy: str = "parallel",
    max_states: int = 10_000,
) -> list[dict[str, Any]]:
    """Derive all distinct token strings reachable from ``source_tokens``.

    Returns ``[{"result": tokens, "proof": [step, ...]}, ...]`` for every
    distinct string reachable in 1..max_depth steps, in BFS discovery order.
    Each proof step records ``rule`` (index into ``rules``), ``positions``,
    ``before`` and ``after``. The source itself is not included.
    """
    if strategy not in _STRATEGIES:
        raise ValueError(f"strategy must be one of {_STRATEGIES}, got {strategy!r}")
    normalized = _normalize_rules(rules)
    source = tuple(source_tokens)

    seen: dict[Tokens, list[dict[str, Any]]] = {source: []}
    queue: deque[tuple[Tokens, int]] = deque([(source, 0)])
    results: list[dict[str, Any]] = []

    while queue:
        tokens, depth = queue.popleft()
        if depth >= max_depth:
            continue
        for result, step in _successors(tokens, normalized, strategy):
            if result in seen:
                continue
            proof = seen[tokens] + [step]
            seen[result] = proof
            results.append({"result": result, "proof": proof})
            if len(seen) < max_states:
                queue.append((result, depth + 1))
    return results


def find_derivation(
    source_tokens: Sequence[Any],
    target_tokens: Sequence[Any],
    rules: Sequence[Sequence[Sequence[Any]]],
    max_depth: int,
    strategy: str = "parallel",
    max_states: int = 10_000,
) -> list[dict[str, Any]] | None:
    """Return a proof that ``target_tokens`` derives from ``source_tokens``, or None.

    Early-exits on first hit; same search as :func:`derive_rewrites`. A
    zero-step derivation (source == target) returns ``[]``.
    """
    if strategy not in _STRATEGIES:
        raise ValueError(f"strategy must be one of {_STRATEGIES}, got {strategy!r}")
    normalized = _normalize_rules(rules)
    source = tuple(source_tokens)
    target = tuple(target_tokens)
    if source == target:
        return []

    seen: dict[Tokens, list[dict[str, Any]]] = {source: []}
    queue: deque[tuple[Tokens, int]] = deque([(source, 0)])

    while queue:
        tokens, depth = queue.popleft()
        if depth >= max_depth:
            continue
        for result, step in _successors(tokens, normalized, strategy):
            if result in seen:
                continue
            proof = seen[tokens] + [step]
            if result == target:
                return proof
            seen[result] = proof
            if len(seen) < max_states:
                queue.append((result, depth + 1))
    return None
