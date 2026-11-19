"""Loudness-aware mix for the zebra sample: the VO is the lead, everything else sits under it.

  * VO stem normalised to -16 LUFS integrated on its own.
  * Music bed -30 LUFS, city ambience -31 LUFS (street) / -40 (tapri), each SFX normalised to its own
    target LUFS before placement (horns/whooshes trimmed short and low; laugh very low, cheer dropped).
  * Sidechain: a VO energy envelope (80 ms attack / 300 ms release) ducks music, ambience, horns and
    whooshes by DUCK_DB while she speaks; Foley (steps, pour, clink, clap) ducks by FOLEY_DB.
  * Full mix two-pass loudnorm'd to -16 LUFS / -1.5 dBTP afterwards (done in scene.py at mux time).
  * verify() measures VO-only vs bed-only loudness over the VO windows (gap must be >= 10 dB).

Loudness is measured with ffmpeg's ebur128 (BS.1770) on temp wavs, so no extra python deps."""
import os, re, wave, subprocess, tempfile
import numpy as np

SR = 44100
DUCK_DB, FOLEY_DB = 10.0, 6.0
T_VO, T_MUS, T_AMB_STREET, T_AMB_TAPRI = -16.0, -30.0, -31.0, -40.0
# per-file target loudness (LUFS of the clip itself, before ducking) and max length (s, None = whole clip)
SFX = {
    'horn_car': (-31, 0.32), 'horn_car_long': (-31, 0.40), 'horn_truck': (-31, 0.40), 'horn_auto': (-32, 0.35),
    'horn_bike': (-32, 0.30), 'cycle_bell': (-34, 0.5),
    'whoosh_car': (-31, 0.7), 'whoosh_auto': (-31, 0.7), 'whoosh_bike': (-32, 0.6), 'whoosh_bus': (-30, 0.9),
    'whoosh_air': (-30, 0.5),
    'footsteps_walk': (-30, None), 'footsteps_hurry': (-29, None), 'footstep_single': (-30, None),
    'chai_pour': (-27, None), 'kulhad_clink': (-27, None), 'kulhad_cheers': (-28, None),
    'hifi_clap_sparkle': (-23, None), 'laugh_group': (-40, None), 'cheer_yay': None,    # None = dropped
}
DUCKED = ('horn', 'whoosh', 'cycle', 'laugh', 'cheer')   # these follow the music/ambience duck


def read(path):
    w = wave.open(path); a = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768
    return a if w.getnchannels() == 1 else a.reshape(-1, w.getnchannels()).mean(1)


def write(path, a):
    with wave.open(path, 'wb') as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((np.clip(a, -1, 1) * 32767).astype(np.int16).tobytes())


def lufs(a):
    """integrated loudness (LUFS) + true peak (dBFS) of a mono float array via ffmpeg ebur128"""
    if np.abs(a).max() < 1e-6: return -120.0, -120.0
    if len(a) < int(0.5 * SR): a = np.pad(a, (0, int(0.5 * SR) - len(a)))   # BS.1770 needs >= one 400 ms block
    with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f: p = f.name
    write(p, a)
    out = subprocess.run(['ffmpeg', '-hide_banner', '-nostats', '-i', p, '-af', 'ebur128=peak=true', '-f', 'null', '-'],
                         capture_output=True, text=True).stderr
    os.unlink(p)
    summ = out[out.rindex('Summary:'):]
    I = float(re.search(r'I:\s+(-?[\d.]+|-inf) LUFS', summ).group(1).replace('-inf', '-120'))
    pk = float(re.search(r'Peak:\s+(-?[\d.]+|-inf) dBFS', summ).group(1).replace('-inf', '-120'))
    return I, pk


def ffilter(a, af):
    """run a mono float array through an ffmpeg audio filter chain"""
    with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f: p = f.name
    q = p[:-4] + '_o.wav'; write(p, a)
    subprocess.run(['ffmpeg', '-y', '-v', 'error', '-i', p, '-af', af, '-ar', str(SR), '-ac', '1', q], check=True)
    b = read(q); os.unlink(p); os.unlink(q)
    return np.pad(b, (0, max(0, len(a) - len(b))))[:len(a)]


def to_lufs(a, target):
    I, _ = lufs(a)
    return a * 10 ** ((target - I) / 20)


def vo_envelope(vo, thresh_db=-38, att=0.080, rel=0.300):
    """0..1 'VO is speaking' control: 5 ms RMS frames above (peak + thresh_db), one-pole 80 ms attack / 300 ms release"""
    hop = int(0.005 * SR); n = len(vo) // hop + 1
    pad = np.pad(vo, (0, n * hop - len(vo)))
    rms = np.sqrt((pad.reshape(n, hop) ** 2).mean(1) + 1e-12); db = 20 * np.log10(rms)
    gate = (db > db.max() + thresh_db).astype(np.float32)
    ka, kr = 1 - np.exp(-hop / SR / att), 1 - np.exp(-hop / SR / rel)
    env = np.zeros(n, np.float32); e = 0.0
    for i in range(n):
        g = gate[i]; e += (ka if g > e else kr) * (g - e); env[i] = e
    return np.interp(np.arange(len(vo)), np.arange(n) * hop, env).astype(np.float32), gate, hop


def build(dur, au, vt, vo_at, events, t_cut, out_path, stems_dir=None):
    N = int(dur * SR); cache = {}
    def clip(name):
        if name not in cache:
            spec = SFX.get(name, (-30, None))
            if spec is None: cache[name] = None
            else:
                a = read(au + name + '.wav'); tgt, mx = spec
                a = to_lufs(a, tgt)                     # gain from the WHOLE clip (a 0.3 s trim can't be gated reliably)
                if mx and len(a) > mx * SR:
                    a = a[:int(mx * SR)].copy(); f = int(0.06 * SR); a[-f:] *= np.linspace(1, 0, f) ** 2
                cache[name] = a
        return cache[name]
    def place(buf, a, t, g=1.0):
        i = int(max(0, t) * SR); L = min(len(a), N - i)
        if L > 0: buf[i:i + L] += a[:L] * g

    # --- VO stem
    vo_src = read(au + 'vo.wav'); vo = np.zeros(N, np.float32)
    for (a, b), at in zip(vt, vo_at):
        seg = vo_src[int(max(0, a - 0.05) * SR):int(min(len(vo_src) / SR, b + 0.15) * SR)].copy()
        f = int(0.01 * SR); seg[:f] *= np.linspace(0, 1, f); seg[-f:] *= np.linspace(1, 0, f)
        place(vo, seg, at - 0.05)
    # gentle comp + brickwall so the VO can sit at -16 LUFS with true peaks under -2 dBFS
    vo = to_lufs(vo, T_VO)
    for _ in range(2):
        vo = ffilter(vo, 'acompressor=threshold=-18dB:ratio=3:attack=5:release=120:makeup=1,alimiter=limit=0.70:attack=1:release=60:level=false')
        vo = to_lufs(vo, T_VO)
    env, _, _ = vo_envelope(vo)

    tt = np.arange(N) / SR
    # --- music + ambience beds
    mus = read(au + 'music_bed_desi.wav')[:N]; mus = np.pad(mus, (0, N - len(mus)))
    mus = to_lufs(mus, T_MUS) * np.clip(tt / 0.4, 0, 1)
    amb = read(au + 'ambience_city_bed.wav')[:N]; amb = np.pad(amb, (0, N - len(amb)))
    xf = np.clip((tt - (t_cut - 0.15)) / 0.3, 0, 1)                      # street -> tapri level change at the cut
    amb = to_lufs(amb, T_AMB_STREET) * (10 ** ((T_AMB_TAPRI - T_AMB_STREET) / 20 * xf)) * np.clip(tt / 0.4, 0, 1)
    # --- SFX buses
    duckfx, foley = np.zeros(N, np.float32), np.zeros(N, np.float32)
    for t, name, g in events:
        a = clip(name)
        if a is None: continue
        g = min(1.0, g / 0.45) if name.startswith(('whoosh', 'horn')) else 1.0   # keep the old relative accents, never boost
        place(duckfx if name.startswith(DUCKED) else foley, a, t, g)
    gd = 10 ** (-DUCK_DB * env / 20); gf = 10 ** (-FOLEY_DB * env / 20)
    bed = (mus + amb + duckfx) * gd + foley * gf
    mix = vo + bed
    # master: sit the mix at -16 LUFS with a brickwall at -2.5 dBFS so the mux-time two-pass loudnorm only
    # needs ~0 dB gain and stays LINEAR (true peak <= -1.5 dBTP; dynamic mode would pump the VO)
    g = 1.0
    for _ in range(3):
        I, _ = lufs(mix); k = 10 ** ((T_VO - I) / 20); mix = mix * k; g *= k
        mix = ffilter(mix, 'alimiter=limit=0.75:attack=1:release=50:level=false')
    vo, bed = vo * g, bed * g
    write(out_path, mix)
    if stems_dir:
        os.makedirs(stems_dir, exist_ok=True); write(stems_dir + '/vo.wav', vo); write(stems_dir + '/bed.wav', bed)
    return vo, bed, env


def verify(vo, bed, env, final_wav=None):
    """VO-vs-bed gap over the VO windows, bed level in the gaps, and final-mix numbers"""
    on = env > 0.5
    r = {}
    r['vo_only_I'] = lufs(vo)[0]
    r['bed_only_I'] = lufs(bed)[0]
    r['vo_in_vo_windows'] = lufs(vo[on])[0]
    r['bed_in_vo_windows'] = lufs(bed[on])[0]
    r['bed_in_gaps'] = lufs(bed[~on])[0]
    r['gap_db'] = r['vo_in_vo_windows'] - r['bed_in_vo_windows']
    if final_wav:
        a = read(final_wav); I, pk = lufs(a); r['final_I'], r['final_peak'] = I, pk
    return r
