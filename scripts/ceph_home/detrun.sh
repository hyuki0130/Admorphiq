#!/bin/bash
export PATH=$HOME/.local/bin:$PATH
export OMP_NUM_THREADS=1
cd ~/admorphiq
: > /tmp/det.log
for g in cd82 sb26 re86 su15 sk48 r11l vc33 cn04; do
  for r in 1 2; do
    ( uv run python scripts/score_efficiency.py --agent kaggle_detect --titles "$g" --max-actions 4000 --out /tmp/det_${g}_${r}.json >/dev/null 2>&1; python3 -c "
import json;d=json.load(open(\"/tmp/det_'$g'_'$r'.json\"))
for x in d.get(\"games\",[]): print(f\"'$g' run'$r' {x.get(chr(103)+chr(97)+chr(109)+chr(101)+chr(95)+chr(115)+chr(99)+chr(111)+chr(114)+chr(101)):.6f} lvl={x.get(chr(108)+chr(101)+chr(118)+chr(101)+chr(108)+chr(115)+chr(95)+chr(99)+chr(111)+chr(109)+chr(112)+chr(108)+chr(101)+chr(116)+chr(101)+chr(100))}\")" >> /tmp/det.log ) &
  done
done
wait
echo DONE >> /tmp/det.log
