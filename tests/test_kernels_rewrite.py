"""Tests for the pure rewrite-derivation kernel (R56)."""

import pytest

from admorphiq.kernels import derive_rewrites, find_derivation


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
