#!/usr/bin/env bash
# R98 self-checks — everything that guards a measurement, in one command.
#
# Ten checks now, added across two sessions, each verified alone and none of them reachable
# together. A guard nobody runs is a guard that stops holding without saying so, and the
# round has already had a table go stale within the hour of being written.
#
# These are the CHEAP checks: seconds not minutes, no GPU, no model server. The live gates
# (oracle, grounding, verifier, mutants) stay separate on purpose — they decide the contract
# and cost minutes each, and mixing them here would make the fast check slow enough to skip.
#
# NINE of the ten need nothing but the repository. The harness self-test is the exception and
# the first version of this file wrongly advertised it as engine-free: its stubs replace the
# MODEL, not the game, so it still drives the real arcade and cannot run where the environment
# files are absent. Measured on a fresh clone, where it failed with "the arcade exposes no sp80
# environment". It is reported as SKIP there rather than FAIL — a guard runner that goes red on
# a clean checkout teaches people to ignore it — and the summary counts skips separately,
# because skipped is not passed.
set -u
cd "$(dirname "$0")/../../.."
fail=0

skipped=0
# ⛔ TESTS GO ON THE BOX (rule 7m). Three concurrent local suites made the laptop unusable and a
# PreToolUse hook now refuses `uv run pytest` — so this runner, which is twelve pytest invocations,
# would be blocked outright for whoever invoked it. Route them through `ptest.sh`, which runs the
# same targets in a private snapshot on ceph-build and deletes it on exit.
#
# ⚠️ Found 2026-08-30 by auditing which scripts still execute a forbidden path. A runner is a place a
# forbidden call hides, exactly as a wrapper is — `integrate.sh` was hiding the superseded gate in
# the same audit.
_pytest() { bash "$(dirname "${BASH_SOURCE[0]}")/../../ptest.sh" --dirty "$@"; }

step() { printf '%-34s ' "$1"; shift
         if "$@" >/tmp/r98_selfcheck.log 2>&1; then echo OK; return; fi
         if grep -q "exposes no sp80 environment" /tmp/r98_selfcheck.log; then
           echo "SKIP (needs the game environments; set ARC_ENVIRONMENTS_DIR)"; skipped=1
           return
         fi
         echo FAIL; fail=1; tail -3 /tmp/r98_selfcheck.log | sed 's/^/    /'; }

step "corpus validity + coverage"  uv run python scripts/rounds/R98/rule_bench.py --all
step "corpus guard pins"           _pytest tests/test_r98_corpus_guard.py -q
step "probe logic pins"            _pytest tests/test_r98_probe_logic.py -q
step "explanation checker pins"    _pytest tests/test_r98_explanation_check.py -q
step "instruments listing"         _pytest tests/test_r98_instruments_listed.py -q
step "harness self-test"           uv run python scripts/probe_r98_model_bench.py --self-test

# The card guards (R99). They protect a DIFFERENT thing from the R98 ones — not whether a
# measurement is valid, but whether the shipped card is what was measured — and they belong
# here for the same reason: run together or they stop holding quietly.
step "detection contract pins"     _pytest tests/test_adapter_detection.py -q
step "adapter quarantine lint"     uv run python scripts/adapters25_lint.py
step "summaries match their data"  uv run python scripts/summary_agrees.py
step "R99 instruments listed"      _pytest tests/test_r99_instruments_listed.py -q

# The R101 guards. Same reason as the R99 block above — run together or they stop holding
# quietly. ⛔ Measured 2026-08-30: all four guards built that weekend ran NOWHERE automatically,
# not in a hook and not here, and `fogscout` has already been committed-but-unregistered once at
# a cost of +0.0942.
step "every tool is registered"   _pytest tests/test_every_tool_is_registered.py -q
step "detect is side-effect free" _pytest tests/test_detect_purity.py -q

if [ "$fail" -eq 0 ] && [ "$skipped" -eq 1 ]; then
  echo "[R98 selfcheck] eleven guards hold; the harness self-test was SKIPPED (no game environments)"
elif [ "$fail" -eq 0 ]; then
  echo "[R98 selfcheck] all twelve guards hold"
else
  echo "[R98 selfcheck] ⛔ a guard is not holding — see above"
fi
exit "$fail"
