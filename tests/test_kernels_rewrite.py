"""Tests for the pure rewrite-derivation kernels (R56): the branching BFS
search (derive_rewrites/find_derivation) and the deterministic greedy parse
(greedy_parse)."""

import pytest

from admorphiq.kernels import derive_rewrites, find_derivation, greedy_parse


def test_single_rule_single_match_derives_one_string():
    """Purpose: the minimal contract — one rule, one match, depth 1 yields
    exactly the substituted string with a one-step proof.
    Expected feedback: failure means the core substitution or proof plumbing
    is broken; nothing built on this kernel can be trusted."""
    out = derive_rewrites(["a", "b"], [(["a"], ["c"])], max_depth=1, strategy="all_matches")
    assert len(out) == 1
    assert out[0]["result"] == ("c", "b")
    proof = out[0]["proof"]
    assert len(proof) == 1
    assert proof[0]["rule"] == 0
    assert proof[0]["positions"] == [0]
    assert proof[0]["before"] == ("a", "b")
    assert proof[0]["after"] == ("c", "b")


def test_all_matches_branches_on_every_position():
    """Purpose: 'all_matches' must branch per match position — "aa" with a→b
    at depth 1 yields both ("b","a") and ("a","b").
    Expected feedback: failure means position enumeration collapses branches,
    making the search incomplete (would silently miss valid derivations)."""
    out = derive_rewrites(["a", "a"], [(["a"], ["b"])], max_depth=1, strategy="all_matches")
    assert {o["result"] for o in out} == {("b", "a"), ("a", "b")}


def test_parallel_rewrites_all_non_overlapping_matches_in_one_step():
    """Purpose: 'parallel' substitutes every non-overlapping match in a single
    step (L-system semantics): "aa" with a→b yields only ("b","b") at depth 1.
    Expected feedback: failure means the parallel strategy degenerated into
    single substitution, breaking L-system-style derivations."""
    out = derive_rewrites(["a", "a"], [(["a"], ["b"])], max_depth=1, strategy="parallel")
    assert [o["result"] for o in out] == [("b", "b")]
    assert out[0]["proof"][0]["positions"] == [0, 1]


def test_leftmost_substitutes_only_first_match():
    """Purpose: 'leftmost' applies each rule only at its leftmost match.
    Expected feedback: failure means the strategy dispatcher mixes up
    strategies — derivation semantics would not match the declared mode."""
    out = derive_rewrites(["a", "a"], [(["a"], ["b"])], max_depth=1, strategy="leftmost")
    assert [o["result"] for o in out] == [("b", "a")]


def test_multi_token_lhs_and_expanding_rhs():
    """Purpose: LHS longer than one token and RHS of different length must
    substitute correctly ("a b c", ab→x gives ("x","c"); x→x y z expands).
    Expected feedback: failure means index arithmetic in _substitute is wrong
    for non-unit rule lengths — exactly the TR87-class rule shape."""
    out = derive_rewrites(
        ["a", "b", "c"],
        [(["a", "b"], ["x"]), (["x"], ["x", "y", "z"])],
        max_depth=2,
        strategy="leftmost",
    )
    results = {o["result"] for o in out}
    assert ("x", "c") in results
    assert ("x", "y", "z", "c") in results


def test_find_derivation_returns_proof_and_none():
    """Purpose: find_derivation returns a replayable proof when the target is
    reachable and None when it is not within max_depth.
    Expected feedback: failure breaks the primary adapter use ("is bar2 a
    valid derivation of bar1?") — false negatives would call solvable levels
    unsolvable and vice versa."""
    rules = [(["a"], ["b"]), (["b"], ["c"])]
    proof = find_derivation(["a"], ["c"], rules, max_depth=2)
    assert proof is not None and len(proof) == 2
    # Replay the proof: each step's after must chain to the next step's before.
    assert proof[0]["before"] == ("a",) and proof[-1]["after"] == ("c",)
    assert all(proof[i]["after"] == proof[i + 1]["before"] for i in range(len(proof) - 1))
    assert find_derivation(["a"], ["c"], rules, max_depth=1) is None


def test_zero_step_derivation_is_empty_proof():
    """Purpose: source == target is a valid zero-step derivation ([]), which
    is distinct from unreachable (None).
    Expected feedback: failure conflates 'already equal' with 'unreachable' —
    an adapter would misjudge already-solved states."""
    assert find_derivation(["a"], ["a"], [(["a"], ["b"])], max_depth=1) == []


def test_dedup_keeps_first_discovered_proof():
    """Purpose: a string reachable by multiple paths appears once, with the
    shortest (BFS-first) proof.
    Expected feedback: failure means duplicate states flood results or proofs
    are non-minimal, blowing up downstream consumers at TR87-scale rule sets."""
    rules = [(["a"], ["b"]), (["a"], ["c"]), (["c"], ["b"])]
    out = derive_rewrites(["a"], rules, max_depth=3, strategy="all_matches")
    b_entries = [o for o in out if o["result"] == ("b",)]
    assert len(b_entries) == 1
    assert len(b_entries[0]["proof"]) == 1


def test_invalid_strategy_and_empty_lhs_raise():
    """Purpose: contract validation — unknown strategy and empty-LHS rules are
    caller errors, rejected loudly rather than silently misbehaving.
    Expected feedback: failure means bad adapter/LLM input would produce
    garbage derivations instead of a diagnosable error."""
    with pytest.raises(ValueError):
        derive_rewrites(["a"], [(["a"], ["b"])], max_depth=1, strategy="bogus")
    with pytest.raises(ValueError):
        derive_rewrites(["a"], [([], ["b"])], max_depth=1)


def test_max_states_bounds_exploration():
    """Purpose: the state cap stops expansion so pathological rule sets
    (exponential growth) terminate deterministically.
    Expected feedback: failure means unbounded blowup — a runtime hang risk
    inside the 9h Kaggle budget."""
    rules = [(["a"], ["a", "a"])]
    out = derive_rewrites(["a"], rules, max_depth=50, strategy="leftmost", max_states=20)
    assert 0 < len(out) <= 20


# ---- greedy_parse: the deterministic single-pass engine, NOT the search above ----


def test_greedy_parse_first_matching_rule_wins_regardless_of_length():
    """Purpose: at a position where MULTIPLE rules' LHS match, greedy_parse
    must commit to whichever is FIRST in rule list order -- not the longest,
    not the "best" for eventual full coverage. Swapping the same two rules'
    order must swap which one wins, proving list order (not shape) decides.
    Expected feedback: failure means the match loop isn't scanning rules in
    strict list order, breaking the "no search, no backtracking" contract
    that distinguishes this from find_derivation."""
    short_first = [(("a",), ("x",)), (("a", "a"), ("y",))]
    out = greedy_parse(("a", "a"), short_first)
    assert out == {
        "result": ("x", "x"),
        "steps": [
            {"rule": 0, "position": 0, "before": ("a",), "after": ("x",)},
            {"rule": 0, "position": 1, "before": ("a",), "after": ("x",)},
        ],
    }

    long_first = [(("a", "a"), ("y",)), (("a",), ("x",))]
    out2 = greedy_parse(("a", "a"), long_first)
    assert out2 == {
        "result": ("y",),
        "steps": [{"rule": 0, "position": 0, "before": ("a", "a"), "after": ("y",)}],
    }


def test_greedy_parse_fails_where_find_derivation_succeeds():
    """Purpose: prove greedy_parse and find_derivation are genuinely
    different engines, not just different call signatures for the same
    search. Rule 0 ('a'->'x') greedily consumes the first 'a' in
    ('a','a','b'), leaving a lone 'b' no rule can ever cover -> greedy_parse
    must FAIL (None), even though rule 1 ('a','a','b'->'z') -- unreachable
    from position 0 once rule 0 already committed -- covers the ENTIRE
    input in one shot. find_derivation's branching search (which tries
    rule 1 as an alternative, not just rule 0's first match) finds exactly
    that derivation to target ('z',) at depth 1.
    Expected feedback: failure of the first assert means greedy_parse grew
    backtracking (violating its documented contract); failure of the
    second means find_derivation regressed on a case its own test suite
    doesn't otherwise cover (an all_matches branch at position 0 that is
    NOT the first-listed rule)."""
    tokens = ("a", "a", "b")
    rules = [(("a",), ("x",)), (("a", "a", "b"), ("z",))]
    assert greedy_parse(tokens, rules) is None
    proof = find_derivation(tokens, ("z",), rules, max_depth=1, strategy="all_matches")
    assert proof == [{"rule": 1, "positions": [0], "before": tokens, "after": ("z",)}]


def test_greedy_parse_rtl_scans_from_the_right_and_can_differ_from_ltr():
    """Purpose: direction="rtl" must genuinely change WHICH matches are made
    (not just relabel ltr's own steps) when the rule set is ambiguous, and
    must report "position" back in ORIGINAL (ltr) token coordinates so rtl
    and ltr results are directly comparable. Here the 2-token rule can only
    grab a pair of 'a's starting from wherever the scan begins: ltr grabs
    (0,1) then a lone 'a' at 2; rtl grabs (1,2) then a lone 'a' at 0 --
    genuinely different tilings, both correctly covering all 3 tokens.
    Expected feedback: failure means the reversed-rule construction or the
    position back-conversion math (n - rev_pos - lhs_len) is wrong."""
    tokens = ("a", "a", "a")
    rules = [(("a", "a"), ("P",)), (("a",), ("Q",))]

    ltr = greedy_parse(tokens, rules, direction="ltr")
    assert ltr == {
        "result": ("P", "Q"),
        "steps": [
            {"rule": 0, "position": 0, "before": ("a", "a"), "after": ("P",)},
            {"rule": 1, "position": 2, "before": ("a",), "after": ("Q",)},
        ],
    }

    rtl = greedy_parse(tokens, rules, direction="rtl")
    assert rtl == {
        "result": ("Q", "P"),
        "steps": [
            {"rule": 1, "position": 0, "before": ("a",), "after": ("Q",)},
            {"rule": 0, "position": 1, "before": ("a", "a"), "after": ("P",)},
        ],
    }


def test_greedy_parse_empty_tokens_trivially_succeeds():
    """Purpose: an empty token sequence has nothing to cover, so it must
    succeed trivially with an empty result and no steps -- regardless of
    what rules are supplied (even an empty rule list).
    Expected feedback: failure means the while-loop's termination condition
    doesn't handle n=0, either raising or misreporting failure."""
    assert greedy_parse((), [(("a",), ("x",))]) == {"result": (), "steps": []}


def test_greedy_parse_rejects_empty_lhs_rule():
    """Purpose: a rule with an empty LHS could never advance the scan
    position, which would make "first match wins" ill-defined at every
    position simultaneously (an empty LHS trivially "matches" everywhere)
    -- this must be rejected up front, mirroring derive_rewrites' identical
    rejection.
    Expected feedback: failure means a degenerate rule silently produces an
    infinite loop or nonsensical zero-width steps instead of a clear error."""
    with pytest.raises(ValueError, match="empty LHS"):
        greedy_parse(("a",), [((), ("x",))])


def test_greedy_parse_rejects_unknown_direction():
    """Purpose: direction is a closed two-value enum ('ltr'/'rtl') -- any
    other value is a caller contract violation and must raise clearly.
    Expected feedback: failure means an invalid direction is silently
    treated as one of the two valid values instead of surfaced as an error."""
    with pytest.raises(ValueError, match="direction"):
        greedy_parse(("a",), [(("a",), ("x",))], direction="sideways")
