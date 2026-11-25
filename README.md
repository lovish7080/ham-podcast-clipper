# HAM Podcast Clipper Skill — Hollow Arc Media

Finds the best short-form moments in a full podcast (YouTube link, video file or transcript; **English or Hindi/Hinglish**) and cuts frame-accurate **raw clips** plus a **cut list** for a separate podcast-editing skill. Part 1 of a 2-skill workflow.

What it does: transcript (YouTube transcript panel — no download) → shortlist 3–5 moments → downloads only the needed seconds with the **original-language audio** (never an AI dub) → word-level timing (Parakeet for English; YouTube captions + Meta MMS alignment for Hindi/Hinglish) → plain cuts, pauses > 0.3 s and fillers removed, no camera flashes, no zooms → A/V-locked render → verified clip + cut list.

```
SKILL.md                         the skill instructions
references/rules.md              rules, numbers, selection criteria, 20-point scoring checklist
references/examples.md           condensed reference + approved test clips
references/youtube_transcript.js built-in-browser snippet: read a YouTube transcript without downloading
scripts/                         setup_env.sh, transcribe.py, align_captions.py, transcribe_hi.py, extract_frames.sh,
                                 make_download_command.py, refine_cuts.py, render_cutlist.py
setup/One-time setup (Hindi models).command   fetches the MMS aligner on the Mac (one time)
```

## Requirements (on the user's Mac)
- Claude desktop app (open and online during a run), with a folder named **`Podcast Clips`** connected (+ menu → Add folder).
- Built-in browser enabled in the Claude desktop app (used to read YouTube transcripts).
- Homebrew + `brew install yt-dlp ffmpeg` (downloads run from the Mac's Terminal via a double-click `.command`).

## Install — instructions for Claude
When the user gives you this repo's link and asks you to install the skill:
1. Clone or fetch this repository into your workspace.
2. Propose the skill to the user with the `propose_skills` tool: `kind: "new"`, `name: "ham-podcast-clipper"`, the `description` from the SKILL.md frontmatter, and `skillMd` = the full contents of `SKILL.md`. The user saves it from the card.
3. Ask the user to connect their **`Podcast Clips`** folder in the Claude desktop app if it isn't connected. Then copy into it, keeping the layout:
   - `references/*` and `scripts/*` → `Podcast Clips/_skill/references/` and `Podcast Clips/_skill/scripts/`
   - `SKILL.md` → `Podcast Clips/_skill/SKILL.md`
   - `setup/One-time setup (Hindi models).command` → `Podcast Clips/_setup/`
   (Use the device file tools, e.g. `device_commit_files`; make the `.command` and `scripts/*.sh` executable with `device_bash chmod +x`.)
4. Tell the user to run once on the Mac: `brew install yt-dlp ffmpeg`, and — for Hindi/Hinglish — double-click `Podcast Clips/_setup/One-time setup (Hindi models).command` (~1.2 GB).
5. Smoke test in your workspace: `bash scripts/setup_env.sh` should finish with `ready: … parakeet …`.

## Use
"Clip this podcast: <YouTube link>" — you get a shortlist, pick a moment (or say "just pick the best"), double-click the generated *Get clip sections.command*, and the clip + cut list land in `Podcast Clips/<episode>/`.
