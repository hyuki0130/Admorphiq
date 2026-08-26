#!/bin/bash
export PATH=$HOME/.local/bin:$PATH
export OMP_NUM_THREADS=1
set -e
cd ~/admorphiq
# Swap in the JULY harness (pre-R92), measure the card, restore. The point is to isolate
# what the agent25 research commits did to the DEPLOYED card — never measured until now.
rm -rf /tmp/harness_now && cp -R src/admorphiq/harness /tmp/harness_now
rm -rf src/admorphiq/harness && tar xzf ~/july_h.tgz -C .
D=scripts/rounds/JULYHARNESS; rm -rf $D; mkdir -p $D/games; : > $D/run.log
ALL="ar25 bp35 cd82 cn04 dc22 ft09 g50t ka59 lf52 lp85 ls20 m0r0 r11l re86 s5i5 sb26 sc25 sk48 sp80 su15 tn36 tr87 tu93 vc33 wa30"
for g in $ALL; do
  while [ "$(jobs -rp | wc -l)" -ge 20 ]; do sleep 3; done
  ( uv run python scripts/score_efficiency.py --agent kaggle_detect --titles "$g" --max-actions 4000 --out "$D/games/${g}.json" >/dev/null 2>&1; echo "$g" >> $D/run.log ) &
done
wait
rm -rf src/admorphiq/harness && cp -R /tmp/harness_now src/admorphiq/harness
echo DONE >> $D/run.log
