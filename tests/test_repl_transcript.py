"""Tests for the code-REPL transcript/replay system (R55 module 1).

These lock the foundation for scientific Kaggle iteration: that a turn's full I/O
round-trips through JSONL losslessly, and that deterministic replay (re-parse +
re-govern with NO model) detects harness regressions while ignoring model
variance. A replay mismatch must localize to the exact turn and field.
"""

from __future__ import annotations

from admorphiq.repl_agent.transcript import (
    TranscriptRecorder,
    TranscriptReplayer,
    TurnRecord,
    image_hash,
    load_transcript,
)


def _rec(turn: int, raw: str, calls: list[dict], action: dict | None) -> TurnRecord:
    return TurnRecord(
        turn=turn, raw_output=raw, parsed_tool_calls=calls, action=action,
        legal_actions=["LEFT", "RIGHT", "MOUSE"], board_changed=True,
    )


def test_turn_record_json_roundtrip():
    """Purpose: a TurnRecord serializes to one JSONL line and back unchanged.

    Feedback: failure means transcripts are lossy — replay and Kaggle debugging
    would operate on corrupted data.
    """
    rec = _rec(3, '{"action":"LEFT"}', [{"tool": "action", "action": "LEFT"}],
               {"action": "LEFT"})
    rec.frame_before = [[0, 1], [2, 3]]
    back = TurnRecord.from_json(rec.to_json())
    assert back == rec


def test_from_json_ignores_unknown_fields():
    """Purpose: forward-compat — a transcript with extra fields still loads.

    Feedback: failure means a schema addition breaks replay of old transcripts.
    """
    line = '{"turn":1,"raw_output":"x","future_field":42}'
    rec = TurnRecord.from_json(line)
    assert rec.turn == 1 and rec.raw_output == "x"


def test_image_hash_stable_and_empty():
    """Purpose: identical image bytes hash identically; None -> "".

    Feedback: failure means image dedup / prompt-cache reasoning is unreliable.
    """
    assert image_hash(b"abc") == image_hash(b"abc")
    assert image_hash(b"abc") != image_hash(b"abd")
    assert image_hash(None) == ""


def test_recorder_writes_jsonl(tmp_path):
    """Purpose: the recorder appends one JSONL line per turn and reloads them.

    Feedback: failure means recorded Kaggle runs cannot be re-read for replay.
    """
    path = tmp_path / "t.jsonl"
    with TranscriptRecorder(path) as rec:
        rec.record(_rec(0, "a", [], None))
        rec.record(_rec(1, "b", [], {"action": "RIGHT"}))
    loaded = load_transcript(path)
    assert [r.turn for r in loaded] == [0, 1]
    assert loaded[1].action == {"action": "RIGHT"}


def test_replay_passes_on_deterministic_parser():
    """Purpose: replaying with a parser/governor that reproduce the recorded
    decisions yields zero mismatches (ok=True).

    Feedback: failure means replay reports false regressions, making it useless
    as a harness-vs-model discriminator.
    """
    recs = [
        _rec(0, "LEFT", [{"tool": "action", "action": "LEFT"}], {"action": "LEFT"}),
        _rec(1, "RIGHT", [{"tool": "action", "action": "RIGHT"}], {"action": "RIGHT"}),
    ]

    def parse(raw: str):
        return [{"tool": "action", "action": raw.strip()}]

    def govern(calls, rec):
        return {"action": calls[0]["action"]}

    result = TranscriptReplayer(parse, govern).replay(recs)
    assert result.ok
    assert result.total == 2


def test_replay_detects_parser_regression():
    """Purpose: a parser that no longer reproduces the recorded parse is flagged
    at the exact turn/field.

    Feedback: failure means a real harness regression would slip through replay.
    """
    recs = [_rec(7, "LEFT", [{"tool": "action", "action": "LEFT"}], {"action": "LEFT"})]

    def broken_parse(raw: str):
        return [{"tool": "action", "action": "RIGHT"}]  # wrong

    result = TranscriptReplayer(broken_parse).replay(recs)
    assert not result.ok
    m = result.mismatches[0]
    assert m.turn == 7 and m.field == "parsed_tool_calls"


def test_replay_detects_governor_regression():
    """Purpose: a governor that changes the chosen action is flagged separately
    from parsing.

    Feedback: failure means governor drift (e.g. a changed legality rule) would
    not be caught by replay.
    """
    recs = [_rec(2, "LEFT", [{"tool": "action", "action": "LEFT"}], {"action": "LEFT"})]

    def parse(raw: str):
        return [{"tool": "action", "action": "LEFT"}]

    def drifted_govern(calls, rec):
        return {"action": "UNDO"}  # governor now decides differently

    result = TranscriptReplayer(parse, drifted_govern).replay(recs)
    fields = {m.field for m in result.mismatches}
    assert "action" in fields
