#!/bin/bash
# HAM Podcast Clipper — one-time setup for Hindi/Hinglish word timing.
# Downloads Meta's free MMS forced-alignment model (~1.2 GB) into Podcast Clips/_setup/mms_fa and splits it into
# <350 MB parts so Claude's workspace can stage it. Safe to re-run.
cd "$(dirname "$0")"
mkdir -p mms_fa && cd mms_fa
if ls model.pt.part_* >/dev/null 2>&1 && [ -f model.pt.sha256 ]; then echo "Already set up."; read -p "Press Enter to close"; exit 0; fi
curl -L --fail --progress-bar -o model.pt "https://dl.fbaipublicfiles.com/mms/torchaudio/ctc_alignment_mling_uroman/model.pt" || { echo "Download failed."; read -p "Enter"; exit 1; }
shasum -a 256 model.pt | awk '{print $1}' > model.pt.sha256
split -b 350m model.pt model.pt.part_ && rm model.pt
echo; echo "Done:"; ls -lh; read -p "Press Enter to close"
