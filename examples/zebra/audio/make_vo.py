"""Zebra-crossing VO via Cartesia (same request as examples/tts.py), then sentence timing
from the energy envelope -> vo.wav + vo_timing.json. Needs CARTESIA_API_KEY."""
import json, os, subprocess, sys, wave
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
LANG = sys.argv[1] if len(sys.argv) > 1 else 'hi'
TEXT = ("Indian traffic mein road cross karna? Yeh patience ka asli exam hai. "
        "Gap mila... bhaago! "
        "Aur reward? Doston ke saath garam kulhad chai. Hi-fi!")
SENTS = ["Indian traffic mein road cross karna?", "Yeh patience ka asli exam hai.",
         "Gap mila...", "bhaago!", "Aur reward?", "Doston ke saath garam kulhad chai.", "Hi-fi!"]
if '--timing-only' not in sys.argv:
    body = json.dumps({"model_id": "sonic-latest", "transcript": TEXT,
                       "voice": {"mode": "id", "id": "ca587611-ddaf-4658-8e13-b130e1abfdb2"},
                       "output_format": {"container": "wav", "encoding": "pcm_s16le", "sample_rate": 44100},
                       "language": LANG})
    r = subprocess.run(['curl', '-s', '-w', '%{http_code}', '-o', f'{HERE}/vo.wav', '-X', 'POST',
                        'https://api.cartesia.ai/tts/bytes', '-H', 'Cartesia-Version: 2024-06-10',
                        '-H', 'X-API-Key: ' + os.environ.get('CARTESIA_API_KEY', ''),
                        '-H', 'Content-Type: application/json', '-d', body], capture_output=True, text=True)
    print('http', r.stdout, r.stderr[:200])
# ---- energy envelope -> speech segments (gaps >= MINGAP split sentences)
x = np.frombuffer(subprocess.check_output(['ffmpeg', '-v', 'error', '-i', f'{HERE}/vo.wav', '-f', 'f32le', '-ac', '1', '-ar', '44100', '-']), np.float32)
hop = 441; n = len(x) // hop
rms = np.sqrt((x[:n * hop].reshape(n, hop) ** 2).mean(1)); db = 20 * np.log10(rms + 1e-9)
on = db > db.max() - 35
segs = []; i = 0
while i < n:
    if on[i]:
        j = i
        while j < n and on[j]: j += 1
        segs.append([i / 100, j / 100]); i = j
    else: i += 1
MINGAP = float(os.environ.get('MINGAP', 0.12))
merged = []
for s in segs:
    if merged and s[0] - merged[-1][1] < MINGAP: merged[-1][1] = s[1]
    else: merged.append(s)
merged = [m for m in merged if m[1] - m[0] > 0.08]
print('segments', merged)
out = {"duration": round(len(x) / 44100, 3), "text": TEXT, "language": LANG, "segments": [[round(a, 2), round(b, 2)] for a, b in merged]}
if len(merged) == len(SENTS):
    out["sentences"] = [{"text": t, "start": round(a, 2), "end": round(b, 2)} for t, (a, b) in zip(SENTS, merged)]
json.dump(out, open(f'{HERE}/vo_timing.json', 'w'), indent=2, ensure_ascii=False)
print(json.dumps(out, indent=2, ensure_ascii=False))
