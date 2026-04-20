"""Generate skeleton wiki/games/<GAME>.md pages from extracted trace JSONL.

Idempotent: skips games whose wiki page already exists (preserves hand-written
TN36.md, SU15.md, AR25.md which have richer content).

Inputs
------
.wiki/raw/traces/<game>.jsonl (produced by scripts/extract_wiki_traces.py)
.wiki/raw/traces/_summary.json

Output
------
.wiki/wiki/games/<GAME>.md for each game not already seeded.
"""

from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
TRACES_DIR = REPO_ROOT / ".wiki" / "raw" / "traces"
GAMES_DIR = REPO_ROOT / ".wiki" / "wiki" / "games"


GAME_TYPE_GUESS: dict[str, str] = {
    "CD82": "click",
    "FT09": "click",
    "SB26": "sort_puzzle",
    "SU15": "merge_puzzle",
    "TN36": "programming_puzzle",
    "KA59": "sokoban",
    "RE86": "transform",
    "WA30": "delivery",
    "S5I5": "slider_puzzle",
    "TU93": "movement",
    "TR87": "rotation",
    "LS20": "movement",
    "AR25": "movement",
    "BP35": "platformer",
    "CN04": "click",
    "DC22": "movement",
    "G50T": "hybrid",
    "LP85": "click",
    "M0R0": "movement",
    "R11L": "sequence",
    "SC25": "spell_cast",
    "SP80": "movement",
    "VC33": "click",
    "LF52": "unknown",
    "SK48": "movement",
}


def load_entries(game_title: str) -> list[dict]:
    path = TRACES_DIR / f"{game_title.lower()}.jsonl"
    if not path.exists():
        return []
    with path.open() as f:
        return [json.loads(line) for line in f]


def render_page(title: str, entries: list[dict]) -> str:
    """Render a single game wiki page as markdown."""
    v1 = entries[0] if entries else {}
    v2 = entries[1] if len(entries) > 1 else None

    v1_cleared = v1.get("cleared", False)
    v1_levels = f"{v1.get('levels_completed', 0)}/{v1.get('win_levels', 0)}"
    v1_status = f"{v1_levels} {'✅' if v1_cleared else '❌'}"
    winning = v1.get("winning_strategy") or "-"
    meta = v1.get("winning_strategy_meta") or {}
    strategy_type = meta.get("type", "unknown")
    internals = meta.get("internals", [])

    if v2:
        v2_cleared = v2.get("cleared", False)
        v2_levels = f"{v2.get('levels_completed', 0)}/{v2.get('win_levels', 0)}"
        v2_status = f"{v2_levels} {'✅' if v2_cleared else '❌'}"
    else:
        v2_status = "n/a (API served only one version)"

    generalizes = "unknown"
    if v2:
        if v2.get("cleared"):
            generalizes = "yes"
        elif v1_cleared:
            generalizes = "no"

    game_type = GAME_TYPE_GUESS.get(title, "unknown")

    lines: list[str] = []
    lines.append("---")
    lines.append("type: game")
    lines.append(f"game_id: {title.lower()}")
    lines.append(f"game_type: {game_type}")
    lines.append(f"status_v1: {v1_status}")
    lines.append(f"status_v2: {v2_status}")
    lines.append(f"current_strategy: {winning} ({strategy_type})")
    lines.append(f"generalizes: {generalizes}")
    lines.append("---")
    lines.append("")
    lines.append(f"# {title}")
    lines.append("")
    oneliner = {
        "frame_only": "Frame-observation solver — generalizes across version hashes.",
        "brittle": "Relies on game internals — high v1 score, fails on v2.",
        "unknown": "Solved by a strategy not yet classified; needs hand review.",
    }[strategy_type]
    lines.append(f"> {oneliner} [to be expanded with mechanics + solution pattern]")
    lines.append("")
    lines.append("## Current Status")
    lines.append("")
    lines.append(f"- **v1** ({v1.get('game_id', '?')}): {v1_status} via `{winning}`")
    if v2:
        v2_winning = v2.get("winning_strategy") or "none"
        lines.append(f"- **v2** ({v2.get('game_id', '?')}): {v2_status} via `{v2_winning}`")
    else:
        lines.append("- **v2**: not served by API as of 2026-04-20")
    lines.append(f"- **Strategy classification**: `{strategy_type}`")
    if internals:
        lines.append("- **Internal access used**:")
        for item in internals:
            lines.append(f"  - `{item}`")
    lines.append("")
    lines.append("## Observations")
    lines.append("")
    lines.append("_To be written by hand or by a downstream LLM compiler pass._")
    lines.append("")
    lines.append("## Mechanics Hypothesis")
    lines.append("")
    lines.append("_To be written._")
    lines.append("")
    lines.append("## Solution Pattern")
    lines.append("")
    tried = v1.get("strategies_tried", [])
    if tried:
        lines.append("Strategies that made progress on v1:")
        lines.append("")
        lines.append("| Strategy | Levels | Actions | Type |")
        lines.append("|---|---|---|---|")
        for s in tried:
            lines.append(
                f"| `{s['name']}` | {s['levels']} | {s['actions']} | {s['meta']['type']} |"
            )
    else:
        lines.append("_No strategy progressed on v1; see `.wiki/raw/traces/` for full attempt log._")
    lines.append("")
    if strategy_type == "brittle":
        lines.append("## Refactor Plan (Phase 8 Step 2)")
        lines.append("")
        lines.append(
            "Replace internal access with frame-only detection (color clusters, diffs, "
            "persistent regions). See `[[../strategies/brittle/internal_method_call]]`."
        )
        lines.append("")
    lines.append("## Related")
    lines.append("")
    lines.append(f"- [[../game_types/{game_type}]]")
    if strategy_type == "brittle":
        lines.append("- [[../strategies/brittle/internal_method_call]]")
    elif strategy_type == "frame_only":
        lines.append(f"- [[../strategies/frame_only/{winning}]] (to be written)")
    lines.append("")
    lines.append("## Sources")
    lines.append("")
    lines.append(f"- `.wiki/raw/traces/{title.lower()}.jsonl`")
    lines.append(f"- `src/admorphiq/agent_ensemble.py` (`strat_{winning}` implementation)")
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    GAMES_DIR.mkdir(parents=True, exist_ok=True)

    created: list[str] = []
    skipped: list[str] = []

    for trace_file in sorted(TRACES_DIR.glob("*.jsonl")):
        title = trace_file.stem.upper()
        out_path = GAMES_DIR / f"{title}.md"
        if out_path.exists():
            skipped.append(title)
            continue
        entries = load_entries(title)
        if not entries:
            continue
        out_path.write_text(render_page(title, entries))
        created.append(title)

    print(f"Created {len(created)} pages: {created}")
    print(f"Skipped (already seeded): {skipped}")


if __name__ == "__main__":
    main()
