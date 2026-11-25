#!/usr/bin/env python3
"""Render a raw clip from a cut list (JSON) with ffmpeg — frame-accurate, A/V-locked, low memory.

Usage: render_cutlist.py CUTLIST.json OUT.mp4 [--src-dir DIR]

How it stays in sync over many short segments:
  * every in/out is snapped to the output frame grid (1/fps) so each segment's audio length == video length;
  * video: each segment is encoded on its own (low memory for long 1080p sources) and joined with the concat demuxer;
  * audio: all segments are cut from 48 kHz PCM in ONE pass (no per-segment AAC padding), then muxed once.
Audio gets 25 ms fades only at real edits; where the audio simply continues (contiguous segments) it is untouched.

Cut-list schema (hand-off format for the podcast-editing skill):
{ "clip_id", "source": {...}, "output": {"width":1920,"height":1080,"fps":25},
  "segments": [ {"id", "file", "in", "out", "source_in", "source_out", "speaker", "angle", "text"} ],
  "removed": [ {"in","out","text","why"} ], "flags": [...] }
(Optional per-segment "punch": {"zoom","cx","cy_top"} is supported but OFF by default — user prefers plain cuts.)
"""
import json, subprocess, argparse, os, tempfile

ap = argparse.ArgumentParser()
ap.add_argument("cutlist"); ap.add_argument("out"); ap.add_argument("--src-dir", default=".")
a = ap.parse_args()
cl = json.load(open(a.cutlist))
from fractions import Fraction
W, H = cl["output"]["width"], cl["output"]["height"]
FPS_S = str(cl["output"].get("fps", 25)); FPS = float(Fraction(FPS_S))   # accepts 25, 29.97, "24000/1001"
snap = lambda t: round(round(t * FPS) / FPS, 6)
segs = cl["segments"]
for s in segs: s["_in"], s["_out"] = snap(s["in"]), snap(s["out"])
tmp = tempfile.mkdtemp(prefix="cut_")

# ---- video, per segment ----
parts = []
for k, s in enumerate(segs):
    nfr = int(round((s["_out"] - s["_in"]) * FPS))
    vf = f"fps={FPS_S}"
    p = s.get("punch")
    if p:
        z = p["zoom"]; cw, ch = round(W / z / 2) * 2, round(H / z / 2) * 2
        x = int(min(max(p["cx"] - cw / 2, 0), W - cw)); y = int(min(max(p.get("cy_top", (H - ch) / 2), 0), H - ch))
        vf += f",crop={cw}:{ch}:{x}:{y}"
    vf += f",scale={W}:{H}:flags=lanczos,setsar=1,format=yuv420p"
    out = os.path.join(tmp, f"v{k:03d}.mp4"); parts.append(out)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{s['_in']:.6f}", "-i", os.path.join(a.src_dir, s["file"]),
                    "-frames:v", str(nfr), "-an", "-vf", vf, "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
                    "-r", FPS_S, "-video_track_timescale", "24000", out], check=True)
lst = os.path.join(tmp, "list.txt"); open(lst, "w").write("".join(f"file '{q}'\n" for q in parts))
vcat = os.path.join(tmp, "video.mp4")
subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", vcat], check=True)

# ---- audio, one pass from PCM ----
files = sorted({s["file"] for s in segs}); idx = {f: i for i, f in enumerate(files)}
inputs = sum([["-i", os.path.join(a.src_dir, f)] for f in files], [])
chains, labels = [], []
for k, s in enumerate(segs):
    d = s["_out"] - s["_in"]
    cont_prev = k > 0 and segs[k - 1]["file"] == s["file"] and abs(segs[k - 1]["_out"] - s["_in"]) < 1e-3
    cont_next = k + 1 < len(segs) and segs[k + 1]["file"] == s["file"] and abs(segs[k + 1]["_in"] - s["_out"]) < 1e-3
    f = [] if cont_prev else ["afade=t=in:d=0.025"]
    if not cont_next: f.append(f"afade=t=out:st={max(d - 0.025, 0):.4f}:d=0.025")
    chains.append(f"[{idx[s['file']]}:a]aresample=48000,atrim=start={s['_in']:.6f}:end={s['_out']:.6f},asetpts=PTS-STARTPTS"
                  + ("," + ",".join(f) if f else "") + f"[a{k}]")
    labels.append(f"[a{k}]")
fc = ";".join(chains) + ";" + "".join(labels) + f"concat=n={len(labels)}:v=0:a=1[a]"
wav = os.path.join(tmp, "audio.wav")
subprocess.run(["ffmpeg", "-v", "error", "-y", *inputs, "-filter_complex", fc, "-map", "[a]", "-ac", "2", "-c:a", "pcm_s16le", wav], check=True)

# ---- mux ----
subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", vcat, "-i", wav, "-map", "0:v", "-map", "1:a", "-c:v", "copy",
                "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", a.out], check=True)
dur = sum(s["_out"] - s["_in"] for s in segs)
probe = lambda st: float(subprocess.run(["ffprobe", "-v", "error", "-select_streams", st, "-show_entries", "stream=duration",
                                          "-of", "csv=p=0", a.out], capture_output=True, text=True).stdout.strip() or 0)
print(f"rendered {a.out}: {len(segs)} segments, cut list {dur:.3f}s | video {probe('v:0'):.3f}s audio {probe('a:0'):.3f}s")
