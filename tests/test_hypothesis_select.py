"""Unit tests for the R95a discriminative-selection templates + probe split.

No trace loads, no LLM, no environment — every fixture is a tiny hand-built
frame so the template contract is exercised deterministically.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

from admorphiq.hypothesis_select import (
    ft09_templates,
    sc25_templates,
    templates_for_game,
)

_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "probe_hypothesis_select.py"
_SPEC = importlib.util.spec_from_file_location("probe_hypothesis_select", _SCRIPT)
assert _SPEC is not None and _SPEC.loader is not None
_MOD = importlib.util.module_from_spec(_SPEC)
sys.modules["probe_hypothesis_select"] = _MOD
_SPEC.loader.exec_module(_MOD)

Transition = _MOD.Transition
_split_by_level = _MOD._split_by_level
_tie_group = _MOD._tie_group
_oracle_strictly_wins = _MOD._oracle_strictly_wins
_is_cast_state = _MOD._is_cast_state
build_ask_prompt = _MOD.build_ask_prompt
ask_once = _MOD.ask_once
_score_choice = _MOD._score_choice
_parse_choice = _MOD._parse_choice
_NEUTRAL_DESCRIPTIONS = _MOD._NEUTRAL_DESCRIPTIONS


def _tiny_transitions(game: str) -> list:
    """A handful of ACTION6 transitions on a small grid — enough for
    build_ask_prompt to assemble (perception on the frames returns empty
    structure, which is fine; the leak/determinism guards are about the prompt
    text, not the observation numbers)."""
    before = tuple(tuple(0 for _ in range(12)) for _ in range(12))
    after = tuple(
        tuple(5 if (r, c) == (3, 3) else 0 for c in range(12)) for r in range(12)
    )
    return [
        Transition(i, 6, (3, 3), i % 2, i % 2 == 0, before, after, i % 2)
        for i in range(6)
    ]


def _by_name(templates):
    return {t.name: t for t in templates}


# A plus of single-pixel buttons on background 0: a centre button at (2,2) with
# one cardinal neighbour in each direction. Clicking the centre changes exactly
# that one cell; the GF(2) stencil hypothesis claims it changes all five.
_FT09_PLUS = (
    (0, 0, 5, 0, 0),
    (0, 0, 0, 0, 0),
    (5, 0, 5, 0, 5),
    (0, 0, 0, 0, 0),
    (0, 0, 5, 0, 0),
)


def test_ft09_oracle_is_single_cell_gf2_is_multicell():
    """Purpose: the ft09 oracle (glyph_constraints) claims a click changes ONE
    cell, while the GF(2)-stencil hard negative claims it changes the clicked
    cell plus its four cardinal neighbours.

    Expected feedback: pass proves the two templates make structurally different
    dynamics claims (single-cell vs multi-cell) — the discriminator R95a scores
    on held-out transitions. Fail means the negative collapsed into the oracle
    and the ft09 set no longer tests dynamics selection."""
    templates = _by_name(ft09_templates())
    oracle = templates["glyph_constraints"]
    gf2 = templates["gf2_stencil"]
    xy = (2, 2)  # (x, y) -> clicked cell (row=2, col=2)

    single = oracle.predict_click(_FT09_PLUS, xy)
    stencil = gf2.predict_click(_FT09_PLUS, xy)

    assert single == {(2, 2)}
    assert stencil == {(2, 2), (0, 2), (4, 2), (2, 0), (2, 4)}
    assert len(single) == 1
    assert len(stencil) > 1
    assert single < stencil  # the stencil is a strict superset of the oracle's cell


def test_ft09_background_click_makes_no_claim():
    """Purpose: a click that lands on background (no button region) yields no
    claim from either ft09 template.

    Expected feedback: pass proves a no-region click is excluded from dynamics
    scoring (predict_click returns None), not silently scored as an empty change
    set. Fail means background clicks would pollute the accuracy denominator."""
    templates = _by_name(ft09_templates())
    xy = (1, 1)  # (row=1, col=1) is background 0
    assert templates["glyph_constraints"].predict_click(_FT09_PLUS, xy) is None
    assert templates["gf2_stencil"].predict_click(_FT09_PLUS, xy) is None


def _sc25_frame():
    """A 3x3 lattice of 2x2 cells on background 0, base colour 2, with two ON
    cells (colour 7) at grid positions (0,0) and (2,2), plus two colour-9 preview
    marks to the LEFT that bin to the same two positions. So the base-parity
    ON-set equals the preview target (oracle win TRUE), but the grid never
    renders a cell in the preview's mark colour 9 (absolute-preview win FALSE)."""
    grid = [[0] * 20 for _ in range(20)]
    cell_rows = (4, 8, 12)
    cell_cols = (9, 12, 15)
    on_positions = {(0, 0), (2, 2)}
    for ri, r0 in enumerate(cell_rows):
        for ci, c0 in enumerate(cell_cols):
            colour = 7 if (ri, ci) in on_positions else 2
            for dr in (0, 1):
                for dc in (0, 1):
                    grid[r0 + dr][c0 + dc] = colour
    # Two single-pixel preview marks (colour 9) left of the grid; their bounding
    # box is the template block, binned 3x3 to positions (0,0) and (2,2).
    grid[4][2] = 9
    grid[13][5] = 9
    return tuple(tuple(row) for row in grid)


def test_sc25_oracle_xor_wins_absolute_preview_loses():
    """Purpose: on a frame whose base parity is non-trivial, the sc25 oracle
    (binary_flip_xor: base XOR preview) recognises the cast state, while the
    absolute-preview hard negative (compare lattice colours to the preview
    colour directly, no XOR) does not.

    Expected feedback: pass proves the win predicates genuinely diverge on the
    base-parity axis the design calls out — the discriminator for sc25 N4. Fail
    means absolute_preview matched the oracle and the sc25 win test is inert."""
    templates = _by_name(sc25_templates())
    frame = _sc25_frame()
    assert templates["binary_flip_xor"].predict_win(frame) is True
    assert templates["absolute_preview"].predict_win(frame) is False


def test_sc25_oracle_single_cell_neighbour_stencil_multicell():
    """Purpose: the sc25 oracle claims a lattice click changes ONE cell; the
    neighbour-stencil hard negative claims it changes that cell plus a lattice
    neighbour.

    Expected feedback: pass proves sc25's dynamics negative (N3) is a genuine
    multi-cell claim distinct from the oracle. Fail means N3 collapsed to the
    oracle's single-cell claim."""
    templates = _by_name(sc25_templates())
    frame = _sc25_frame()
    xy = (9, 4)  # click the top-left lattice cell (col=9, row=4)
    single = templates["binary_flip_xor"].predict_click(frame, xy)
    stencil = templates["neighbour_stencil"].predict_click(frame, xy)
    assert single is not None and len(single) == 4  # a 2x2 cell region
    assert stencil is not None and single < stencil  # cell + >= 1 neighbour


def test_split_by_level_even_odd_is_deterministic():
    """Purpose: the per-level train/held-out split assigns even-index
    transitions (within a level, in trace order) to TRAIN and odd to HELD-OUT,
    with no RNG, and repeats identically.

    Expected feedback: pass proves the held-out evaluation partition is a pure
    function of trace order — the reproducibility the R95a baseline depends on.
    Fail means the split is order-sensitive or non-deterministic."""
    trivial = ((0,),)
    rows = [
        Transition(0, 6, (0, 0), 0, True, trivial, trivial, 0),
        Transition(1, 6, (0, 0), 0, True, trivial, trivial, 0),
        Transition(2, 6, (0, 0), 0, True, trivial, trivial, 0),
        Transition(3, 6, (0, 0), 1, True, trivial, trivial, 1),
        Transition(4, 6, (0, 0), 1, True, trivial, trivial, 1),
    ]
    train, heldout = _split_by_level(rows)
    assert [t.index for t in train] == [0, 2, 3]  # level0 even (0,2) + level1 even (3)
    assert [t.index for t in heldout] == [1, 4]  # level0 odd (1) + level1 odd (4)

    again_train, again_heldout = _split_by_level(rows)
    assert [t.index for t in again_train] == [t.index for t in train]
    assert [t.index for t in again_heldout] == [t.index for t in heldout]


def test_tie_detection_reports_equivalence_class_and_gates_strict_win():
    """Purpose: an exhaustive winner chosen only by an ordering tie-break is not
    a real win. _tie_group must surface templates behaviourally identical to the
    oracle as an equivalence class, and _oracle_strictly_wins must be True only
    when every OTHER template is either in that class or scores strictly below.

    Expected feedback: pass proves the ft09 nearest-glyph / sc25 colour-cycle
    situations (measured: zero divergence from the oracle over the whole trace)
    are reported as ties rather than silently declared oracle wins, and that a
    non-tied template sharing the oracle's key blocks the win. Fail means the
    prereg would record an order-based winner as a genuine discrimination."""
    # 'twin' has the oracle's exact signature (a true equivalence); 'weak' is
    # strictly worse; 'ordering_only' matches the key but has a DIFFERENT
    # signature (a bare ordering tie that must NOT count as an oracle win).
    signatures = {
        "oracle": (("1", "1"), (True,), ()),
        "twin": (("1", "1"), (True,), ()),
        "weak": (("0", "0"), (False,), ()),
    }
    assert _tie_group("oracle", signatures) == ["twin"]

    keys = {"oracle": (0.8, 1.0), "twin": (0.8, 1.0), "weak": (0.1, 0.0)}
    assert _oracle_strictly_wins("oracle", keys, {"twin"}) is True

    signatures["ordering_only"] = (("1", "0"), (True,), ())  # different signature
    keys["ordering_only"] = (0.8, 1.0)  # yet an equal ranking key
    tie = set(_tie_group("oracle", signatures))
    assert "ordering_only" not in tie
    assert _oracle_strictly_wins("oracle", keys, tie) is False


def test_is_cast_state_excludes_configuration_repeats_not_only_byte_equal():
    """Purpose: a specificity-pool negative must exclude genuine cast/win states
    even when they are not byte-identical to the selected win frame — sc25's
    matched pattern recurs under transient cursor/cast colours, so exclusion must
    use a colour-canonical STATE signature, not just raw equality.

    Expected feedback: pass proves a same-configuration repeat is recognised as a
    cast state (kept out of the false-positive pool) while a genuinely different
    board is not. Fail means cast-animation frames leak into the negatives and
    inflate the oracle's false-positive rate (the measured 0.6/0.9 artifact)."""
    win = ((3, 1), (1, 3))  # colour 3 = transient cursor; the settled ON cell is 1
    same_config_diff_bytes = ((0, 1), (1, 0))  # different bytes, same ON signature
    different_board = ((2, 2), (2, 2))

    # A signature that ignores the transient colours (0 = background, 3 = cursor)
    # so a cast state and its cursor-recoloured repeat map to one key.
    def sig(frame):
        return frozenset(v for row in frame for v in row if v not in (0, 3))

    win_grids = {win}
    win_sigs = {sig(win)}
    assert _is_cast_state(win, win_grids, win_sigs, sig) is True  # byte-equal
    assert _is_cast_state(same_config_diff_bytes, win_grids, win_sigs, sig) is True
    assert _is_cast_state(different_board, win_grids, win_sigs, sig) is False
    # With no signature function, only byte-equality excludes.
    assert _is_cast_state(same_config_diff_bytes, win_grids, set(), None) is False


def test_templates_for_game_rejects_unknown():
    """Purpose: templates_for_game returns the (candidate set, oracle name) pair
    for a known game and rejects anything else.

    Expected feedback: pass proves the game dispatch is closed to the two decoded
    families and names the oracle each set is scored against. Fail means an
    unknown game would silently resolve to the wrong template set."""
    ft09, ft09_oracle = templates_for_game("ft09")
    assert ft09_oracle == "glyph_constraints"
    assert {t.name for t in ft09} == {
        "glyph_constraints",
        "gf2_stencil",
        "nearest_glyph_only",
        "uniform_colour",
        "all_ink_equal",
    }
    _sc25, sc25_oracle = templates_for_game("sc25")
    assert sc25_oracle == "binary_flip_xor"
    try:
        templates_for_game("nope")
    except ValueError:
        pass
    else:  # pragma: no cover - the call above must raise
        raise AssertionError("templates_for_game must reject an unknown game")


def test_ask_prompt_deterministic_shuffle_across_calls():
    """Purpose: the T1..T5 assignment is a pure deterministic function of the
    game string (hashlib-keyed, no RNG), so the same game always yields the same
    shuffle and the same assembled prompt.

    Expected feedback: pass proves the LLM ask is reproducible run-to-run (a
    prereg requirement — a reshuffling prompt would make PASS rates
    incomparable). Fail means the ask ordering drifts between calls."""
    for game in ("ft09", "sc25"):
        transitions = _tiny_transitions(game)
        msgs_a, map_a, _obs_a = build_ask_prompt(game, transitions)
        msgs_b, map_b, _obs_b = build_ask_prompt(game, transitions)
        assert map_a == map_b
        assert sorted(map_a) == ["T1", "T2", "T3", "T4", "T5"]
        assert msgs_a == msgs_b


def test_ask_prompt_contains_no_names_oracle_or_gameid_leak():
    """Purpose: the ask prompt must expose only neutral descriptions + neutral
    ids — never an internal template name, the word "oracle", a game id, or any
    held-out metric label.

    Expected feedback: pass proves the model cannot shortcut on a leaked label
    and the ask measures genuine mechanic reasoning. Fail means the prompt leaks
    an answer key and the part-2 verdict would be contaminated."""
    forbidden = [
        "oracle", "ft09", "sc25", "heldout", "held-out", "dynamics_",
        "win_true_positive", "tied_with_oracle",
        "glyph_constraints", "gf2_stencil", "nearest_glyph_only", "uniform_colour",
        "all_ink_equal", "binary_flip_xor", "colour_cycle", "near_match_threshold",
        "neighbour_stencil", "absolute_preview",
    ]
    for game in ("ft09", "sc25"):
        msgs, _mapping, _obs = build_ask_prompt(game, _tiny_transitions(game))
        text = (msgs[0]["content"] + "\n" + msgs[1]["content"]).lower()
        leaked = [tok for tok in forbidden if tok.lower() in text]
        assert leaked == [], f"{game} prompt leaked {leaked}"


def test_score_choice_pass_only_inside_equivalence_class():
    """Purpose: a rep PASSes only when the mapped template is in the oracle
    equivalence class (oracle + ties); a strictly-dominated negative or an
    unmappable/null choice FAILs.

    Expected feedback: pass proves the part-2 scoring honours part-1's measured
    equivalence classes and does not credit a wrong pick. Fail means PASS rates
    would over- or under-count the model."""
    mapping = {"T1": "gf2_stencil", "T2": "glyph_constraints", "T3": "nearest_glyph_only"}
    eq = {"glyph_constraints", "nearest_glyph_only"}  # oracle + its tie
    assert _score_choice("T2", mapping, eq) == ("glyph_constraints", True)
    assert _score_choice("T3", mapping, eq) == ("nearest_glyph_only", True)
    assert _score_choice("T1", mapping, eq) == ("gf2_stencil", False)  # dominated negative
    assert _score_choice(None, mapping, eq) == (None, False)  # hard failure
    assert _score_choice("T9", mapping, eq) == (None, False)  # unmappable id


def test_parse_choice_extracts_json_and_validates_enum():
    """Purpose: _parse_choice extracts the ask JSON even amid surrounding prose,
    validates the choice against the allowed ids, and normalises confidence.

    Expected feedback: pass proves the guided-json parse is robust to a chatty
    model and rejects an out-of-set choice. Fail means malformed or invalid
    completions would be scored as if valid."""
    valid = {"T1", "T2", "T3", "T4", "T5"}
    ok, err = _parse_choice('here you go {"choice": "T3", "confidence": "high", "evidence": "x"}', valid)
    assert err == "" and ok["choice"] == "T3" and ok["confidence"] == "high"
    bad, err2 = _parse_choice('{"choice": "T9", "confidence": "high", "evidence": "x"}', valid)
    assert bad is None and "T9" in err2
    none, err3 = _parse_choice("no json here", valid)
    assert none is None and err3
    # confidence outside the closed set falls back to "low", not an error.
    norm, err4 = _parse_choice('{"choice": "T1", "confidence": "certain", "evidence": ""}', valid)
    assert err4 == "" and norm["confidence"] == "low"


def test_ask_once_retries_once_on_invalid_then_parses():
    """Purpose: ask_once validates the completion and retries exactly once with
    error feedback; a second valid reply is accepted (attempts=2), and a valid
    first reply needs no retry (attempts=1).

    Expected feedback: pass proves the ask has the same validate-and-retry
    robustness as the R94 holdout runner without any network. Fail means a
    single malformed reply would be recorded as a hard failure (understating the
    model) or an infinite retry loop."""
    valid = {"T1", "T2", "T3", "T4", "T5"}
    messages = [{"role": "user", "content": "pick one"}]

    calls = {"n": 0}

    def flaky(_msgs):
        calls["n"] += 1
        return "I think..." if calls["n"] == 1 else '{"choice": "T2", "confidence": "medium", "evidence": "ok"}'

    res = ask_once(flaky, messages, valid)
    assert res["choice"] == "T2" and res["attempts"] == 2 and res["error"] is None

    def clean(_msgs):
        return '{"choice": "T1", "confidence": "low", "evidence": "y"}'

    res2 = ask_once(clean, messages, valid)
    assert res2["choice"] == "T1" and res2["attempts"] == 1


def test_neutral_descriptions_cover_every_template_exactly():
    """Purpose: every template of both games has exactly one neutral description
    and no extras — the shuffle maps all five ids to real descriptions.

    Expected feedback: pass proves build_ask_prompt cannot KeyError on a missing
    description or silently drop a candidate. Fail means the candidate set shown
    to the model diverges from the scored template set."""
    for game in ("ft09", "sc25"):
        names = {t.name for t in templates_for_game(game)[0]}
        assert set(_NEUTRAL_DESCRIPTIONS[game]) == names
