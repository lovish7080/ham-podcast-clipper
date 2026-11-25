# HAM Podcast Clipper — rules and numbers

Derived from 9 Hollow Arc Media reference clips (Phase 1–2) and the user's feedback on 4 test clips (Phase 3).
Feedback rules override reference patterns where they differ.

## Reference clip numbers (finished shorts, n = 9)
| Measure | Median | Range |
|---|---|---|
| Clip length | 35.4 s | 13.6–52.8 s |
| First line (hook) | 2.4 s | 1.2–16 s |
| Interviewer question | 4.4 s | 2.1–16 s |
| Interviewer share of talk | 16 % | 6–39 % |
| Speaking pace | 194 wpm | 167–334 wpm |
| Raw camera-angle hold (C3, C6 raw panels) | 4.0–4.5 s | 1.4–8.9 s |
| Visual change in finished edit (incl. graphics) | 3.0 s | 2.2–4.5 s |

Shape that recurs: **question (2–7 s) → one-line thesis (1–3 s) → ONE device (example / analogy / list / evidence, 10–25 s) → payoff line (2–5 s), cut on the last word.**

## Length
- Target 35–45 s. Minimum ~30 s (a single aphorism can carry 14–22 s — flag it). **Hard maximum 60 s.**
- End where the idea is complete. If the follow-up adds nothing, stop on the reveal line (user: "the video feels complete at '…3-4 degree difference ho gaya'").

## Hook / opening
- First line = the hook. No warm-up ("great question", "so", "let me be specific").
- Open on the interviewer's question, trimmed to its core (≤ 7 s target; long only if the question IS the promise).
- **If the question does not stand alone** (e.g. lacks the context the answer gives — "why is a beer harder to buy than a gun?" without saying *in the US*): **drop it and open on the guest's answer**, or move it later where it has context. (User feedback.)
- **Cold open allowed** when a later guest line is clearly stronger and would stop the scroll AND supports the story.
- A question that spoils the twist (mentions the reveal) is a weak hook.

## Structure inside the answer
- Thesis in the first answer sentence. One supporting device only. Then the payoff.
- **Stitching non-adjacent moments is allowed** when it makes the story clearly more impactful. Log every stitch in `removed`.

## Tightening (user: "make it crisp")
- Remove every pause **> 0.3 s** (keep 0.2–0.3 s pauses — they sound natural).
- Remove fillers and restarts: um/uh/"you know"/"like" (when filler)/"okay," · Hindi: अ, अह, हम्म, "हम उसी…" restarts, repeated half-phrases.
- Remove false starts and stumbles ("but not choking, choking", "in my back in my car").
- Remove tangents, process detail, credibility-denting asides ("I'm forgetting exactly where").
- Same-angle **jump cuts are fine** — they are the consequence of tightening.

## Camera / cutting (user feedback — strict)
- **Plain cuts only. NO zooms / punch-ins / crops.** Use only the angles the source already has.
- **Never leave a camera flash:** no shot shorter than ~1.5 s at a join; never let a segment start/end within 1 s of a source camera switch — move the edge onto the switch (refine_cuts.py does this).
- Out-points end ≥ 1 frame before the next source camera cut.
- Long single-angle holds (> 8 s) and burned-in overlays (subscribe pop-ups, lower thirds) are NOT fixed in the clipper — list them in `flags` for the editing skill.

## Edit points (user feedback — strict)
- Cut audio at the energy minimum **between** words; never keep a partial word ("bec-" from "because").
- Let each kept word finish (word-aware snapping in refine_cuts.py extends the out-point to where the voice dies, stopping before the next word).
- No audio fade inside continuous speech; 25 ms fades only at real edits.
- Snap all cuts to the frame grid; audio and video durations must match exactly (render_cutlist.py prints both).

## Source / audio
- Always the **original-language audio track** — many Indian podcasts default to an English AI dub on YouTube. Verify language after download (Parakeet on an English dub gives clean English; on Hinglish it catches only the English words).
- Whisper auto-detect mislabels English-heavy Hinglish as English (and translates). Don't trust it for the language check — compare with the YouTube caption track language.

## Selection criteria
Clip-worthy:
- Universal / high-stakes question (life advice, money, career, identity, health, the future, India-relevant issues).
- Quotable thesis in the first answer sentence; contrarian or surprising.
- One concrete device: a number, an experiment, a vivid analogy, a named example.
- A natural landing line (punchline, CTA, rhetorical question, a number).
- Conviction / energy in delivery; guest-dominant (interviewer ≤ 20 %).
Disqualifiers:
- Needs earlier context; no thesis; payoff never comes within 60 s; answer cut off by the source (e.g. an excerpt that ends mid-sentence).
- Interviewer > ~40 % or crosstalk; best line buried mid-ramble; unexplained jargon; ad reads; defamatory claims about third parties.

## Scoring checklist (0–2 each, /20)
1. Hook is a question or bold claim ≤ 7 s, and stands alone
2. Understandable with zero context
3. Thesis in the first answer sentence
4. One concrete device (number, analogy, list, experiment)
5. Clean payoff line to end on
6. 30–60 s after tightening
7. Interviewer ≤ 20 % of talk
8. Universal / high-stakes topic for the target audience
9. Conviction / energy in delivery
10. Clean cutting: no flashes, no partial words, no pauses > 0.3 s, A/V in sync
Report the score honestly with the specific shortfalls.
