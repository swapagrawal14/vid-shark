# Zebra crossing: audio kit (~18 s sample)

Every file is mono, 16-bit, 44.1 kHz WAV. Nothing here is mixed into a video yet.
Rebuild: `python3 make_vo.py hi` (needs `CARTESIA_API_KEY`, add `--timing-only` to only re-measure) and `python3 make_sfx.py` (procedural, built on `engine/sfx.py`, no samples).

## Voiceover
| File | Duration | Notes |
|---|---|---|
| `vo.wav` | 10.80 s | Cartesia `sonic-latest`, voice "Kuku" `ca587611-ddaf-4658-8e13-b130e1abfdb2`, `language: hi`, romanised Hinglish. Same request as `examples/tts.py` |
| `vo_timing.json` | n/a | Phrase start/end from the energy envelope: 10 ms RMS frames, speech means within 35 dB of the peak, gaps under 0.12 s merged |

Script: *"Indian traffic mein road cross karna? Yeh patience ka asli exam hai. Gap mila... bhaago! Aur reward? Doston ke saath garam kulhad chai. Hi-fi!"*

| # | Phrase | Start | End | Story beat |
|---|---|---|---|---|
| 1 | Indian traffic mein road cross karna? | 0.06 | 2.05 | Busy zebra crossing, horns |
| 2 | Yeh patience ka asli exam hai. | 2.52 | 4.40 | Waits nervously on the median |
| 3 | Gap mila... | 4.72 | 5.52 | Gap opens |
| 4 | bhaago! | 5.65 | 6.68 | Hurries across (speech ends near 6.45; the rest is the tail) |
| 5 | Aur reward? | 6.85 | 7.52 | Arrives at the chai tapri, friends wave |
| 6 | Doston ke saath garam kulhad chai. | 7.81 | 9.77 | Chai pours into kulhads |
| 7 | Hi-fi! | 9.95 | 10.58 | Big hi-fi, then everyone laughs |

The times are relative to the start of vo.wav, so add your VO offset (`PRE`). The VO is about 10.8 s long, which leaves around 7 s of an 18 s cut for traffic-only intro and outro beats.

## Horns
| File | Duration | What |
|---|---|---|
| `horn_auto.wav` | 0.95 s | Auto-rickshaw: nasal, buzzy "pee-pee-peeep" |
| `horn_car.wav` | 0.55 s | Two-tone car honk |
| `horn_car_long.wav` | 1.55 s | Impatient stab, then a long honk |
| `horn_truck.wav` | 0.90 s | Deep bus or truck blare |
| `horn_bike.wav` | 0.42 s | Scooter or bike "beep-beep" |
| `cycle_bell.wav` | 0.70 s | Bicycle bell "tring tring" (bonus) |

## Traffic pass-bys (Doppler: the pitch drops and the sound swells at about the midpoint)
| File | Duration | What |
|---|---|---|
| `whoosh_car.wav` | 1.40 s | Car passing |
| `whoosh_bike.wav` | 1.00 s | Two-wheeler, buzzy and quick |
| `whoosh_auto.wav` | 1.30 s | Rattly auto-rickshaw |
| `whoosh_bus.wav` | 2.20 s | Heavy bus or truck |
| `whoosh_air.wav` | 0.55 s | Plain air whoosh (the engine `whoosh`, darkened) |

## Beds
| File | Duration | What |
|---|---|---|
| `ambience_city_bed.wav` | 20.00 s | Traffic rumble, idling engines, crowd murmur, distant horns and pass-bys. Quiet, about −26 LUFS |
| `music_bed_desi.wav` | 20.00 s | Soft, upbeat and desi: tanpura drone, santoor-like plucks in a Khamaj-ish phrase, dholak keherwa at 104 bpm, light manjira. 1 s fade in, 1.5 s fade out, about −25 LUFS |

## Footsteps
| File | Duration | What |
|---|---|---|
| `footstep_single.wav` | 0.16 s | One step: thump plus scuff on asphalt |
| `footsteps_walk.wav` | 2.40 s | Nervous walk, about 2 steps/s |
| `footsteps_hurry.wav` | 1.80 s | Hurried, about 4.6 steps/s |

## Tapri moment
| File | Duration | What |
|---|---|---|
| `hifi_clap_sparkle.wav` | 1.40 s | Palm-slap flam with a rising chime sparkle and a glitter tail |
| `chai_pour.wav` | 1.80 s | Pour stream with rising glugs and a final drip |
| `kulhad_clink.wav` | 0.50 s | Two clay cups knock (dull and woody, not glassy) |
| `kulhad_cheers.wav` | 0.80 s | Several kulhads clink together |
| `laugh_group.wav` | 1.90 s | Small group "ha-ha" laugh. Stylised and synthesised, so use it low |
| `cheer_yay.wav` | 1.60 s | Short "yaay" with a few claps. Stylised, so use it low |

## Levels and mixing hints
- One-shots are peak-normalised to about −3 to −6 dBFS. Horns are loud by design, so start them around 0.3–0.4× gain and keep pass-bys around 0.4–0.6×.
- Under the VO, run the city bed at about 0.5–0.7× and the music at about 0.5×. Bring the bed down and the music up when the scene cuts to the tapri.
- Loudness-normalise the final mix to −16 LUFS, as `common.finish_audio` already does.
- The laugh and cheer are procedural vocal approximations. If they sound robotic in context, drop them or replace them with a real recording.
