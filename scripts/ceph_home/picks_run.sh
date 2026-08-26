#!/bin/bash
export PATH=$HOME/.local/bin:$PATH
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
cd ~/admorphiq
: > /tmp/picks.log
for g in vc33 sk48 lf52 tu93 r11l sp80 m0r0 lp85 tn36 s5i5 dc22 cn04 bp35 g50t sc25; do
  ( uv run python scripts/click_efficacy.py "$g" 1500 2>&1 | grep -oE "pick=[a-z_]+" | sort | uniq -c | sed "s/^/$g /" >> /tmp/picks.log ) &
done
wait
echo DONE >> /tmp/picks.log
