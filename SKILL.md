---
name: ham-podcast-clipper
description: HAM Podcast Clipper Skill (Hollow Arc Media) — find the best short-form moments in a full podcast (YouTube link, video file, or transcript; English or Hindi/Hinglish) and cut frame-accurate raw clips plus a cut list for the podcast-editing skill.
---

# HAM Podcast Clipper Skill (Hollow Arc Media)

Part 1 of a 2-skill workflow. This skill **finds and cuts the raw clip** (16:9, source resolution, plain cuts) and writes a **cut list** that the separate *podcast-editing* skill picks up (captions, B-roll, reframing, graphics happen there — not here).

## Files this skill depends on
Everything lives in the user's connected folder **`Podcast Clips/_skill/`** (on Lovish's Mac: `~/My Editing Workspace/Claude Workspace/Podcast Clips/_skill/`). At the start of every run, stage these into the workspace (device_stage_files) and read the references:
- `references/rules.md` — **the rules, numbers, selection criteria and scoring checklist. Read it first, every run.**
- `references/examples.md` — condensed reference + approved test clips.
- `references/youtube_transcript.js` — built-in-browser snippet that reads a YouTube transcript without downloading.
- `scripts/setup_env.sh` — installs deps + fetches models from GitHub into the cloud workspace.
- `scripts/transcribe.py` — English: Parakeet-TDT word timestamps.
- `scripts/align_captions.py` — Hindi/Hinglish: aligns YouTube captions to audio with MMS_FA (word timestamps).
- `scripts/transcribe_hi.py` — fallback for non-English with NO captions: Whisper turbo + MMS (flag output as unreliable).
- `scripts/extract_frames.sh` — 2 fps frames + scene-change list.
- `scripts/make_download_command.py` — writes the double-click `.command` that downloads only the needed sections, original audio.
- `scripts/refine_cuts.py` — snaps cuts to word gaps / camera cuts, trims silence, warns on flashes and long holds.
- `scripts/render_cutlist.py` — frame-exact, A/V-locked render from the cut list.
- `_setup/mms_fa/model.pt.part_*` — Hindi aligner (made once by `_setup/One-time setup (Hindi models).command`). Stage in ≤ 1 part per call (500 MB limit); align scripts reassemble + checksum it via `--mms-parts`.

If `_skill/` or the folder is missing: ask the user to open this chat in the Claude desktop app and **Add folder → Podcast Clips**.

## Environment facts (don't rediscover)
- Neither the cloud workspace nor the Mac's sandbox (device_bash) can reach YouTube, Hugging Face or Meta's model servers. GitHub and PyPI work.
- The **built-in browser** on the Mac can open YouTube → use it for metadata + transcripts.
- Only the **Mac's own Terminal** can download from YouTube, and Claude may not type in Terminal. So downloads happen through a `.command` file **the user double-clicks** (one per episode/batch). One-time: `brew install yt-dlp ffmpeg`.
- Never upscale, never zoom.

## Inputs
| Input | Path |
|---|---|
| YouTube link (default) | transcript via browser → shortlist → `.command` downloads sections → cut |
| Single multicam program video file (most common) | transcribe file directly; angles come from the program's own edit |
| Separate camera files (true multicam) | sync by audio, pick angles per segment (cut list `file` per segment) — no zooms |
| Transcript only | shortlist + exact cut list; cannot render — say so |

## Workflow

### 1. Prepare
`bash setup_env.sh` (add `HINDI=1` for Hindi/Hinglish). Read `rules.md`. Make a task list.

### 2. Get the transcript
- **YouTube:** open the link in the built-in browser, run `youtube_transcript.js`. Record: title, length, caption tracks, **audio tracks** (an "original" track that isn't the default ⇒ the default is an AI dub). Print the transcript in ~35k-char chunks and read all of it.
- **File:** English → `transcribe.py`; Hindi/Hinglish with captions available → captions + `align_captions.py`; otherwise `transcribe_hi.py` (warn: Whisper int8 can loop and drop English words on Hinglish).
- **Language routing:** use the YouTube caption track language / the user's word. Don't trust Whisper auto-detect on Hinglish (it says "en" and translates).

### 3. Shortlist 3–5 candidates
Apply the selection criteria in `rules.md`. For each: episode timestamps, hook line, thesis, device, payoff line, est. length, why it works, risks.
**Default: stop here and let the user pick.** If the user said "just pick the best", continue with the top one.

### 4. Fetch only what's needed (YouTube)
`make_download_command.py "<episode folder>/Get clip sections.command" --url … --lang hi|en --section NAME START END …` with ~3 s padding per side (several clips → one command). Write it into `Podcast Clips/<episode short name>/` on the Mac. Ask the user to double-click it (right-click → Open the first time).
After download: read `sections/download_log.txt` (chosen audio format + yt-dlp version) and `offsets.txt`; **verify the language** of the audio before cutting.

### 5. Word timing + camera map
- English: `transcribe.py SECTION.mp4 words.json`.
- Hindi/Hinglish: save the caption lines covering the section as `[[sec, "text"], …]` → `align_captions.py SECTION.mp4 caps.json words.json --offset <section start sec> --mms-parts <staged _setup/mms_fa dir>`.
- Camera cuts: `ffmpeg … select='gt(scene,0.08)'` (dark studios need 0.08, not 0.3) + a 1 fps contact sheet; look at it — note angles, burned-in pop-ups, logos.

### 6. Build the draft cut list
Keep-spans in section time; for each: `file, in, out, first_word_start, last_word_end, speaker, angle, text`. Apply `rules.md`: hook that stands alone (or answer-first / cold open), one device, end on the payoff, remove pauses > 0.3 s + fillers + restarts + tangents, stitch only when it clearly helps. Log every removal in `removed` with `why`. Output fps = source fps (`"24000/1001"` style allowed), size = source size.

### 7. Refine and render
```
python3 refine_cuts.py draft.json cutlist.json --src-dir . --window 0.08 --fps <src fps> --words words.json
python3 render_cutlist.py cutlist.json <clip>_raw.mp4 --src-dir .
```
Fix every `refine_notes` warning that is a real problem (a flash, a long hold → flag).

### 8. Verify (always, before showing the user)
- `render_cutlist.py` must print equal video/audio durations.
- Re-transcribe the render (or align for Hindi): no partial words, no missing words at joins.
- Audio energy at every join: quiet before the cut (≲ −30 dB) unless the speech is continuous.
- Frame strips (25 fps) around every join: no flashes of another angle.
- Silence scan of the render: no pauses > 0.3 s.

### 9. Deliver
Save `<clip>_raw.mp4` + `<clip>_cutlist.json` to `Podcast Clips/<episode>/` (device_commit_files) and send the clip (SendUserFile). Report: what the clip is, the cut list summary (episode in/out per segment, angle), what was removed, the **score /20 with honest shortfalls**, and flags for the editing skill. Iterate on feedback; version files `_v2`, `_v3`.

## Cut list = hand-off format
```json
{ "clip_id": "...", "version": 1, "language": "en|hi",
  "transcript_engine": "parakeet | youtube-captions + mms_fa | whisper-turbo + mms_fa",
  "source": {"url": "...", "title": "...", "audio_track": "...", "source_type": "single multicam program"},
  "output": {"width": 1920, "height": 1080, "fps": 25},
  "structure": "hook → thesis → device → payoff",
  "segments": [{"id": 1, "file": "A.mp4", "in": 8.85, "out": 13.32, "source_in": "1:17:41.85", "source_out": "1:17:46.32",
                "speaker": "guest", "angle": "guest wide → close side", "text": "..."}],
  "removed": [{"in": 13.32, "out": 14.85, "text": "...", "why": "..."}],
  "flags": ["burned-in subscribe pop-up at clip 46–50 s", "single-angle hold 17 s at clip 6–24 s", "source 624x352"] }
```

## Hard rules learned from the user (never break)
1. Plain cuts only — **no zooms/punch-ins/crops**.
2. Crisp: no pause > 0.3 s; no fillers; no partial words.
3. No split-second flashes of another camera angle.
4. A hook question must stand alone; otherwise open on the answer.
5. End on the line where the idea is complete.
6. Always the original-language audio track.
7. Max 60 s.
