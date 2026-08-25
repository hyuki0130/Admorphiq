"""R98 STEP (vi/vii): the MODEL stage for the flow family.

The finale of the R98 substage order. Instead of executing the hand-authored
oracle, the OFFLINE MODEL supplies the hypothesis and the harness gates it:

* ``--mode select`` — the model picks among the canonical instances (the oracle
  and the frozen mutants) from their NEUTRAL serialized form plus the live
  grounding evidence gathered this run.
* ``--mode fill`` — variant-first slot generation: ASK 1 chooses the objective
  variant with its completion quantifier and hazard policy; ASK 2 fills the
  response-table slots that the contract gates. Slots measured INERT are never
  asked — forcing a closed choice from absent evidence is how a false result gets
  manufactured.

Either way the VERIFIER gates the result: UNKNOWN or CONTRADICTED never executes,
so a wrong hypothesis costs zero actions. A PASSing hypothesis is compiled and
executed exactly like the oracle gate.

The model never sees an instance name, the words oracle/mutant, a game id, or any
notation: candidates are serialized with ``schema_flow.to_neutral_json`` under a
deterministic shuffle, and the evidence is rendered as PROSE from the measured
trajectory — the twice-measured lesson that every enforced rule must be stated in
the model-facing contract, and stated in words the model will not misparse.

Usage::

    python scripts/probe_r98_model_bench.py --runs 3 --out out.json
    python scripts/probe_r98_model_bench.py --mode fill --dry-run   # prompts only
    python scripts/probe_r98_model_bench.py --self-test             # stub LLMs, no server
"""

from __future__ import annotations

import argparse
import json
import os
import random
import re
import sys
from dataclasses import replace
from pathlib import Path
from typing import Any, Callable, Optional

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from admorphiq.hypothesis_select import schema_flow as F  # noqa: E402
from admorphiq.hypothesis_select.compiler import PlanStatus  # noqa: E402
from admorphiq.hypothesis_select.compiler_flow import (  # noqa: E402
    Select,
    compile_flow_hypothesis,
)
from admorphiq.hypothesis_select.grounding_flow import UNKNOWN, FlowGrounding  # noqa: E402
from admorphiq.hypothesis_select.schema import Verdict  # noqa: E402
from admorphiq.hypothesis_select.verifier_flow import (  # noqa: E402
    FlowEvidence,
    build_flow_evidence,
    neutralised,
    verify_with_evidence,
)

ACTION_CAP = 20
COMMIT_CAP = 3
SHUFFLE_SEED = 9808

# The slots the contract gates, with their closed vocabularies. own_flow and
# boundary are ABSENT on purpose: both were measured inert, so asking would force
# a guess the evidence cannot score.
GATED_SLOTS: dict[str, tuple[str, ...]] = {
    "piece_response_spawn": ("empty_flanks_only", "both_flanks", "none"),
    "piece_response_direction": ("preserved", "outward_turned"),
    "piece_response_propagation": ("cellwise_iterative", "edge_teleport"),
    "sink_response_predicate": ("same_sink_flanks", "contact"),
    "sink_response_miss": ("spread_like_piece", "stop", "absorb"),
    "hazard_response": ("terminate_fatal", "terminate_local", "pass_through"),
}

# Every closed choice is glossed. The value names are internal identifiers, and a
# model cannot be expected to map "same_sink_flanks" onto "entered the notch in
# the target's top edge" by guessing.
SLOT_GLOSS: dict[str, dict[str, str]] = {
    "piece_response_spawn": {
        "empty_flanks_only": "new cells are created only in the side cells that are still empty",
        "both_flanks": "both side cells are used, whether or not they are already filled",
        "none": "nothing is created; the flow simply ends at the piece",
    },
    "piece_response_direction": {
        "preserved": "each newly created cell travels in the SAME direction the flow "
                     "was already travelling",
        "outward_turned": "each newly created cell turns and travels SIDEWAYS, away "
                          "from the point of impact",
    },
    "piece_response_propagation": {
        "cellwise_iterative": "the split happens one cell at a time, repeating on "
                              "each following tick",
        "edge_teleport": "the flow reappears immediately at the far ends of the "
                         "piece, skipping the cells in between",
    },
    "sink_response_predicate": {
        "same_sink_flanks": "the target is satisfied only when the flow occupies the "
                            "notch in its top edge — the cell whose left and right "
                            "neighbours both belong to that same target",
        "contact": "the target is satisfied as soon as the flow is directly next to "
                   "any part of it",
    },
    "sink_response_miss": {
        "spread_like_piece": "the flow goes around the target, exactly as it would "
                             "go around a piece",
        "stop": "the flow ends there",
        "absorb": "the flow is swallowed and nothing continues",
    },
    "hazard_response": {
        "terminate_fatal": "the stream ends AND the whole attempt fails, even if "
                           "every target was satisfied",
        "terminate_local": "the stream ends, but the attempt can still succeed",
        "pass_through": "the flow continues straight through the barrier",
    },
}

OBJECTIVE_VARIANTS = ("cover_all_sinks", "any_sink_covered")
COMPLETIONS = ("all", "count")
HAZARD_POLICIES = ("fatal_on_contact", "neutral")

# How the barrier contact is worded in the observed evidence. "default" leaves the cause
# implicit, which is what every frozen verdict was measured under; "explicit" names the
# contact. Set by --evidence; never changed to move a verdict.
EVIDENCE_STYLE = "default"


# ── the rules the harness enforces, stated to the model in words ────────────

CONTRACT_PROSE = """How this world works, stated in full so nothing enforced is left unsaid:

- There are two phases. In the first you arrange a movable piece; one particular
  action commits the arrangement and starts the second phase, which runs by
  itself to a standstill and then decides the level.
- Flow starts at fixed source cells and travels one cell per tick in a fixed
  direction.
- FLOW CELLS PERSIST. A cell that has been reached stays filled for the rest of
  the phase, and is never entered again. So when a filled cell appears next to an
  older one, that is a NEW cell being created there — it is not the older cell
  having moved sideways. Read every description of the animation that way.
- When flow meets a cell it already fills, the front continues past it.
- When flow meets a piece, what happens is one of the choices you are asked
  about. If it splits, the new cells are created in the cells either side of the
  flow's CURRENT cell, and each of them travels in the ORIGINAL direction. A
  splitting flow can therefore look as though it is spreading sideways along the
  piece, because the split repeats: each newly created cell also has the piece
  directly ahead of it, so it splits again, one cell further out, on the next
  tick. Sideways APPEARANCE is not sideways TRAVEL.
- A target is satisfied only under the condition you are asked about; when that
  condition is not met, what the flow does instead is also one of your choices.
- Reaching a barrier ends that stream. Whether it ALSO fails the whole attempt is
  a separate choice you are asked about, and the two choices must agree: if a
  barrier can fail an attempt, say so in BOTH answers.
- A failed attempt clears the flow and the target marks and re-selects the piece,
  but the piece KEEPS the position you moved it to.
- Every action spends from a limited allowance, and only a limited number of
  commits are permitted; exhausting either loses the level."""


def _prose_evidence(evidence: FlowEvidence, grounding: FlowGrounding) -> list[str]:
    """Render the measured events as sentences. Every line is derived from the
    recovered trajectory or the grounded board — none of it is narration."""
    lines: list[str] = []
    board = evidence.board
    traj = evidence.trajectory
    if board is None or not traj:
        return ["No scripted consequence was observed."]

    deltas = grounding.piece_deltas()
    if deltas is not UNKNOWN:
        lines.append(
            f"Pressing a direction moved every cell of one wide region together by one "
            f"cell, and {len(deltas.value)} different directions each moved it."
        )
    ev = grounding.placement_evidence()
    if ev is not UNKNOWN and ev.value["blocked_contrasts"]:
        lines.append(
            "The same press that moved the region elsewhere produced no movement at one "
            "position, so something blocks it there."
        )
    lines.append(
        "One action returned a stack of pictures showing a consequence that ran by "
        "itself; every other action returned a single picture."
    )
    lines.append(
        f"In that stack a single cell appeared near the top and descended one row per "
        f"picture for {sum(1 for f in traj if len(f) == 1 and f[0][1] == traj[0][0][1])} "
        f"pictures."
    )

    piece_rows = {r for r, _ in board.piece_cells}
    for i, frontier in enumerate(traj):
        if len(frontier) == 2 and frontier[0][0] == frontier[1][0] and (
            frontier[1][1] - frontier[0][1] == 2
        ):
            same_row_as_piece = (frontier[0][0] + 1) in piece_rows
            lines.append(
                "When the descending cell reached the row just above the wide region, two "
                "new cells appeared in the same row, one on each side of it"
                + (", and both continued downward afterwards." if same_row_as_piece
                   else ".")
            )
            break
        if i > 6:
            break

    outward = [f for f in traj if len(f) == 2 and f[0][0] == f[1][0]]
    if len(outward) >= 2:
        lines.append(
            "On each following picture two more filled cells appeared on that same row, "
            "one further out on each side, until the outermost ones were past the ends of "
            "the wide region; from there the newly filled cells appeared one row lower at "
            "a time. Remember that filled cells persist, so these are new cells being "
            "created, not the earlier ones travelling sideways."
        )

    sink_cells = {c for s in board.sinks for c in s}
    for i in range(len(traj) - 1):
        for (r, c) in traj[i]:
            if (r + 1, c) in sink_cells and {(r, c - 1), (r, c + 1)} <= set(traj[i + 1]):
                lines.append(
                    "One stream came to rest directly above a cup-shaped region while being "
                    "in contact with it, and the region did NOT change appearance at that "
                    "moment; instead new cells appeared to its left and right. That region "
                    "only changed appearance later, on the picture after a filled cell "
                    "occupied the notch in its top edge — the cell whose left and right "
                    "neighbours both belong to that same region."
                )
                break
        else:
            continue
        break

    all_covered = evidence.n_sinks > 0
    if board.hazard_cells and all_covered and not evidence.advanced:
        # the discriminating pair: full coverage AND a failed attempt, with the only
        # other event being the barrier contact
        # The default wording states the POSITION and the STOP and leaves the cause
        # implicit: a reader has to infer that "the row just above the bottom edge" means
        # the stream was in contact with the edge. Measured — gpt-oss makes that inference
        # and answers terminate_fatal 3/3, while gemma4 and qwen3.8 read the same sentence
        # as a harmless stop and answer terminate_local. `explicit` names the contact the
        # grounding already knows about (it is why hazard_cells is non-empty), and is a
        # SEPARATE experiment: the frozen verdicts were taken under the default.
        if EVIDENCE_STYLE == "explicit":
            lines.append(
                f"All {evidence.n_sinks} of the cup-shaped regions ended in the distinct "
                "appearance that marks a satisfied target, and the level still did NOT "
                "advance. The only other thing that happened in the whole animation is "
                "that a stream came into contact with the board's bottom edge — it "
                "reached the row directly above it and stopped there against it."
            )
        else:
            lines.append(
                f"All {evidence.n_sinks} of the cup-shaped regions ended in the distinct "
                "appearance that marks a satisfied target, and the level still did NOT "
                "advance. The only other thing that happened in the whole animation is "
                "that a stream reached the row just above the bottom edge and stopped "
                "there."
            )
    else:
        lines.append(
            f"{evidence.n_sinks} cup-shaped regions ended in a distinct appearance"
            + (", and the level did not advance." if not evidence.advanced
               else ", and the level advanced.")
        )
        if board.hazard_cells:
            lines.append(
                "At least one stream reached the row just above the bottom edge and "
                "stopped there without changing anything."
            )
    return lines


# ── ASK 1 (select): pick a serialized candidate ─────────────────────────────


def build_select_ask(
    evidence: FlowEvidence, grounding: FlowGrounding
) -> tuple[list[dict[str, str]], dict[str, str]]:
    # Candidates whose only deviation lies in a slot the evidence cannot separate
    # serialize IDENTICALLY to the truth once neutralised. Offering them would ask
    # the model to choose between indistinguishable options and bake a random
    # failure into the harness, so they are excluded here. They still do their job
    # in the mutant table, where they measure the VERIFIER's discriminating power.
    truth_json = json.dumps(
        F.to_neutral_json(neutralised(F.sp80_oracle_instance())), sort_keys=True
    )
    candidates = [("__truth__", F.sp80_oracle_instance())] + [
        (m.name, m.instance)
        for m in F.MUTANTS_FLOW
        if json.dumps(F.to_neutral_json(neutralised(m.instance)), sort_keys=True) != truth_json
    ]
    rng = random.Random(SHUFFLE_SEED)
    rng.shuffle(candidates)
    mapping = {f"I{i + 1}": name for i, (name, _) in enumerate(candidates)}
    blocks = [
        f"{f'I{i + 1}'}:\n"
        + json.dumps(F.to_neutral_json(neutralised(inst)), indent=1, sort_keys=True)
        for i, (_, inst) in enumerate(candidates)
    ]

    system = (
        "You are given a description of how an interactive world works, a list of what "
        "was actually observed in it, and several candidate models of that world. "
        "Exactly one candidate is consistent with every observation.\n\n"
        "Answer with a single line of the form ANSWER: <id>. Do not explain."
    )
    user = (
        CONTRACT_PROSE
        + "\n\nWhat was observed:\n"
        + "\n".join(f"- {line}" for line in _prose_evidence(evidence, grounding))
        + "\n\nCandidate models:\n\n"
        + "\n\n".join(blocks)
        + "\n\nWhich candidate is consistent with every observation?"
    )
    return [{"role": "system", "content": system}, {"role": "user", "content": user}], mapping


# ── ASK 1/2 (fill): variant, then the gated slots ───────────────────────────


def build_variant_ask(
    evidence: FlowEvidence, grounding: FlowGrounding, fused_hazard: bool = False
) -> list[dict[str, str]]:
    """The objective ask. ``fused_hazard`` is the SEPARATE EXPERIMENT the round owes, not
    a fix: our encoding asks whether a barrier is fatal TWICE — as `hazard_policy` here
    and as `hazard_response` in the slot ask — and gemma4 answered the pair
    self-contradictorily while gpt-oss resolved the same encoding 3/3. Asking once
    measures whether the split is what it stumbles on. It is off by default because the
    contract is frozen on the split form, and because re-cutting the representation until
    a weaker model passes is tuning, not measurement."""
    system = (
        "Answer with a single JSON object and nothing else. Use exactly the keys "
        "asked for, and for each key choose exactly one of the listed values."
    )
    user = (
        CONTRACT_PROSE
        + "\n\nWhat was observed:\n"
        + "\n".join(f"- {line}" for line in _prose_evidence(evidence, grounding))
        + "\n\nDecide what the level requires. Keys and their allowed values:\n"
        + '  "objective":\n'
          "      cover_all_sinks — the level is won by satisfying targets\n"
          "      any_sink_covered — one satisfied target is enough\n"
          '  "completion":\n'
          "      all — every target must be satisfied\n"
          "      count — a specific number of them must be\n"
        + ("" if fused_hazard else
           '  "hazard_policy":\n'
           "      fatal_on_contact — touching a barrier fails the attempt even when "
           "every target was satisfied\n"
           "      neutral — touching a barrier does not by itself fail the attempt\n")
        + '\nIf you choose "count" for completion, add "completion_count" as a whole '
          "number.\n"
        + ("Whether touching a barrier fails the attempt is asked ONCE, in the other "
           "question.\n" if fused_hazard else
           "Your hazard_policy must agree with the hazard_response you give in the "
           "other question: fatal_on_contact goes with terminate_fatal, and neutral "
           "goes with terminate_local.\n")
        + "Answer with the JSON object only."
    )
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def build_slot_ask(
    evidence: FlowEvidence, grounding: FlowGrounding
) -> list[dict[str, str]]:
    system = (
        "Answer with a single JSON object and nothing else. Use exactly the keys "
        "asked for, and for each key choose exactly one of the listed values."
    )
    listing = "\n".join(
        f'  "{k}":\n'
        + "\n".join(f"      {value} — {SLOT_GLOSS[k][value]}" for value in values)
        for k, values in GATED_SLOTS.items()
    )
    user = (
        CONTRACT_PROSE
        + "\n\nWhat was observed:\n"
        + "\n".join(f"- {line}" for line in _prose_evidence(evidence, grounding))
        + "\n\nDecide how the flow behaves. Keys and their allowed values:\n"
        + listing
        + "\n\nAnswer with the JSON object only."
    )
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


# ── parsing ─────────────────────────────────────────────────────────────────


def parse_select(text: str, valid: set[str]) -> Optional[str]:
    match = re.search(r"ANSWER:\s*(I\d+)", text or "", re.IGNORECASE)
    if match and match.group(1).upper() in valid:
        return match.group(1).upper()
    for token in re.findall(r"\bI\d+\b", text or ""):
        if token.upper() in valid:
            return token.upper()
    return None


def parse_json_object(text: str) -> Optional[dict[str, Any]]:
    match = re.search(r"\{.*\}", text or "", re.DOTALL)
    if not match:
        return None
    try:
        value = json.loads(match.group(0))
    except json.JSONDecodeError:
        return None
    return value if isinstance(value, dict) else None


def instance_from_answers(variant: dict[str, Any], slots: dict[str, Any],
                          fused_hazard: bool = False) -> Optional[F.FlowHypothesis]:
    """Assemble a hypothesis from the model's two answers, or None if a value is
    outside its closed vocabulary.

    With ``fused_hazard`` the objective ask never carried `hazard_policy`, so it is read
    off the slot answer instead — the two were required to agree anyway."""
    for key, allowed in GATED_SLOTS.items():
        if slots.get(key) not in allowed:
            return None
    if variant.get("objective") not in OBJECTIVE_VARIANTS:
        return None

    roles = ("sink_0", "sink_1")
    if variant["objective"] == "any_sink_covered":
        objective: F.FlowObjective = F.AnySinkCovered(sink_roles=roles)
    else:
        if variant.get("completion") not in COMPLETIONS:
            return None
        policy = variant.get("hazard_policy")
        if policy is None and fused_hazard:
            # asked once: the response IS the policy
            policy = ("fatal_on_contact" if slots.get("hazard_response") == "terminate_fatal"
                      else "neutral")
        if policy not in HAZARD_POLICIES:
            return None
        count = variant.get("completion_count")
        objective = F.CoverAllSinks(
            sink_roles=roles,
            completion=variant["completion"],
            hazard_policy=policy,
            completion_count=int(count) if variant["completion"] == "count" and count else None,
        )

    base = F.sp80_oracle_instance().transition_model
    table = F.ResponseTable(
        piece_by_class=(
            (
                "straight",
                F.PieceResponse(
                    spawn=slots["piece_response_spawn"],
                    direction=slots["piece_response_direction"],
                    propagation=slots["piece_response_propagation"],
                ),
            ),
        ),
        sink=F.SinkResponse(
            predicate=slots["sink_response_predicate"], miss=slots["sink_response_miss"]
        ),
        hazard=slots["hazard_response"],
    )
    return F.FlowHypothesis(
        objective=objective,
        transition_model=replace(base, responses=table),
        phases=F.sp80_oracle_instance().phases,
    )


# ── scoring with the contract's equivalence classes ─────────────────────────


def equivalent_to_truth(instance: F.FlowHypothesis) -> bool:
    """Does the instance name the same world as the truth, allowing the
    equivalence classes the contract records? A data-indistinguishable answer is
    CORRECT, not a near miss."""
    truth = neutralised(F.sp80_oracle_instance())
    got = neutralised(instance)
    if got == truth:
        return True
    if not isinstance(got.transition_model, F.PlaceThenPropagate):
        return False
    classes = dict(F.EQUIVALENCE_CLASSES)
    (_, gp), = got.transition_model.responses.piece_by_class
    (_, tp), = truth.transition_model.responses.piece_by_class
    members = classes.get("PieceResponse.spawn", frozenset())
    if gp.spawn != tp.spawn and {gp.spawn, tp.spawn} <= members:
        gp = replace(gp, spawn=tp.spawn)
        table = replace(
            got.transition_model.responses, piece_by_class=(("straight", gp),)
        )
        got = replace(got, transition_model=replace(got.transition_model, responses=table))
    return got == truth


# ── the live run ────────────────────────────────────────────────────────────


def _open_arcade():
    """Open the offline arcade, honouring ``ARC_ENVIRONMENTS_DIR``.

    The repo convention: the WRAPPER exports the directory and the SCRIPT passes
    it to the constructor. arc_agi's own fallback variable is spelled differently,
    so relying on the environment alone silently yields an arcade with no games —
    which is exactly how a GPU run once reached a healthy model server and then
    failed on the first line that needed a board.
    """
    from arc_agi import Arcade, OperationMode

    envs_dir = os.environ.get("ARC_ENVIRONMENTS_DIR")
    return (
        Arcade(operation_mode=OperationMode.OFFLINE, environments_dir=envs_dir)
        if envs_dir
        else Arcade(operation_mode=OperationMode.OFFLINE)
    )


def _run_discovery():
    from arcengine import GameAction

    actions = {
        1: GameAction.ACTION1,
        2: GameAction.ACTION2,
        3: GameAction.ACTION3,
        4: GameAction.ACTION4,
        5: GameAction.ACTION5,
    }
    arcade = _open_arcade()
    envs = list(arcade.get_environments())
    gid = next((e.game_id for e in envs if e.game_id.startswith("sp80")), None)
    if gid is None:
        raise SystemExit(
            "the arcade exposes no sp80 environment "
            f"({len(envs)} environment(s) visible; ARC_ENVIRONMENTS_DIR="
            f"{os.environ.get('ARC_ENVIRONMENTS_DIR')!r}). Point it at the directory "
            "that holds the per-game environment folders."
        )
    env = arcade.make(gid)
    state = {"obs": env.step(GameAction.RESET), "actions": 0, "commits": 0}
    g = FlowGrounding()
    g.observe(0, None, state["obs"].frame)

    def act(a: int) -> None:
        state["obs"] = env.step(actions[a])
        state["actions"] += 1
        if len(state["obs"].frame) > 1:
            state["commits"] += 1
        g.observe(a, None, state["obs"].frame)

    def run_step(step) -> None:
        """A plan step is a simple action id, or a Select click on a piece."""
        if not isinstance(step, Select):
            act(step)
            return
        scale = g.scale()
        px = 4 if scale is UNKNOWN else scale.value
        row, col = step.cell
        xy = (col * px + px // 2, row * px + px // 2)
        state["obs"] = env.step(GameAction.ACTION6, data={"x": xy[0], "y": xy[1]})
        state["actions"] += 1
        g.observe(6, xy, state["obs"].frame)

    state["run_step"] = run_step

    for a in (1, 1, 2, 3, 4):
        act(a)
    hint = g.flow_origin_hint()
    if hint is not UNKNOWN and g.tracked_region() is not UNKNOWN:
        target = max(c for _, c in hint.value)
        while max(c for _, c in g.tracked_region().value) < target:
            act(4)
    act(5)
    return g, state, act


def _board_fingerprint(g) -> dict[str, Any]:
    """What the grounding was looking at when the verdict was taken.

    A CONTRADICTED verdict has two possible authors: the model named the wrong world,
    or the grounding built the wrong board and the verifier judged a correct answer
    against it. Measured 2026-08-25, gpt-oss returned all six response slots exactly
    right and was still contradicted; the variant field is what proved the model was
    at fault, and nothing in the record could have told the other story apart from it.
    This is small, so it can ride on every run."""
    board = g.board()
    if board is UNKNOWN:
        return {"board": "UNKNOWN"}
    b = board.value
    return {
        "size": b.size,
        "direction": list(b.direction),
        "pieces": [len(p) for p in b.pieces],
        "sinks": [sorted(s)[0] for s in b.sinks],
        "hazards": sorted(b.hazard_cells),
        "absorbers": len(b.absorber_cells),
        "falling_sources": [list(s) for s in b.falling_sources],
    }


def _gate_and_execute(instance, g, state, act, record: dict[str, Any]) -> None:
    evidence = build_flow_evidence(g, state["obs"].levels_completed >= 1)
    verdict = verify_with_evidence(instance, evidence)
    record["verdict"] = verdict.verdict.value
    record["verdict_reason"] = verdict.reason
    record["board"] = _board_fingerprint(g)
    if verdict.verdict is not Verdict.PASS:
        record["executed_actions"] = 0
        record["outcome"] = "blocked_by_verifier"
        return

    plan = compile_flow_hypothesis(instance, g)
    record["plan_status"] = plan.status.value
    record["plan_offsets"] = [list(o) for o in plan.offsets]
    executed = 0
    if plan.status is PlanStatus.SOLVABLE:
        for step in plan.steps:
            if state["actions"] >= ACTION_CAP or state["commits"] >= COMMIT_CAP:
                break
            state["run_step"](step)
            executed += 1
            if state["obs"].levels_completed >= 1:
                break
    record["executed_actions"] = executed
    record["cleared"] = state["obs"].levels_completed >= 1
    record["total_actions"] = state["actions"]
    record["commits"] = state["commits"]
    record["outcome"] = "cleared" if record["cleared"] else "not_cleared"


def run_select_once(index: int, llm: Callable[[list[dict[str, str]]], str]) -> dict[str, Any]:
    g, state, act = _run_discovery()
    evidence = build_flow_evidence(g, state["obs"].levels_completed >= 1)
    messages, mapping = build_select_ask(evidence, g)
    reply = llm(messages)
    pick = parse_select(reply, set(mapping))
    record: dict[str, Any] = {"run": index, "mode": "select", "pick": pick,
                              "candidates": len(mapping),
                              "picked_truth": mapping.get(pick or "") == "__truth__"}
    if pick is None:
        record["outcome"] = "unparsable"
        record["executed_actions"] = 0
        # Keep what could not be parsed. gpt-oss came back unparsable twice on select and
        # the record held nothing but the word "unparsable", so the failure could not be
        # told from a refusal, a truncation, or an answer in the wrong shape.
        record["raw_reply"] = (reply or "")[-1200:]
        record["reply_chars"] = len(reply or "")
        return record
    name = mapping[pick]
    instance = (
        F.sp80_oracle_instance() if name == "__truth__"
        else next(m.instance for m in F.MUTANTS_FLOW if m.name == name)
    )
    _gate_and_execute(instance, g, state, act, record)
    return record


def run_fill_once(index: int, llm: Callable[[list[dict[str, str]]], str],
                  fused_hazard: bool = False) -> dict[str, Any]:
    g, state, act = _run_discovery()
    evidence = build_flow_evidence(g, state["obs"].levels_completed >= 1)
    variant_reply = llm(build_variant_ask(evidence, g, fused_hazard))
    slot_reply = llm(build_slot_ask(evidence, g))
    variant = parse_json_object(variant_reply)
    slots = parse_json_object(slot_reply)
    record: dict[str, Any] = {"run": index, "mode": "fill", "hazard": "fused" if fused_hazard
                              else "split", "variant": variant, "slots": slots}
    if os.environ.get("R98_EXPLAIN") == "1":
        # A THIRD ask, after both scored ones and never read by the scorer. The two scored
        # prompts demand "a single JSON object and nothing else", which is what makes the
        # answer parseable and also what leaves nothing to diagnose: gemma4's reply is 286
        # characters of bare JSON, identical across nine runs. This asks the model to explain
        # the answer it has already given, so the question "did it consider the fatality
        # inference or reject it" has a surface to be read from.
        #
        # It cannot move a verdict: it runs after `slots` is parsed, its reply is stored and
        # nothing else, and the scored asks are byte-identical with it on or off. That is the
        # distinction the round's prohibition draws — do not tune the question until a weaker
        # model passes; asking a different question that scores nothing is not that.
        # A CONTINUATION of the scored exchange, not a fresh one. The first version sent a
        # bare system+user pair with no evidence, and gemma4 answered in incident-management
        # language about "a critical system failure that could not be contained" — no
        # droplets, no targets, no barrier. Asked cold about a choice whose basis it cannot
        # see, a model confabulates, and the reply says nothing about the scored reasoning.
        # Replaying the same messages plus its own answer is what makes the follow-up an
        # explanation rather than a fresh invention.
        why = llm(build_slot_ask(evidence, g) + [
            {"role": "assistant", "content": slot_reply or ""},
            {"role": "user", "content":
             "In two or three sentences: what in the animation above led you to that "
             "`hazard_response`, and what would have made you answer differently? Do not "
             "restate the answer."},
        ])
        record["explanation"] = (why or "")[-2000:]
    if os.environ.get("R98_KEEP_REPLIES") == "1":
        # DIAGNOSIS, not scoring. The fill stage is a one-slot exam and two models fail it
        # deterministically on hazard fatality, but a slot value cannot say whether the model
        # never considered the inference or considered and rejected it. The evidence contains
        # a complete syllogism — every target satisfied, the level did not advance, the only
        # other event was the barrier contact — so what the reply SAYS about that contact is
        # the difference between a reasoning limit and an evidence one. Off by default: the
        # frozen verdicts were measured without it and the replies are large.
        record["raw_slot_reply"] = (slot_reply or "")[-4000:]
    if variant is None or slots is None:
        record["outcome"] = "unparsable"
        record["executed_actions"] = 0
        record["raw_variant_reply"] = (variant_reply or "")[-1200:]
        record["raw_slot_reply"] = (slot_reply or "")[-1200:]
        return record
    instance = instance_from_answers(variant, slots, fused_hazard)
    if instance is None:
        record["outcome"] = "out_of_vocabulary"
        record["executed_actions"] = 0
        return record
    record["equivalent_to_truth"] = equivalent_to_truth(instance)
    _gate_and_execute(instance, g, state, act, record)
    return record


def verdict_of(runs: list[dict[str, Any]]) -> str:
    """Per-model success = at least 2 of 3 runs cleared (the frozen contract)."""
    cleared = sum(1 for r in runs if r.get("outcome") == "cleared")
    return f"{cleared}/{len(runs)} " + ("PASS" if cleared >= 2 else "FAIL")


# ── stub LLMs for the harness self-test ─────────────────────────────────────


def _candidate_blocks(user_text: str) -> list[tuple[str, dict[str, Any]]]:
    """Recover the ``I<k> -> serialized candidate`` blocks from an assembled ask.

    Used by the self-test stubs to answer as a model that reasoned correctly would.
    Parsing the prompt back is deliberate: it proves the ask actually carries the
    candidates it claims to, rather than trusting the builder."""
    out: list[tuple[str, dict[str, Any]]] = []
    for match in re.finditer(r"^(I\d+):\n(\{.*?^\})", user_text, re.DOTALL | re.MULTILINE):
        try:
            out.append((match.group(1), json.loads(match.group(2))))
        except json.JSONDecodeError:
            continue
    return out


def _truthful_stub(mode: str) -> Callable[[list[dict[str, str]]], str]:
    truth = F.sp80_oracle_instance()
    (_, piece), = truth.transition_model.responses.piece_by_class
    calls = {"n": 0}

    def llm(messages: list[dict[str, str]]) -> str:
        if mode == "select":
            wanted = F.to_neutral_json(neutralised(truth))
            for ident, blob in _candidate_blocks(messages[1]["content"]):
                if blob == wanted:
                    return f"ANSWER: {ident}"
            return "ANSWER: I1"
        calls["n"] += 1
        if calls["n"] % 2 == 1:
            return json.dumps({"objective": "cover_all_sinks", "completion": "all",
                               "hazard_policy": "fatal_on_contact"})
        return json.dumps({
            "piece_response_spawn": piece.spawn,
            "piece_response_direction": piece.direction,
            "piece_response_propagation": piece.propagation,
            "sink_response_predicate": truth.transition_model.responses.sink.predicate,
            "sink_response_miss": truth.transition_model.responses.sink.miss,
            "hazard_response": truth.transition_model.responses.hazard,
        })

    return llm


def _wrong_stub(mode: str) -> Callable[[list[dict[str, str]]], str]:
    calls = {"n": 0}

    def llm(messages: list[dict[str, str]]) -> str:
        if mode == "select":
            return "ANSWER: I1" if "I1:" in messages[1]["content"] else "ANSWER: I2"
        calls["n"] += 1
        if calls["n"] % 2 == 1:
            return json.dumps({"objective": "cover_all_sinks", "completion": "all",
                               "hazard_policy": "neutral"})
        return json.dumps({
            "piece_response_spawn": "none",
            "piece_response_direction": "outward_turned",
            "piece_response_propagation": "edge_teleport",
            "sink_response_predicate": "contact",
            "sink_response_miss": "stop",
            "hazard_response": "pass_through",
        })

    return llm


def _equivalent_stub() -> Callable[[list[dict[str, str]]], str]:
    """Answers with the data-indistinguishable member of the equivalence class."""
    truth = F.sp80_oracle_instance()
    calls = {"n": 0}

    def llm(messages: list[dict[str, str]]) -> str:
        calls["n"] += 1
        if calls["n"] % 2 == 1:
            return json.dumps({"objective": "cover_all_sinks", "completion": "all",
                               "hazard_policy": "fatal_on_contact"})
        return json.dumps({
            "piece_response_spawn": "both_flanks",
            "piece_response_direction": "preserved",
            "piece_response_propagation": "cellwise_iterative",
            "sink_response_predicate": truth.transition_model.responses.sink.predicate,
            "sink_response_miss": truth.transition_model.responses.sink.miss,
            "hazard_response": truth.transition_model.responses.hazard,
        })

    return llm


def leak_report(messages: list[dict[str, str]]) -> list[str]:
    """Anything in the prompt that would let a model score without reasoning."""
    blob = " ".join(m["content"] for m in messages).lower()
    banned = ["sp80", "oracle", "mutant", "harness_measured", "model_selected",
              "compiler_derived", "ownership", "correct answer", "ground truth"]
    return [b for b in banned if b in blob]


def self_test() -> int:
    print("harness self-test (deterministic stubs, no server)\n")
    ok = True
    for mode, stub, expect in (
        ("select", _truthful_stub("select"), "cleared"),
        ("select", _wrong_stub("select"), "blocked_by_verifier"),
        ("fill", _truthful_stub("fill"), "cleared"),
        ("fill", _wrong_stub("fill"), "blocked_by_verifier"),
    ):
        run = (run_select_once if mode == "select" else run_fill_once)(0, stub)
        good = run.get("outcome") == expect
        if expect == "blocked_by_verifier":
            good = good and run.get("executed_actions") == 0
        # Every record must carry the board the verdict was taken on, populated. A
        # CONTRADICTED verdict has two possible authors and the artefact has to be able
        # to tell them apart; an empty or missing fingerprint silently gives that up.
        board = run.get("board") or {}
        good = good and bool(board.get("size")) and bool(board.get("hazards"))
        ok &= good
        print(f"  {mode:<7} {'truthful' if expect == 'cleared' else 'wrong':<9} "
              f"-> outcome={run.get('outcome')} executed={run.get('executed_actions')} "
              f"{'PASS' if good else 'FAIL'}")

    # The FUSED variant, driven by a stub that answers as the fused ask asks: no
    # hazard_policy, because the fused objective ask never offers one. Without this the
    # self-test only ever exercises the split default, and the experiment the round owes
    # would first be run on a GPU with nothing having checked its wiring.
    _inner = _truthful_stub("fill")     # ONE stub: it answers the two asks in order,
                                       # so rebuilding it per call replays the first

    def _fused_stub(messages: list[dict[str, str]]) -> str:
        reply = _inner(messages)
        answer = parse_json_object(reply)
        if not isinstance(answer, dict) or "hazard_policy" not in answer:
            return reply          # the slot ask: pass it through untouched
        answer.pop("hazard_policy")
        return json.dumps(answer)

    fused = run_fill_once(0, _fused_stub, fused_hazard=True)
    good = (fused.get("outcome") == "cleared" and fused.get("hazard") == "fused")
    ok &= good
    print(f"  fill    fused     -> hazard={fused.get('hazard')} "
          f"outcome={fused.get('outcome')} {'PASS' if good else 'FAIL'}")

    equiv = run_fill_once(0, _equivalent_stub())
    good = equiv.get("equivalent_to_truth") is True and equiv.get("outcome") == "cleared"
    ok &= good
    print(f"  fill    equivalent -> equivalent_to_truth={equiv.get('equivalent_to_truth')} "
          f"outcome={equiv.get('outcome')} {'PASS' if good else 'FAIL'}")

    # The explanation ask, checked WITHOUT a GPU. Two properties matter and neither is
    # visible from the reply alone: it must arrive as a CONTINUATION carrying the evidence and
    # the model's own answer, and it must not exist at all when the flag is off. Both cost a
    # verdict if wrong — the first version asked cold and got a confabulation about "a
    # critical system failure", describing nothing that happened.
    seen: list = []

    def _recording_stub(messages):
        seen.append(messages)
        return _truthful_stub("fill")(messages) if len(seen) <= 2 else "because."

    os.environ["R98_EXPLAIN"] = "1"
    explained = run_fill_once(0, _recording_stub)
    os.environ.pop("R98_EXPLAIN")
    follow = seen[-1] if len(seen) >= 3 else []
    roles = [m["role"] for m in follow]
    carries_evidence = any("animation" in m["content"] for m in follow)
    good = (explained.get("explanation") == "because."
            and "assistant" in roles and carries_evidence)
    ok &= good
    print(f"  fill    explain   -> {len(follow)} message(s), roles={roles[-2:]}, "
          f"evidence carried={carries_evidence} {'PASS' if good else 'FAIL'}")

    quiet = run_fill_once(0, _truthful_stub("fill"))
    good = "explanation" not in quiet
    ok &= good
    print(f"  fill    explain-off -> key absent={good} {'PASS' if good else 'FAIL'}")

    g, state, _ = _run_discovery()
    evidence = build_flow_evidence(g, False)
    leaks = (leak_report(build_select_ask(evidence, g)[0])
             + leak_report(build_variant_ask(evidence, g))
             + leak_report(build_slot_ask(evidence, g)))
    ok &= not leaks
    print(f"  leak guard -> {'clean' if not leaks else 'LEAKS ' + str(leaks)} "
          f"{'PASS' if not leaks else 'FAIL'}")

    print(f"\n[self-test] {'PASS' if ok else 'FAIL'} — the harness "
          f"{'rewards a correct hypothesis, blocks a wrong one at zero cost, and accepts an equivalence-class answer'
             if ok else 'does NOT behave as the contract requires'}")
    return 0 if ok else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=["select", "fill"], default="select")
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--out")
    parser.add_argument("--dry-run", action="store_true",
                        help="print the assembled asks (no LLM server needed)")
    parser.add_argument("--evidence", choices=["default", "explicit"], default="default",
                        help="how the barrier contact is worded: leave the cause implicit "
                             "(the frozen wording) or name the contact")
    parser.add_argument("--hazard", choices=["split", "fused"], default="split",
                        help="ask whether a barrier is fatal twice (the frozen contract) "
                             "or once (the separate experiment the round owes)")
    parser.add_argument("--self-test", action="store_true",
                        help="drive the harness with deterministic stubs")
    args = parser.parse_args()

    global EVIDENCE_STYLE
    EVIDENCE_STYLE = args.evidence

    if args.self_test:
        return self_test()

    if args.dry_run:
        g, state, _ = _run_discovery()
        evidence = build_flow_evidence(g, state["obs"].levels_completed >= 1)
        if args.mode == "select":
            messages, mapping = build_select_ask(evidence, g)
            print("=== ID MAPPING (never shown to the model) ===")
            print(json.dumps(mapping, indent=2))
        else:
            messages = build_variant_ask(evidence, g, args.hazard == "fused")
            print("=== ASK 2 (SLOTS) ===\n"
                  + build_slot_ask(evidence, g)[1]["content"] + "\n")
        print("=== SYSTEM ===\n" + messages[0]["content"])
        print("\n=== USER ===\n" + messages[1]["content"])
        leaks = leak_report(messages)
        print(f"\n[leak guard] {'clean' if not leaks else 'LEAKS ' + str(leaks)}")
        return 0

    from admorphiq.harness.registry import openai_compat_llm

    llm = openai_compat_llm(
        num_predict=int(os.environ.get("HARNESS_PATCH_NUM_PREDICT", "2048")),
        timeout=float(os.environ.get("HARNESS_PATCH_TIMEOUT", "900")),
    )
    fused = args.hazard == "fused"
    runs = ([run_select_once(i, llm) for i in range(args.runs)]
            if args.mode == "select"
            else [run_fill_once(i, llm, fused) for i in range(args.runs)])
    report = {
        "mode": args.mode,
        "hazard": args.hazard,
        "model": os.environ.get("HARNESS_LLM_MODEL", ""),
        "runs": runs,
        "verdict": verdict_of(runs),
    }
    text = json.dumps(report, indent=2)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
