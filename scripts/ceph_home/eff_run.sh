#!/bin/bash
export PATH=$HOME/.local/bin:$PATH
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
cd ~/admorphiq
: > /tmp/eff.log
for g in vc33 sk48 lf52 tu93 r11l sp80 m0r0 lp85 tn36 s5i5; do
  ( uv run python scripts/click_efficacy.py "$g" 3000 2>/dev/null | grep -E "FIRST|cleared" >> /tmp/eff.log ) &
done
wait
echo DONE >> /tmp/eff.log
