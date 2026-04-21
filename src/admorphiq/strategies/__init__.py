"""Strategy implementations organized into modules.

`src/admorphiq/agent_ensemble.py` is the legacy single-file registry
that the introspector walks to build the LLM-pickable whitelist. New
strategies go in dedicated modules here and are re-exported into
`agent_ensemble` so the introspector still finds them by their
`strat_*` name.
"""
