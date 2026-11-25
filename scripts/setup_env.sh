#!/usr/bin/env bash
# HAM Podcast Clipper — prepare Claude's cloud workspace (run once per session).
# Installs Python deps from PyPI and fetches the speech models from GitHub (both reachable from the workspace).
# The Hindi aligner (MMS_FA) is NOT downloadable here: it lives in the user's folder (_setup/mms_fa, split in
# <350 MB parts by "_setup/One-time setup (Hindi models).command") and is staged in when needed.
set -e
MODELS=${MODELS:-/home/claude/models}
mkdir -p "$MODELS"
pip install --break-system-packages -q sherpa-onnx numpy 2>&1 | grep -v WARN || true
REL=https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models
if [ ! -d "$MODELS/sherpa-onnx-nemo-parakeet-tdt-0.6b-v2-int8" ]; then      # English ASR, word timestamps (~630 MB)
  curl -sSL "$REL/sherpa-onnx-nemo-parakeet-tdt-0.6b-v2-int8.tar.bz2" | tar xj -C "$MODELS"
fi
if [ "${HINDI:-0}" = "1" ]; then
  pip install --break-system-packages -q torch torchaudio uroman 2>&1 | grep -v WARN || true   # MMS forced alignment
  if [ "${WHISPER:-0}" = "1" ] && [ ! -d "$MODELS/sherpa-onnx-whisper-turbo" ]; then          # fallback ASR (~560 MB)
    curl -sSL "$REL/sherpa-onnx-whisper-turbo.tar.bz2" | tar xj -C "$MODELS"
  fi
fi
which ffmpeg ffprobe >/dev/null
echo "ready: $(ls $MODELS)"
