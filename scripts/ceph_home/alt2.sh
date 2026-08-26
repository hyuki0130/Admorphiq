#!/bin/bash
export PATH=$HOME/.local/bin:$PATH
export OMP_NUM_THREADS=1
cd ~/admorphiq
: > /tmp/alt2.log
for t in graph toggle; do
  ( uv run python scripts/tool_alternatives.py vc33 "$t" 4000 2>/dev/null | grep "levels=" >> /tmp/alt2.log ) &
done
wait
echo DONE >> /tmp/alt2.log
