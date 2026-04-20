---
type: reasoning
input_type: game classification output
output_type: ordered list of wiki pages to load as LLM context
---

# Wiki Retrieval Recipe

> At Kaggle inference time (offline, no internet), the Hypothesis Engine LLM needs to assemble a context window of relevant wiki pages. This recipe prescribes *which* pages to load in *what order*, optimizing for the 128K-token context budget.

## When to invoke

- Immediately after `[[discovery_phase]]` produces a classification (game_type guess)
- After `[[hypothesis_check]]` revises the classification
- After the primary strategy stalls (fallback escalation)

## Retrieval algorithm

Given: classified `game_type`, identified entities, and current `strategy_name`.

### Always include (≤5KB)
1. `.wiki/schema.md` — conventions (so the LLM stays on-format)
2. `.wiki/wiki/selector.md` — dispatch rules
3. `.wiki/wiki/reasoning/discovery_phase.md` — in case reclassification is needed
4. `.wiki/wiki/reasoning/frame_to_strategy_chain.md`
5. `.wiki/wiki/reasoning/hypothesis_check.md`

### Game-type-specific (≤10KB)
6. `.wiki/wiki/game_types/<game_type>.md`
7. Top-3 `.wiki/wiki/games/*.md` whose `game_type` frontmatter matches

### Concept-specific (≤10KB)
For each concept mentioned in the selected game_type's Related section:
8. `.wiki/wiki/concepts/<concept>.md`

### Strategy-specific (≤5KB)
9. `.wiki/wiki/strategies/frame_only/<primary_strategy>.md`
10. If fallback triggered, fallback strategy pages

### Lessons/debug gating (≤10KB, load on demand)
Only when relevant:
11. `.wiki/wiki/lessons/v2_hash_obfuscation.md` if attribute-error-like symptom
12. `.wiki/wiki/lessons/brittle_tells.md` when reviewing a strategy choice
13. `.wiki/wiki/debug/<playbook>.md` when a specific failure mode is active

### Raw (load only when specifically needed, up to budget)
14. `.wiki/raw/traces/<game>.jsonl` — only if the game title matches a known game
15. `.wiki/raw/regressions/<latest>.md` — only on error diagnosis

### Total budget target
- Typical load: ~30KB markdown → fits comfortably in any candidate LLM's 128K context with room for reasoning output
- Never exceed: 60KB (leaves half of context for LLM working memory)

## Worked example — LLM facing unknown movement game

```
Input:
  game_type_guess = "movement"
  entities = {player_color: 5, walls: [...], goal: (45, 30)}
  no prior strategy

Load:
  schema.md
  wiki/selector.md
  wiki/reasoning/discovery_phase.md
  wiki/reasoning/frame_to_strategy_chain.md
  wiki/reasoning/hypothesis_check.md
  wiki/game_types/movement.md
  wiki/games/AR25.md        (best match — generalizes)
  wiki/games/DC22.md        (close match)
  wiki/games/M0R0.md        (close match)
  wiki/concepts/sprite_cluster.md
  wiki/concepts/frame_hashing.md
  wiki/strategies/frame_only/bfs_state_space.md

Output (from LLM):
  primary_strategy: bfs_state_space
  rationale: "Classic movement game; frame-hash BFS succeeded on AR25, DC22, M0R0 with same architecture."
  fallback_stack: [graph_explore, wall_avoid]
```

## Worked example — LLM facing attribute error

```
Input:
  symptom = "AttributeError: no attribute hmeulfxgy"
  game_type_guess was "merge_puzzle" (matched SU15)
  selected strategy was su15_vacuum (brittle)

Load (additionally):
  wiki/lessons/v2_hash_obfuscation.md
  wiki/lessons/brittle_tells.md
  wiki/debug/attribute_error_playbook.md
  wiki/strategies/brittle/internal_method_call.md

Output (from LLM):
  primary_strategy: click_rare_near_largest_cluster  (substitute until frame-only merge solver is ready)
  fallback_stack: [click_grid, bfs_state_space]
  note: "Brittle v1 solver failed on v2 hash. Falling back to frame-only clicks."
```

## Implementation notes

For `scripts/run_wiki_agent.py` (Phase 8 Step 3):

```python
def load_wiki_context(game_type: str, game_title_hint: str | None = None) -> str:
    base = [
        ".wiki/schema.md",
        ".wiki/wiki/selector.md",
        ".wiki/wiki/reasoning/discovery_phase.md",
        ".wiki/wiki/reasoning/frame_to_strategy_chain.md",
        ".wiki/wiki/reasoning/hypothesis_check.md",
    ]
    type_page = f".wiki/wiki/game_types/{game_type}.md"
    similar_games = find_similar_game_pages(game_type, top_n=3)
    concept_pages = extract_concept_links(type_page)
    strategy_page = f".wiki/wiki/strategies/frame_only/{DISPATCH[game_type]}.md"
    return "\n\n---\n\n".join(read(p) for p in base + [type_page] + similar_games + concept_pages + [strategy_page])
```

## Related

- [[discovery_phase]]
- [[frame_to_strategy_chain]]
- [[hypothesis_check]]
- [[../selector]]
