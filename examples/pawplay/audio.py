"""Paw Playlists audio: procedural SFX on every action + an upbeat ukulele/marimba bed, mixed with engine/mix.py.

No voiceover in this intro, so the music bed leads: it sits a few LU under the master and every SFX gets its
own loudness target on top. Mix still wants a VO stem, so it gets silence and every bus uses duck_db=0
(a silent VO makes the envelope gate read 'speaking' everywhere; 0 dB keeps that from ducking anything).

The cue list comes from scene.cues(): the same timing constants the visuals use.

    python3 audio.py          # -> mix.wav, stems/, sfx.json  (+ prints the QA numbers)
"""
import os, sys, json
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '../../engine')); sys.path.insert(0, HERE)
from mix import Mix, SR, verify, check, loudnorm_apply, lufs, read
import scene

R = np.random.default_rng(7)
DUR = scene.DUR


def T(sec): return np.arange(int(sec * SR)) / SR


def sweep(f, sec):                      # phase from an instantaneous-frequency array
    return np.sin(2 * np.pi * np.cumsum(f) / SR)


def noise_band(sec, lo, hi):
    n = R.standard_normal(int(sec * SR)); F = np.fft.rfft(n); fr = np.fft.rfftfreq(len(n), 1 / SR)
    F[(fr < lo) | (fr > hi)] = 0; return np.fft.irfft(F, len(n)).astype(np.float32)


# ---------------------------------------------------------------- SFX (mono float32, unnormalised: Mix sets loudness)
def whoosh(sec=0.42, up=True):
    t = T(sec); u = t / sec
    lo = 300 + 1500 * (u if up else 1 - u)
    n = noise_band(sec, 250, 4000)
    # moving band: crude 1-pole lowpass whose cutoff follows the sweep
    out = np.zeros_like(n); y = 0.0; k = 1 - np.exp(-2 * np.pi * lo / SR)
    for i in range(len(n)): y += k[i] * (n[i] - y); out[i] = y
    return out * np.sin(np.pi * u) ** 1.5


def swish(): return whoosh(0.3, up=False) * 0.7


def pop(pitch=1.0):
    t = T(0.11); f = (620 * np.exp(-t * 14) + 260) * pitch
    return sweep(f, 0.11) * np.exp(-t * 40)


def boing(base=180, depth=110, sec=0.42):
    t = T(sec); f = base + depth * np.sin(t * 2 * np.pi * 11) * np.exp(-t * 7) + 60 * np.exp(-t * 20)
    tone = sweep(f, sec) + 0.25 * sweep(2 * f, sec)
    return tone * np.exp(-t * 7.5) * np.minimum(1, t / 0.004)


def boing_small(): return boing(300, 80, 0.28)


def squish():
    t = T(0.22); f = 120 + 70 * np.sin(t * 50)
    return (sweep(f, 0.22) * 0.7 + noise_band(0.22, 200, 1500) * 0.6) * np.exp(-t * 16)


def thud():
    t = T(0.3); f = 95 * np.exp(-t * 6) + 45
    return (sweep(f, 0.3) + noise_band(0.3, 60, 600) * 0.5 * np.exp(-t * 40)) * np.exp(-t * 14)


def fall(sec=0.45):                     # slide-whistle drop for the hamster
    t = T(sec); f = 1500 * np.exp(-t * 2.4) + 300
    return (sweep(f, sec) + 0.2 * sweep(2 * f, sec)) * np.minimum(1, t / 0.03) * np.minimum(1, (sec - t) / 0.05)


def bonk(pitch=1.0):                    # wood-block knock + a short bright ping (note hitting a head)
    t = T(0.22)
    wood = (np.sin(2 * np.pi * 820 * pitch * t) + 0.5 * np.sin(2 * np.pi * 1880 * pitch * t)) * np.exp(-t * 55)
    ping = np.sin(2 * np.pi * 1320 * pitch * t) * np.exp(-t * 14) * 0.35
    return (wood + ping + noise_band(0.22, 1500, 6000) * np.exp(-t * 120) * 0.4) * np.minimum(1, t / 0.0015)


def tick():                             # soft blink tick, very quiet in the mix
    t = T(0.035); return np.sin(2 * np.pi * 3200 * t) * np.exp(-t * 160)


def plip(pitch=1.0):
    t = T(0.14); f = (1000 + 1300 * np.exp(-t * 40)) * pitch
    return sweep(f, 0.14) * np.exp(-t * 28)


def click():
    t = T(0.06)
    return (noise_band(0.06, 1500, 8000) * np.exp(-t * 150) + np.sin(2 * np.pi * 1800 * t) * np.exp(-t * 90) * 0.6) * np.minimum(1, t / 0.001)


def sparkle():                          # bell arpeggio for the note burst
    out = np.zeros(int(0.9 * SR), np.float32)
    for i, f in enumerate((1568, 2093, 2637, 3136, 4186)):
        t = T(0.5); b = (np.sin(2 * np.pi * f * t) + 0.3 * np.sin(2 * np.pi * f * 2.76 * t)) * np.exp(-t * 9)
        j = int(i * 0.065 * SR); out[j:j + len(b)] += b[:len(out) - j]
    return out


def chord():                            # everyone sings: a bright 'aah' major chord with soft formants
    sec = 0.95; t = T(sec); out = np.zeros(len(t))
    for f in (392.0, 493.9, 587.3, 784.0):
        vib = 1 + 0.006 * np.sin(2 * np.pi * 5.5 * t)
        for h, a in ((1, 1), (2, .5), (3, .35), (4, .2)):
            out += a * np.sin(2 * np.pi * f * h * np.cumsum(vib) / SR) * (1 if 600 < f * h < 1300 else 0.5)
    env = np.minimum(1, t / 0.05) * np.minimum(1, (sec - t) / 0.25)
    return out * env


# ---------------------------------------------------------------- music bed: uke strums + marimba melody + bass + shaker
BPM = 116; BEAT = 60 / BPM
NOTE = lambda m: 440.0 * 2 ** ((m - 69) / 12)
CHORDS = [('C', [60, 64, 67, 72]), ('G', [55, 62, 67, 71]), ('Am', [57, 64, 69, 72]), ('F', [53, 60, 65, 69])]


def ks_pluck(f, sec=0.9, bright=0.5):    # Karplus-Strong string (ukulele-ish nylon)
    N = int(sec * SR); p = max(2, int(SR / f)); buf = noise_band(p / SR + 0.001, 200, 6000)[:p] * 0.9
    out = np.zeros(N, np.float32); b = buf.copy()
    for i in range(N):
        j = i % p; out[i] = b[j]; b[j] = 0.996 * (bright * b[j] + (1 - bright) * b[(j - 1) % p])
    return out * np.minimum(1, np.arange(N) / (0.003 * SR))


def strum(notes, down=True, vol=1.0):
    out = np.zeros(int(1.0 * SR), np.float32); seq = notes if down else notes[::-1]
    for k, m in enumerate(seq):
        s = ks_pluck(NOTE(m), 0.9, 0.5); i = int(k * 0.012 * SR); out[i:i + len(s)] += s[:len(out) - i] * (1 - 0.1 * k)
    return out * vol


def marimba(f, sec=0.6):
    t = T(sec)
    return (np.sin(2 * np.pi * f * t) + 0.35 * np.sin(2 * np.pi * f * 3.93 * t) * np.exp(-t * 30)) * np.exp(-t * 7) \
        * np.minimum(1, t / 0.002)


def music(dur):
    N = int(dur * SR); uke = np.zeros(N); mar = np.zeros(N); bass = np.zeros(N); shk = np.zeros(N)
    def put(buf, a, t, g=1.0):
        i = int(t * SR); L = min(len(a), N - i)
        if 0 <= i < N and L > 0: buf[i:i + L] += a[:L] * g
    cache = {}
    end = dur - 2.2                                   # last bar: let the final chord ring out under the end hold
    # pentatonic marimba hook (scale degrees per 8th note, None = rest), two bars, varied on repeat
    hook = [72, None, 76, 79, 76, None, 74, 72, 74, None, 76, None, 72, None, 69, None]
    hook2 = [79, None, 76, 79, 81, None, 79, 76, 74, None, 72, None, 74, 76, None, None]
    bar = 0; t = 0.0
    while t < end:
        name, ch = CHORDS[bar % 4]
        for e8, (dn, g) in enumerate([(True, 1.0), (None, 0), (True, .7), (False, .55), (None, 0), (False, .6), (True, .75), (False, .5)]):
            if dn is None: continue
            key = (name, dn)
            if key not in cache: cache[key] = strum(ch, dn)
            put(uke, cache[key], t + e8 * BEAT / 2, g)
        for b in range(4):                            # bass on beats 1 and 3, pickup on 4&
            if b in (0, 2): put(bass, np.sin(2 * np.pi * NOTE(ch[0] - 24) * T(0.45)) * np.exp(-T(0.45) * 5), t + b * BEAT)
        if bar >= 1:                                  # melody enters after one bar of strums
            h = hook if (bar // 2) % 2 == 0 else hook2
            for e8 in range(8):
                m = h[(bar % 2) * 8 + e8]
                if m is not None: put(mar, marimba(NOTE(m)), t + e8 * BEAT / 2, 0.9 if e8 % 2 == 0 else 0.7)
        for e16 in range(8):                          # shaker on 8ths, accent off-beats
            put(shk, noise_band(0.05, 5000, 12000) * np.exp(-T(0.05) * 70) * np.minimum(1, T(0.05) / 0.004), t + e16 * BEAT / 2, 0.6 if e16 % 2 else 0.35)
        t += 4 * BEAT; bar += 1
    # final ring: C chord strum + marimba C-E-G-C rolled
    put(uke, strum(CHORDS[0][1], True) , t, 1.0)
    for k, m in enumerate((72, 76, 79, 84)): put(mar, marimba(NOTE(m), 1.2), t + k * 0.08, 0.9)
    put(bass, np.sin(2 * np.pi * NOTE(36) * T(1.5)) * np.exp(-T(1.5) * 2.5), t)
    mixb = uke * 0.55 + mar * 0.5 + bass * 0.45 + shk * 0.12
    tt = np.arange(N) / SR
    mixb *= np.clip(tt / 0.3, 0, 1) * np.clip((dur - tt) / 0.8, 0, 1)   # in at the top, out at the very end
    return mixb.astype(np.float32), t


# ---------------------------------------------------------------- per-SFX loudness (LUFS of the clip itself), max length
LEVEL = dict(whoosh=-26, swish=-28, pop=-25, boing=-23, boing_small=-25, squish=-27, thud=-22, fall=-27,
             bonk=-22, tick=-36, plip=-31, click=-24, sparkle=-25, chord=-22)


def build():
    cues = scene.cues()
    m = Mix(DUR)
    m.vo(np.zeros(int(DUR * SR), np.float32))       # no VO in this intro (see docstring)
    bed, t_final = music(DUR)
    m.bed(bed, lufs=-20.5, duck_db=0.0, fade_in=0.05, loop=False)
    letter_i = 0; bonk_i = 0; plip_i = 0
    gen = dict(whoosh=whoosh, swish=swish, boing=boing, boing_small=boing_small, squish=squish, fall=fall,
               tick=tick, click=click, sparkle=sparkle, chord=chord)
    pre = {k: f() for k, f in gen.items()}
    log = []
    title_pops = {round(scene.T_TITLE + L['i'] * scene.T_LET, 4) for L in scene.LETTERS}
    for t, name in cues:
        if name == 'pop' and round(t, 4) in title_pops:          # title letters: rising pitch, one per letter
            clip = pop(1.0 + 0.06 * letter_i); letter_i += 1
        elif name == 'pop':
            clip = pop(0.85)
        elif name == 'bonk':
            clip = bonk((1.0, 1.25, 0.9)[bonk_i % 3]); bonk_i += 1
        elif name == 'plip':
            clip = plip((1.0, 1.12, 1.26, 0.94)[plip_i % 4]); plip_i += 1
        else:
            clip = pre[name]
        m.sfx(t, clip, lufs=LEVEL[name], duck_db=0.0)
        log.append((round(t, 3), name))
    # hamster lands: add a low thud under the boing
    m.sfx(scene.T_HAM_LAND, thud(), lufs=LEVEL['thud'], duck_db=0.0); log.append((scene.T_HAM_LAND, 'thud'))
    # button press: a short rising pluck run = the note burst
    for k, mm in enumerate((72, 76, 79, 84, 88, 91)):
        tt = scene.T_PRESS + 0.05 + k * 0.045
        m.sfx(tt, marimba(NOTE(mm), 0.4), lufs=-28, duck_db=0.0); log.append((round(tt, 3), 'burst_note'))
    os.makedirs(os.path.join(HERE, 'stems'), exist_ok=True)
    vo, bedstem, env = m.render(os.path.join(HERE, 'mix.wav'), stems_dir=os.path.join(HERE, 'stems'))
    json.dump(sorted(log), open(os.path.join(HERE, 'sfx.json'), 'w'))
    return vo, bedstem, env, log


if __name__ == '__main__':
    vo, bedstem, env, log = build()
    print(f'{len(log)} SFX cues placed')
    tmp = '/tmp/pawplay_ln.wav'
    d2 = loudnorm_apply(os.path.join(HERE, 'mix.wav'), tmp)
    I, pk = lufs(read(tmp))
    r = {'gap_db': float('nan'), 'final_I': I, 'final_peak': pk, 'loudnorm_type': d2['normalization_type']}
    print('no VO: VO-over-bed gap gate not applicable')
    for ok, txt in check(r)[1:]: print(('PASS ' if ok else 'FAIL ') + txt)
