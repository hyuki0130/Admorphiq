#!/usr/bin/env bash
# R98 self-checks — everything that guards a measurement, in one command.
#
# Six checks were added across one session, each verified alone and none of them reachable
# together. A guard nobody runs is a guard that stops holding without saying so, and the
# round has already had a table go stale within the hour of being written.
#
# These are the CHEAP checks: seconds not minutes, no GPU, no model server. The live gates
# (oracle, grounding, verifier, mutants) stay separate on purpose — they decide the contract
# and cost minutes each, and mixing them here would make the fast check slow enough to skip.
#
# FIVE of the six need nothing but the repository. The harness self-test is the exception and
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
step() { printf '%-34s ' "$1"; shift
         if "$@" >/tmp/r98_selfcheck.log 2>&1; then echo OK; return; fi
         if grep -q "exposes no sp80 environment" /tmp/r98_selfcheck.log; then
           echo "SKIP (needs the game environments; set ARC_ENVIRONMENTS_DIR)"; skipped=1
           return
         fi
         echo FAIL; fail=1; tail -3 /tmp/r98_selfcheck.log | sed 's/^/    /'; }

step "corpus validity + coverage"  uv run python scripts/rounds/R98/rule_bench.py --all
step "corpus guard pins"           uv run pytest tests/test_r98_corpus_guard.py -q
step "probe logic pins"            uv run pytest tests/test_r98_probe_logic.py -q
step "explanation checker pins"    uv run pytest tests/test_r98_explanation_check.py -q
step "instruments listing"         uv run pytest tests/test_r98_instruments_listed.py -q
step "harness self-test"           uv run python scripts/probe_r98_model_bench.py --self-test

if [ "$fail" -eq 0 ] && [ "$skipped" -eq 1 ]; then
  echo "[R98 selfcheck] five guards hold; the harness self-test was SKIPPED (no game environments)"
elif [ "$fail" -eq 0 ]; then
  echo "[R98 selfcheck] all six guards hold"
else
  echo "[R98 selfcheck] ⛔ a guard is not holding — see above"
fi
exit "$fail"
