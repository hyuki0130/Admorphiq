"""Enrich skeleton wiki/games/*.md pages with curated Observations and Mechanics sections.

Regenerates every game page except AR25, SU15, TN36 (which were hand-written as rich
templates earlier). Uses `.wiki/raw/traces/<game>.jsonl` for measured stats and a
curated GAME_KNOWLEDGE dict for narrative sections derived from docstrings in
`src/admorphiq/agent_ensemble.py`.

Idempotent: safe to run after each source-code change (re-reads traces, re-renders).
"""

from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
TRACES_DIR = REPO_ROOT / ".wiki" / "raw" / "traces"
GAMES_DIR = REPO_ROOT / ".wiki" / "wiki" / "games"

HAND_WRITTEN = {"AR25", "SU15", "TN36"}


GAME_TYPE: dict[str, str] = {
    "CD82": "click", "FT09": "click", "SB26": "sort_puzzle",
    "SU15": "merge_puzzle", "TN36": "programming_puzzle",
    "KA59": "sokoban", "RE86": "transform", "WA30": "delivery",
    "S5I5": "slider_puzzle", "TU93": "movement", "TR87": "rotation",
    "LS20": "movement", "AR25": "movement", "BP35": "platformer",
    "CN04": "click", "DC22": "movement", "G50T": "hybrid",
    "LP85": "click", "M0R0": "movement", "R11L": "sequence",
    "SC25": "spell_cast", "SP80": "movement", "VC33": "click",
    "LF52": "unknown", "SK48": "movement",
}


# Per-game cross-links to concepts/, lessons/, debug/, and peer games.
# Drives the "Lessons Learned" and "Related concepts" sections added to each page.
GAME_LINKS: dict[str, dict[str, list[str]]] = {
    "BP35": {
        "concepts": ["gravity", "sprite_cluster", "frame_hashing"],
        "lessons": ["frame_diff_as_probe"],
        "debug": [],
        "peers": ["AR25", "M0R0"],
    },
    "CD82": {
        "concepts": ["sprite_cluster"],
        "lessons": ["v2_hash_obfuscation", "hardcoded_is_anti", "brittle_tells"],
        "debug": ["attribute_error_playbook", "v1_vs_v2_diagnosis"],
        "peers": ["FT09"],
    },
    "CN04": {
        "concepts": ["sprite_cluster", "rare_color_click"],
        "lessons": ["frame_diff_as_probe"],
        "debug": [],
        "peers": ["LP85", "VC33"],
    },
    "DC22": {
        "concepts": ["sprite_cluster", "frame_hashing"],
        "lessons": ["frame_diff_as_probe"],
        "debug": [],
        "peers": ["AR25", "M0R0", "SP80"],
    },
    "FT09": {
        "concepts": ["sprite_cluster"],
        "lessons": ["v2_hash_obfuscation", "brittle_tells", "hardcoded_is_anti"],
        "debug": ["attribute_error_playbook", "v1_vs_v2_diagnosis"],
        "peers": ["CD82", "SB26"],
    },
    "G50T": {
        "concepts": ["sprite_cluster", "frame_hashing"],
        "lessons": ["frame_diff_as_probe"],
        "debug": [],
        "peers": ["AR25"],
    },
    "KA59": {
        "concepts": ["pushable_block", "sprite_cluster", "frame_hashing"],
        "lessons": ["v2_hash_obfuscation", "hardcoded_is_anti", "brittle_tells"],
        "debug": ["attribute_error_playbook", "v1_vs_v2_diagnosis"],
        "peers": ["WA30"],
    },
    "LF52": {
        "concepts": ["sprite_cluster", "frame_hashing"],
        "lessons": ["silent_regression", "trust_regression_not_commits"],
        "debug": ["regression_bisect_playbook"],
        "peers": ["SK48"],
    },
    "LP85": {
        "concepts": ["rare_color_click", "sprite_cluster"],
        "lessons": ["frame_diff_as_probe"],
        "debug": [],
        "peers": ["VC33", "CN04"],
    },
    "LS20": {
        "concepts": ["rotation_state", "sprite_cluster"],
        "lessons": ["hardcoded_is_anti", "brittle_tells"],
        "debug": ["v1_vs_v2_diagnosis"],
        "peers": ["TR87"],
    },
    "M0R0": {
        "concepts": ["sprite_cluster", "frame_hashing"],
        "lessons": ["frame_diff_as_probe"],
        "debug": [],
        "peers": ["AR25", "DC22", "SP80"],
    },
    "R11L": {
        "concepts": ["sprite_cluster"],
        "lessons": ["frame_diff_as_probe"],
        "debug": [],
        "peers": ["SC25"],
    },
    "RE86": {
        "concepts": ["sprite_cluster"],
        "lessons": ["v2_hash_obfuscation", "brittle_tells", "hardcoded_is_anti"],
        "debug": ["attribute_error_playbook", "v1_vs_v2_diagnosis"],
        "peers": ["WA30"],
    },
    "S5I5": {
        "concepts": ["sprite_cluster"],
        "lessons": ["v2_hash_obfuscation", "brittle_tells"],
        "debug": ["attribute_error_playbook", "v1_vs_v2_diagnosis"],
        "peers": ["LS20"],
    },
    "SB26": {
        "concepts": ["sprite_cluster"],
        "lessons": ["v2_hash_obfuscation", "brittle_tells", "hardcoded_is_anti"],
        "debug": ["attribute_error_playbook"],
        "peers": ["CD82"],
    },
    "SC25": {
        "concepts": ["sprite_cluster"],
        "lessons": ["frame_diff_as_probe"],
        "debug": [],
        "peers": ["R11L"],
    },
    "SK48": {
        "concepts": ["sprite_cluster", "frame_hashing"],
        "lessons": ["silent_regression", "trust_regression_not_commits"],
        "debug": ["regression_bisect_playbook"],
        "peers": ["LF52"],
    },
    "SP80": {
        "concepts": ["sprite_cluster", "frame_hashing"],
        "lessons": ["frame_diff_as_probe"],
        "debug": [],
        "peers": ["AR25", "DC22", "M0R0"],
    },
    "TR87": {
        "concepts": ["rotation_state", "sprite_cluster"],
        "lessons": ["hardcoded_is_anti", "brittle_tells"],
        "debug": ["v1_vs_v2_diagnosis"],
        "peers": ["LS20"],
    },
    "TU93": {
        "concepts": ["sprite_cluster", "frame_hashing"],
        "lessons": ["hardcoded_is_anti", "brittle_tells"],
        "debug": ["v1_vs_v2_diagnosis"],
        "peers": ["AR25", "M0R0"],
    },
    "VC33": {
        "concepts": ["rare_color_click", "sprite_cluster"],
        "lessons": ["frame_diff_as_probe"],
        "debug": [],
        "peers": ["LP85"],
    },
    "WA30": {
        "concepts": ["pushable_block", "sprite_cluster"],
        "lessons": ["v2_hash_obfuscation", "brittle_tells", "hardcoded_is_anti"],
        "debug": ["attribute_error_playbook", "v1_vs_v2_diagnosis"],
        "peers": ["KA59", "RE86"],
    },
}


# Curated per-game knowledge. Each entry: (observations_bullets, mechanics, refactor_or_notes)
# observations: list of short bullets about frame-level features + action effects
# mechanics: a single paragraph naming the game's rule/goal
# notes: for brittle strategies, the frame-only refactor direction; for frame-only,
#        a note about why BFS or click_rare works.
GAME_KNOWLEDGE: dict[str, dict[str, object]] = {
    "BP35": {
        "observations": [
            "Gravity platformer: player falls unless on a block",
            "ACTION1/2 = horizontal movement; ACTION6 clicks destroy blocks",
            "Exit marker is a distinct color (typically a `+`-shaped cluster)",
        ],
        "mechanics": (
            "Navigate the player to the exit by combining lateral moves with selective "
            "block destruction. Destroying a block below the player causes a controlled "
            "fall; clearing a lateral block opens a passage."
        ),
        "notes": (
            "Frame-only strategy `bp35_platformer` works by detecting player sprite via "
            "color-motion diff and tracing a gravity-aware path. Already generalizes."
        ),
    },
    "CD82": {
        "observations": [
            "3x3 grid of color swatches below a canvas region",
            "ACTION6 on swatch selects a color; ACTION6 on launch button paints canvas",
            "Levels demand a specific color pattern on the canvas",
        ],
        "mechanics": (
            "Navigate a basket across a 3x3 grid to pick colors, then fire them onto a "
            "canvas to reproduce a target color pattern. Level progresses when the "
            "canvas matches."
        ),
        "notes": (
            "Current `strat_paint_game` reads hardcoded sprite positions "
            "(`pqkenviek`, `ctwspzkygu`). Refactor: detect swatch centers via "
            "color clustering (contiguous same-color pixels), detect launch button "
            "via diff after a probe click."
        ),
    },
    "CN04": {
        "observations": [
            "Click-reactive sprites on a static background",
            "ACTION6 at specific coordinates triggers level progression",
            "Diagonal zig-zag pattern (ACTION2+ACTION4) reliably clears level 1",
        ],
        "mechanics": (
            "A click/movement puzzle where progression requires specific coordinate "
            "choices. The winning strategy `zig3_A2A4` zig-zags via two alternating "
            "actions — suggests the game accepts a simple repeating pattern rather "
            "than a targeted click."
        ),
        "notes": (
            "Frame-only via action-pattern probing. v2 failure implies tuning (count/"
            "timing) is version-specific; generalize by learning repeat-count from "
            "frame response during discovery."
        ),
    },
    "DC22": {
        "observations": [
            "Single-layer grid, movement game",
            "ACTION1-4 cardinal; ACTION6 can toggle barriers by clicking buttons",
            "`button_click_move`: click buttons first, then navigate the exit path",
        ],
        "mechanics": (
            "Hybrid button + movement: certain buttons in the grid toggle barrier "
            "states; the player must click-toggle the right buttons and then walk "
            "to the exit."
        ),
        "notes": (
            "Frame-only via state-space BFS. Works on both v1 and v2 since only "
            "pixel-level state is read."
        ),
    },
    "FT09": {
        "observations": [
            "Grid of clickable cells; clicking toggles the clicked cell and neighbors",
            "Constraints (color targets) printed on designated cells",
            "Classic lights-out variant over GF(p) for some p",
        ],
        "mechanics": (
            "A lights-out / XOR-toggle puzzle where each click modifies the clicked "
            "cell plus a neighborhood; the goal configuration is encoded by constraint "
            "sprites. Solvable analytically via linear algebra over the small finite field."
        ),
        "notes": (
            "Current `strat_lights_out` reads sprite tags `Hkx`, `NTi`, `bsT`, `ZkU` "
            "to identify cell positions and constraints. Refactor: detect cell grid "
            "via uniform spacing in frame diff (clicks change local color); infer "
            "constraint type by probing."
        ),
    },
    "G50T": {
        "observations": [
            "Hybrid game combining exploration and interaction",
            "`explore_interact` strategy found to be effective",
            "Large action budget was required (~15k actions)",
        ],
        "mechanics": (
            "Mixed movement and interactive objects; progression requires discovering "
            "which objects respond to ACTION5 or specific click coordinates while "
            "navigating the grid."
        ),
        "notes": (
            "Frame-only via explore-interact pattern (random interaction followed by "
            "memory of successful triggers). Low depth (1/7) — more sophisticated "
            "solver needed for later levels."
        ),
    },
    "KA59": {
        "observations": [
            "Multi-player (cooperative) Sokoban: two agents push blocks",
            "ACTION1-4 move; certain blocks push when adjacent",
            "Goal zones accept pushed blocks in specific formation",
        ],
        "mechanics": (
            "Sokoban variant where the agent coordinates movement of multiple player "
            "avatars to push blocks into marked goal cells. Block arrangement and "
            "avatar coupling vary per level."
        ),
        "notes": (
            "Current `strat_ka59_sokoban` uses hardcoded push sequences for L1-L4. "
            "Refactor: detect pushable blocks via frame diff (sprites that move when "
            "adjacent agent moves), detect goals via persistent region coloring, "
            "plan pushes via A* on a sokoban lattice."
        ),
    },
    "LF52": {
        "observations": [
            "Never cleared in latest regression (0/10)",
            "Historical commits (b1cbc91) cleared level 1 via ensemble budget 50K",
            "Multi-layer grid suggests movement + interaction",
        ],
        "mechanics": (
            "Unknown post-regression (the prior clearing strategy no longer triggers). "
            "Likely a movement-plus-interaction game that needs a more targeted approach."
        ),
        "notes": (
            "Highest priority target for Phase 8 Step 4 (regression bisect) — pin down "
            "the commit that broke it and restore frame-only working strategy."
        ),
    },
    "LP85": {
        "observations": [
            "Click at a specific coordinate clears level (winning move: `click_c8_(30,4)`)",
            "Strategy `click_rare` succeeds — rare-color pixel is the click target",
            "Static non-interactive elements dominate the frame",
        ],
        "mechanics": (
            "The game exposes a single correct pixel per level whose color is distinct "
            "(rare) in the frame. Clicking it triggers level completion."
        ),
        "notes": (
            "Frame-only via rare-color click. Trivially generalizes as long as rarity "
            "as a heuristic identifies the target."
        ),
    },
    "LS20": {
        "observations": [
            "Grid with shapes in cells — shape, color, and rotation all matter",
            "ACTION6 to pick/place; ACTION1-4 to move cursor or rotate",
            "Matching puzzle: arrange cells so rows/columns meet a pattern",
        ],
        "mechanics": (
            "A grid-matching puzzle where each cell has shape/color/rotation attributes. "
            "Solving requires assigning cells to positions so the pattern criterion holds."
        ),
        "notes": (
            "Current `strat_ls20_grid` has hardcoded L1 move sequence. Refactor: detect "
            "cell attributes via per-cell color histogram and shape hashing, then search "
            "valid assignments."
        ),
    },
    "M0R0": {
        "observations": [
            "Movement game with mirror / reflection mechanic",
            "ACTION1-4 move; obstacle layout forces path discovery",
            "BFS over state hashes resolves up to L2 on both v1 and v2",
        ],
        "mechanics": (
            "Navigate through mirrored/rotated environments where the player's action "
            "mapping may effectively flip. BFS captures the deterministic transitions."
        ),
        "notes": "Frame-only via BFS — robust. Deeper levels likely need symmetry reasoning.",
    },
    "R11L": {
        "observations": [
            "Short action sequences trigger progression",
            "Strategy `seq_repeat` and `seq_search` make progress",
            "Frame diff reveals a short period that repeats on success",
        ],
        "mechanics": (
            "The game accepts an action sequence (likely 3-5 actions) whose execution "
            "progresses the level. Discovering the sequence by short search over "
            "action k-tuples works."
        ),
        "notes": "Frame-only via sequence search. v2 passes unchanged.",
    },
    "RE86": {
        "observations": [
            "Multiple sprites must be moved to target positions",
            "`changer` cells modify sprite color on contact",
            "Multi-sprite same-color constraints require routing through changers",
        ],
        "mechanics": (
            "A transform puzzle: each movable sprite must reach one of several target "
            "positions, optionally routing through color-changing tiles. Correct "
            "assignment depends on sprite and target colors."
        ),
        "notes": (
            "Current `strat_re86_analytical` reads tags `vzuwsebntu` (targets), "
            "`vfaeucgcyr` (movables), `ozhohpbjxz` (changers). Refactor: derive "
            "these classes from frame — targets are static, movables respond to "
            "movement actions, changers trigger color change on overlap."
        ),
    },
    "S5I5": {
        "observations": [
            "Resizeable slider objects plus rotate buttons",
            "Clicking a slider moves its goal marker by 3 units along slider axis",
            "Rotate buttons change slider direction (costs a step)",
        ],
        "mechanics": (
            "A spatial puzzle: adjust sliders so that linked goal markers reach target "
            "positions. Each slider has an axis and a rotation handle; goals are "
            "dragged by resizing."
        ),
        "notes": (
            "Current `strat_s5i5_slider` reads tags `myzmclysbl` (rotate buttons), "
            "`zylvdxoiuq` (goals). Refactor: detect sliders by elongated color clusters, "
            "rotate buttons by small isolated clickables, goals by distinct color."
        ),
    },
    "SB26": {
        "observations": [
            "Items at the bottom of the frame must be swapped into target slots",
            "ACTION5 scans/verifies; ACTION6 clicks to select or swap; ACTION7 undoes",
            "Frames can contain portals that redirect to other frames",
        ],
        "mechanics": (
            "A sorting/matching puzzle where the agent swaps items into slots matching "
            "a target color sequence. Portals complicate routing across multiple frames."
        ),
        "notes": (
            "Current `strat_sb26_sort` reads portal/slot internals. Refactor: detect "
            "slots via target-color sequence visible on screen; detect portals via "
            "frame-level jumps after clicks."
        ),
    },
    "SC25": {
        "observations": [
            "Spell-casting sub-game: click exact 3x3 spell slots",
            "Wait for animation between clicks",
            "After casting, navigate to exit",
        ],
        "mechanics": (
            "A two-phase game: cast the correct spell pattern on a 3x3 grid, then "
            "move through the unlocked path to the exit."
        ),
        "notes": (
            "Frame-only via `spell_cast` — generalizes because the grid geometry "
            "is inferred from pixel positions, not tag names."
        ),
    },
    "SK48": {
        "observations": [
            "Previously cleared on L1 via `sk48_snake` strategy",
            "Both v1 and v2 fail in current regression (silent regression)",
            "Multi-layer grid with movement mechanic",
        ],
        "mechanics": (
            "Snake-style movement where the player occupies a growing tail and must "
            "navigate to food or exit cells without self-collision."
        ),
        "notes": (
            "Phase 8 Step 4 target: bisect regression, restore snake strategy with "
            "frame-only head/tail detection."
        ),
    },
    "SP80": {
        "observations": [
            "Cardinal movement grid",
            "BFS over state-space solves L1 on both v1 and v2",
            "Deeper levels likely introduce new mechanics",
        ],
        "mechanics": "Deterministic movement puzzle solvable by BFS when reachable states are bounded.",
        "notes": "Frame-only via BFS — generalizes. Deeper levels may need heuristic pruning.",
    },
    "TR87": {
        "observations": [
            "Rotatable pieces; ACTION1/ACTION2 rotate; ACTION3/ACTION4 select",
            "Pattern-match target visible in a corner of the frame",
            "L1 solved by a hardcoded rotation sequence",
        ],
        "mechanics": (
            "Rotate each piece to match a reference pattern. Pieces are selected one "
            "at a time; each select+rotate cycle is a step."
        ),
        "notes": (
            "Current `strat_tr87_rotation` hardcodes L1 values. Refactor: compare "
            "current piece orientation to target pattern via per-cell color signature "
            "and BFS over rotation operations."
        ),
    },
    "TU93": {
        "observations": [
            "Maze navigation: player reaches exit on grid board",
            "L1/L2 cleared via hardcoded move sequences",
            "Surprisingly v2 also passes — move sequences happened to match layout",
        ],
        "mechanics": "Standard 2D maze with walls and a single exit cell per level.",
        "notes": (
            "Current `strat_tu93_maze` has hardcoded L1/L2 solutions. Refactor: "
            "detect walls/floor via color, run BFS from player position to exit. "
            "Generic movement strategy should work — the hardcoding is gratuitous."
        ),
    },
    "VC33": {
        "observations": [
            "Click at specific coordinate clears level (winner: `click_c9_(33,60)`)",
            "Color 9 cluster is the target; located near bottom-right",
            "Similar shape to LP85 but with different target color",
        ],
        "mechanics": (
            "Click-to-advance game where a specific-color pixel is the correct "
            "click target. Different levels may pick different colors/positions."
        ),
        "notes": (
            "Frame-only via color-indexed click; generalizes. May benefit from "
            "adaptive color detection to handle color-palette shifts."
        ),
    },
    "WA30": {
        "observations": [
            "Delivery task: pick up items and deliver to target zones",
            "Sokoban-like pushing with sprite constraints",
            "Worker character navigates pickups and drop-off zones",
        ],
        "mechanics": (
            "The worker picks up items at pickup zones and delivers them to matching "
            "target zones. Multiple items per level; routing matters."
        ),
        "notes": (
            "Current `strat_wa30_analytical` reads tags `wbmdvjhthc`, `wyzquhjerd`, "
            "`pkbufziase`. Refactor: detect pickups/targets by persistent regions, "
            "detect worker via movement response, plan deliveries via min-cost "
            "matching + movement BFS."
        ),
    },
}


def load_entries(title: str) -> list[dict]:
    path = TRACES_DIR / f"{title.lower()}.jsonl"
    if not path.exists():
        return []
    with path.open() as f:
        return [json.loads(line) for line in f]


def render(title: str, entries: list[dict]) -> str:
    k = GAME_KNOWLEDGE.get(title)
    v1 = entries[0] if entries else {}
    v2 = entries[1] if len(entries) > 1 else None

    v1_cleared = v1.get("cleared", False)
    v1_levels = f"{v1.get('levels_completed', 0)}/{v1.get('win_levels', 0)}"
    v1_status = f"{v1_levels} {'✅' if v1_cleared else '❌'}"
    winning = v1.get("winning_strategy") or "-"
    meta = v1.get("winning_strategy_meta") or {}
    strategy_type = meta.get("type", "unknown")
    internals = meta.get("internals", [])
    game_type = GAME_TYPE.get(title, "unknown")

    if v2:
        v2_cleared = v2.get("cleared", False)
        v2_levels = f"{v2.get('levels_completed', 0)}/{v2.get('win_levels', 0)}"
        v2_status = f"{v2_levels} {'✅' if v2_cleared else '❌'}"
        generalizes = "yes" if v2_cleared else ("no" if v1_cleared else "unknown")
    else:
        v2_status = "n/a (API served only one version)"
        generalizes = "unknown"

    oneliner = {
        "frame_only": "Frame-observation solver — generalizes across version hashes.",
        "brittle": "Relies on game internals — high v1 score, fails on v2.",
        "unknown": "Not yet classified; needs hand review.",
    }[strategy_type]

    lines: list[str] = [
        "---",
        "type: game",
        f"game_id: {title.lower()}",
        f"game_type: {game_type}",
        f"status_v1: {v1_status}",
        f"status_v2: {v2_status}",
        f"current_strategy: {winning} ({strategy_type})",
        f"generalizes: {generalizes}",
        "---",
        "",
        f"# {title}",
        "",
        f"> {oneliner}",
        "",
        "## Current Status",
        "",
        f"- **v1** ({v1.get('game_id', '?')}): {v1_status} via `{winning}`",
    ]
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
    if k and k.get("observations"):
        for obs in k["observations"]:
            lines.append(f"- {obs}")
    else:
        lines.append("_Pending curation; run `scripts/enrich_wiki_game_pages.py` after editing GAME_KNOWLEDGE._")
    lines.append("")

    lines.append("## Mechanics Hypothesis")
    lines.append("")
    lines.append(k.get("mechanics") if k else "_Pending curation._")
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
        note = k.get("notes") if k else ""
        if note:
            lines.append(note)
        else:
            lines.append(
                "Replace internal access with frame-only detection (color clusters, "
                "diffs, persistent regions). See `[[../strategies/brittle/internal_method_call]]`."
            )
        lines.append("")
    else:
        if k and k.get("notes"):
            lines.append("## Notes")
            lines.append("")
            lines.append(k["notes"])
            lines.append("")

    # Lessons Learned + Related concepts (knowledge-graph cross-links)
    links = GAME_LINKS.get(title, {})
    if links:
        lines.append("## Lessons Learned")
        lines.append("")
        if strategy_type == "brittle":
            lines.append(
                "- Current solver is brittle — v1 works, v2 fails. See the linked lessons for "
                "the underlying pattern and refactor path."
            )
        elif strategy_type == "frame_only":
            lines.append(
                "- Frame-only solver generalizes across version hashes. See linked lessons "
                "for why frame-observation strategies are preferred."
            )
        for lesson in links.get("lessons", []):
            lines.append(f"- [[../lessons/{lesson}]]")
        for debug in links.get("debug", []):
            lines.append(f"- [[../debug/{debug}]]")
        lines.append("")

        lines.append("## Related Concepts")
        lines.append("")
        for concept in links.get("concepts", []):
            lines.append(f"- [[../concepts/{concept}]]")
        lines.append("")

        if links.get("peers"):
            lines.append("## Peer Games")
            lines.append("")
            for peer in links["peers"]:
                lines.append(f"- [[{peer}]]")
            lines.append("")

    lines.append("## Related")
    lines.append("")
    lines.append(f"- [[../game_types/{game_type}]]")
    if strategy_type == "brittle":
        lines.append("- [[../strategies/brittle/internal_method_call]]")
    elif strategy_type == "frame_only":
        lines.append(f"- [[../strategies/frame_only/{winning}]] (may need to be written)")
    lines.append("")

    lines.append("## Sources")
    lines.append("")
    lines.append(f"- `.wiki/raw/traces/{title.lower()}.jsonl`")
    lines.append(f"- `src/admorphiq/agent_ensemble.py` (`strat_{winning}` implementation)")
    lines.append("")

    return "\n".join(lines)


def main() -> None:
    GAMES_DIR.mkdir(parents=True, exist_ok=True)
    written: list[str] = []
    skipped: list[str] = []

    for trace_file in sorted(TRACES_DIR.glob("*.jsonl")):
        title = trace_file.stem.upper()
        if title in HAND_WRITTEN:
            skipped.append(title)
            continue
        entries = load_entries(title)
        if not entries:
            continue
        out_path = GAMES_DIR / f"{title}.md"
        out_path.write_text(render(title, entries))
        written.append(title)

    print(f"Enriched {len(written)} pages: {written}")
    print(f"Skipped (hand-written): {skipped}")


if __name__ == "__main__":
    main()
