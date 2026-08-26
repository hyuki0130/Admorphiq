#!/bin/bash
export PATH=$HOME/.local/bin:$PATH
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
cd ~/admorphiq
: > /tmp/stall.log
for g in vc33 r11l sp80 lf52; do
  for s in 80 12; do
    ( HARNESS_STALL=$s uv run python scripts/click_efficacy.py "$g" 3000 2>&1 | grep -E "cleared|FIRST|pick=" | sed "s/^/stall$s $g | /" >> /tmp/stall.log ) &
  done
done
wait
echo DONE >> /tmp/stall.log
