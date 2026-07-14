"""Append-only event stream for the bench (R55 observability, item 2).

The v1/v3 bench wrote its per-game diagnostics only AFTER the game finished, so a
killed kernel lost the record entirely. This replaces that with an append-only
JSONL event stream flushed per event: each event carries a monotonic ``seq`` and
correlation ids (``action_id`` links an executed action to the transition it
produced). The per-game summary is DERIVED from the events, and a run with no
terminal event is marked ``run_incomplete`` — so a crash still leaves a truthful,
analyzable partial record.

No model calls; pure I/O + derivation.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any


class EventStream:
    """Append-only JSONL event writer with monotonic sequence numbers.

    ``path=None`` keeps events in memory only (for tests / derivation). Every
    ``emit`` assigns the next ``seq``, timestamps the event, writes+flushes it,
    and returns it.
    """

    def __init__(self, path: str | Path | None = None,
                 clock: Any = time.monotonic) -> None:
        self.path = Path(path) if path is not None else None
        self.events: list[dict[str, Any]] = []
        self._seq = 0
        self._clock = clock
        self._fh = None
        if self.path is not None:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self._fh = self.path.open("w", encoding="utf-8")

    def emit(self, type: str, **fields: Any) -> dict[str, Any]:
        ev = {"seq": self._seq, "t": round(self._clock(), 4), "type": type, **fields}
        self._seq += 1
        self.events.append(ev)
        if self._fh is not None:
            self._fh.write(json.dumps(ev, separators=(",", ":")) + "\n")
            self._fh.flush()
        return ev

    def close(self) -> None:
        if self._fh is not None:
            self._fh.close()
            self._fh = None

    def __enter__(self) -> EventStream:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()


def derive_summary(events: list[dict[str, Any]]) -> dict[str, Any]:
    """Build the per-game summary from the event log (the authoritative source).

    ``run_incomplete`` is True when no ``terminal`` event is present (a killed
    kernel), so the summary never silently claims a clean finish.
    """
    terminal = next((e for e in reversed(events) if e["type"] == "terminal"), None)
    transitions = [e for e in events if e["type"] == "transition"]
    start = next((e for e in events if e["type"] == "game_start"), None)
    changed = sum(1 for e in transitions if e.get("changed"))
    max_level = max((int(e.get("level", 0)) for e in transitions), default=0)
    return {
        "game_id": (start or {}).get("game_id", ""),
        "run_incomplete": terminal is None,
        "events": len(events),
        "actions": len(transitions),
        "changed_transitions": changed,
        "levels": int(terminal["levels"]) if terminal and "levels" in terminal else max_level,
        "terminal_reason": (terminal or {}).get("reason", "incomplete"),
    }
