#!/usr/bin/env python3
"""Hindi / Hinglish (and any non-English) transcription with word-level timestamps.

Pipeline (free, open-source, WhisperX-style):
  1. Whisper large-v3-turbo (ONNX int8 via sherpa-onnx, CPU) -> text + segment timestamps.
     Audio is split into <=28 s windows at low-energy points.
  2. Meta MMS forced aligner (torchaudio MMS_FA, 1100+ languages, works on romanized text via uroman)
     -> start/end time for every word, per segment. Handles Devanagari + Latin (Hinglish) in one line.
  3. Words that can't be aligned (pure digits/symbols) are interpolated between neighbours.

Usage:
  transcribe_hi.py INPUT OUT.json [--lang hi|auto] [--whisper-dir DIR] [--mms MODEL.pt]
Output JSON (same schema as transcribe.py): {"engine","language","duration","words":[{start,end,word}],"segments":[{start,end,text}]}

Models:
  Whisper: github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/sherpa-onnx-whisper-turbo.tar.bz2
  MMS_FA:  dl.fbaipublicfiles.com/mms/torchaudio/ctc_alignment_mling_uroman/model.pt
           (if that host is blocked, fetch it on the user's Mac with the one-time setup .command,
            which saves it split into model.pt.part_* — pass --mms-parts DIR to reassemble)
"""
import argparse, json, os, re, subprocess, glob, hashlib
import numpy as np

ap = argparse.ArgumentParser()
ap.add_argument("input"); ap.add_argument("out")
ap.add_argument("--lang", default="hi", help="Whisper language code, or 'auto' to detect")
ap.add_argument("--whisper-dir", default="/home/claude/models/sherpa-onnx-whisper-turbo")
ap.add_argument("--mms", default=None, help="path to MMS_FA model.pt")
ap.add_argument("--mms-parts", default=None, help="dir with model.pt.part_* (+ model.pt.sha256) to reassemble")
ap.add_argument("--chunk", type=float, default=28.0)
a = ap.parse_args()

SR = 16000
pcm = subprocess.run(["ffmpeg", "-v", "error", "-i", a.input, "-ac", "1", "-ar", str(SR), "-f", "s16le", "-"],
                     capture_output=True, check=True).stdout
audio = np.frombuffer(pcm, np.int16).astype(np.float32) / 32768.0
dur = len(audio) / SR

# ---------- 1. Whisper ----------
import sherpa_onnx
d = a.whisper_dir
rec = sherpa_onnx.OfflineRecognizer.from_whisper(
    encoder=f"{d}/turbo-encoder.int8.onnx", decoder=f"{d}/turbo-decoder.int8.onnx", tokens=f"{d}/turbo-tokens.txt",
    language="" if a.lang == "auto" else a.lang, task="transcribe", num_threads=os.cpu_count() or 4,
    enable_segment_timestamps=True)

def split_points(x, maxlen):
    hop = int(0.02 * SR)
    e = np.array([np.sqrt(np.mean(x[i:i + hop] ** 2) + 1e-12) for i in range(0, max(len(x) - hop, 1), hop)])
    pts, start = [0], 0
    while (len(x) - start) / SR > maxlen:
        lo = int((start / SR + maxlen * 0.6) / 0.02); hi = int((start / SR + maxlen) / 0.02)
        k = lo + int(np.argmin(e[lo:hi])); start = k * hop; pts.append(start)
    pts.append(len(x)); return pts

segs, lang = [], a.lang
for s0, s1 in zip(split_points(audio, a.chunk)[:-1], split_points(audio, a.chunk)[1:]):
    st = rec.create_stream(); st.accept_waveform(SR, audio[s0:s1]); rec.decode_stream(st)
    r = st.result; off = s0 / SR
    if getattr(r, "lang", None): lang = r.lang.strip("<|>") or lang
    texts = list(getattr(r, "segment_texts", []) or [])
    starts = list(getattr(r, "segment_timestamps", []) or [])
    durs = list(getattr(r, "segment_durations", []) or [])
    if texts and len(texts) == len(starts):
        for i, t in enumerate(texts):
            b = off + starts[i]
            e = off + (starts[i] + durs[i] if i < len(durs) and durs[i] > 0 else (starts[i + 1] if i + 1 < len(starts) else (s1 - s0) / SR))
            if t.strip(): segs.append({"start": round(b, 2), "end": round(min(e, s1 / SR), 2), "text": t.strip()})
    elif r.text.strip():
        segs.append({"start": round(off, 2), "end": round(s1 / SR, 2), "text": r.text.strip()})

# ---------- 2. MMS forced alignment ----------
import torch, torchaudio
from torchaudio.pipelines import MMS_FA as bundle
from torchaudio.functional import forced_align, merge_tokens
from uroman import Uroman

if a.mms_parts:
    parts = sorted(glob.glob(os.path.join(a.mms_parts, "model.pt.part_*")))
    a.mms = "/tmp/mms_fa_model.pt"
    if not os.path.exists(a.mms):
        with open(a.mms, "wb") as f:
            for p in parts: f.write(open(p, "rb").read())
    sha_f = os.path.join(a.mms_parts, "model.pt.sha256")
    if os.path.exists(sha_f):
        h = hashlib.sha256(open(a.mms, "rb").read()).hexdigest()
        assert h == open(sha_f).read().strip(), "MMS model checksum mismatch"
hub = os.path.join(torch.hub.get_dir(), "checkpoints"); os.makedirs(hub, exist_ok=True)
if a.mms and not os.path.exists(os.path.join(hub, "model.pt")):
    os.symlink(os.path.abspath(a.mms), os.path.join(hub, "model.pt"))
model = bundle.get_model(with_star=False).eval()
DICT = bundle.get_dict(star=None)
ur = Uroman()

def romanize(w):
    r = ur.romanize_string(w).lower()
    return "".join(c for c in r if c in DICT and c != "-")

words = []
wav = torch.from_numpy(audio)
for sg in segs:
    raw = [w for w in re.split(r"\s+", sg["text"]) if w]
    rom = [romanize(w) for w in raw]
    b0 = max(0.0, sg["start"] - 0.3); b1 = min(dur, sg["end"] + 0.3)
    chunk = wav[int(b0 * SR):int(b1 * SR)].unsqueeze(0)
    idx = [i for i, r in enumerate(rom) if r]
    times = {}
    if idx and chunk.shape[1] > SR * 0.2:
        with torch.inference_mode():
            em, _ = model(chunk)
        em = torch.log_softmax(em, -1)
        tgt = [DICT[c] for i in idx for c in rom[i]]
        if em.shape[1] >= len(tgt):
            ali, sc = forced_align(em, torch.tensor([tgt], dtype=torch.int32), blank=0)
            spans = merge_tokens(ali[0], sc[0].exp())
            ratio = chunk.shape[1] / em.shape[1] / SR
            k = 0
            for i in idx:
                n = len(rom[i]); sp = spans[k:k + n]; k += n
                times[i] = (round(b0 + sp[0].start * ratio, 2), round(b0 + sp[-1].end * ratio, 2))
    for i, w in enumerate(raw):
        words.append({"start": times.get(i, (None, None))[0], "end": times.get(i, (None, None))[1], "word": w,
                      "aligned": i in times, "_seg": (sg["start"], sg["end"])})

# ---------- 3. fill unaligned words ----------
for i, w in enumerate(words):
    if w["start"] is None:
        prev = next((words[j]["end"] for j in range(i - 1, -1, -1) if words[j]["end"] is not None), w["_seg"][0])
        nxt = next((words[j]["start"] for j in range(i + 1, len(words)) if words[j]["start"] is not None), w["_seg"][1])
        w["start"], w["end"] = round(prev, 2), round(max(prev, nxt), 2)
    del w["_seg"]

json.dump({"engine": "whisper-large-v3-turbo + mms_fa", "language": lang, "duration": round(dur, 2),
           "words": words, "segments": segs}, open(a.out, "w"), indent=1, ensure_ascii=False)
print(f"{a.input}: {dur:.1f}s lang={lang} {len(words)} words ({sum(w['aligned'] for w in words)} aligned), {len(segs)} segments")
