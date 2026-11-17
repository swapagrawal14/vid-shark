<p align="center">
  <img src="docs/media/banner.jpg" alt="vid-shark — motion-graphics videos where things actually move" width="100%">
</p>

<p align="center">
  <b>An agent skill for making real motion-graphics videos — where the objects and characters themselves move.</b><br>
  Any style · any topic · synced to voiceover · procedural SFX · one command to render
</p>

<p align="center">
  <img src="https://img.shields.io/badge/agent-skill-E27056?style=for-the-badge">
  <img src="https://img.shields.io/badge/python-3.9+-40A096?style=for-the-badge">
  <img src="https://img.shields.io/badge/output-1080p%20MP4-F0B446?style=for-the-badge">
  <img src="https://img.shields.io/badge/styles-clay%20·%20desi%20·%20paper%20·%203D-9678C8?style=for-the-badge">
</p>

---

## 🎬 See it move

<p align="center">
  <img src="docs/media/demo.gif" alt="Claymation demo: brush paints fluoride varnish onto a clay tooth arch" width="80%">
</p>

The brush flies in, the gauze wipes, the brush **paints** and the teeth turn amber behind it, saliva drops fall and splat, the clock spins — all timed to the voiceover words.
▶️ **[Watch the full 22 s sample with sound](docs/media/varnish_sample.mp4)**

<p align="center">
  <img src="docs/media/frames.jpg" alt="Six frames from the sample scene" width="100%">
</p>

---

## 🎞️ Sample gallery — four styles, four topics

| 🟠 Claymation · *Fluoride varnish* | 🪔 Desi illustration · *Masala chai* |
|---|---|
| <img src="docs/media/demo.gif" width="100%"> | <img src="docs/media/chai.gif" width="100%"> |
| Brush paints, teeth turn amber, saliva drips · [▶️ with sound](docs/media/varnish_sample.mp4) | Kettle pours high, kulhad fills, elaichi drops, steam curls · [▶️ with sound](docs/media/chai_sample.mp4) |
| ✂️ **Paper cut-out · *Rocket launch*** | 🧸 **3D toy · *Seed to sprout*** |
| <img src="docs/media/rocket.gif" width="100%"> | <img src="docs/media/sprout.gif" width="100%"> |
| 3-2-1 slams in, paper smoke billows, camera follows it to the stars · [▶️ with sound](docs/media/rocket_sample.mp4) | Pot slides in, seed bounces, can waters, sun rises, sprout springs up · [▶️ with sound](docs/media/sprout_sample.mp4) |

Every sample: same engine, different asset prompts. Voiceover synced, SFX on every action.

---

## ❌ Not this → ✅ This

| Slideshow (what most AI "explainers" do) | vid-shark |
|---|---|
| Static background | Background with slow camera push + stop-motion jitter |
| Text boxes popping up | Objects **perform the action** the voiceover describes |
| Silence or one music loop | A sound on every action: pop, whoosh, squish, plip, tick, pour |
| Captions carry the story | Mute it and it still explains itself |

---

## 🚀 Use it with any agent

Give the repo link to Claude Code, Codex, Cursor, Hark, or any coding agent and say:

```text
Read SKILL.md from https://github.com/swapagrawal14/vid-shark
and make me a 30-second motion-graphics video on <topic> in <style> style.
```

The agent writes the script, makes the voiceover, generates every object as a separate cut-out layer, animates them in code, adds SFX and music, and renders a 1080p MP4.

## 🎨 Styles

| 🟠 Claymation | 🪔 Desi flat illustration | ✂️ Paper cut-out | 🧸 3D toy |
|---|---|---|---|
| Plasticine, fingerprint texture, animated "on twos" | Bold Indian illustration, jharokha frames, pour & peel actions | Layered paper, hinged joints, stepped motion | Glossy pastel, bouncy overshoot |

## ⚙️ How it works

```text
script ─▶ voiceover ─▶ style frame ─▶ cut-out layers ─▶ animate in code ─▶ SFX + music ─▶ MP4
            (TTS)       (1 plate)      (1 per object)    (synced to words)   (−16 LUFS)
```

- **Squash & stretch** on every landing, **overshoot pops** on every entrance
- **Paths and arcs** for tools, **pivot rotation** for brushes and limbs
- **Reveal masks** for state changes (teeth turning amber, a glass filling)
- **Particles**: drops, splats, sparkles
- **Preview stills first**, then render the full scene

## 🏃 Run the example

```bash
pip install -r requirements.txt        # needs ffmpeg on PATH
cd examples/varnish
PREVIEW=40,110,185,250 python3 render.py   # quick stills
python3 render.py && python3 audio.py      # → final.mp4

# the other samples render + mix in one go
cd ../chai   && python3 render.py   # desi illustration
cd ../rocket && python3 render.py   # paper cut-out
cd ../sprout && python3 render.py   # 3D toy
```

## 📁 Inside

```text
SKILL.md              the playbook an agent follows: rules, pipeline, styles, limits
engine/motion.py      easing, squash, paste/pivot/shadow, paths, camera, film finish
engine/sfx.py         procedural SFX + music bed + mixer (no sample files needed)
engine/claylib.py     clay-style label plates
examples/common.py    shared scene runner (camera, finish, render loop, audio mix)
examples/varnish/     claymation scene: arch, gauze, brush, reveal mask, saliva, clock
examples/chai/        desi illustration: pour stream, cup fill, falling pods, steam
examples/rocket/      paper cut-out: countdown, smoke particles, camera follow, star streaks
examples/sprout/      3D toy: slide-in, seed bounce, watering, sun rays, growth
examples/tts.py       voiceover via Cartesia (swap in any TTS)
```

## ⚠️ Honest limits

- No frame-by-frame hand-drawn acting or lip-sync. Rigged cut-out characters (limbs, blinks, head tilts) get about 80% of that feel.
- Facts on screen should be checked by a human expert before publishing.

---

<p align="center">Made by <b>Swapnil Agrawal (BDS intern)</b> · <a href="https://github.com/swapagrawal14">@swapagrawal14</a></p>
