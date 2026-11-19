# Zebra crossing (desi illustration · pose packs · Hinglish VO)

An ~18 s sample in a desi flat-illustration (gouache) look. A girl waits at a busy Indian zebra crossing while horns blare and traffic streams both ways, braves the median, hurries across on *"bhaago!"*, then a hard cut to the chai tapri: her friends wave, chai pours into kulhads, a big hi-fi, everyone laughs.

Voiceover is Hinglish, in her own Cartesia voice:
*"Indian traffic mein road cross karna? Yeh patience ka asli exam hai. Gap mila... bhaago! Aur reward? Doston ke saath garam kulhad chai. Hi-fi!"*

What it shows:
- **Pose packs** for every character (girl + tapri friends), hard cuts between key poses, no vector puppets.
- **Front/back stepping sheets** (4-frame walk, 6-frame hurry) registered on the master canvas, so she walks *down* the screen instead of sliding. Cycle fps is tied to ground speed / stride.
- **Panorama street** with vehicle cut-outs (auto, bus, car, bikes) passing in both lanes, Doppler whooshes and horns.
- **VO-led mix**: VO stem at −16 LUFS, beds ~−30 LUFS, sidechain ducking, per-SFX loudness targets, VO ≥10 dB over the bed verified before muxing.

## Files
```text
scene.py        the whole cut: street shots, crossing, hurry, hard cut, mux + two-pass loudnorm
tapri_shot.py   tapri shot (wave → pour close-up → kulhads + sip → hi-fi → laugh), imported by scene.py
audio_mix.py    loudness-aware mix: per-stem LUFS targets, VO-envelope ducking, verify()
audio/make_vo.py   Cartesia VO + phrase timing → audio/vo.wav, audio/vo_timing.json
audio/make_sfx.py  procedural horns, pass-bys, footsteps, pour, clink, hi-fi, desi music bed (engine/sfx.py)
audio/README.md    what every audio file is, durations, VO phrase timings
```

## Regenerate it
Assets are **not committed** (AI-generated per project; same convention as `examples/posepack`). The generated PNGs (`girl/`, `street/`, `tapri/`) and the SFX/VO WAVs (`audio/*.wav`) have to be rebuilt.

1. **Art (pose pack method, see `SKILL.md` and `examples/posepack/README.md`)** with `generate_image`:
   - `girl/master.png`: full-body master, transparent. Then key poses `girl/girl_<pose>.png` (idle, look, worried, flinch, impatient, go, wave, sip, hifi, laugh) with the master as the FIRST reference: "same character, same size, same position in frame and same framing as the first reference … POSE: …". Check registration with `alpha_bbox` (`girl/girl_meta.json`).
   - Stepping sheets: `girl/front_walk_sheet.png` (4 frames) and a 6-frame hurry sheet, front/back view, sliced into `front_walk_*.png` / `front_hurry_*.png` and registered on the master canvas. If every frame has the same leg forward, mirror the legs below the hem and blend.
   - `street/street_panorama.png` (blank wide canvas as first ref + style frame), `street/zebra_closeup.png`, vehicle cut-outs (`auto_rickshaw`, `bus`, `car`, `motorbike`, `scooter_rider`).
   - `tapri/tapri_bg.png`, friends' pose packs in `tapri/poses/<name>_<pose>.png`, props in `tapri/props/`.
2. **Audio**
   ```bash
   cd examples/zebra/audio
   CARTESIA_API_KEY=... python3 make_vo.py hi    # vo.wav + vo_timing.json (--timing-only to re-measure)
   python3 make_sfx.py                           # horns, whooshes, footsteps, pour, clink, hi-fi, beds
   ```
3. **Mix check + render**
   ```bash
   cd examples/zebra
   python3 scene.py --audio-only                 # mix.wav + stems/, prints LUFS and the VO-over-bed gap
   PREVIEW=1.0,4.0,6.0,9.5,12.0,14.3 python3 scene.py   # stills → pv/
   python3 scene.py                              # → final.mp4 (1080p, mix loudnorm'd to −16 LUFS)
   ```
   `END=6 python3 scene.py` renders only the first 6 s; `OUT=/path/out.mp4` changes the output.

## Notes
- All art is AI-generated; the voice is the creator's own Cartesia voice. SFX and music are procedural.
- The friends' cut-outs had a green-screen fringe; `tapri_shot.despill_edge()` clamps G to max(R,B) on a 4 px edge ring and erodes alpha 1 px at load time.
- The laugh/cheer are synthesised approximations and sit very low (cheer is dropped in the mix).

Made by **Swapnil Agrawal (BDS intern)**.
