#!/bin/bash
# r56s5: full-adapter parallel measurement on ceph-build (64 cores — one process per game)
cd ~/admorphiq
OUT=~/r56s5
mkdir -p $OUT
ADAPTERS="ft09 tr87 sb26 lp85 m0r0 vc33 tu93 dc22 ka59 su15"
for a in $ADAPTERS; do
  nohup ~/.local/bin/uv run python scripts/script25.py --games $a --max-actions 5000 \
    --out $OUT/$a > $OUT/$a.log 2>&1 &
  echo "launched $a pid $!"
done
wait
echo "=== ALL DONE $(date '+%H:%M:%S') ==="
grep -h "levels=" $OUT/*/SUMMARY.txt 2>/dev/null
