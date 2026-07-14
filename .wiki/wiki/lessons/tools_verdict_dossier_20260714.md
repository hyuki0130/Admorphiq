---
type: lesson
date: 2026-07-14
keywords: [tools, hand-crafted, duck, reki, tolani, tool-evolution, dossier, leaderboard]
---

# 10+ team dossier: the "hand-crafted tools" question (2026-07-14)

> "Hand-crafted tools are harmful" is a MISREADING of Duck's claim — game-SPECIFIC tools hurt,
> GENERIC perception/efficiency tools help (winners keep them); tool-EVOLUTION is untouched
> white space; Tolani's LB 1.32 (above Duck 1.21) validates the learned-dynamics-WM direction.

## Key corrected facts (researcher-verified, sources in the round-3 dossier)
- Duck's exact words: hand-crafting SPECIFIC tools "did not help… hinders creative abilities";
  the SAME team ships a GENERIC segmentation tool it calls "significantly helps".
- Reki (M1 #2) KEEPS hand-crafted machinery: numpy click-heuristic fallback + dead-signature
  suppression. forge (#3) built arbiter/confidence machinery — best run had it OFF.
- **Akhil Tolani: LB 1.32 > Duck 1.21** — Gemma-4-31B (QAT, pruned vocab) vision policy + a
  LEARNED dynamics world model (LeWM/JEPA action-effect predictor). Open source at public
  0.6-0.8 (disc/716711, code saltb0x/arc3-gemma-dynamics). Independent validation of the
  learned-WM direction (our world_model/EWM track).
- Public code tab >1.0 ≈ all Duck forks (thtennant v2-v12, taaf-* reshares…). Real LB top-50
  (1.28-1.61) methods are NOT public — "top teams chose no-tools" is unsupported narrative.
- Tool-EVOLUTION (LLM builds/improves a persistent helper library): NOBODY does it. Closest:
  RGB Agent (generic coding workspace over a history log; near-human on 3 preview games) and
  Duck's cross-turn "World model:" note. This is differentiation white space (user's proposal).
- huikang: "autoresearch" NN-architecture search fitted on public gameplay (transfer risk).
- The "0.44 BFS" rumor: refuted — hidden games aren't file-accessible at rerun (disc/687950).

## Implications adopted
1. Keep GENERIC perception/efficiency tools in the REPL (segmentation, dead-signature); the
   banned line is game-specific solvers in the decision loop. Our brittle-purge doctrine stands.
2. Strengthen the world_model track (Tolani evidence) — candidate REPL tool: online-fitted
   action-effect predictor.
3. Tool-evolution = high-risk/high-differentiation experiment worth a SMALL measured probe.
4. Verdict + concrete design delegated to Codex deep-dive (codex_tools_verdict) — binding for
   R55 Round 1 inventory.

## Related
[[lb_top_team_research_20260714]], [[duck_harness_teardown_20260714]], [[r55_code-repl-agent]]
