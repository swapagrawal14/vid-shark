---
name: layered-motion-video
description: Make polished explainer / tutorial / story videos where the OBJECTS and CHARACTERS themselves move and act (bounce, pour, paint, drip, tick), in any visual style (claymation, desi flat illustration, paper cut-out, 3D-toy, ink), on any topic, synced to a voiceover. Use when someone asks for an "animated video", "motion graphics", "explainer", "claymation video", "tutorial video" — anything beyond a slideshow.
author: Swapnil Agrawal (BDS intern)
---

# Layered Motion Video

## The one rule
**Things move, not text boxes.** A slideshow with a static background and text plates popping up is NOT motion graphics.
In every shot something physical must be *doing the action the voiceover describes*: the brush paints, the gel squeezes out, the drop falls and splats, the clock hand spins, the tray flips and seats. Text is a small supporting label, never the star.

Why: viewers remember actions, not captions. If you mute the video it should still explain itself.

## How it works (pipeline)
1. **Script → beats.** Write the VO (≈150 words/min). For every sentence write the *action* that will be on screen (verb + object). If a sentence has no action, redesign it until it does.
2. **Voiceover first.** Generate VO (any TTS: Cartesia, ElevenLabs…). Timing of every animation is keyed to the words (`word_time()` or real TTS word timestamps). VO drives the edit, never the other way round.
3. **Style frame.** Generate ONE background plate for the whole video in the chosen style (plain/minimal, room for objects, no text, no main objects baked in). 16:9 → render at 1920×1080.
4. **Cut-out layers.** Generate every object/character part as a SEPARATE image with transparent background (prompt on chroma green #00FF00, key it out). Pass the first good asset as a style reference to every later one so the set matches. Characters → separate parts (head, torso, arm upper/lower, hand) so they can be rigged.
5. **Masks for state changes.** Where an object changes (teeth turning amber, glass filling, stain spreading) make a mask and a "changed" version; reveal it progressively along the action path (see `reveal` in the example).
6. **Animate in code** (`engine/motion.py`): easing, overshoot pop, squash-and-stretch on impact, objects following paths, pivot rotation, particles (drops, sparkles, crumbs), cast shadows, slow camera push, stop-motion jitter, grain and vignette.
7. **SFX on every action** (`engine/sfx.py`): pop, whoosh, squish, dab, plip, tick, boing, pour — logged during render as `(time, kind)` so they're frame-accurate. Soft music bed under VO. Loudness-normalise to −16 LUFS.
8. **Preview before full render.** Render 6–8 still frames (`PREVIEW=12,40,80…`), contact-sheet them, LOOK at them, fix, then render. Send progress (frames, sample) to the person as you go.

## Animation principles to always apply
- **Anticipation → action → follow-through.** Brush lifts slightly before diving in; arch overshoots and squashes on landing.
- **Squash & stretch** on every landing/impact (`squash()`), pop-in overshoot on every appearance (`back()`, `POP`).
- **Arcs, not straight lines** for flying objects; things enter from off-screen with a whoosh.
- **Secondary motion:** hover bob, little wobble on idle objects, droplets flung from a wiping gauze, sparkles on splats.
- **Contact shadows** under everything that touches the set; cast shadows lift when the object lifts.
- **Stagger.** Never pop two things on the same frame.
- **One focus at a time.** Exit tools (fly off) when their job is done.
- **Claymation feel:** animate "on twos" (12 fps internal → 24 fps out), ±1 px jitter + tiny rotation per step, fingerprint noise texture on clay, slight light flicker. For flat/illustrated styles: 24 fps internal, no jitter, crisper easing.

## Styles (swap the asset prompts, keep the engine)
| Style | Asset prompt core | Motion feel |
|---|---|---|
| Claymation | plasticine stop-motion, Aardman-like, fingerprint texture, soft studio light | on twos, jitter, squash heavy |
| Desi flat illustration | flat Indian illustration, limited palette, bold shapes, slight grain, ornate frame motifs (jharokha arch) | smooth 24 fps, pour/peel actions, characters with blinks and head tilts |
| Paper cut-out | layered paper, visible paper edges, drop shadows | stepped motion, parts hinge at joints |
| 3D toy | glossy soft 3D, pastel | smooth, bouncy overshoot |

## Honest limits (tell the person up front)
- Frame-by-frame hand-drawn acting (expressive faces, full body turns) and lip-sync are not achievable with this method. Rigged cut-out characters (limb rotation, blinks, head tilt, walk cycles via parts) get ≈80% of the feel.
- AI image gen won't keep a character 100% identical across many poses: generate parts once and reuse them.
- Facts on screen (dosages, numbers) must be checked by a human expert before publishing.

## Workflow rules
- Show a ~20 s sample scene first; build the full video only after the look is approved.
- Send progress (each generated asset, preview sheets, sample) while working.
- Never publish/post anything in the person's name without asking.
- Credit line as the person specifies (e.g. "Swapnil Agrawal (BDS intern)").

## Repo layout
```
engine/claylib.py    clay text plates (Fredoka font), make_item(), pop curve
engine/motion.py     easing, squash, paste/pivot/shadow, Path, camera, finish, word_time, ffmpeg_writer
engine/sfx.py        procedural SFX + pluck music bed + mix()
examples/varnish/    full worked scene: arch drops in, gauze wipes, brush paints with reveal mask, saliva drips, clock spins
fonts/               Fredoka
```

## Run the example
```bash
pip install -r requirements.txt   # + ffmpeg on PATH
cd examples/varnish
PREVIEW=40,110,185,250 python3 render.py   # stills first
python3 render.py && python3 audio.py      # → final.mp4
```

## New scene recipe (copy examples/varnish/render.py)
1. Load BG + layers; set positions/scales.
2. Compute key times from VO words.
3. Per step: `fr = camera(...)` → draw layers back-to-front with their motion functions → particles → labels (small) → `finish(fr, step)`.
4. Append `(t, 'pop'|'whoosh'|...)` to SFX at each action; dump to sfx.json; `sfx.mix()` + ffmpeg mux.
