#!/bin/bash
# r56s6: FULL-25 parallel measurement on ceph-build (one process per game; lp85 excluded — still finishing its r56s5 run)
cd ~/admorphiq
OUT=~/r56s6
mkdir -p $OUT
ADAPTERS="ft09 tr87 sb26 m0r0 vc33 tu93 dc22 ka59 su15 ar25 ls20 sp80 cn04 r11l sk48 wa30 g50t bp35 re86 tn36 lf52 sc25 s5i5"
for a in $ADAPTERS; do
  nohup ~/.local/bin/uv run python scripts/script25.py --games $a --max-actions 5000 \
    --out $OUT/$a > $OUT/$a.log 2>&1 &
  echo "launched $a pid $!"
done
wait
echo "=== ALL DONE $(date '+%H:%M:%S') ==="
