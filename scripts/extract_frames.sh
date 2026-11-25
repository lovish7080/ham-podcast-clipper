#!/usr/bin/env bash
# Extract frames at N fps + scene-change timestamps for a video.
# Usage: extract_frames.sh INPUT OUTDIR [FPS=2] [SCENE_THRESH=0.3]
# Produces: OUTDIR/f_%04d.jpg (frame k is at t=(k-1)/FPS), OUTDIR/scenes.txt (one timestamp per line, with score)
set -euo pipefail
IN="$1"; OUT="$2"; FPS="${3:-2}"; TH="${4:-0.3}"
mkdir -p "$OUT"
ffmpeg -v error -y -i "$IN" -vf "fps=$FPS,scale=-2:360" -q:v 4 "$OUT/f_%04d.jpg"
ffmpeg -v info -i "$IN" -vf "select='gt(scene,$TH)',metadata=print" -an -f null - 2>&1 \
  | awk '/pts_time/{match($0,/pts_time:[0-9.]+/);t=substr($0,RSTART+9,RLENGTH-9)} /lavfi.scene_score/{split($0,a,"=");printf "%.2f %.3f\n",t,a[2]}' > "$OUT/scenes.txt"
echo "$(ls "$OUT"/f_*.jpg | wc -l) frames, $(wc -l < "$OUT/scenes.txt") scene changes -> $OUT"
