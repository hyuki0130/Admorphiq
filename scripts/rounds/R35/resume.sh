#!/bin/zsh
cd /Users/nhn/Workspace/Admorphiq
D=scripts/rounds/R35; log=$D/run.log; sum=$D/SUMMARY.txt
echo "[R35-resume] pretrain ($(date '+%H:%M:%S'))" >> $log
uv run python scripts/pretrain_forward_model.py --train-npz 'data/transitions/train/*.npz' --epochs 8 --out models/forward_model_pretrained.pt >> $log 2>&1 || { echo "[R35] PRETRAIN FAILED — see run.log" > $sum; exit 1; }
echo "[R35-resume] eval ($(date '+%H:%M:%S'))" >> $log
uv run python scripts/eval_forward_transfer.py --model models/forward_model_pretrained.pt \
  --heldout-npz 'data/transitions/heldout/*.npz' --train-npz 'data/transitions/train/*.npz' > $sum 2>>$log
echo "" >> $sum
echo "[R35] DONE $(date '+%Y-%m-%d %H:%M:%S %Z') — gate: held-out change metrics >> trivial no-change baseline => path(b) LIVE" >> $sum
