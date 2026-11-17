# Pose-pack examples (Bablu ki Metro)

Assets are not committed (they're AI-generated per project). Regenerate them with `generate_image`:

- `poses/<char>_<pose>.png`: 960x1102, transparent. First reference = the character's master pose, prompt "same character, same size, same position in frame and same framing as the first reference … POSE: …".
- `bablu_walk_sheet.png` / `uncle_run_sheet.png`: first reference = blank 2400x700 #00FF00 canvas, second = the character. "exactly N frames in one horizontal row, strict side view, feet on one baseline, no ground line".
- `bg_street.png`: first reference = blank 2400x768 canvas, second = an existing background for style. Side-on panorama with an empty sidewalk band.

`metro_scene.py` imports timing/props from the original scene script (ep1.py); treat it as a reference for structure (Cast per character, `seq` pose tables, anchors) rather than a drop-in runner. `street_scene.py` is self-contained apart from its assets and VO.
