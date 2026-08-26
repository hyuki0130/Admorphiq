#!/bin/bash
export PATH=$HOME/.local/bin:$PATH
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
cd ~/admorphiq
: > /tmp/alt.log
for g in vc33 r11l sp80; do
  for t in graph world_model paint toggle dealias; do
    ( uv run python scripts/tool_alternatives.py "$g" "$t" 3000 2>/dev/null | grep -E "levels=" >> /tmp/alt.log ) &
  done
done
wait
echo DONE >> /tmp/alt.log
