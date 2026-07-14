"""Turn-packet builder for the code-REPL agent (R55 module 3).

Assembles the per-turn prompt payload in the GAME / LAST_ACTION / CHANGE / SCENE
/ RECENT_EVENTS / MEMORY YAML shape from the Codex design doc — optimized around
CHANGES rather than dumping the full 4096-cell grid (which stays available to the
sandbox). Includes the three-tier history (recent full transitions / compact
event ledger / persistent environment memory) and a falsifiable-hypothesis memory
whose confidence is DOWNGRADED on contradiction, so a plausible early story can
be rejected instead of entrenched.

Deterministic: `yaml.safe_dump(sort_keys=False)` over an ordered dict with
integer-rounded centroids gives snapshot-stable output, and a token-budget cap
trims the largest sections first. No model calls.
"""

from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass, field
from typing import Any

import yaml

from admorphiq.repl_agent.segmentation import Scene, SceneObject
from admorphiq.tools.base import base_hash, diff_bbox, diff_cells

_CONFIRM_AT = 0.9
_REJECT_AT = 0.2
_SUPPORT_STEP = 0.1
_CONTRADICT_STEP = 0.25


def estimate_tokens(text: str) -> int:
    """Rough token count (~4 chars/token) — no tokenizer needed offline."""
    return math.ceil(len(text) / 4)


@dataclass
class Hypothesis:
    """A falsifiable statement about the environment with evidence tracking.

    Contradiction lowers confidence and can flip ``status`` to ``rejected`` —
    the mechanism that prevents a plausible early theory from becoming permanent
    fact (the "contradiction recovery" kill-test).
    """

    hypothesis: str
    prediction: str = ""
    confidence: float = 0.5
    supporting_events: list[str] = field(default_factory=list)
    contradicting_events: list[str] = field(default_factory=list)
    status: str = "active"  # active | rejected | confirmed

    def support(self, event: str) -> None:
        self.supporting_events.append(event)
        self.confidence = min(1.0, self.confidence + _SUPPORT_STEP)
        if self.confidence >= _CONFIRM_AT and not self.contradicting_events:
            self.status = "confirmed"

    def contradict(self, event: str) -> None:
        self.contradicting_events.append(event)
        self.confidence = max(0.0, self.confidence - _CONTRADICT_STEP)
        # Any contradiction downgrades a previously-confirmed theory back to
        # active; sustained contradiction rejects it.
        if self.status == "confirmed":
            self.status = "active"
        if self.confidence <= _REJECT_AT or len(self.contradicting_events) >= 2:
            self.status = "rejected"

    def to_dict(self) -> dict[str, Any]:
        return {
            "hypothesis": self.hypothesis,
            "prediction": self.prediction,
            "confidence": round(self.confidence, 2),
            "supporting_events": list(self.supporting_events[-4:]),
            "contradicting_events": list(self.contradicting_events[-4:]),
            "status": self.status,
        }


@dataclass
class EnvironmentMemory:
    """Persistent structured theory carried across levels (1-2K tokens)."""

    goal_hypotheses: list[Hypothesis] = field(default_factory=list)
    action_semantics: dict[str, str] = field(default_factory=dict)
    invariants: list[str] = field(default_factory=list)
    dead_interventions: list[str] = field(default_factory=list)
    learned_options: list[str] = field(default_factory=list)
    unresolved_questions: list[str] = field(default_factory=list)
    current_plan: list[str] = field(default_factory=list)

    def add_hypothesis(self, h: Hypothesis) -> None:
        self.goal_hypotheses.append(h)

    def record_prediction(self, text: str, prediction: str, correct: bool,
                          cap: int = 32) -> Hypothesis:
        """Score a per-turn prediction, evolving a deduped falsifiable hypothesis.

        Finds the existing hypothesis with the same (text, prediction) or creates
        one, then ``support``\\ s it on a correct prediction / ``contradict``\\ s
        on a wrong one — so confidence tracks the model's real predictive
        accuracy instead of a static note. Bounded: drops the oldest rejected
        (else oldest) hypothesis past ``cap``.
        """
        h = next((x for x in self.goal_hypotheses
                  if x.hypothesis == text and x.prediction == prediction), None)
        if h is None:
            h = Hypothesis(hypothesis=text, prediction=prediction, confidence=0.5)
            self.goal_hypotheses.append(h)
        (h.support if correct else h.contradict)(
            "observed match" if correct else "observed mismatch")
        if len(self.goal_hypotheses) > cap:
            rejected = [i for i, x in enumerate(self.goal_hypotheses)
                        if x.status == "rejected"]
            self.goal_hypotheses.pop(rejected[0] if rejected else 0)
        return h

    def active_hypotheses(self) -> list[Hypothesis]:
        return [h for h in self.goal_hypotheses if h.status != "rejected"]

    def to_dict(self, max_hyps: int = 6) -> dict[str, Any]:
        # Surface the most confident non-rejected hypotheses first.
        hyps = sorted(self.active_hypotheses(),
                      key=lambda h: h.confidence, reverse=True)[:max_hyps]
        return {
            "goal_hypotheses": [h.to_dict() for h in hyps],
            "action_semantics": dict(self.action_semantics),
            "invariants": list(self.invariants),
            "dead_interventions": list(self.dead_interventions),
            "learned_options": list(self.learned_options),
            "unresolved_questions": list(self.unresolved_questions),
            "current_plan": list(self.current_plan),
        }


class HistoryTiers:
    """Three-tier history: recent full transitions + compact event ledger.

    The recent window holds the last few detailed transitions (for local
    reasoning); the ledger holds compact causal one-liners for the current level.
    Persistent memory is the separate :class:`EnvironmentMemory`.
    """

    def __init__(self, recent: int = 8, ledger: int = 40) -> None:
        self.recent: deque[dict[str, Any]] = deque(maxlen=recent)
        self.ledger: deque[str] = deque(maxlen=ledger)

    def push(self, transition: dict[str, Any], events: list[str]) -> None:
        self.recent.append(transition)
        for e in events:
            self.ledger.append(e)

    def reset_level(self) -> None:
        """Clear the per-level ledger + recent window (persistent memory stays)."""
        self.recent.clear()
        self.ledger.clear()

    def recent_events(self, n: int = 8) -> list[str]:
        return list(self.ledger)[-n:]


def _rc(centroid: tuple[float, float]) -> list[int]:
    return [int(round(centroid[0])), int(round(centroid[1]))]


def _object_to_packet(obj: SceneObject) -> dict[str, Any]:
    return {
        "id": obj.id,
        "bbox": list(obj.bbox),
        "centroid": _rc(obj.centroid),
        "colors": {int(obj.color): obj.area},
        "area": obj.area,
        "shape_hash": obj.shape_hash,
        "topology": {"components": 1, "holes": obj.holes},
        "touches_boundary": obj.touches_boundary,
        "contained_by": obj.contained_by,
        "adjacent": obj.adjacent,
        "change_history": "; ".join(obj.change_history[-3:]),
        "safe_click": list(obj.safe_click),
    }


def _change_section(scene: Scene, prev_scene: Scene | None,
                    frame: Any, prev_frame: Any) -> dict[str, Any]:
    appeared = [e["id"] for e in scene.events if e["type"] == "appeared"]
    disappeared = [e["id"] for e in scene.events if e["type"] == "disappeared"]
    moved = [{"id": e["id"], "from": e["from"], "to": e["to"]}
             for e in scene.events if e["type"] == "moved"]
    recolored = [{"id": e["id"], "from": e["from"], "to": e["to"]}
                 for e in scene.events if e["type"] == "recolored"]
    split = [e for e in scene.events if e["type"] == "split"]
    merged = [e for e in scene.events if e["type"] == "merged"]

    bbox = None
    cells = 0
    if frame is not None and prev_frame is not None:
        bb = diff_bbox(prev_frame, frame)
        bbox = list(bb) if bb is not None else None
        cells = diff_cells(prev_frame, frame)

    relations_changed = _relation_changes(scene, prev_scene)
    out: dict[str, Any] = {
        "changed_bbox": bbox,
        "cells_changed": cells,
        "appeared": appeared,
        "disappeared": disappeared,
        "moved": moved,
        "recolored": recolored,
        "relations_changed": relations_changed,
    }
    if split:
        out["split"] = [{"id": e["id"], "into": e["into"]} for e in split]
    if merged:
        out["merged"] = [{"ids": e["ids"], "into": e["into"]} for e in merged]
    return out


def _relation_changes(scene: Scene, prev_scene: Scene | None) -> list[str]:
    if prev_scene is None:
        return []
    prev_adj: dict[str, set[tuple[str, str]]] = {
        o.id: {(a["id"], a["direction"]) for a in o.adjacent} for o in prev_scene.objects
    }
    out: list[str] = []
    for o in scene.objects:
        now = {(a["id"], a["direction"]) for a in o.adjacent}
        new = now - prev_adj.get(o.id, set())
        for other_id, direction in sorted(new):
            out.append(f"{o.id} now {direction}_of {other_id}")
    return out


class TurnPacketBuilder:
    """Builds the turn packet dict + its YAML serialization, under a token cap."""

    def __init__(
        self,
        coordinate_rule: str = "MOUSE(row, col), zero-based",
        max_objects: int = 20,
        token_budget: int = 3000,
        recent_events_shown: int = 8,
    ) -> None:
        self.coordinate_rule = coordinate_rule
        self.max_objects = max_objects
        self.token_budget = token_budget
        self.recent_events_shown = recent_events_shown

    def build(
        self,
        *,
        game: dict[str, Any],
        last_action: dict[str, Any] | None,
        scene: Scene,
        history: HistoryTiers,
        memory: EnvironmentMemory,
        prev_scene: Scene | None = None,
        frame: Any = None,
        prev_frame: Any = None,
    ) -> dict[str, Any]:
        game_sec = dict(game)
        game_sec.setdefault("coordinate_rule", self.coordinate_rule)

        objects = sorted(scene.objects, key=lambda o: o.area, reverse=True)
        obj_packets = [_object_to_packet(o) for o in objects[: self.max_objects]]
        regions = [{"id": o.id, "bbox": list(o.bbox), "role_guess": "unknown"}
                   for o in objects
                   if any(x.contained_by == o.id for x in scene.objects)]

        scene_sec = {
            "frame_hash": base_hash(frame) if frame is not None else "",
            "background_color": scene.background,
            "regions": regions,
            "objects": obj_packets,
        }

        packet = {
            "GAME": game_sec,
            "LAST_ACTION": last_action or {},
            "CHANGE": _change_section(scene, prev_scene, frame, prev_frame),
            "SCENE": scene_sec,
            "RECENT_EVENTS": history.recent_events(self.recent_events_shown),
            "MEMORY": memory.to_dict(),
        }
        return self._enforce_budget(packet)

    def _enforce_budget(self, packet: dict[str, Any]) -> dict[str, Any]:
        """Trim the largest section (SCENE.objects) until under the token cap."""
        packet.setdefault("_meta", {})
        while True:
            text = self.to_yaml(packet)
            if estimate_tokens(text) <= self.token_budget:
                break
            objs = packet["SCENE"]["objects"]
            if len(objs) <= 1:
                packet["_meta"]["truncated"] = True
                break
            # drop the smallest-area (last, since sorted desc) object.
            objs.pop()
            packet["_meta"]["truncated"] = True
            packet["_meta"]["objects_shown"] = len(objs)
        return packet

    def to_yaml(self, packet: dict[str, Any]) -> str:
        body = {k: v for k, v in packet.items() if k != "_meta"}
        return yaml.safe_dump(body, sort_keys=False, default_flow_style=False,
                              allow_unicode=True)
