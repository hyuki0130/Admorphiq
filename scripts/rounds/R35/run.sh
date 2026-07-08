#!/bin/zsh
# R35 — forward-model TRANSFER test: collect -> pretrain(18 games) -> eval(7 held-out).
# Decision gate (architect): held-out change-mask accuracy/IoU meaningfully above the
# trivial "predict-no-change" baseline => path (b) live; ~= trivial => kill path (b).
cd /Users/nhn/Workspace/Admorphiq
D=scripts/rounds/R35; log=$D/run.log; sum=$D/SUMMARY.txt
mkdir -p $D data/transitions/train data/transitions/heldout
: > $log; : > $sum
TRAIN="ar25,dc22,g50t,ka59,lf52,lp85,re86,s5i5,sb26,sc25,sk48,sp80,su15,tn36,tr87,tu93,vc33,wa30"
HELD="ft09,m0r0,bp35,cd82,cn04,ls20,r11l"
echo "[R35] START $(date '+%Y-%m-%d %H:%M:%S %Z') — collect(2000 act/game) -> pretrain(18) -> eval(7 held-out)" | tee -a $log

echo "[R35] collect TRAIN ($(date '+%H:%M:%S'))" >> $log
uv run python scripts/collect_transitions.py --titles "$TRAIN" --max-actions 2000 --seed 1 --out data/transitions/train >> $log 2>&1
echo "[R35] collect HELDOUT ($(date '+%H:%M:%S'))" >> $log
uv run python scripts/collect_transitions.py --titles "$HELD" --max-actions 2000 --seed 1 --out data/transitions/heldout >> $log 2>&1

echo "[R35] pretrain ($(date '+%H:%M:%S'))" >> $log
uv run python scripts/pretrain_forward_model.py --train-npz 'data/transitions/train/*.npz' --epochs 8 --out models/forward_model_pretrained.pt >> $log 2>&1

echo "[R35] eval ($(date '+%H:%M:%S'))" >> $log
uv run python scripts/eval_forward_transfer.py --model models/forward_model_pretrained.pt \
  --heldout-npz 'data/transitions/heldout/*.npz' --train-npz 'data/transitions/train/*.npz' > $sum 2>>$log

echo "" >> $sum
echo "[R35] DONE $(date '+%Y-%m-%d %H:%M:%S %Z') — gate: held-out change metrics >> trivial no-change baseline => path(b) LIVE" >> $sum
echo "[R35] DONE $(date '+%Y-%m-%d %H:%M:%S %Z')" | tee -a $log
