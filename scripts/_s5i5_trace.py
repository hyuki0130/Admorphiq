"""Divergence trace for the s5i5 platform-diff diagnosis (macOS-arm64 vs Linux-x86_64).

Same code + same env files + same library versions give s5i5 = 1/8 on the Mac but
0/8 on the ceph-build VM, BOTH loading the `a48e4b1d` content variant. This probe
runs the s5i5 adapter's first N decisions against a FIXED env variant (forced, so
both machines trace byte-identical frames) and dumps, per action, everything that
drives the adapter's choice — in RAW (unsorted) order, since the leading hypothesis
is that `find_regions`/candidate ORDER diverges by platform and a `min()` tie-break
then picks a different click. Run on both machines, diff the JSON; the FIRST divergent
field localises the platform-sensitive bug.

Usage:
  uv run python scripts/_s5i5_trace.py --hash a48e4b1d --actions 40 --out trace_mac.json
Then diff trace_mac.json (Mac) vs trace_vm.json (ceph-build).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))

from arc_agi import Arcade, OperationMode  # noqa: E402

from admorphiq.adapters25 import s5i5  # noqa: E402
from admorphiq.adapters25.base import (  # noqa: E402
    canonical_layer,
    has_frame,
    most_common_color,
    state_name,
)
from admorphiq.kernels import find_regions  # noqa: E402

_ENV_ROOT = REPO / "environment_files" / "s5i5"


def _force_latest(target_hash: str) -> dict[str, str]:
    """Bump ``target_hash``'s metadata date so the arcade loads THAT variant on
    every machine (both platforms must trace the same env content). Returns the
    original dates for restoration."""
    saved: dict[str, str] = {}
    for d in _ENV_ROOT.iterdir():
        meta = d / "metadata.json"
        if not meta.exists():
            continue
        m = json.loads(meta.read_text())
        saved[str(meta)] = m.get("date_downloaded", "")
        newest = "2099-01-01T00:00:00.000000+00:00"
        oldest = "2000-01-01T00:00:00.000000+00:00"
        m["date_downloaded"] = newest if d.name == target_hash else oldest
        meta.write_text(json.dumps(m, indent=2))
    return saved


def _restore(saved: dict[str, str]) -> None:
    for path, date in saved.items():
        m = json.loads(Path(path).read_text())
        m["date_downloaded"] = date
        Path(path).write_text(json.dumps(m, indent=2))


def _frame_hash(grid) -> str:
    return hashlib.md5(repr(grid).encode()).hexdigest()[:12]


def _regions_raw(grid) -> list[dict]:
    """Regions in the EXACT order find_regions returns them (unsorted — that order
    is the suspected platform-divergent quantity), with the fields the adapter keys
    on: color, size, centroid, bbox."""
    bg = most_common_color(grid)
    out = []
    for r in find_regions(grid, background=bg, connectivity=8):
        out.append(
            {
                "color": int(r["color"]),
                "size": int(r["size"]),
                "centroid": [int(x) for x in s5i5._centroid(r)],
                "bbox": [int(x) for x in r["bbox"]],
            }
        )
    return out


def _action_tuple(action) -> list:
    aid = getattr(action, "value", None) or getattr(getattr(action, "id", None), "value", None) or str(action)
    data = {}
    try:
        data = action.action_data.model_dump()
    except Exception:
        pass
    return [str(aid), data.get("x"), data.get("y")]


class _LoadPathCapture:
    """Captures arc_agi's 'Successfully loaded game class ... from <path>' log so
    the trace records WHICH env dir actually loaded (the dynamic game class exposes
    no __file__). The frame_hash also fingerprints the variant, but this is explicit."""

    def __init__(self) -> None:
        self.path = "?"

    def write(self, msg: str) -> None:
        if "Successfully loaded game class" in msg and "from " in msg:
            self.path = msg.split("from ", 1)[1].strip()

    def flush(self) -> None:  # logging.StreamHandler contract
        pass


def trace(target_hash: str, n_actions: int, out_path: str) -> None:
    import logging
    import platform

    cap = _LoadPathCapture()
    handler = logging.StreamHandler(cap)  # type: ignore[arg-type]
    logging.getLogger().addHandler(handler)
    saved = _force_latest(target_hash)
    try:
        arcade = Arcade(operation_mode=OperationMode.OFFLINE)
        env = arcade.make("s5i5")
        adapter = s5i5.Adapter()
        loaded = cap.path
        obs = env.step(__import__("admorphiq.adapters25.base", fromlist=["reset_action"]).reset_action())
        records = []
        for step in range(n_actions):
            state = state_name(obs)
            rec: dict = {"step": step, "state": state}
            if has_frame(obs):
                grid = canonical_layer(obs)
                rec["frame_hash"] = _frame_hash(grid)
                rec["levels"] = int(getattr(obs, "levels_completed", 0) or 0)
                rec["regions_raw"] = _regions_raw(grid)
            action = adapter.choose_action([], obs)
            rec["action"] = _action_tuple(action)
            # adapter internal decision state AFTER the choice (the trajectory drivers)
            rec["candidates"] = [list(map(int, c)) for c in getattr(adapter, "_candidates", [])]
            rec["probe_idx"] = int(getattr(adapter, "_probe_idx", -1))
            rec["targets"] = [list(map(int, t)) for t in getattr(adapter, "_targets", [])]
            rec["effect"] = sorted(
                [list(map(int, k)), int(v[0]), list(map(int, v[1]))]
                for k, v in getattr(adapter, "_effect", {}).items()
            )
            rec["dead"] = sorted([list(map(int, d)) for d in getattr(adapter, "_dead", set())])
            # Compact per-step digest of the decision-relevant fields, so the two
            # machines' traces can be compared in ONE pass to find the FIRST
            # divergent step (then inspect that step's full record).
            rec["digest"] = hashlib.md5(
                json.dumps(
                    [rec.get("frame_hash"), rec.get("regions_raw"), rec["action"], rec["candidates"], rec["probe_idx"]],
                    sort_keys=True,
                ).encode()
            ).hexdigest()[:10]
            records.append(rec)
            if action.is_complex():
                obs = env.step(action, data=action.action_data.model_dump())
            else:
                obs = env.step(action)
            if obs is None or state_name(obs) == "WIN":
                records.append({"step": step + 1, "state": state_name(obs) if obs else "NONE", "terminal": True})
                break
        payload = {
            "platform": platform.platform(),
            "machine": platform.machine(),
            "python": platform.python_version(),
            "env_hash_forced": target_hash,
            "loaded_module": loaded,
            "n_records": len(records),
            "records": records,
        }
        Path(out_path).write_text(json.dumps(payload, indent=2))
        print(f"wrote {out_path}: {len(records)} records on {platform.machine()} ({platform.platform()})")
        cleared = any(r.get("state") == "WIN" or (r.get("levels", 0) or 0) >= 1 for r in records)
        print(f"  cleared L0 within {n_actions} actions: {cleared}  (loaded {loaded})")
    finally:
        _restore(saved)
        logging.getLogger().removeHandler(handler)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--hash", default="a48e4b1d", help="env content hash to force-load (both machines)")
    ap.add_argument("--actions", type=int, default=120)
    ap.add_argument("--out", default="s5i5_trace.json")
    args = ap.parse_args()
    trace(args.hash, args.actions, args.out)


if __name__ == "__main__":
    main()
