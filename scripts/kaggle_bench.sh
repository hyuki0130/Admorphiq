#!/usr/bin/env bash
# The Kaggle bench, as ONE command. Written 2026-08-28 because the flow was being re-derived
# from scratch every time it was needed — where the CLI lives, what the kernel slug is, which
# files carry the numbers. All of that is here now.
#
# ⛔ NOT a submission. `kernels push` runs the notebook server-side and does NOT consume the
# daily submission slot. There is deliberately no --submit path: the standing user order is that
# nothing is submitted until the sample games are cleared, and that call is the user's alone.
#
# ⚠️ The CLI is NOT on PATH — it lives in the project venv, so every call goes through `uv run`.
#
# Usage:
#   bash scripts/kaggle_bench.sh status     # kernel state + submission history + GPU-run dates
#   bash scripts/kaggle_bench.sh results    # download the last run and print BOTH arms' totals
#   bash scripts/kaggle_bench.sh push       # stage the dataset, push the kernel, poll to done
set -uo pipefail
cd "$(dirname "$0")/.."
K="uv run kaggle"
SLUG="jaehyukhyun/admorphiq-r101-llm-full25"
OUT="/tmp/kaggle_bench_out"

case "${1:-status}" in
status)
  echo "=== kernel"; $K kernels status "$SLUG" 2>&1 | tail -2
  echo "=== submissions (the hidden-score history)"
  $K competitions submissions arc-prize-2026-arc-agi-3 2>&1 | head -6
  ;;
results)
  rm -rf "$OUT"; mkdir -p "$OUT"
  $K kernels output "$SLUG" -p "$OUT" >/dev/null 2>&1
  ls "$OUT"
  uv run python - "$OUT" <<'PY'
import json, sys, pathlib
out = pathlib.Path(sys.argv[1])
for name in ("arm_llm", "arm_fallback"):
    f = out / f"{name}.json"
    if not f.exists():
        print(f"{name}: MISSING"); continue
    d = json.load(open(f))
    print(f"{name:14} total_score={d.get('total_score')}  games={len(d.get('games', []))}")
a, b = out / "arm_llm.json", out / "arm_fallback.json"
if a.exists() and b.exists():
    la, lb = json.load(open(a)), json.load(open(b))
    ga = {g["game_id"]: g.get("game_score") for g in la.get("games", [])}
    gb = {g["game_id"]: g.get("game_score") for g in lb.get("games", [])}
    diff = [k for k in ga if abs((ga[k] or 0) - (gb.get(k) or 0)) > 1e-9]
    print(f"games where the LLM arm differs from the fallback arm: {len(diff)}")
    for k in diff:
        print(f"   {k}  llm {ga[k]}  fallback {gb[k]}")
PY
  ;;
push)
  bash kaggle_bench/build_and_run.sh
  echo "=== polling"
  for _ in $(seq 1 120); do
    s=$($K kernels status "$SLUG" 2>&1 | tail -1)
    echo "  $s"
    case "$s" in *COMPLETE*|*ERROR*|*CANCEL*) break;; esac
    sleep 60
  done
  ;;
*) echo "usage: $0 {status|results|push}"; exit 2;;
esac
