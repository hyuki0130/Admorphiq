#!/bin/bash
# DETECTION DISPATCH — full-25 with --agent kaggle_detect. Proves the port ships depth without
# regressing any game where no detector fires.
export PATH=$HOME/.local/bin:$PATH
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
export TORCH_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1
PARMAX=20
cd ~/admorphiq
D=scripts/rounds/CAP4000; mkdir -p $D/games; : > $D/run.log
ALL="ar25 bp35 cd82 cn04 dc22 ft09 g50t ka59 lf52 lp85 ls20 m0r0 r11l re86 s5i5 sb26 sc25 sk48 sp80 su15 tn36 tr87 tu93 vc33 wa30"
for g in $ALL; do
  while [ "$(jobs -rp | wc -l)" -ge "$PARMAX" ]; do sleep 5; done
  (
    t0=$(date +%s)
    uv run python scripts/score_efficiency.py --agent kaggle_detect \
      --titles "$g" --max-actions 4000 --out "$D/games/${g}.json" >/dev/null 2>&1
    echo "[CAP4000] $g $(($(date +%s)-t0))s $(date '+%H:%M:%S')" >> $D/run.log
  ) &
done
wait
echo "[CAP4000] DONE $(date '+%Y-%m-%d %H:%M:%S %Z')" >> $D/run.log
