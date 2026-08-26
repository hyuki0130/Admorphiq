#!/bin/bash
# r59s8: FULL-25 official measurement at post-depth-phase HEAD (one process per game)
cd ~/admorphiq
OUT=~/r59s8
mkdir -p $OUT
ADAPTERS="ft09 tr87 sb26 m0r0 vc33 tu93 dc22 ka59 su15 ar25 ls20 sp80 cn04 r11l sk48 wa30 g50t bp35 re86 tn36 lf52 sc25 s5i5 cd82 lp85"
for a in $ADAPTERS; do
  nohup ~/.local/bin/uv run python scripts/script25.py --games $a --max-actions 5000 \
    --out $OUT/$a > $OUT/$a.log 2>&1 &
done
echo "launched $(jobs -p | wc -l) games"
wait
echo "=== ALL DONE $(date '+%H:%M:%S') ==="
