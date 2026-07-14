"""Transcript / replay system for the code-REPL agent (R55 module 1).

Built FIRST per the Codex design doc: it is the foundation that makes one-hour
Kaggle iterations scientifically useful by separating harness regressions from
model variance. Every turn is recorded as a JSONL row capturing the full I/O of
the decision (prompt + image hash, raw model output, parsed tool calls, sandbox
stdout/errors, action taken, frame before/after, memory before/after, latency,
tokens). The deterministic replayer re-runs a recorded transcript through the
harness WITHOUT a model — re-parsing the recorded raw output and re-deriving the
governor decision — and asserts they match what was recorded. A mismatch means a
harness (parser/governor) regression, not model noise.

No model calls, no heavy deps — pure dataclasses + JSONL.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable, Iterator


def image_hash(png_bytes: bytes | None) -> str:
    """Stable md5 hex of rendered image bytes, or "" when no image."""
    if not png_bytes:
        return ""
    return hashlib.md5(png_bytes).hexdigest()


@dataclass
class TurnRecord:
    """One decision boundary's full input/output, serialized to a JSONL row.

    Frames are stored as nested int lists (nullable — hashes are always kept so a
    lean transcript can omit the grids). ``parsed_tool_calls`` and ``action`` are
    the harness's structured interpretations of ``raw_output``; the replayer
    re-derives them and checks equality.
    """

    turn: int = 0
    game_id: str = ""
    level: int = 0
    turn_in_level: int = 0
    total_actions: int = 0
    legal_actions: list[str] = field(default_factory=list)
    prompt_text: str = ""
    image_hash: str = ""
    image_hashes: list[str] = field(default_factory=list)  # ordered images sent
    raw_output: str = ""
    finish_reason: str = ""  # stop | length | ... (length = truncated output)
    parsed_tool_calls: list[dict[str, Any]] = field(default_factory=list)
    sandbox_stdout: str = ""
    sandbox_error: str = ""
    action: dict[str, Any] | None = None
    frame_before_hash: str = ""
    frame_after_hash: str = ""
    frame_before: list[list[int]] | None = None
    frame_after: list[list[int]] | None = None
    board_changed: bool = False
    level_completed: bool = False
    game_over: bool = False
    memory_before: dict[str, Any] = field(default_factory=dict)
    memory_after: dict[str, Any] = field(default_factory=dict)
    latency_ms: float = 0.0
    tokens: dict[str, int] = field(default_factory=dict)

    def to_json(self) -> str:
        return json.dumps(asdict(self), separators=(",", ":"), ensure_ascii=False)

    @classmethod
    def from_json(cls, line: str) -> TurnRecord:
        data = json.loads(line)
        known = {f for f in cls.__dataclass_fields__}  # type: ignore[attr-defined]
        return cls(**{k: v for k, v in data.items() if k in known})


class TranscriptRecorder:
    """Append-only JSONL recorder for turn records.

    Use as a context manager or call :meth:`record` / :meth:`close`. When
    ``path`` is None the records are held in memory only (``records``), which the
    unit tests and the replayer use without touching disk.
    """

    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path) if path is not None else None
        self.records: list[TurnRecord] = []
        self._fh = None
        if self.path is not None:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self._fh = self.path.open("w", encoding="utf-8")

    def record(self, rec: TurnRecord) -> None:
        self.records.append(rec)
        if self._fh is not None:
            self._fh.write(rec.to_json() + "\n")
            self._fh.flush()

    def close(self) -> None:
        if self._fh is not None:
            self._fh.close()
            self._fh = None

    def __enter__(self) -> TranscriptRecorder:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()


def load_transcript(path: str | Path) -> list[TurnRecord]:
    """Read a JSONL transcript file into a list of :class:`TurnRecord`."""
    out: list[TurnRecord] = []
    with Path(path).open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                out.append(TurnRecord.from_json(line))
    return out


@dataclass
class ReplayMismatch:
    """A single divergence between a recorded turn and its deterministic replay."""

    turn: int
    field: str  # "parsed_tool_calls" or "action"
    recorded: Any
    replayed: Any


@dataclass
class ReplayResult:
    """Outcome of replaying a transcript without a model."""

    total: int
    mismatches: list[ReplayMismatch] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.mismatches


class TranscriptReplayer:
    """Re-run a recorded transcript through the harness with NO model.

    For each record, the recorded ``raw_output`` is re-parsed by ``parse_fn`` and
    the governor decision re-derived by ``govern_fn``; both are compared to what
    the record stored. Identical results prove the parser/governor are
    deterministic and unchanged; differences localize a harness regression to a
    specific turn and field — independent of any model stochasticity.

    Both callables are injected so this module has no dependency on the parser or
    governor implementations (later R55 modules provide them).
    """

    def __init__(
        self,
        parse_fn: Callable[[str], list[dict[str, Any]]],
        govern_fn: Callable[[list[dict[str, Any]], TurnRecord], dict[str, Any] | None]
        | None = None,
    ) -> None:
        self._parse = parse_fn
        self._govern = govern_fn

    def replay(self, records: Iterable[TurnRecord]) -> ReplayResult:
        records = list(records)
        result = ReplayResult(total=len(records))
        for rec in records:
            replayed_calls = self._parse(rec.raw_output)
            if _normalize(replayed_calls) != _normalize(rec.parsed_tool_calls):
                result.mismatches.append(
                    ReplayMismatch(rec.turn, "parsed_tool_calls",
                                   rec.parsed_tool_calls, replayed_calls)
                )
                # If parsing already diverged, the governor input differs too;
                # still check the governor against the RECORDED parse so both
                # regressions surface independently.
            if self._govern is not None:
                replayed_action = self._govern(rec.parsed_tool_calls, rec)
                if _normalize(replayed_action) != _normalize(rec.action):
                    result.mismatches.append(
                        ReplayMismatch(rec.turn, "action",
                                       rec.action, replayed_action)
                    )
        return result


def _normalize(obj: Any) -> Any:
    """Round-trip through JSON so tuples/ints/key-order compare structurally."""
    return json.loads(json.dumps(obj, sort_keys=True, default=list))


def iter_transcript(path: str | Path) -> Iterator[TurnRecord]:
    """Stream a JSONL transcript one record at a time (memory-friendly)."""
    with Path(path).open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                yield TurnRecord.from_json(line)
