#!/usr/bin/env python3
"""Word-level timestamps by forced-aligning an EXISTING transcript (e.g. YouTube captions) to audio.
WhisperX-style alignment step, using Meta's MMS_FA model (1100+ languages; text romanized with uroman,
so Devanagari Hindi, Latin English and Hinglish mixes all align in one pass).

Use this for Hindi/Hinglish when YouTube captions exist — YouTube's Hindi ASR handles code-mixed
speech far better than the int8 Whisper builds available offline (which loop/drop English words).

Usage:
  align_captions.py AUDIO_OR_VIDEO CAPTIONS.json OUT.json --offset SECONDS --mms-parts DIR
CAPTIONS.json: [[start_seconds_in_episode, "line text"], ...]  (YouTube transcript-panel lines, in order)
--offset: episode time of the media file's t=0 (section start). Each caption line is aligned inside
          its own window [start, next_start] (+/-0.5 s), clipped to the file.
Output: same schema as transcribe.py, word times relative to the media file; plus "aligned" flags.
"""
import argparse, json, os, re, subprocess, glob, hashlib
import numpy as np, torch
from torchaudio.pipelines import MMS_FA as bundle
from torchaudio.functional import forced_align, merge_tokens
from uroman import Uroman

ap = argparse.ArgumentParser()
ap.add_argument("media"); ap.add_argument("captions"); ap.add_argument("out")
ap.add_argument("--offset", type=float, required=True)
ap.add_argument("--mms", default=None); ap.add_argument("--mms-parts", default=None)
ap.add_argument("--pad", type=float, default=0.5)
a = ap.parse_args()

SR = 16000
pcm = subprocess.run(["ffmpeg", "-v", "error", "-i", a.media, "-ac", "1", "-ar", str(SR), "-f", "s16le", "-"],
                     capture_output=True, check=True).stdout
audio = torch.from_numpy(np.frombuffer(pcm, np.int16).astype(np.float32) / 32768.0)
dur = len(audio) / SR

if a.mms_parts:
    a.mms = "/tmp/mms_fa_model.pt"
    if not os.path.exists(a.mms):
        with open(a.mms, "wb") as f:
            for p in sorted(glob.glob(os.path.join(a.mms_parts, "model.pt.part_*"))): f.write(open(p, "rb").read())
        sha = os.path.join(a.mms_parts, "model.pt.sha256")
        if os.path.exists(sha):
            assert hashlib.sha256(open(a.mms, "rb").read()).hexdigest() == open(sha).read().strip(), "MMS checksum mismatch"
hub = os.path.join(torch.hub.get_dir(), "checkpoints"); os.makedirs(hub, exist_ok=True)
if a.mms and not os.path.exists(os.path.join(hub, "model.pt")):
    os.symlink(os.path.abspath(a.mms), os.path.join(hub, "model.pt"))
model = bundle.get_model(with_star=False).eval(); DICT = bundle.get_dict(star=None); ur = Uroman()

def romanize(w):
    r = ur.romanize_string(w).lower()
    return "".join(c for c in r if c in DICT and c != "-")

caps = json.load(open(a.captions))
words, segs = [], []
for i, (t, text) in enumerate(caps):
    t0 = t - a.offset; t1 = (caps[i + 1][0] if i + 1 < len(caps) else t + 8) - a.offset
    if t1 <= 0 or t0 >= dur: continue
    b0, b1 = max(0.0, t0 - a.pad), min(dur, t1 + a.pad)
    raw = [w for w in re.split(r"\s+", text.strip()) if w]
    rom = [romanize(w) for w in raw]; idx = [k for k, r in enumerate(rom) if r]
    chunk = audio[int(b0 * SR):int(b1 * SR)].unsqueeze(0)
    times = {}
    if idx:
        with torch.inference_mode(): em, _ = model(chunk)
        em = torch.log_softmax(em, -1)
        tgt = [DICT[c] for k in idx for c in rom[k]]
        if em.shape[1] >= len(tgt):
            ali, sc = forced_align(em, torch.tensor([tgt], dtype=torch.int32), blank=0)
            spans = merge_tokens(ali[0], sc[0].exp()); ratio = chunk.shape[1] / em.shape[1] / SR; j = 0
            for k in idx:
                sp = spans[j:j + len(rom[k])]; j += len(rom[k])
                score = float(sum(s.score for s in sp) / len(sp))
                times[k] = (round(b0 + sp[0].start * ratio, 2), round(b0 + sp[-1].end * ratio, 2), round(score, 2))
    lw = []
    for k, w in enumerate(raw):
        s, e, sc = times.get(k, (None, None, None))
        lw.append({"start": s, "end": e, "word": w, "aligned": k in times, "score": sc})
    # interpolate unaligned (digits/symbols)
    for k, w in enumerate(lw):
        if w["start"] is None:
            p = next((lw[j]["end"] for j in range(k - 1, -1, -1) if lw[j]["end"] is not None), max(b0, t0))
            n = next((lw[j]["start"] for j in range(k + 1, len(lw)) if lw[j]["start"] is not None), min(b1, t1))
            w["start"], w["end"] = round(p, 2), round(max(p, n), 2)
    # drop words that fall before the file start (caption line began before the section)
    lw = [w for w in lw if w["end"] > 0.05]
    if lw:
        words += lw; segs.append({"start": lw[0]["start"], "end": lw[-1]["end"], "text": " ".join(w["word"] for w in lw)})

json.dump({"engine": "youtube-captions + mms_fa", "duration": round(dur, 2), "offset": a.offset, "words": words, "segments": segs},
          open(a.out, "w"), indent=1, ensure_ascii=False)
low = [w["word"] for w in words if w["aligned"] and w["score"] is not None and w["score"] < 0.2]
print(f"{a.media}: {len(words)} words, {sum(w['aligned'] for w in words)} aligned, low-confidence: {low[:15]}")
