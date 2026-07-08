#!/bin/zsh
# R54 — US-7 tune-before-discard sweep for goal-conditioned WM planning.
# R52/R53 showed synthesis fit rarely clears the 0.8 gate on raw runtime
# observations, so planning almost never engages. Before discarding the lever,
# sweep the two knobs that gate engagement: the accept gate (GF_EWM_MIN_FIT)
# and the per-step planning confidence floor (GF_EWM_PLAN_CONF). Planning stays
# additive — a lower floor lets a partially-accurate model steer only when its
# rollout still clears the floor.
# Subset = the games that cleared the 0.8 fit gate in R52 (FT09/LP85/SP80)
# plus a few reliable movers, where engagement is even possible. Cheap: ~9
# games x 3 configs. Waits for R53 to finish (GPU is single-tenant on 24GB).
cd /Users/nhn/Workspace/Admorphiq
while pgrep -f "R53/run_launchd.sh" >/dev/null 2>&1; do sleep 60; done
D=scripts/rounds/R54
SUBSET=(ft09 lp85 sp80 cd82 cn04 dc22 m0r0 tu93 vc33)
# config = "gate:conf" tuples
CONFIGS=("0.5:0.55" "0.5:0.35" "0.3:0.35")
PAR=2

run_one() {
  local cfg=$1 g=$2 gate=${cfg%%:*} conf=${cfg##*:} t0=$(date +%s)
  local tag="g${gate}_c${conf}"
  local out="$D/${tag}/${g}.json"
  [ -f "$out" ] && return
  mkdir -p "$D/${tag}"
  GF_GIVEUP=8000 GF_EWM_PLAN=1 GF_EWM_MODEL=gpt-oss:20b \
    GF_EWM_MIN_FIT=$gate GF_EWM_PLAN_CONF=$conf GF_DEBUG=1 \
    /Users/nhn/.local/bin/uv run python scripts/score_efficiency.py \
    --agent graph_frontier --titles "$g" --max-actions 8000 \
    --out "$out" > "$D/${tag}/${g}.log" 2>&1
  echo "[R54 $tag] $g $(($(date +%s)-t0))s $(date '+%H:%M:%S')" >> $D/run.log
}

mkdir -p $D
echo "[$(date '+%Y-%m-%d %H:%M:%S %Z')] R54 sweep start (after R53): gates/confs ${CONFIGS[*]} on ${SUBSET[*]}" >> $D/run.log
for cfg in $CONFIGS; do
  pids=()
  for g in $SUBSET; do
    run_one "$cfg" "$g" &
    pids+=($!)
    while (( ${#pids[@]} >= PAR )); do wait ${pids[1]} 2>/dev/null; pids=(${pids[2,-1]}); done
  done
  wait
  echo "[$(date '+%Y-%m-%d %H:%M:%S %Z')] R54 config $cfg DONE" >> $D/run.log
done
echo "[$(date '+%Y-%m-%d %H:%M:%S %Z')] R54 ALL DONE" >> $D/run.log
