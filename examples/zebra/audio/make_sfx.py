"""Procedural SFX + desi music bed for the zebra-crossing sample. Builds on engine/sfx.py
(same SR, same envelope/noise style, reuses pour/whoosh/pop/plip). Mono 16-bit 44.1 kHz.
One-shots are peak-normalised to -3 dBFS (0.7); beds are kept quiet so they can sit under VO.
Run: python3 make_sfx.py  -> writes *.wav next to this file."""
import os, sys, wave
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', '..', '..', 'engine'))
import sfx as S
SR = S.SR
R = np.random.default_rng(1411)

# ---------------- helpers ----------------
def T(sec): return np.arange(int(sec * SR)) / SR
def tone(freq, t):  # freq: scalar or array
    f = np.broadcast_to(np.asarray(freq, np.float64), t.shape)
    return np.sin(2 * np.pi * np.cumsum(f) / SR)
def saw(freq, t, harm=12):
    f = np.broadcast_to(np.asarray(freq, np.float64), t.shape); ph = 2 * np.pi * np.cumsum(f) / SR
    return sum(np.sin(k * ph) / k for k in range(1, harm + 1))
def square(freq, t, harm=9):
    f = np.broadcast_to(np.asarray(freq, np.float64), t.shape); ph = 2 * np.pi * np.cumsum(f) / SR
    return sum(np.sin(k * ph) / k for k in range(1, harm + 1, 2))
def lp(x, a):   # one-pole low-pass, a in (0,1): smaller = darker
    y = np.empty_like(x); acc = 0.0
    for i, v in enumerate(x): acc += a * (v - acc); y[i] = acc
    return y
def lpf(x, cutoff):  # FFT brick-ish low-pass with soft knee (fast)
    X = np.fft.rfft(x); f = np.fft.rfftfreq(len(x), 1 / SR); X *= 1 / (1 + (f / cutoff) ** 4); return np.fft.irfft(X, len(x))
def bpf(x, lo, hi):
    X = np.fft.rfft(x); f = np.fft.rfftfreq(len(x), 1 / SR)
    X *= (1 / (1 + (f / hi) ** 4)) * (1 / (1 + (lo / np.maximum(f, 1)) ** 4)); return np.fft.irfft(X, len(x))
def noise(sec): return R.standard_normal(int(sec * SR))
def adsr(n, a=.01, r=.05):
    e = np.ones(n); ai = max(1, int(a * SR)); ri = max(1, int(r * SR))
    e[:ai] = np.linspace(0, 1, ai); e[-ri:] *= np.linspace(1, 0, ri); return e
def add(dst, src, at, g=1.0):
    i = int(at * SR); L = min(len(src), len(dst) - i)
    if L > 0 and i >= 0: dst[i:i + L] += src[:L] * g
def norm(x, peak=.7): return x / (np.abs(x).max() + 1e-9) * peak
def fade(x, fi=.005, fo=.02):
    x = x.copy(); a = int(fi * SR); b = int(fo * SR)
    if a: x[:a] *= np.linspace(0, 1, a)
    if b: x[-b:] *= np.linspace(1, 0, b)
    return x
OUT = {}
def save(name, x, peak=.7):
    x = fade(norm(x, peak) if peak else x)
    with wave.open(f'{HERE}/{name}.wav', 'wb') as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((np.clip(x, -1, 1) * 32767).astype(np.int16).tobytes())
    OUT[name] = len(x) / SR

# ---------------- horns ----------------
def horn_auto():  # auto-rickshaw: nasal, buzzy "pee-pee-peep", slightly sagging pitch
    out = np.zeros(int(.95 * SR))
    for at, d in ((0, .13), (.2, .13), (.42, .42)):
        t = T(d); f = 470 * (1 - .03 * t / d) + 6 * np.sin(2 * np.pi * 31 * t)
        x = np.tanh(2.5 * square(f, t)) + .3 * saw(f * 2, t, 6)
        x = bpf(x, 350, 3200) * adsr(len(t), .008, .03); add(out, x, at)
    return out
def horn_car():   # two-tone car horn, ~0.55 s
    t = T(.55); x = saw(415, t) + .9 * saw(523, t)
    x = np.tanh(1.8 * bpf(x, 250, 2800)) * adsr(len(t), .01, .06); return x
def horn_car_long():  # impatient long honk with a stab before it
    out = np.zeros(int(1.55 * SR)); t1 = T(.16); t2 = T(1.1)
    for t, at in ((t1, 0), (t2, .3)):
        x = saw(392, t) + .9 * saw(494, t); x = np.tanh(1.8 * bpf(x, 250, 2800)) * adsr(len(t), .01, .08); add(out, x, at)
    return out
def horn_truck():  # deep, blaring
    t = T(.9); x = saw(185, t, 20) + .8 * saw(233, t, 20) + .5 * saw(277, t, 20)
    return np.tanh(1.5 * bpf(x, 90, 2200)) * adsr(len(t), .03, .15)
def horn_bike():  # scooter/bike: thin high "beep-beep"
    out = np.zeros(int(.42 * SR))
    for at in (0, .2):
        t = T(.15); x = square(880 + 8 * np.sin(2 * np.pi * 40 * t), t, 7); add(out, bpf(x, 500, 5000) * adsr(len(t), .005, .02), at)
    return out
def cycle_bell():  # bicycle bell "tring tring" (bonus for the street)
    out = np.zeros(int(.7 * SR))
    for at in (0, .22):
        t = T(.45); e = np.exp(-t * 7) * (1 + .5 * np.sign(np.sin(2 * np.pi * 26 * t)))
        x = (tone(2600, t) + .6 * tone(3710, t) + .3 * tone(5200, t)) * e; add(out, x, at)
    return out

# ---------------- pass-bys (doppler: pitch falls, loudness swells then fades) ----------------
def passby(sec, f0, body_lp, rough, nz_gain, peak_at=.5):
    t = T(sec); u = t / sec; c = (u - peak_at) * 6
    dop = 1 + .09 * (-np.tanh(c))                     # pitch drops through centre
    amp = 1 / (1 + c ** 2)                            # swell
    eng = saw(f0 * dop, t, 10) * (1 + rough * np.sin(2 * np.pi * f0 * .25 * t)); eng = lpf(eng, body_lp)
    nz = noise(sec); air = (lpf(nz, 1800) * (1 - amp) + lpf(nz, 6000) * amp) * nz_gain   # hiss brightens at the pass
    return (eng * .5 + air) * amp
def whoosh_car(): return passby(1.4, 72, 900, .4, .9)
def whoosh_bike(): return passby(1.0, 145, 2200, .7, .55)      # 2-wheeler: buzzy, quicker
def whoosh_auto(): return passby(1.3, 105, 1600, .9, .6)       # rickshaw: rattly 2-stroke
def whoosh_bus(): return passby(2.2, 46, 600, .3, 1.2)         # bus/truck: heavy and long
def whoosh_air():  # pure air whoosh (from engine), stretched/darkened
    x = np.concatenate([S.whoosh(), np.zeros(int(.1 * SR))]); return lpf(x, 3000)

# ---------------- ambient city bed (20 s, quiet, loop-friendly ends faded) ----------------
def city_bed(sec=20.0):
    n = int(sec * SR); t = np.arange(n) / SR
    rumble = lpf(noise(sec), 180) * 3.0
    hiss = lpf(noise(sec), 2500) * (.35 + .1 * np.sin(2 * np.pi * .13 * t))
    idle = lpf(saw(38 + 2 * np.sin(2 * np.pi * .3 * t), t, 8), 300) * .25
    bed = rumble + hiss + idle
    # crowd murmur: band-limited noise with syllable-rate modulation
    mur = bpf(noise(sec), 250, 1400) * (.5 + .5 * np.abs(np.sin(2 * np.pi * 3.1 * t + 2 * np.sin(t)))) * .35
    bed += mur
    # distant traffic + horns (low-passed, quiet), random spacing
    k = .4
    while k < sec - 2.4:
        ch = R.integers(0, 5)
        src = [horn_auto, horn_car, horn_bike, whoosh_car, whoosh_bike][ch]()
        add(bed, lpf(src, 1200) * (.25 if ch < 3 else .6), k); k += R.uniform(.9, 2.2)
    return bed

# ---------------- footsteps ----------------
def step(hard=1.0):  # sandal/shoe on asphalt: low thump + gritty scuff
    t = T(.16); thump = tone(95 * np.exp(-t * 20) + 60, t) * np.exp(-t * 45) * .8
    scuff = bpf(noise(.16), 900, 5000) * np.exp(-t * 35) * .35
    return (thump + scuff) * hard
def steps(sec, rate, jitter=.02, accent=0):
    out = np.zeros(int(sec * SR)); k = .03; i = 0
    while k < sec - .16:
        add(out, step(1.0 if i % 2 == 0 else .82), k + R.uniform(-jitter, jitter)); i += 1; k += 1 / rate
    return out

# ---------------- hi-fi clap + sparkle ----------------
def hifi():
    out = np.zeros(int(1.4 * SR)); t = T(.12)
    clap = bpf(noise(.12), 700, 6000) * np.exp(-t * 38)
    for d, g in ((0, 1), (.007, .7), (.014, .45)): add(out, clap, d, g)       # flam = two palms
    add(out, tone(160 * np.exp(-t * 12) + 70, t) * np.exp(-t * 30) * .6, 0)  # body thump
    notes = [1568, 2093, 2637, 3136, 4186]                                   # rising sparkle chime
    for j, f in enumerate(notes):
        tt = T(.6); ch = (tone(f, tt) + .4 * tone(f * 2.76, tt)) * np.exp(-tt * 7) * .22
        add(out, ch, .06 + j * .055)
    tw = T(.9)                                                                # glitter shimmer tail
    add(out, bpf(noise(.9), 6000, 12000) * np.exp(-tw * 4) * (.6 + .4 * np.sin(2 * np.pi * 23 * tw)) * .15, .1)
    return out

# ---------------- chai pour + kulhad clink ----------------
def chai_pour(sec=1.8):
    base = S.pour(sec); n = len(base); t = np.arange(n) / SR
    stream = lpf(base, 2200) * 4
    out = stream * adsr(n, .08, .25)
    k = .1                                                    # bubbles / glugs rising as kulhad fills
    while k < sec - .2:
        bt = T(.05); f = (500 + 600 * k / sec) * (1 + 1.5 * bt / .05)
        add(out, tone(f, bt) * np.exp(-bt * 70) * .12, k); k += R.uniform(.03, .09)
    add(out, S.plip() * .8, sec - .12)                       # last drip
    return out
def kulhad_clink():  # clay cups: dull, woody, quick (not glassy)
    out = np.zeros(int(.5 * SR)); t = T(.35)
    hit = sum(a * tone(f, t) * np.exp(-t * d) for f, a, d in ((820, 1, 28), (1370, .7, 35), (2190, .45, 45), (3050, .25, 60)))
    hit += bpf(noise(.35), 1500, 6000) * np.exp(-t * 90) * .5
    add(out, hit, 0); add(out, hit * .55, .07)                # two cups knock, slight double
    return out
def cheers_clink():  # several kulhads together
    out = np.zeros(int(.8 * SR)); k = kulhad_clink()
    for d, g in ((0, 1), (.045, .8), (.11, .6), (.16, .5)): add(out, k * g, d)
    return out

# ---------------- laugh / cheer (stylised, synthesised) ----------------
VOW = {'a': (800, 1200, 2500), 'e': (500, 1800, 2600), 'i': (330, 2300, 3000)}
def voice(f0, sec, vowel='a', breath=.25):
    t = T(sec); f = f0 * (1 + .02 * np.sin(2 * np.pi * 5.5 * t)); src = saw(f, t, 25) + breath * noise(sec)
    return sum(bpf(src, F * .85, F * 1.15) * g for F, g in zip(VOW[vowel], (1, .6, .3)))
def ha_burst(f0, n, rate=6.5, vowel='a', fall=.12):
    sec = n / rate + .15; out = np.zeros(int(sec * SR))
    for i in range(n):
        d = .5 / rate; v = voice(f0 * (1 - fall * i / n), d, vowel)
        h = bpf(noise(.04), 1000, 4000) * .3                  # the "h"
        seg = np.concatenate([h, v]) * adsr(len(h) + len(v), .01, .04); add(out, seg, i / rate)
    return out
def laugh_group():
    out = np.zeros(int(1.9 * SR))
    for f0, n, at, vw, g in ((240, 7, 0, 'a', 1), (300, 6, .08, 'e', .8), (190, 6, .15, 'a', .7), (330, 5, .25, 'i', .6)):
        add(out, ha_burst(f0, n, R.uniform(5.8, 7.0), vw), at, g)
    return out
def cheer():  # short "yaay" + claps
    out = np.zeros(int(1.6 * SR))
    for f0, at, g in ((280, 0, 1), (340, .05, .8), (230, .1, .7)):
        t = T(.9); v = voice(f0 * (1 + .25 * np.sin(np.pi * t / .9)), .9, 'e') * adsr(len(t), .05, .3); add(out, v, at, g)
    for k in np.cumsum(R.uniform(.09, .16, 9)) + .2:
        tt = T(.06); add(out, bpf(noise(.06), 800, 6000) * np.exp(-tt * 60) * .5, k)
    return out

# ---------------- desi music bed (~20 s): tanpura drone + santoor-ish plucks + dholak keherwa ----------------
def music_bed(sec=20.0, bpm=104):
    n = int(sec * SR); out = np.zeros(n); t = np.arange(n) / SR
    Sa = 220.0                                                   # A3 as Sa
    # tanpura: Pa-Sa-Sa-Sa' cycle, buzzy, slow swells
    tp_notes = [Sa * 1.5 / 2, Sa, Sa, Sa / 2]; k = 0.0; i = 0
    while k < sec:
        tt = T(2.6); f = tp_notes[i % 4]
        x = saw(f, tt, 18) * (1 + .3 * np.sin(2 * np.pi * 3 * tt)); x = lpf(x, 1800) * np.minimum(1, tt / .3) * np.exp(-tt * .9)
        add(out, x * .05, k); k += .65; i += 1
    # santoor-like plucks: Khamaj-ish (major with flat 7 on the way down), bright and playful
    sw = {'S': 1, 'R': 9 / 8, 'G': 5 / 4, 'm': 4 / 3, 'P': 3 / 2, 'D': 5 / 3, 'n': 16 / 9, "S'": 2, "R'": 9 / 4, "G'": 5 / 2}
    phrase = ("G m P - D P m G | R G m - G R S - | P D n D P m G m | G R S - - - - - |"
              "S' - n D P - m G | m P D P m G R G | G m P D n S' n D | P m G R S - - - |")
    beat = 60 / bpm / 2                                          # 8th notes
    seq = [s for s in phrase.replace('|', ' ').split()]
    k = beat * 8                                                 # melody enters after 1 bar of drone + dholak
    for s in seq * 3:
        if k > sec - 1.0: break
        if s != '-':
            f = Sa * 2 * sw[s]; tt = T(1.0)
            x = sum(a * tone(f * h * (1 + .0007 * h * h), tt) * np.exp(-tt * (5 + 2 * h)) for h, a in ((1, 1), (2, .5), (3, .25), (4, .12)))
            x[:441] += bpf(noise(.01), 2000, 8000) * np.linspace(.15, 0, 441)   # mallet tick
            add(out, x * .07, k)
            if R.random() < .25: add(out, x * .035, k + beat / 2)   # occasional santoor double-strike
        k += beat
    # dholak keherwa (8 beats): dha ge na ti | na ka dhi na
    def bayan(): tt = T(.35); return tone(95 * (1 + .6 * np.exp(-tt * 25)), tt) * np.exp(-tt * 9)
    def dayan(): tt = T(.15); return (tone(520, tt) + .5 * tone(780, tt)) * np.exp(-tt * 30) + bpf(noise(.15), 1500, 6000) * np.exp(-tt * 60) * .4
    def ka(): tt = T(.06); return bpf(noise(.06), 600, 3000) * np.exp(-tt * 70)
    pat = [('B', 'D'), ('B',), ('D',), ('K',), ('D',), ('K',), ('B', 'D'), ('D',)]
    k = 0.0; i = 0
    while k < sec - .4:
        for h in pat[i % 8]:
            src = {'B': bayan, 'D': dayan, 'K': ka}[h]()
            add(out, src * (.09 if h == 'B' else .05) * (1.15 if i % 8 == 0 else 1), k + R.uniform(-.004, .004))
        k += beat; i += 1
    # gentle manjira on 1 and 5
    k = 0.0; i = 0
    while k < sec - .4:
        if i % 4 == 0:
            tt = T(.5); add(out, (tone(3200, tt) + .7 * tone(4730, tt)) * np.exp(-tt * 6) * .012, k)
        k += beat; i += 1
    env = np.minimum(1, t / 1.0) * np.minimum(1, (sec - t) / 1.5)  # 1 s fade-in, 1.5 s fade-out
    return out * env

if __name__ == '__main__':
    save('horn_auto', horn_auto()); save('horn_car', horn_car()); save('horn_car_long', horn_car_long())
    save('horn_truck', horn_truck()); save('horn_bike', horn_bike()); save('cycle_bell', cycle_bell(), .5)
    save('whoosh_car', whoosh_car()); save('whoosh_bike', whoosh_bike()); save('whoosh_auto', whoosh_auto())
    save('whoosh_bus', whoosh_bus()); save('whoosh_air', whoosh_air(), .5)
    save('ambience_city_bed', city_bed(20.0), .3)
    save('footstep_single', step(), .6); save('footsteps_walk', steps(2.4, 2.0), .6); save('footsteps_hurry', steps(1.8, 4.6, .012), .6)
    save('hifi_clap_sparkle', hifi()); save('chai_pour', chai_pour(1.8), .5)
    save('kulhad_clink', kulhad_clink(), .6); save('kulhad_cheers', cheers_clink(), .6)
    save('laugh_group', laugh_group(), .5); save('cheer_yay', cheer(), .5)
    save('music_bed_desi', music_bed(20.0), .35)
    for k, v in OUT.items(): print(f'{k}.wav {v:.2f}s')
