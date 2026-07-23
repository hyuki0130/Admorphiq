"""R97 build #2 tests: the dedicated AST-validating sandbox for the authored
``update`` function.

The validator's acceptance + rejection surface (imports, extra statements, wrong
signature, decorators, global/nonlocal, nested defs/classes, dangerous attributes
and dunder escape handles, AST size cap), the subprocess executor's contract
enforcement (return-in-palette, non-mutation, timeout), and the reusable
:class:`AuthoredUpdate` wrapper + the extensional-equivalence helper.
"""

from __future__ import annotations

import pytest

from admorphiq.hypothesis_select.authored import (
    AuthoredError,
    AuthoredUpdate,
    execute_in_subprocess,
    extensionally_equal,
    validate_authored,
)

_SUCC = (
    "def update(colour, click_index, palette):\n"
    "    i = palette.index(colour)\n"
    "    return palette[(i + 1) % len(palette)]\n"
)
_IDENTITY = "def update(colour, click_index, palette):\n    return colour\n"


def test_validate_accepts_a_pure_cyclic_successor_rule():
    """Purpose: a well-formed pure ``update`` using only arithmetic, indexing, and
    the whitelisted ``.index`` list lookup validates ok, with a counted AST size.

    Expected feedback: pass proves the validator permits the rules the tier-2
    contract actually needs. Fail means the gate is too strict and no legal rule
    can pass, defeating self-extension."""
    result = validate_authored(_SUCC)
    assert result.ok is True
    assert result.reason == ""
    assert result.node_count > 0


@pytest.mark.parametrize(
    "source, needle",
    [
        ("def update(colour, click_index, palette):\n    import os\n    return colour\n", "import"),
        ("import os\ndef update(colour, click_index, palette):\n    return colour\n", "exactly one function"),
        ("x = 1\ndef update(colour, click_index, palette):\n    return colour\n", "exactly one function"),
        ("def other(colour, click_index, palette):\n    return colour\n", "named 'update'"),
        ("def update(a, b, c):\n    return a\n", "parameters must be"),
        ("def update(colour, click_index, palette, extra):\n    return colour\n", "parameters must be"),
        ("@staticmethod\ndef update(colour, click_index, palette):\n    return colour\n", "decorators"),
        ("def update(colour, click_index, palette):\n    global x\n    return colour\n", "global/nonlocal"),
        (
            "def update(colour, click_index, palette):\n    def inner():\n        return 0\n    return colour\n",
            "nested function",
        ),
        ("def update(colour, click_index, palette):\n    class C:\n        pass\n    return colour\n", "class/lambda"),
        ("def update(colour, click_index, palette):\n    return colour.__class__\n", "attribute access"),
        ("def update(colour, click_index, palette):\n    return palette.append(colour)\n", "attribute access"),
        ("def update(colour, click_index, palette):\n    return eval('1')\n", "disallowed name 'eval'"),
        ("def update(colour, click_index, palette):\n    return (\n", "syntax error"),
    ],
)
def test_validate_rejects_disallowed_constructs(source: str, needle: str):
    """Purpose: every disallowed construct — imports, extra top-level statements,
    wrong name/signature, decorators, global, nested def, class, dunder/method
    attribute access, dangerous builtins, and syntax errors — is rejected with a
    reason that names the violation.

    Expected feedback: pass proves the AST gate closes each escape/contract hole
    the R49 loader left open (Codex correction 8). Fail means a rejected shape
    leaked through and the sandbox trust boundary is unsound."""
    result = validate_authored(source)
    assert result.ok is False
    assert needle in result.reason


def test_validate_rejects_oversized_ast():
    """Purpose: a function whose AST exceeds the node cap is rejected before
    execution.

    Expected feedback: pass proves the size bound holds (a runaway generation
    cannot be run). Fail means the AST cap is not enforced."""
    body = "\n".join(f"    x{i} = colour + {i}" for i in range(200))
    source = f"def update(colour, click_index, palette):\n{body}\n    return colour\n"
    result = validate_authored(source)
    assert result.ok is False
    assert "AST too large" in result.reason


def test_subprocess_runs_a_valid_rule_and_enforces_the_return_contract():
    """Purpose: the subprocess executor runs a valid rule and returns its value,
    and rejects a return outside the palette, a palette mutation, and a non-int
    return.

    Expected feedback: pass proves the trust-boundary executor enforces
    return-in-palette + non-mutation + int type in a fresh interpreter. Fail means
    an out-of-contract result could be trusted."""
    ok = execute_in_subprocess(_SUCC, 8, 0, [8, 9, 12])
    assert ok.ok is True and ok.value == 9
    out_of_palette = execute_in_subprocess(
        "def update(colour, click_index, palette):\n    return 99\n", 8, 0, [8, 9, 12]
    )
    assert out_of_palette.ok is False and "not in palette" in out_of_palette.error
    mutation = execute_in_subprocess(
        "def update(colour, click_index, palette):\n    palette[0] = 99\n    return colour\n", 8, 0, [8, 9, 12]
    )
    assert mutation.ok is False and "mutated" in mutation.error
    non_int = execute_in_subprocess(
        "def update(colour, click_index, palette):\n    return [colour]\n", 8, 0, [8, 9, 12]
    )
    assert non_int.ok is False


def test_subprocess_times_out_on_an_infinite_loop():
    """Purpose: a validated-but-non-terminating rule is bounded by the wall-clock
    timeout and reported as a failure, not a hang.

    Expected feedback: pass proves the executor cannot be hung by an authored
    infinite loop. Fail means a runaway rule blocks the harness."""
    loop = "def update(colour, click_index, palette):\n    while True:\n        colour = colour\n    return colour\n"
    result = execute_in_subprocess(loop, 8, 0, [8, 9, 12], timeout=0.6)
    assert result.ok is False and result.error == "timeout"


def test_authored_update_wrapper_predicts_counts_and_hashes():
    """Purpose: AuthoredUpdate validates + probes at construction, then serves fast
    predictions, counting invocations and pinning the source hash + proposed name.

    Expected feedback: pass proves the reusable wrapper is ready for causal planning
    use (audit counter + hash). Fail means the compiler node cannot log/trust the
    authored rule."""
    au = AuthoredUpdate(_SUCC, "cyclic_successor")
    assert au.name == "cyclic_successor"
    assert len(au.source_hash) == 64
    assert au.predict(8, 0, [8, 9, 12]) == 9
    assert au.predict(9, 0, [8, 9, 12]) == 12
    assert au.invocations == 2


def test_authored_update_rejects_invalid_source_at_construction():
    """Purpose: constructing AuthoredUpdate from an invalid source raises
    AuthoredError — an unvalidated rule never becomes a usable object.

    Expected feedback: pass proves validation gates construction. Fail means an
    invalid rule could be wrapped and later executed."""
    with pytest.raises(AuthoredError):
        AuthoredUpdate("import os\ndef update(colour, click_index, palette):\n    return colour\n", "bad")


def test_extensional_equivalence_matches_a_canned_rule_and_finds_mismatches():
    """Purpose: extensionally_equal reports an authored cyclic-successor as EQUAL to
    the canned successor over exhaustive palette x click-index fixtures, and reports
    the identity rule as UNEQUAL with the first diverging fixture.

    Expected feedback: pass proves behaviour-over-fixtures equivalence (Codex
    correction 7) — an authored rule can be checked against a canned rule without
    source identity. Fail means metamorphic equivalence is unreliable."""
    palette = [8, 9, 12]
    canned = lambda c, k, pal: pal[(pal.index(c) + 1) % len(pal)]  # noqa: E731 - test-local rule
    equal, mismatch = extensionally_equal(AuthoredUpdate(_SUCC, "succ"), canned, palette)
    assert equal is True and mismatch is None
    unequal, first = extensionally_equal(AuthoredUpdate(_IDENTITY, "id"), canned, palette)
    assert unequal is False and first is not None
