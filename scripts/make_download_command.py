#!/usr/bin/env python3
"""Write a double-clickable macOS .command that downloads ONLY the needed sections of a YouTube video,
with the ORIGINAL-language audio track (never an AI dub), into <episode folder>/sections/.

Usage:
  make_download_command.py OUT.command --url URL --lang hi|en|... --section NAME START END [--section ...]
  make_download_command.py OUT.command --url URL --lang en --audio-only      # whole-episode audio (no captions case)
START/END: episode time "H:MM:SS" or seconds. Add ~3 s padding yourself (the cut is made later, frame-exact).

The script it writes:
  * logs `yt-dlp --version` and `yt-dlp -F` to sections/download_log.txt (Claude reads this if anything fails)
  * picks the audio format whose line says "original" or matches [LANG], excluding dubbed/default-dub tracks
  * refuses to download if no original-language track is found (never silently takes the dub)
  * appends NAME|START|END|audio=ID to sections/offsets.txt (episode time of each file's t=0)
"""
import argparse, os, stat

ap = argparse.ArgumentParser()
ap.add_argument("out"); ap.add_argument("--url", required=True); ap.add_argument("--lang", default="en")
ap.add_argument("--section", nargs=3, action="append", metavar=("NAME", "START", "END"), default=[])
ap.add_argument("--audio-only", action="store_true")
a = ap.parse_args()

sections = "\n".join(f"{n}|{s}|{e}" for n, s, e in a.section)
script = f'''#!/bin/bash
# HAM Podcast Clipper — downloads ONLY what the clip needs (never the full video), ORIGINAL audio track.
export PATH="/opt/homebrew/bin:/usr/local/bin:$HOME/.local/bin:$PATH"
cd "$(dirname "$0")"
URL="{a.url}"
WANT_LANG="{a.lang}"
AUDIO_ONLY={"1" if a.audio_only else "0"}
SECTIONS="
{sections}
"
for tool in yt-dlp ffmpeg; do command -v $tool >/dev/null || {{ echo "Missing $tool. Install once: brew install yt-dlp ffmpeg"; read -p "Enter to close"; exit 1; }}; done
mkdir -p sections
LOG=sections/download_log.txt
{{ echo "yt-dlp $(yt-dlp --version)"; date; }} > $LOG
yt-dlp -F --no-playlist "$URL" >> $LOG 2>&1
# original-language audio: a line that says "original", else one tagged [LANG]; never a dub
AID=$(grep -E "audio only" $LOG | grep -iE "original" | grep -E "m4a|webm" | awk '{{print $1}}' | tail -1)
[ -z "$AID" ] && AID=$(grep -E "audio only" $LOG | grep -E "\\[$WANT_LANG[]-]" | grep -viE "dubbed" | grep -E "m4a|webm" | awk '{{print $1}}' | tail -1)
[ -z "$AID" ] && ! grep -qiE "dubbed" $LOG && AID="ba"     # no dubs on this video: plain best audio is the original
echo "chosen audio format: ${{AID:-NONE}}" | tee -a $LOG
if [ -z "$AID" ]; then echo "Could not identify the original-language audio. Nothing downloaded — tell Claude."; read -p "Enter to close"; exit 1; fi
if [ "$AUDIO_ONLY" = "1" ]; then
  yt-dlp -f "$AID" --no-playlist -x --audio-format m4a -o "sections/episode_audio.%(ext)s" "$URL" 2>&1 | tee -a $LOG
else
  echo "$SECTIONS" | while IFS='|' read -r NAME S E; do
    [ -z "$NAME" ] && continue
    echo "== $NAME ($S – $E)"
    yt-dlp -f "bv*[height<=1080][ext=mp4]+$AID/bv*[height<=1080]+$AID" --no-playlist --download-sections "*$S-$E" \\
      --force-keyframes-at-cuts --merge-output-format mp4 -o "sections/$NAME.%(ext)s" "$URL" 2>&1 | tee -a $LOG
    echo "$NAME|$S|$E|audio=$AID" >> sections/offsets.txt
  done
fi
echo; echo "Done."; ls -lh sections; read -p "Press Enter to close"
'''
os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
open(a.out, "w").write(script)
os.chmod(a.out, os.stat(a.out).st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
print("wrote", a.out)
