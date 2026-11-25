#!/usr/bin/env python3
"""Snap a draft cut list's in/out points to safe, clean edit points.

For every segment boundary it:
  1. searches +/- WINDOW s around the draft time for the audio-energy minimum (the gap between words),
     preferring the earliest deep dip after the last kept word (out) / the latest dip before the first
     kept word (in) — so partial words like "bec-" are never kept;
  2. moves the point so it sits >= 1 frame away from any camera cut in the source (no 1-2 frame flashes);
  3. trims leading/trailing silence longer than MAX_SIL s inside the segment;
  4. reports any segment shorter than MIN_SHOT s or any camera shot inside a segment shorter than 1.5 s.

Usage: refine_cuts.py DRAFT.json OUT.json --src-dir DIR [--scene 0.08]
DRAFT.json uses the cut-list schema (render_cutlist.py) — each segment needs file/in/out;
optional "first_word_start"/"last_word_end" (from the transcript) let it protect the kept words.
"""
import argparse, json, os, subprocess, re
import numpy as np

ap = argparse.ArgumentParser()
ap.add_argument("draft"); ap.add_argument("out"); ap.add_argument("--src-dir", default=".")
ap.add_argument("--scene", type=float, default=0.08); ap.add_argument("--window", type=float, default=0.15)
ap.add_argument("--max-sil", type=float, default=0.15)
ap.add_argument("--words", default=None, help="transcript JSON (word timings) of the source: enables word-boundary-aware snapping"); ap.add_argument("--fps", type=float, default=25)
a = ap.parse_args()
cl = json.load(open(a.draft)); F = 1.0 / a.fps; SR = 16000; STEP = 0.01

cache = {}
def load(f):
    if f in cache: return cache[f]
    p = os.path.join(a.src_dir, f)
    pcm = subprocess.run(["ffmpeg", "-v", "error", "-i", p, "-ac", "1", "-ar", str(SR), "-f", "s16le", "-"], capture_output=True).stdout
    x = np.frombuffer(pcm, np.int16).astype(np.float32) / 32768
    n = int(STEP * SR); db = np.array([20 * np.log10(np.sqrt(np.mean(x[i:i + n] ** 2)) + 1e-9) for i in range(0, len(x) - n, n)])
    log = subprocess.run(["ffmpeg", "-v", "info", "-i", p, "-vf", f"select='gt(scene,{a.scene})',metadata=print", "-an", "-f", "null", "-"],
                         capture_output=True, text=True).stderr
    cuts = [float(m) for m in re.findall(r"pts_time:([0-9.]+)", log)]
    cache[f] = (db, cuts); return cache[f]

def snap_audio(db, t, lo, hi):
    i0, i1 = max(0, int(lo / STEP)), min(len(db) - 1, int(hi / STEP))
    if i1 <= i0: return t
    seg = db[i0:i1 + 1]; k = int(np.argmin(seg)); return round((i0 + k) * STEP + STEP / 2, 3)

def avoid_cam(t, cuts, kind):
    for c in cuts:
        if kind == "out" and c - F * 0.5 < t < c + F * 1.5: return round(c - F * 0.5, 3)   # end just before the cut
        if kind == "in" and c - F * 1.5 < t < c + F * 0.5: return round(c + F * 0.5, 3)    # start just after the cut
    return t

WORDS = json.load(open(a.words))["words"] if a.words else None
def quiet_floor(db, t):
    i0, i1 = max(0, int((t - 1.5) / STEP)), min(len(db), int((t + 1.5) / STEP))
    return np.percentile(db[i0:i1], 10)
def end_of_voice(db, t, limit):
    """first point after t (<= limit) where the voice has died away (near the local noise floor) for >= 30 ms"""
    fl = quiet_floor(db, t); k = int(t / STEP); run = 0
    while k * STEP < limit and k < len(db):
        run = run + 1 if db[k] < fl + 10 else 0
        if run >= 3: return round((k - 2) * STEP + STEP, 3)
        k += 1
    return round(limit, 3)
def start_of_voice(db, t, limit):
    """last quiet point before t (>= limit)"""
    fl = quiet_floor(db, t); k = int(t / STEP); run = 0
    while k * STEP > limit and k > 0:
        run = run + 1 if db[k] < fl + 10 else 0
        if run >= 3: return round((k + 2) * STEP, 3)
        k -= 1
    return round(limit, 3)
notes = []
segs = cl["segments"]
# contiguous neighbours (same file, out == next in): snap the shared boundary once, later copy it to both
shared = [i for i in range(len(segs) - 1) if segs[i]["file"] == segs[i + 1]["file"] and abs(segs[i]["out"] - segs[i + 1]["in"]) < 0.02]
for s in segs:
    db, cuts = load(s["file"])
    fw, lw = s.get("first_word_start", s["in"] + a.window), s.get("last_word_end", s["out"] - a.window)
    # in-point: quietest spot between (in - window) and the first kept word
    s["in"] = snap_audio(db, s["in"], s["in"] - a.window, min(fw, s["in"] + a.window))
    # out-point: quietest spot between the last kept word's end and (out + window)
    s["out"] = snap_audio(db, s["out"], max(lw, s["out"] - a.window), s["out"] + a.window)
    if WORDS:
        nxt = [w for w in WORDS if w["start"] > s["out"] - 0.02]
        prv = [w for w in WORDS if w["end"] is not None and w["end"] < s["in"] + 0.02]
        lim_out = (nxt[0]["start"] - 0.02) if nxt else s["out"] + 0.4
        lim_in = (prv[-1]["end"] + 0.02) if prv else s["in"] - 0.4
        s["out"] = max(s["out"], end_of_voice(db, s["out"] - 0.05, min(lim_out, s["out"] + 0.45)))
        s["in"] = min(s["in"], start_of_voice(db, s["in"] + 0.05, max(lim_in, s["in"] - 0.45)))
    # trim silence > max_sil at both ends
    th = np.percentile(db[int(s["in"] / STEP):int(s["out"] / STEP)], 30) if s["out"] > s["in"] + 0.2 else -60
    i = int(s["in"] / STEP)
    while i < int(s["out"] / STEP) and db[i] < th - 6: i += 1
    if (i * STEP - s["in"]) > a.max_sil: s["in"] = round(i * STEP - a.max_sil / 2, 3)
    j = int(s["out"] / STEP)
    while j > i and db[j] < th - 6: j -= 1
    if (s["out"] - j * STEP) > a.max_sil: s["out"] = round(j * STEP + a.max_sil / 2 + STEP, 3)
    s["in"], s["out"] = avoid_cam(s["in"], cuts, "in"), avoid_cam(s["out"], cuts, "out")
for i in shared:   # a shared boundary keeps the out-point of the first segment (gap-free, no repeated audio)
    t = segs[i]["out"]; _, cuts = load(segs[i]["file"])
    near = [c for c in cuts if abs(c - t) <= 0.08]
    if near: t = round(near[0], 3)          # boundary sits on a source camera cut: put it exactly on the cut
    segs[i]["out"] = segs[i + 1]["in"] = t
for s in segs:
    db, cuts = load(s["file"])
    # never leave a sliver of another angle (< 1 s) at either end of a segment: move the edge onto the camera cut
    for c in cuts:
        if s["in"] < c < s["out"] and s["out"] - c < 1.0: s["out"] = round(c - F * 0.5, 3); s.setdefault("warn", []).append(f"out moved onto camera cut {c}")
        if s["in"] < c < s["out"] and c - s["in"] < 1.0: s["in"] = round(c + F * 0.5, 3); s.setdefault("warn", []).append(f"in moved onto camera cut {c}")
    inner = [c for c in cuts if s["in"] < c < s["out"]]
    bounds = [s["in"]] + inner + [s["out"]]; shots = [round(b - a_, 2) for a_, b in zip(bounds, bounds[1:])]
    s["camera_cuts_inside"] = inner; s["shots"] = shots
    if len(shots) > 1 and min(shots) < 1.5: notes.append(f"segment {s.get('id')}: a camera shot of {min(shots)} s inside (source edit) — consider moving in/out")
    if max(shots) > 8 and not s.get("punch"): notes.append(f"segment {s.get('id')}: {max(shots)} s single-angle hold — add a steady punch-in")
cl["refine_notes"] = notes
json.dump(cl, open(a.out, "w"), indent=1, ensure_ascii=False)
for s in cl["segments"]: print(s.get("id"), s["in"], s["out"], "shots:", s["shots"])
print("\n".join(notes) or "no warnings")
