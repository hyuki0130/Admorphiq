"""Offline tests for the death-clock allowance ledger (harness/allowance.py).

Purpose: prove the ledger learns a level's action budget from deaths alone AND refuses to learn one
where the deaths scatter — the trust gate is the whole instrument, because a fabricated allowance
would be acted on exactly like a real one.
Expected feedback: a pass means the nine games whose deaths agreed in the R101ALLOW sweep would be
learned and the four whose deaths scattered would not; a failure means the gate has moved and any
behaviour wired to it is acting on fiction.
"""

from __future__ import annotations

from admorphiq.harness.allowance import AllowanceLedger

# The R101ALLOW sweep's own numbers, kept as the fixture so a change to the gate is measured against
# what was actually observed rather than against a hand-picked example.
TRUSTED_SWEEP = {
    "cn04": [125, 126, 126, 126, 126, 126, 126],
    "re86": [100, 101, 101, 101, 101, 101, 101],
    "ka59": [100, 101, 101, 101, 101, 101, 101, 101],
    "s5i5": [200, 201, 201, 201, 201, 201],
    "m0r0": [151, 152, 152, 152, 152, 152, 152],
    "tn36": [61, 62, 62, 62, 62, 62, 62, 62, 62, 62, 62, 62],
    "r11l": [60, 61, 61, 61, 61, 61, 61, 61, 61, 61, 61, 61],
    "bp35": [64, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65],
    "tr87": [129, 129, 129, 129, 129, 129, 129, 129],
}
SCATTERED_SWEEP = {
    "tu93": [50, 51, 39, 12, 9, 9, 47, 12, 9, 9, 9, 9],
    "su15": [48, 49, 49, 49, 150, 106, 93, 98, 91, 96, 100, 85],
    "sb26": [69, 217, 193, 160, 184, 181, 119],
    "sp80": [120, 121, 99, 38, 15, 81, 72, 51, 51, 14, 94, 71],
    "ls20": [260, 132, 136, 143, 144],
    "ar25": [174, 185, 196, 174],
    "sc25": [95, 67, 67, 67, 67, 67, 67, 67, 67, 67, 67, 67],
}


def _fill(lengths: list[int], level: int = 3) -> AllowanceLedger:
    led = AllowanceLedger()
    for n in lengths:
        led.note_death(level, n)
    return led


def test_agreeing_deaths_yield_the_allowance():
    """Purpose: every game whose R101ALLOW deaths agreed must produce an allowance of min-1.
    Expected feedback: pass = the nine learnable games stay learnable; fail = the mechanism the
    round measured no longer fires on the data that measured it."""
    for title, lengths in TRUSTED_SWEEP.items():
        led = _fill(lengths)
        assert led.is_trusted(3), title
        assert led.allowance(3) == min(lengths) - 1, title


def test_scattered_deaths_are_refused():
    """Purpose: a level that ends for some reason OTHER than an allowance must teach NOTHING.
    Expected feedback: pass = the trust gate still separates the four scattered games (and the two
    other rejects) from the nine; fail = the agent would act on a number it invented."""
    for title, lengths in SCATTERED_SWEEP.items():
        led = _fill(lengths)
        assert not led.is_trusted(3), title
        assert led.allowance(3) is None, title


def test_one_death_is_never_enough():
    """Purpose: the gate requires TWO deaths — one death cannot distinguish a clock from a hazard.
    Expected feedback: pass = a single death is banked but not acted on."""
    led = _fill([64])
    assert led.deaths(3) == [64]
    assert led.allowance(3) is None


def test_idle_game_over_ticks_are_not_attempts():
    """Purpose: cd82 reported nineteen length-1 "deaths" — the harness idling inside GAME_OVER, not
    attempts. They must not be recorded, or the level would learn an allowance of zero.
    Expected feedback: pass = the instrument's measured floor holds; fail = a game that never had a
    budget gets one of 0 and is starved."""
    led = _fill([1] * 19)
    assert led.deaths(3) == []
    assert led.allowance(3) is None


def test_newly_trusted_fires_exactly_once():
    """Purpose: note_death returns True only on the death that CROSSES into trust, so a consumer
    wired to it acts once per level rather than on every repeat death.
    Expected feedback: pass = the consumer is a one-shot; fail = it would re-fire 19 times on bp35."""
    led = AllowanceLedger()
    assert led.note_death(2, 64) is False
    assert led.note_death(2, 65) is True
    assert led.note_death(2, 65) is False
    assert led.note_death(2, 65) is False


def test_remaining_counts_down_and_floors_at_zero():
    """Purpose: the number handed to a tool is what is LEFT, never negative.
    Expected feedback: pass = a tool reading it can compare against its own plan length."""
    led = _fill([64, 65])
    assert led.allowance(3) == 63
    assert led.remaining(3, 0) == 63
    assert led.remaining(3, 60) == 3
    assert led.remaining(3, 900) == 0
    assert led.remaining(4, 0) is None  # a level with no deaths teaches nothing


def test_levels_are_independent():
    """Purpose: allowances are per LEVEL — bp35 died at 7/35 on one level and 64/65 on another, and
    the scattered pair must not contaminate the learnable one.
    Expected feedback: pass = a per-level ledger; fail = one noisy level disables a clean one."""
    led = AllowanceLedger()
    for n in (7, 35):
        led.note_death(1, n)
    for n in (64, 65):
        led.note_death(5, n)
    assert led.allowance(1) is None
    assert led.allowance(5) == 63
