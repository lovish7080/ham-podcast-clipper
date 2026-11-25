// HAM Podcast Clipper — read a YouTube episode's transcript in the BUILT-IN BROWSER (browser_repl), no download.
// Direct timedtext API fetches return empty (YouTube requires a token); the transcript panel works.
// 1) open:   let tab = await browser.tabs.create("https://www.youtube.com/watch?v=VIDEO_ID");
// 2) run the block below in the next script (narrow layouts need the visible "more" button first).
const p = tab.page;
const meta = await p.evaluate(() => {
  const pr = window.ytInitialPlayerResponse;
  const tr = pr?.captions?.playerCaptionsTracklistRenderer?.captionTracks || [];
  const fm = (pr?.streamingData?.adaptiveFormats || []).filter(f => f.audioTrack)
    .map(f => ({ name: f.audioTrack.displayName, id: f.audioTrack.id, def: f.audioTrack.audioIsDefault }));
  const u = {}; fm.forEach(f => u[f.id] = f);
  return { title: pr?.videoDetails?.title, seconds: pr?.videoDetails?.lengthSeconds,
           captions: tr.map(t => `${t.languageCode}:${t.kind || 'manual'}`), audioTracks: Object.values(u) };
});
console.log(JSON.stringify(meta));   // audioTracks with "original" ≠ default ⇒ the default is an AI dub
await p.getByRole('button', { name: /^more$/i }).filter({ visible: true }).first().click().catch(() => {});
await p.getByRole('button', { name: /show transcript/i }).filter({ visible: true }).first().click();
await p.locator('ytd-transcript-segment-renderer, transcript-segment-view-model').first().waitFor({ timeout: 15000 });
const raw = await p.evaluate(() => [...document.querySelectorAll('ytd-transcript-segment-renderer, transcript-segment-view-model')]
  .map(el => el.textContent.replace(/\s+/g, ' ').trim()));
const toS = t => t.split(':').reduce((a, b) => a * 60 + (+b), 0);
// each row reads "1:08:37" + "1 hour, 8 minutes, 37 seconds" + text; the last clock digit can merge with the spoken form
globalThis.LINES = raw.map(r => {
  const m = r.match(/^(\d+(?::\d{2})+)((?:\d+ (?:hours?|minutes?|seconds?),? ?)+)(.*)$/);
  if (!m) return null;
  const parts = m[1].split(':'); const last = parts.pop();
  return [toS(parts.concat(last.slice(0, 2)).join(':')), m[3].replace(/\[.*?\]/g, '').trim()];
}).filter(Boolean);
console.log('lines', LINES.length);
// 3) print in ~35k-char chunks:  console.log(LINES.map(([t,x]) => t + ' ' + x).join('\n').slice(0, 35000));
// 4) for Hindi/Hinglish: print the lines covering a section as JSON → save as captions.json for align_captions.py
//    console.log(JSON.stringify(LINES.filter(([t]) => t >= START - 5 && t <= END + 5)));
