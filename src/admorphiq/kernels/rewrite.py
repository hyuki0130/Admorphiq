"""Pure rewrite-derivation kernels: a branching BFS search
(``derive_rewrites``/``find_derivation``) and a deterministic single-pass
greedy parse (``greedy_parse``) — two GENUINELY DIFFERENT engines over the
same (source tokens, (LHS, RHS) rules) shape, not two configurations of one
algorithm. The caller supplies tokens and rules; the kernels only compute.
This is the generic computation behind production-grammar win rules (e.g.
the TR87 class: an editable bar must be a valid derivation of a static bar)
— but neither kernel knows anything about bars, frames, or games.

BFS search (``derive_rewrites`` / ``find_derivation``)
--------------------------------------------------------
Explores every possible sequence of rule applications, branching at every
matching position and rule choice, to find ANY reachable derivation —
necessary when multiple derivations may exist and a specific target must be
found among them. Strategies:

- ``all_matches``: branch on every rule at every match position (one
  substitution per step). Complete single-step rewriting search.
- ``leftmost``: per rule, substitute only at its leftmost match.
- ``parallel``: per rule, substitute all non-overlapping matches
  simultaneously (greedy left-to-right), L-system style.

The search is breadth-first and deterministic: states expand in insertion
order, rules in index order, positions left to right. ``max_states`` bounds
the explored set; hitting it stops expansion (the return is then the
complete set of derivations found up to that point, not of the full space).

**Use BFS search only diagnostically, not as an action-driving fallback for
a grammar-shaped game.** A search finds ANY valid derivation reachable under
the rule set — but a real game's own win-check may require ONE SPECIFIC
committed parse (see ``greedy_parse`` below), and a derivation the search
finds via a different rule-choice order can be grammatically valid while
still being REJECTED by the game (Codex review,
``docs/r56_codex_tr87_review_20260715.md``). Use ``derive_rewrites``/
``find_derivation`` to ask "does ANY derivation exist" (a genuinely useful
diagnostic when ``greedy_parse`` fails and you need to know whether that's
because the rule SET is unparseable or because the greedy commitment order
was wrong) — never to generate the actual action plan for a game whose win
condition is a specific committed parse.

Deterministic greedy parse (``greedy_parse``)
-----------------------------------------------
A single left-to-right (or right-to-left) pass: at each position, apply the
FIRST rule (by list order) whose LHS matches, advance past the consumed
LHS, and never reconsider that choice. No branching, no backtracking — this
is the right (and much cheaper) tool when the task's OWN rule is itself a
committed, non-backtracking tiling, e.g. TR87's win-check parses its target
row exactly this way (see ``docs/tr87_frame_only_grammar_design_20260715.md``).
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
    zero-step derivation (source == target) returns ``[]``. See this
    module's docstring: use this diagnostically, not as an action-driving
    fallback for a grammar-shaped game — see :func:`greedy_parse`.
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


def greedy_parse(
    tokens: Sequence[Any], rules: Sequence[Sequence[Sequence[Any]]], direction: str = "ltr"
) -> dict[str, Any] | None:
    """Deterministic single-pass greedy token-string parse: NOT a search — see this module's docstring.

    Scans ``tokens`` from one end (``direction="ltr"`` from the left,
    ``"rtl"`` from the right), and at each position tries every rule *in
    list order*, applying the FIRST whose LHS matches a run of tokens
    starting there — no backtracking, and no consideration of any OTHER
    rule that might also have matched. On a match, the position advances
    past the consumed LHS run (not the RHS — the parse always consumes
    ``tokens``, the RHS only contributes to the OUTPUT). If NO rule matches
    at some position, the entire parse FAILS and this returns ``None`` —
    there is no partial-credit / pass-through-unmatched-tokens mode; every
    token must be covered by some rule's LHS.

    When a greedy tiling genuinely doesn't exist for some input even though
    a valid (non-greedy, differently-ordered) derivation does,
    ``greedy_parse`` returns ``None`` where :func:`find_derivation` would
    still find a derivation exists — useful as a DIAGNOSTIC to distinguish
    "this rule set is truly unparseable" from "the greedy commitment order
    was wrong," but see this module's docstring for why the search should
    not become the action-driving fallback.

    Returns ``{"result": tokens, "steps": [{"rule": idx, "position": p,
    "before": lhs_tokens, "after": rhs_tokens}, ...]}`` on success —
    ``result`` is the concatenation of every matched rule's RHS, in match
    order; ``position`` is always reported in ORIGINAL (``ltr``) token
    coordinates regardless of ``direction``, so steps from an ``"rtl"``
    parse are directly comparable to an ``"ltr"`` one. An empty ``tokens``
    trivially succeeds with an empty result and no steps, regardless of
    ``rules``. Raises ``ValueError`` for an unknown ``direction`` or a rule
    with an empty LHS (same rejection :func:`derive_rewrites` applies, and
    for the same reason: an empty LHS can never advance the scan position).
    """
    if direction not in ("ltr", "rtl"):
        raise ValueError(f"direction must be 'ltr' or 'rtl', got {direction!r}")
    normalized = _normalize_rules(rules)
    tokens_t = tuple(tokens)
    if direction == "ltr":
        return _greedy_parse_ltr(tokens_t, normalized)

    n = len(tokens_t)
    rev_tokens = tuple(reversed(tokens_t))
    rev_rules = [(tuple(reversed(lhs)), tuple(reversed(rhs))) for lhs, rhs in normalized]
    parsed = _greedy_parse_ltr(rev_tokens, rev_rules)
    if parsed is None:
        return None
    steps = []
    for step in reversed(parsed["steps"]):
        lhs_len = len(step["before"])
        orig_pos = n - step["position"] - lhs_len
        steps.append(
            {
                "rule": step["rule"],
                "position": orig_pos,
                "before": tuple(reversed(step["before"])),
                "after": tuple(reversed(step["after"])),
            }
        )
    return {"result": tuple(reversed(parsed["result"])), "steps": steps}


def _greedy_parse_ltr(tokens: Tokens, rules: list[Rule]) -> dict[str, Any] | None:
    pos = 0
    n = len(tokens)
    steps: list[dict[str, Any]] = []
    result: list[Any] = []
    while pos < n:
        matched = None
        for idx, (lhs, rhs) in enumerate(rules):
            m = len(lhs)
            if tokens[pos : pos + m] == lhs:
                matched = (idx, lhs, rhs)
                break
        if matched is None:
            return None
        idx, lhs, rhs = matched
        steps.append({"rule": idx, "position": pos, "before": lhs, "after": rhs})
        result.extend(rhs)
        pos += len(lhs)
    return {"result": tuple(result), "steps": steps}
