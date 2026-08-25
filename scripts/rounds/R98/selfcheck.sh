#!/usr/bin/env bash
# R98 self-checks — everything that guards a measurement, in one command.
#
# Six checks were added across one session, each verified alone and none of them reachable
# together. A guard nobody runs is a guard that stops holding without saying so, and the
# round has already had a table go stale within the hour of being written.
#
# These are the CHEAP checks: no live engine, no GPU, seconds not minutes. The live gates
# (oracle, grounding, verifier, mutants) stay separate on purpose — they decide the contract
# and cost minutes each, and mixing them here would make the fast check slow enough to skip.
set -u
cd "$(dirname "$0")/../../.."
fail=0

step() { printf '%-34s ' "$1"; shift; if "$@" >/tmp/r98_selfcheck.log 2>&1; then echo OK;
         else echo FAIL; fail=1; tail -3 /tmp/r98_selfcheck.log | sed 's/^/    /'; fi; }

step "corpus validity + coverage"  uv run python scripts/rounds/R98/rule_bench.py --all
step "corpus guard pins"           uv run pytest tests/test_r98_corpus_guard.py -q
step "probe logic pins"            uv run pytest tests/test_r98_probe_logic.py -q
step "explanation checker pins"    uv run pytest tests/test_r98_explanation_check.py -q
step "instruments listing"         uv run pytest tests/test_r98_instruments_listed.py -q
step "harness self-test"           uv run python scripts/probe_r98_model_bench.py --self-test

if [ "$fail" -eq 0 ]; then
  echo "[R98 selfcheck] all six guards hold"
else
  echo "[R98 selfcheck] ⛔ a guard is not holding — see above"
fi
exit "$fail"
