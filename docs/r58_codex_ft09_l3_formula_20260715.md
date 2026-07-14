# Codex verdict — FT09 L3 click-count formula SOLVED (2026-07-15)

> Input brief: scripts/_r58_ft09_l3_formula_brief.md (from the gold-trace decode work).
> Rule: 3-colour cycle 9->8->12->9; ink0 = final colour MUST EQUAL covering glyph's
> marker, ink2 = MUST DIFFER; all covering glyphs' constraints hold simultaneously.
> Verified 18/18 cells incl. the anomaly; gold contains one redundant click (30,28).

## Decisive rule

Level 3 uses a three-colour cycle:

\[
9 \xrightarrow{1\ click} 8 \xrightarrow{1\ click} 12 \xrightarrow{1\ click} 9
\]

For a cell with total click count \(c\), let:

\[
F(c)=[9,8,12]_{c\bmod 3}
\]

Every covering glyph contributes a constraint:

- ink **0**: \(F(c)=\text{glyph marker}\)
- ink **2**: \(F(c)\ne\text{glyph marker}\)

All covering-glyph constraints must hold simultaneously.

Thus ink 2 does **not** designate one particular “other colour.” It means any colour unequal to the marker. The earlier exact-other-colour interpretation worked on two-colour levels only because “not marker” had a unique answer there.

Importantly, this is a winning-state rule, not always a unique click count. The gold trace contains one redundant click: `(30,28)` could remain at 9 with zero clicks, but gold changes it to 8; both colours differ from marker 12.

## Verification against every cell

Here `0→9`, `1→8`, and `2→12`.

| Cell | Gold count → final | All constraints |
|---|---:|---|
| (14,20) | 2 → 12 | G(22,20): ink0, `12=12` |
| (14,28) | 1 → 8 | ink2 under markers 12 and 9: `8≠12`, `8≠9` |
| (14,36) | 0 → 9 | G(22,36): ink0, `9=9` |
| (14,44) | 1 → 8 | G(22,36): ink2, `8≠9` |
| (14,12) | 0 → 9 | G(22,20): ink2, `9≠12` |
| (22,12) | 0 → 9 | G(22,20): ink2, `9≠12` |
| (22,28) | 1 → 8 | ink2 under markers 12 and 9: `8≠12`, `8≠9` |
| (22,44) | 1 → 8 | G(22,36): ink2, `8≠9` |
| (30,12) | 0 → 9 | G(22,20): ink2, `9≠12` |
| (30,20) | 2 → 12 | ink0 under two marker-12 glyphs: `12=12` twice |
| (30,28) | 1 → 8 | ink2 under two marker-12 glyphs: `8≠12` twice |
| (30,36) | 1 → 8 | ink2 under markers 9 and 12: `8≠9`, `8≠12` |
| (30,44) | 0 → 9 | G(22,36): ink0, `9=9` |
| (38,20) | 0 → 9 | G(38,28): ink2, `9≠12` |
| (38,36) | 0 → 9 | G(38,28): ink2, `9≠12` |
| (46,20) | 2 → 12 | G(38,28): ink0, `12=12` |
| (46,28) | 2 → 12 | G(38,28): ink0, `12=12` |
| (46,36) | 2 → 12 | G(38,28): ink0, `12=12` |

This explains the apparent anomaly cleanly: `(14,44)` and `(22,44)` must leave base colour 9 because their marker is 9, so one click takes them to acceptable colour 8. The other single-covered ink-2 cells have marker 12, so their initial 9 is already acceptable.

The only non-minimal entry is `(30,28)`: both covering glyphs merely require “not 12,” so either 9 or 8 works.

## Best single confirming/refuting observation

Replay the gold solution while omitting only the click on `(30,28)`.

- If the level clears after the remaining 15 actions, it confirms inequality semantics and proves the gold click count is not unique.
- If it does not clear, the rule is refuted.

## Independent source verification

After deriving the rule from the table and trace transitions, the environment source confirms it:

- Level 3’s cycle is `[9, 8, 12]` at [ft09.py](/Users/nhn/Workspace/Admorphiq/environment_files/ft09/0d8bbf25/ft09.py:2170).
- Clicking advances one position cyclically at [ft09.py](/Users/nhn/Workspace/Admorphiq/environment_files/ft09/0d8bbf25/ft09.py:2422).
- The completion test uses equality when the ink is 0 and inequality otherwise at [ft09.py](/Users/nhn/Workspace/Admorphiq/environment_files/ft09/0d8bbf25/ft09.py:2446).

So the controlled omission should clear the level in 15 actions.
