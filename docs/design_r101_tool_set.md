# R101 design — the tool set derived from the 25 sample games

Stage 1 of the top policy (`OPERATING_RULES.md` rule 0): build generic tools until they clear all 25.
This names the tools from the games' MECHANICS, so each is generic over a CLASS rather than tuned to a
game. No tool reads a game id; every one keys on structure visible in frames.

## Why the current set does not do it

`graph` expands a state graph over ACTIONS — class A's shape and only class A's. Measured
(`scripts/rounds/TOOLDIAG`, bare UnifiedAgent, 3000 actions): eleven games run 72-99% INERT actions,
two never draw a goal, twelve expand and aim and still clear nothing. ft09 opens 24 states from 1,610
transitions. Eighteen of twenty-five games are in classes B, C and D; the only tool that clears
anything is built for A.

## The four tools

### T-A `reach` — navigate an avatar to a goal cell   (7 games: dc22 tu93 ls20 m0r0 g50t bp35 s5i5)

What it must do, in order:
1. **Identify the avatar by MOTION** — the region that translates under a direction probe. Not by
   colour: g50t's player and goal share colour 9, and identity there is motion (recorded on its page).
2. **Learn the direction map** — which action id moves which way, measured, never assumed.
3. **Build a reachability model** — which cells are enterable, refined online when a move is refused.
4. **Find the goal cell** — a static region the avatar is not, reached by the win.
5. **Plan a path and walk it closed-loop**, re-planning when the board answers differently.

This is closest to what `graph` already does; the difference is that `reach` plans over CELLS with a
learned obstacle model instead of over opaque state hashes, so a refused move teaches a wall rather
than adding a self-loop.

### T-B `deliver` — carry objects onto their destinations   (6 games: wa30 re86 ka59 su15 r11l lp85)

1. **Segment objects and destinations**, and pair them — the pairing is the problem, not the walking.
2. **Learn the carry model** — what attaches an object to the mover (adjacency + an action, a click,
   a vacuum radius), measured from one attempt.
3. **Solve the ASSIGNMENT** — which object to which destination, minimising total travel, with
   colour/shape constraints when the board imposes them.
4. **Sequence the deliveries** — an early drop can block a later route, so ordering is part of the
   plan, not an afterthought.

⛔ This is the capability with no tool today, and six games need it.

### T-C `configure` — set a layout, let the board resolve it   (5 games: sp80 tn36 sc25 cd82 ar25)

1. **Detect the two-phase shape** — actions edit a configuration; one COMMIT action resolves it.
2. **Learn the resolution as a SIMULATOR** from one sacrificial commit — sp80's whole spill arrives as
   frame layers, so one commit buys the entire trajectory (R98 measured this at 1 action).
3. **Search over CONFIGURATIONS, not actions.** The action graph explodes here because one
   configuration is tens of actions; the search space is layouts, scored by the simulator.
4. **Commit only a layout the simulator says wins**, so a failed commit is a modelling error to learn
   from rather than a guess.

R98 built exactly this for one member (sp80) and proved the shape: *"for two-phase place-then-propagate
boards the transition model IS the simulator"*. `configure` is that generalised to the class.

### T-D `induce` — infer the rule, then apply it to a target   (7 games: ft09 sb26 sk48 tr87 lf52 cn04 vc33)

1. **Read the target off the board** — these games show what the answer looks like (a pattern, a
   multiset, a shape) somewhere in the frame.
2. **INDUCE the rule from observed transitions** — what one click/move actually does, as a mapping,
   before planning anything. This is the missing step that makes every action a guess.
3. **Search in RULE space** — compose the induced operation toward the target (GF(2) for parity, DFS
   for portal traversal, rewriting for grammars).
4. **Order the applications** when they interfere.

⛔ This is where the inert-action measurement lives: all four of the worst games (ft09 99%, vc33 97%,
s5i5 97%, sb26 87%) are class D, guessing because no rule was induced first.

## Order of work, and why

**T-D first.** It is the largest class (7), it owns the sharpest measured failure (99% inert), and its
step 2 — induce before acting — is the one that turns a guessing loop into a directed one. **T-B
second** (6 games, no tool at all today). **T-C third** (5 games, and R98 already proved the shape on
one). **T-A last** — `graph` half-covers it, so it is the smallest gain.

## What must not regress

The deployed card is `--agent kaggle_detect`, full 25 = **0.3162**. These tools live in
`admorphiq.tools` behind the harness; adding one must leave that number unchanged until it is
deliberately promoted.
