"""Efficiency-first action primitives for the general agent.

Each primitive is a *deterministic* (no-LLM) detector + solver pair keyed on
observable frame / probe signatures, so it transfers to the 110 private Kaggle
games (never branches on game id / title). See
``docs/game_win_conditions_taxonomy.md`` for the win-condition classes the
primitives target.
"""
