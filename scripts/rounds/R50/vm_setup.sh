#!/bin/bash
# R50 — cloud bench setup on the g4-standard-48 VM (RTX PRO 6000 96GB).
# Installs Ollama, pulls the three Kaggle-candidate models, preps python env.
# Idempotent: safe to re-run after a spot preemption.
set -e
cd "$HOME"

if ! command -v ollama >/dev/null; then
  curl -fsSL https://ollama.com/install.sh | sh
fi
sudo systemctl enable --now ollama 2>/dev/null || (nohup ollama serve > ollama.log 2>&1 &)
sleep 3

python3 -m pip install --user --quiet numpy 2>/dev/null || sudo apt-get install -y python3-numpy

# Kaggle-candidate models (96GB VRAM: each fits; pulled sequentially)
# Flash attention on (safe default for Blackwell); fp16 KV for fidelity.
sudo mkdir -p /etc/systemd/system/ollama.service.d
printf '[Service]\nEnvironment=OLLAMA_FLASH_ATTENTION=1\n' | sudo tee /etc/systemd/system/ollama.service.d/override.conf >/dev/null
sudo systemctl daemon-reload && sudo systemctl restart ollama 2>/dev/null || true
sleep 3

# 96GB VRAM: prefer q8_0 over q4 defaults to remove the quant-damage confound
# measured locally (Q3-30b-coder collapsed; see R49). gpt-oss-120b MXFP4 IS its
# native precision.
ollama pull gpt-oss:120b
ollama pull qwen3-coder:30b-a3b-q8_0 || ollama pull qwen3-coder:30b
ollama pull gemma4:26b-a4b-it-qat
ollama pull gemma4:31b-it-q8_0 || ollama pull gemma4:31b-it-qat || ollama pull gemma4:31b

mkdir -p bench/data/transitions/train bench/out/games
echo "setup done: $(date -u '+%Y-%m-%d %H:%M:%S UTC')"
nvidia-smi --query-gpu=name,memory.total --format=csv,noheader
ollama list
