"""The death-clock allowance ledger — learn a level's action budget by dying on it.

MEASURED (scripts/rounds/R101ALLOW, 24-game sweep, artefacts committed): many games END a level on
action-count overrun, and ``obs.state`` reports GAME_OVER directly, so attempt boundaries are free —
no pixel reading is involved. The action count at that moment IS the declared allowance plus one (the
death is seen one action after the counter trips), which makes the number learnable from a SINGLE
death on ANY game. That is the property worth having: a level-data grep finds twelve declared
allowances, the death clock recovers nine WITHOUT source access, and three of those nine (tn36 L3 61,
tr87 L1 129, r11l L6 60) are declared nowhere at all. Source access is exactly what the 110 PRIVATE
evaluation games do not offer.

⛔ A TRUST GATE IS NOT OPTIONAL, and it is what this module mostly is. Where something OTHER than an
allowance ends the level — a hazard, a lost life — the death lengths SCATTER: tu93's 127 deaths run
9..51 against declared budgets of 50/50/35/20, su15 48..150, sb26 69..217, sp80 14..121. Requiring
the deaths on a level to AGREE (spread <= ``TOLERANCE``) separates the nine learnable games from
those four with nothing in between:

    cn04 125..126   re86 100..101   ka59 100..101   s5i5 200..201   m0r0 151..152
    tn36  61.. 62   r11l  60.. 61   bp35  64.. 65   tr87 129..129        <- trusted
    tu93   9.. 51   su15  48..150   sb26  69..217   sp80  14..121        <- rejected
    ls20 132..260   ar25 174..196   sc25  26.. 60 / 67..95               <- rejected

⚠️ ``FLOOR`` is the instrument's own floor, not a taste knob. cd82 reported NINETEEN "deaths" of
length 1: that is the harness idling inside GAME_OVER between attempts, not an attempt. Those inflate
the death COUNT and never the lengths, and a length-1 death would otherwise "teach" an allowance of
zero — the one number that could starve a level that never had a budget at all.

The recorded allowance is ``min(lengths) - 1``: the last action index that is certainly still inside
the budget. Erring one action short is free; erring one long re-enters the death this exists to stop.
"""

from __future__ import annotations

#: Maximum spread (max - min) among a level's death lengths that still counts as AGREEMENT.
#: 1, not 0: the shortest death is one action shorter than the rest on eight of the nine learnable
#: games (the first death of a streak is seen one tick earlier), while every scattered game spreads
#: by 22 or more. Nothing measured lands between 1 and 22.
TOLERANCE = 1

#: Shortest death length that counts as an ATTEMPT rather than an idle tick (see the cd82 note).
FLOOR = 2


class AllowanceLedger:
    """Per-level death lengths, and the allowance they justify once they agree.

    Purely a record: it decides what is KNOWN, never what to do about it. The consumer lives in
    :mod:`admorphiq.harness.loop`.
    """

    def __init__(self, tolerance: int = TOLERANCE, floor: int = FLOOR) -> None:
        self.tolerance = tolerance
        self.floor = floor
        self._deaths: dict[int, list[int]] = {}

    # -- recording ------------------------------------------------------------

    def note_death(self, level: int, length: int) -> bool:
        """Record one attempt on ``level`` that ended in GAME_OVER after ``length`` actions.

        Returns True when this death is the one that makes the level's allowance TRUSTED — i.e. the
        caller may now act on it and could not before. Returns False for every death that leaves the
        level untrusted, and for every death AFTER the level is already trusted, so a caller wiring
        behaviour to the return value acts exactly once per level per streak.
        """
        if length < self.floor:
            return False
        was = self.is_trusted(level)
        self._deaths.setdefault(level, []).append(length)
        return self.is_trusted(level) and not was

    # -- reading --------------------------------------------------------------

    def deaths(self, level: int) -> list[int]:
        return list(self._deaths.get(level, ()))

    def is_trusted(self, level: int) -> bool:
        lens = self._deaths.get(level)
        if lens is None or len(lens) < 2:
            return False
        return max(lens) - min(lens) <= self.tolerance

    def allowance(self, level: int) -> int | None:
        """Actions this level is known to permit, or None while the level is untrusted."""
        if not self.is_trusted(level):
            return None
        return min(self._deaths[level]) - 1

    def remaining(self, level: int, spent: int) -> int | None:
        """Actions left in the current attempt, or None while the level is untrusted."""
        allow = self.allowance(level)
        return None if allow is None else max(0, allow - spent)
