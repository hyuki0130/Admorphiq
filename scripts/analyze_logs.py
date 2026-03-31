"""Analyze JSONL game logs and print summary statistics."""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path


def analyze(log_file: str) -> None:
    path = Path(log_file)
    if not path.exists():
        print(f"File not found: {log_file}")
        return

    steps: list[dict] = []
    events: list[dict] = []
    summaries: list[dict] = []
    frame_diffs: list[dict] = []

    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            entry = json.loads(line)
            entry_type = entry.get("type", "")
            if entry_type == "step":
                steps.append(entry)
            elif entry_type == "event":
                events.append(entry)
            elif entry_type == "summary":
                summaries.append(entry)
            elif entry_type == "frame_diff":
                frame_diffs.append(entry)
            else:
                steps.append(entry)  # legacy format

    print(f"=== {path.name} ===")
    print(f"Steps: {len(steps)}, Events: {len(events)}, Frame diffs: {len(frame_diffs)}")

    # Summary
    for s in summaries:
        print(
            f"Summary: {s.get('total_actions')} actions, "
            f"{s.get('levels_cleared')} levels, "
            f"{s.get('elapsed_seconds')}s ({s.get('ms_per_action')}ms/act)"
        )

    # Events
    if events:
        event_types = Counter(e.get("event", "?") for e in events)
        print(f"Events: {dict(event_types)}")

    # Frame change stats
    if steps:
        changed = [s for s in steps if s.get("frame_changed")]
        pct = len(changed) / len(steps) * 100
        print(f"Frame changed: {len(changed)}/{len(steps)} ({pct:.0f}%)")

    # Action distribution
    if steps:
        actions = Counter(s.get("action", "?") for s in steps)
        print(f"Action distribution (top 10): {dict(actions.most_common(10))}")

    # Strategy distribution (ensemble)
    if steps:
        strategies = Counter(s.get("strategy", None) for s in steps)
        strategies.pop(None, None)
        if strategies:
            print(f"Strategy distribution: {dict(strategies)}")

    # Frame diff stats
    if frame_diffs:
        pixel_changes = [d.get("changed_pixels", 0) for d in frame_diffs]
        avg_change = sum(pixel_changes) / len(pixel_changes)
        max_change = max(pixel_changes)
        print(f"Pixel changes: avg={avg_change:.1f}, max={max_change}")

    # Reward stats
    if steps:
        rewards = [s.get("reward") for s in steps if s.get("reward") is not None]
        if rewards:
            avg_reward = sum(rewards) / len(rewards)
            print(f"Rewards: avg={avg_reward:.3f}, count={len(rewards)}")

    print()


def main() -> None:
    if len(sys.argv) < 2:
        # Auto-discover log files
        log_dir = Path("logs")
        if not log_dir.exists():
            print("Usage: python analyze_logs.py <log_file.jsonl> [...]")
            print("Or run from project root with logs/ directory present.")
            return
        files = sorted(log_dir.glob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)
        if not files:
            print("No .jsonl files found in logs/")
            return
        print(f"Found {len(files)} log files, showing latest 5:\n")
        for f in files[:5]:
            analyze(str(f))
    else:
        for arg in sys.argv[1:]:
            analyze(arg)


if __name__ == "__main__":
    main()
