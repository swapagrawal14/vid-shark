"""Loudness-aware mix for the zebra sample: the VO is the lead, everything else sits under it.

  * VO stem normalised to -16 LUFS integrated on its own.
  * Music bed -30 LUFS, city ambience -31 LUFS (street) / -40 (tapri), each SFX normalised to its own
    target LUFS before placement (horns/whooshes trimmed short and low; laugh very low, cheer dropped).
  * Sidechain: a VO energy envelope (80 ms attack / 300 ms release) ducks music, ambience, horns and
    whooshes by DUCK_DB while she speaks; Foley (steps, pour, clink, clap) ducks by FOLEY_DB.
  * Full mix two-pass loudnorm'd to -16 LUFS / -1.5 dBTP afterwards (done in scene.py at mux time).
  * verify() measures VO-only vs bed-only loudness over the VO windows (gap must be >= 10 dB).

Generic version for new videos: engine/mix.py (Mix builder, verify(), check(), loudnorm_filter()).
Loudness is measured with ffmpeg's ebur128 (BS.1770) on temp wavs, so no extra python deps."""
import os, sys
import numpy as np
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'engine'))

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


# shared helpers live in engine/mix.py (generalised from this file); the zebra-specific build() stays here
from mix import read, write, lufs, ffilter, to_lufs, vo_envelope, verify   # noqa: F401  (verify re-exported for scene.py)


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
