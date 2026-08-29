---
type: lesson
topic: partial observability
date: 2026-08-29
keywords: [scrolling board, partial observability, win predicate, local win, camera, railpeg, lf52, travel tier, boarding a cart]
---
# A predicate over a camera is not a predicate over the state

> `railpeg` reached its own win condition on lf52 level 6 — one piece of each colour — and the
> level did not end, because four more pieces were scrolled off the screen. It then claimed the
> same win **43 times**. The tool was not wrong about anything it could see; it was wrong that what
> it could see was the board.

## The claim

A tool that keeps a model of the board, and fills that model from frames, will sooner or later
evaluate a GOAL PREDICATE over the model. On a board that fits the screen those are the same
thing. On a board that does not, they are not — and the failure is silent, because the tool is not
wrong about anything it can see.

## How it was measured

`railpeg` on lf52 level 6. Its win test is `_won` — every capturable colour down to a single
piece — evaluated over `Model.pieces`, which holds what the camera has shown.

The board is **28 cells wide and the screen shows about ten**. It carries 7 green pads, 1 red pad
and 3 stepping stones; the engine's own win is the count reaching 2, so six captures are needed.
Four pads and every stepping stone start off screen.

What the tool does, and it is all correct play: it walks a green down the left column **using the
red pad as a ladder** (a piece of another colour is a permanent stepping stone, which its own
docstring already knew), takes both captures the visible region offers, and arrives at one green
and one red — `_won`, exactly. The level does not end.

```
green 36 px -> 12 px, red 12 px          one piece of each colour: its own _won
tiers  win 43 · travel 32 · capture 4 · none 1
_elsewhere true, 297 sync calls, 244 of them placed
```

⛔ **It then claims the same win forty-three times.** The tier that would have gone looking sits
behind "no capture is reachable", and a LOCAL win is always reachable.

## Why the existing guard was not enough

The tool already had the tell — `_claiming` is set when a win is played, and a win that did not win
sets `_elsewhere`. That is the right instrument and it fires. What was missing is that `_elsewhere`
did not feed back into the predicate: knowing the board is bigger changed the tier ORDER but not
what counts as a solution. So the tool kept solving the tenth of the board it could see.

`plan_level(..., refuse_local_win=True)` fixes it in one line of meaning: once the board is known
to extend past the screen, a `_won` state is still the cheapest route to real captures and is still
worth playing toward — it is simply no longer a SOLUTION.

## The second half: an objective must be able to want to GET ON

Refusing the false win only helps if there is somewhere else to go, and here there was exactly one
route: a cart, whose track runs off the screen. The tool's "go and look" tier produced **32 plans
and boarded a cart zero times**.

The cause is that **the reward for boarding arrives after the drives**. The novelty objective
scores a state by how far its pieces stand from ground already worked; a cart parked at the edge of
the worked region is an ordinary cell a step or two from home, while the track under it goes
everywhere. So the measure ranked "shuffle one more hole" above "get on the thing that leaves".

`_rail_reach` scores a boarded piece by **what its track can reach**, not by where the cart
currently stands. It stays selective by construction: a stub of track whose cells are all near home
is worth its own cell and no more, so boards that merely draw a rail do not pull the tool onto it.

## What generalises

- Any tool with a MAP and a GOAL has this bug latent. Ask of every predicate: is it over the state,
  or over the part of the state I have seen? If the second, it needs a flag for the moment the
  difference is known.
- The evidence that the two differ is cheap and already available: **a goal you reached that did
  not end the level**. Nothing else on a partial map distinguishes "two remain and both are here"
  from "six remain and four are elsewhere".
- An objective whose payoff is several actions away cannot be ranked by a measure evaluated at the
  current state. Score the DESTINATION the move commits to.

## Related

- [[sample_games_mechanics]] — lf52's mechanics, the level-6 clear, and the game's
  own rendered legal-move oracle
- [[../rounds/r101_silent-specialists]] — the EMPTY-path retirement this replaces
- [[refusal_and_lag_are_the_same_picture_20260829]] — the sibling defect on the same tool, and the
  reason both repairs on this page fired hard and scored identically: the boardings they produced
  were followed by drives the engine refused, and every refusal was read as an animation

## What would falsify it

A scrolling board on which the local win IS the real win — then `refuse_local_win` costs actions
for nothing. That is why it is gated on `_elsewhere` (a win already played and refuted) rather than
on "the board might be bigger". And if `_rail_reach` moves a game that has rails but no reason to
ride them, the bonus is not selective enough and the component-maximum is the term to re-examine.
