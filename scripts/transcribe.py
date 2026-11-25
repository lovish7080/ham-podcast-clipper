#!/usr/bin/env python3
"""Transcribe audio/video with word-level timestamps.

Backend: sherpa-onnx + NVIDIA Parakeet-TDT 0.6B v2 (ONNX int8, CPU, English).
Gives punctuated text with per-token timestamps. Long audio is split into
<=CHUNK s pieces at the quietest point; timestamps are shifted back to source time.
Model: github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/
       sherpa-onnx-nemo-parakeet-tdt-0.6b-v2-int8.tar.bz2

Usage:
  transcribe.py INPUT OUT.json [--model-dir DIR] [--prefix small.en]
INPUT can be any audio/video file (ffmpeg converts to 16 kHz mono).
Output JSON: {"duration":s, "words":[{"start","end","word"}], "segments":[{"start","end","text"}]}
"""
import argparse, json, subprocess, sys
import numpy as np
import sherpa_onnx

ap = argparse.ArgumentParser()
ap.add_argument("input"); ap.add_argument("out")
ap.add_argument("--model-dir", default="/home/claude/models/sherpa-onnx-nemo-parakeet-tdt-0.6b-v2-int8")
ap.add_argument("--chunk", type=float, default=60.0)
a = ap.parse_args()

SR = 16000
pcm = subprocess.run(["ffmpeg", "-v", "error", "-i", a.input, "-ac", "1", "-ar", str(SR), "-f", "s16le", "-"],
                     capture_output=True, check=True).stdout
audio = np.frombuffer(pcm, np.int16).astype(np.float32) / 32768.0
dur = len(audio) / SR

d = a.model_dir
rec = sherpa_onnx.OfflineRecognizer.from_transducer(
    encoder=f"{d}/encoder.int8.onnx", decoder=f"{d}/decoder.int8.onnx", joiner=f"{d}/joiner.int8.onnx",
    tokens=f"{d}/tokens.txt", model_type="nemo_transducer", num_threads=4)

# choose split points at low-energy frames
def split_points(x):
    hop = int(0.02 * SR)
    e = np.array([np.sqrt(np.mean(x[i:i + hop] ** 2) + 1e-12) for i in range(0, len(x) - hop, hop)])
    pts, start = [0], 0
    while (len(x) - start) / SR > a.chunk:
        lo = int((start / SR + a.chunk * 0.6) / 0.02); hi = int((start / SR + a.chunk) / 0.02)
        k = lo + int(np.argmin(e[lo:hi]))
        start = k * hop; pts.append(start)
    pts.append(len(x)); return pts

words = []
pts = split_points(audio)
for s, e in zip(pts[:-1], pts[1:]):
    st = rec.create_stream(); st.accept_waveform(SR, audio[s:e]); rec.decode_stream(st)
    r = st.result; off = s / SR
    toks, ts = list(r.tokens), list(r.timestamps)
    cur = None
    for t, tt in zip(toks, ts):
        if t.startswith(" ") or t.startswith("▁") or cur is None:
            if cur: words.append(cur)
            cur = {"start": round(off + tt, 2), "word": t.strip().lstrip("▁")}
        else:
            cur["word"] += t
    if cur: words.append(cur)
words = [w for w in words if w["word"]]
for i, w in enumerate(words):
    w["end"] = words[i + 1]["start"] if i + 1 < len(words) else round(dur, 2)
    w["end"] = round(min(w["end"], w["start"] + 1.2), 2)  # cap gaps (pauses)

# sentence-ish segments: break on punctuation or pause > 0.6 s
segs, cur = [], []
for i, w in enumerate(words):
    cur.append(w)
    nxt = words[i + 1] if i + 1 < len(words) else None
    if w["word"][-1:] in ".?!" or nxt is None or nxt["start"] - w["end"] > 0.6:
        segs.append({"start": cur[0]["start"], "end": cur[-1]["end"], "text": " ".join(x["word"] for x in cur)}); cur = []

json.dump({"duration": round(dur, 2), "words": words, "segments": segs}, open(a.out, "w"), indent=1)
print(f"{a.input}: {dur:.1f}s, {len(words)} words, {len(segs)} segments")
