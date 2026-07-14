# Codex verdict — FT09 L4 SOLVED: cross-toggle controls, no commit invariant (2026-07-15)

> Input: scripts/_r58_ft09_l4_mystery_brief.md. Resolution: the 3 'commit glyphs' are
> stateful cross-toggle BUTTONS (click toggles self 14<->15 + every ink-6 stencil
> position); TWO 3-member target glyphs were missed by the >=4-member ring filter and
> constrain the controls themselves; gold = 9 targets + 9 compensations + 3 control
> clicks; order NOT load-bearing (replay-verified). The equality/inequality framework
> holds completely — ink6 is an ACTION STENCIL, not a constraint.

## Exact resolution

There is no additional commit invariant. The three “commit glyphs” are actually stateful cross-toggle buttons, and they are themselves constrained by ordinary target glyphs.

Clicking one toggles:

- Its own state, 14↔15.
- Every existing position painted with ink 6: N/W/E/S.

The trace analysis missed the self-toggle because Section 4 only measured the 27 ordinary field cells. Directly inspecting the control bboxes shows, on rows 221–223:

```text
before: 14  6 14      after: 15  6 15
         6 14  6              6 15  6
        14  6 14             15  6 15
```

That contributes 20 changed pixels per control click. Thus row 223’s 128-pixel diff is exactly three 36-pixel field cells plus the control’s 20 pixels.

The implementation confirms the center-plus-ink-6 stencil at [ft09.py](/Users/nhn/Workspace/Admorphiq/environment_files/ft09/0d8bbf25/ft09.py:2400), while the ordinary win check explicitly accepts both normal cells and these control cells as constraint targets at [ft09.py](/Users/nhn/Workspace/Admorphiq/environment_files/ft09/0d8bbf25/ft09.py:2436).

## Two target glyphs were missed

There are eight ordinary constraint glyphs, not six. The two omitted three-member glyphs are:

```text
glyph@(4,14), marker=14
{NW:3,N:3,NE:3,W:3,E:0,SW:3,S:0,SE:2}

glyph@(52,46), marker=14
{NW:2,N:0,NE:3,W:0,E:3,SW:3,S:3,SE:3}
```

They were rejected because the adapter requires at least four ring members at [ft09.py](/Users/nhn/Workspace/Admorphiq/src/admorphiq/adapters25/ft09.py:160); both have only three.

Together with the already-known glyph at `(36,22)`, they constrain the three controls:

| Control | Covering constraint | Required state |
|---|---|---|
| `(12,22)` | SE of glyph `(4,14)`, ink 2, marker 14 | 15 |
| `(28,22)` | N of glyph `(36,22)`, ink 2, marker 14 | 15 |
| `(44,38)` | NW of glyph `(52,46)`, ink 2, marker 14 | 15 |

Therefore each control must be clicked once. Its cross side effects must then be cancelled.

## Why gold’s 21 clicks work

Gold consists of:

- Nine ordinary cells that genuinely need to become 15.
- Nine ordinary compensation clicks on cells that must finish at 14.
- Three cross-control clicks, which turn the controls themselves to 15.

The shared cell `(20,22)` is toggled by two controls, so it cancels automatically and needs no direct compensation.

Final state:

- Nine ordinary target cells: 15.
- Three control cells: 15.
- Seventeen other constrained ordinary cells: 14.
- `(20,22)`: unconstrained, ending at 14.

Thus 29 of the 30 stateful sprites are constrained; only `(20,22)` is genuinely free. The supposed eight unaccounted cells resulted from omitting the two three-member glyphs and treating controls as gaps.

## Answers to the open questions

- Win triggers when all ordinary equality/inequality constraints hold simultaneously. Row 223 is simply the click that supplies the last required control state while restoring its affected equality cells to 14.
- There is no “at most one,” “exactly one,” parity-count, or commit invariant.
- Ink 6 describes an action stencil, not a constraint relationship.
- Order is not load-bearing. I verified the exact game class with gold order, complete reverse order, and all three controls first; all clear on click 21.
- Replay A fails because all three constrained controls remain 14.
- Replay B does not satisfy the win constraints: it leaves many equality-required ordinary cells at 15 and all three controls at 14.

Finally, the apparent decoy→reveal is not an L4 mechanic. Level installation is deferred until the next action; the engine installs and renders the new level, then processes that same click. That lifecycle is visible in [base_game.py](/Users/nhn/Workspace/Admorphiq/.venv/lib/python3.12/site-packages/arcengine/base_game.py:224). The wholesale row-203 transition is the previous-level frame being replaced by L4, not a hidden L4 board reveal.
