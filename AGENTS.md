# AGENTS.md — quickstart for AI agents

You were given this repo and asked for a video. This page is the whole loop: what you need, what to ask, the
pipeline, the QA gates every video must pass, and the rules. The craft details (motion principles, styles,
pose packs) are in [SKILL.md](SKILL.md); read it once before you start.

**Goal:** a polished 1080p MP4 where objects and characters *do the action the voiceover describes*, synced to
the VO, with a sound on every action and a clean VO-led mix. Not a slideshow.

---

## 1. Prerequisites

| Need | Why | Check |
|---|---|---|
| Python 3.9+ and `pip install -r requirements.txt` (numpy, opencv-python-headless, Pillow) | engine | `python3 -c "import numpy, cv2, PIL"` |
| `ffmpeg` + `ffprobe` on PATH | encoding, loudness metering (ebur128 / loudnorm) | `ffmpeg -version` |
| An **image generator** that can (a) output a transparent background, or a flat `#00FF00` background you key out, and (b) take **reference images** (first ref = canvas/style/character to copy) | every cut-out, pose pack, sprite sheet, background | generate one test asset first |
| A **TTS** with an API key in an env var, e.g. `CARTESIA_API_KEY` (see `examples/tts.py`, `examples/zebra/audio/make_vo.py`). ElevenLabs etc. work too | voiceover, ideally with word/phrase timestamps | `echo ${CARTESIA_API_KEY:+set}` |

**Never hard-code an API key** in a script, commit, log or message. Read it from the environment. If it is
missing, ask the human to set it.

No image generator with reference images? Say so up front: pose packs and matched cut-outs depend on it.
Never fall back to SVG / vector / code-drawn characters.

## 2. Ask the human first (one short message)

1. **Topic + length** (default: 15–30 s) and **who it's for** (platform/aspect: 16:9 default; 9:16 for Reels/Shorts).
2. **Style** (claymation · desi flat illustration · paper cut-out · 3D toy · or "match this reference image").
3. **Voice + language** (their own cloned voice? Hinglish/Hindi/English?) and **credit line** exactly as they want it.
4. Anything **factual** on screen (medical, numbers)? They (or an expert) must check it before publishing.

Offer a default for each so a one-word answer works. Don't ask more than this; decide the rest yourself.

## 3. Pipeline

Work in a new folder, e.g. `examples/<name>/` (copy the closest example: `zebra/` for characters,
`varnish/` or `chai/` for objects). Keep generated PNG/WAV assets out of git (see `.gitignore`).

1. **Script + beats.** ~150 words/min. For every sentence write the on-screen action (verb + object). A sentence
   with no action gets rewritten.
2. **VO + timing.** Generate the VO, then measure timing: TTS word timestamps if available, otherwise phrase
   starts/ends from the energy envelope (`examples/zebra/audio/make_vo.py --timing-only` → `vo_timing.json`).
   The VO drives the edit; place each phrase in the cut (`VO_AT`) and key every action to it.
3. **Assets.**
   - One style frame / background (or a wide panorama: blank wide canvas as FIRST ref + style frame).
   - Every object a separate transparent cut-out. Pass the **first good asset as the style reference** to every
     later generation so the set matches.
   - Characters: **pose packs only** (SKILL.md → "Characters that ACT"). Master pose first, then 5–10 key poses
     with the master as FIRST reference; walk/run as sprite sheets (`engine/sheets.py`); front/back stepping
     sheets registered on the master canvas.
   - Run the cut-out QA gates (§4 A–C) before animating anything.
4. **Scene code.** One `scene.py` exposing `frame(t, step)`, `W, H, FPS, DUR` (render loop under
   `if __name__ == '__main__':`). Engine: `motion.py` (easing, squash, paste, paths, camera, finish),
   `posepack.py` (Cast, seq, anchors), `sheets.py` (cycles). Hard cuts between poses; cycle fps from ground
   speed; props on anchors; actions timed to VO phrase/word times.
5. **SFX.** A sound on every action: procedural (`engine/sfx.py`, `examples/zebra/audio/make_sfx.py`) or
   your own WAVs. Log each cue as `(t, name)` from the same timing constants the visuals use.
6. **Mix.** `engine/mix.py` `Mix`: VO stem alone to −16 LUFS, beds ~−30 LUFS, per-SFX loudness targets,
   sidechain ducking, master limiter. Run `verify()` / `check()` (§4 G).
7. **Preview sheet.** Render 6–8 stills at the key beats (`PREVIEW=1.0,4.0,…`), tile them into one contact
   sheet, **look at it** (§4 F), fix, repeat.
8. **~20 s sample for approval.** Render the strongest ~20 s (or the whole thing if shorter) and send it to the
   human. Wait for "yes" on look, voice and pacing before the full render.
9. **Full render.** `python3 engine/chunkrender.py examples/<name>/scene.py --chunks 8 --audio mix.wav --loudnorm --out final.mp4`
   (or one `--chunk i` per shell call, then `--join`, when commands time out at ~2 min). Run the file-size and
   final audio gates, then deliver.

Send progress as you go (first assets, preview sheet, sample). Silence for an hour then a finished video is
worse than three check-ins.

## 4. QA gates (every video, before the human sees it)

Fail a gate → fix or regenerate, don't hide it. Tools in brackets.

**A. Alpha coverage (every cut-out).** `alpha_coverage(im)` must be well under 1.0 (full body ≈ 0.05–0.6).
1.0 = keying failed / opaque background → regenerate (with a registered pose as first ref). Also check the
canvas size matches its siblings. [`engine/posepack.py`: `alpha_coverage`, `check_registration`]

**B. Green / halo despill.** `green_fringe(im)` > ~0.05 means a visible green rim. Apply `despill_edge(im)` at
load time (clamps G to max(R,B) on a 4 px edge ring, erodes alpha 1 px) and inspect one cut-out over a dark
and a light background. [`posepack.despill_edge`, `posepack.green_fringe`]

**C. Pose registration.** All poses of a character share one canvas; feet baseline (alpha bottom) within a few
px of the median; figure heights within ~4 % (raised arms excepted). Outliers → `Cast(fix_scale={...})` or
regenerate with a registered pose as FIRST ref. Intentional lifts (tiptoe, hop) are fine, but decide that
consciously. [`python3 engine/posepack.py 'girl/girl_*.png'`]

**D. Walk check.** Contact-sheet every cycle (`python3 engine/sheets.py walk_check.png frame*.png`): legs must
**alternate** between frames, feet sit on the red baseline, no frame with different arms/props (it flickers;
drop it). Same leg forward everywhere → `sheets.mirror_legs_below_hem(im, hem_y)` for the alternate frames.
Cycle fps = ground speed ÷ stride × frames per step (`sheets.cycle_fps`), same screen units, scaled with the
character. Never slide a static pose across the ground.

**E. Hi-fi / contact registration.** Anything that must touch (hands in a hi-fi, cup to lips, brush to tooth):
test-draw both characters at the **impact time** off-screen, read the contact points with `cast.world(anchor)`,
and shift/hop one so they overlap by a few px, including sway, the pose-cut pop and the impact squash. Never
eyeball it from separate stills. [see `examples/zebra/tapri_shot.py` `_register_hifi`]

**F. Preview contact sheet inspected.** 6–8 stills at the beats, tiled into one image, actually opened and
looked at: nothing clipped by the frame edge, no green rims, no floating feet, labels readable, every beat
shows its action, style consistent across assets. Then a ~2 s low-res motion check of the trickiest moment:
`python3 engine/chunkrender.py scene.py --start 9 --end 11 --chunks 2 --scale 0.33 --out /tmp/check.mp4`.

**G. Audio numbers** (`engine/mix.py`; CLI: `python3 engine/mix.py verify stems/vo.wav stems/bed.wav mix.wav`):
- VO sits **≥ 10 dB** over the bed inside the VO windows (`gap_db`).
- Final integrated loudness **−16 LUFS** (±1).
- True peak **≤ −1.5 dBFS**.
- Final loudnorm is two-pass **linear** (`loudnorm_type == linear`). `loudnorm_filter()` sets LRA ≥ the mix's
  own range (+1); with LRA too low ffmpeg silently switches to dynamic mode and pumps the VO. `Mix.master()`
  leaves the mix where loudnorm needs ~0 dB gain, so linear mode is possible.
- Listen to the sample once: horns/whooshes short and under the VO, no cheer/laugh louder than the words.

**H. File size budget.** Aim ≤ ~1 MB per second of 1080p (≈ 5–6 Mbps video, AAC 160 kbps); an 18 s video
under 15 MB. GIFs for a README: ≤ ~5 MB, 480–640 px wide, 12–15 fps. Check with `ls -lh` / `ffprobe`
before delivering.

## 5. Honest limits (tell the human up front)

- **No lip-sync** (mouth patches per pose aren't built) and **no frame-by-frame hand-drawn acting**. Acting comes
  from AI-drawn key poses with hard cuts, cycles and living-pose warps; it reads well but isn't Pixar.
- AI image generation drifts a little between poses: registration checks catch most of it; some poses need
  regenerating.
- Procedural SFX are good for pops/whooshes/horns; laughs and cheers are approximations, keep them low.
- Facts on screen must be checked by a human expert before publishing.

## 6. Rules

- **Never publish, post, upload, deploy or send anything in the owner's name without asking first**, including
  pushing to a public repo or posting to social media. Show the result and wait for an explicit yes.
- Credit exactly as the owner specifies (e.g. "Swapnil Agrawal (BDS intern)").
- No SVG / vector / code-drawn characters. Pose packs only.
- Don't commit generated assets, renders, other people's reference art, or secrets.
- When editing an existing video project: keep its engine, characters and style; add, don't redesign.

## 7. Engine map

```text
engine/motion.py       easing, squash, paste/pivot/shadow, Path, camera, finish, word_time, ffmpeg_writer
engine/posepack.py     Cast (registered pose packs, hard cuts, living pose, cycles, anchors) + QA:
                       alpha_coverage, green_fringe, despill_edge, check_registration (CLI)
engine/sheets.py       slice_sheet (sprite sheets → registered frames), mirror_legs_below_hem, cycle_fps,
                       contact_sheet (walk check, CLI)
engine/mix.py          VO-led mix: Mix builder, per-SFX loudness, ducking, master, verify/check, loudnorm_filter (CLI)
engine/chunkrender.py  parallel chunked render with warm-up frames, concat + audio mux (CLI)
engine/sfx.py          procedural SFX + pluck music bed
engine/claylib.py      clay label plates
```
