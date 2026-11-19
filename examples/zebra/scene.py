"""Zebra crossing: ~18 s pose-pack sample (gouache desi illustration).
Girl waits at a busy Indian zebra crossing, braves the median while traffic streams both ways,
hurries across on 'bhaago!', hard cut to the chai tapri: friends wave, chai pours, hi-fi, laughs.

Only generated raster assets (pose packs, walk cycle, panorama, vehicle cutouts). No vector characters.
Everything is drawn in SCREEN space (sprites scaled per frame) so close-ups stay sharp.

    PREVIEW=1.0,4.0,6.0 python3 scene.py      # stills -> pv/pv_XX.X.jpg
    python3 scene.py                          # final.mp4
"""
import os, sys, math, json, wave, random, subprocess
import numpy as np, cv2
from PIL import Image
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', '..', 'engine'))
from motion import ease, ease_out, ease_in, back, squash, xform, paste, place_pivot, clamp, make_finish, ffmpeg_writer
from posepack import Cast, seq, alpha_bbox

W, H, FPS = 1920, 1080, 24
G, ST, TP, AU = HERE + '/girl/', HERE + '/street/', HERE + '/tapri/', HERE + '/audio/'

# ------------------------------------------------------------------ timing (VO split per phrase)
VT = json.load(open(AU + 'vo_timing.json'))['segments']
# where each phrase lands in the cut (seconds). Street part is stretched around the VO.
VO_AT = [1.15, 4.85, 8.05, 9.05, 10.95, 11.95, 14.15]
T_WALK0, T_MEDIAN = 3.25, 4.65            # kerb -> median walk; hard cut to medium shot at T_MEDIAN
T_GO, T_HURRY0, T_HURRY1 = 8.95, 9.30, 10.55
T_CUT = 10.85                             # hard cut to tapri
T_HIFI = VO_AT[6] + 0.08                  # palm impact on "Hi-fi!"
DUR = 18.0
EV = []                                   # (t, wav name, gain)

# ------------------------------------------------------------------ street world (1080-high coords)
PAN = cv2.imread(ST + 'street_panorama.png'); s = 1080 / PAN.shape[0]
PAN = cv2.resize(PAN, (int(round(PAN.shape[1] * s)), 1080), interpolation=cv2.INTER_LANCZOS4).astype(np.float32)
PW = PAN.shape[1]
FAR_BASE, NEAR_BASE = 781, 1022
KERB_Y, MED_Y, FARK_Y = 1066, 850, 664      # near pavement, median path, far footpath (feet y)
X_CROSS = 1630                               # zebra centre line; she crosses straight DOWN the screen
P_START, P_FARK, P_MED, P_EXIT = (1330, FARK_Y), (X_CROSS, FARK_Y), (X_CROSS, MED_Y), (X_CROSS + 30, 1260)
HB = 240                                 # girl height (world px) at the near kerb
ZMAX = 2.0                               # sprites are prescaled for the closest zoom, then shrunk

# median plants sit in front of far-lane wheels: colour-key them out of the panorama as an occluder
_b, _g, _r = [PAN[..., i] for i in range(3)]
_m = ((_b < _g - 22) & (_r > 60)).astype(np.float32); _m[:715] = 0; _m[800:] = 0
_m = cv2.GaussianBlur(cv2.dilate(_m, np.ones((3, 3), np.uint8)), (0, 0), 1.0)
PLANTS = np.concatenate([PAN, _m[..., None] * 255], 2)

def depth(y):                            # perspective: smaller up the road, grows fast as she nears camera
    if y > KERB_Y: return 1.0 + 0.6 * (y - KERB_Y) / 200
    return 1.0 - 0.14 * clamp((KERB_Y - y) / (KERB_Y - FARK_Y))

# ---- girl casts (front pose pack + side walk cycle), prescaled for ZMAX
POSES = ['idle', 'look', 'worried', 'impatient', 'flinch', 'go', 'wave', 'hifi', 'laugh', 'sip']
GIRL = Cast(G + 'girl', POSES, x=0, floor=0, scale=HB * ZMAX / 1274, phase=0.3, sway=0.6, bob=0, pop=0.07, shadow=False)
walk = [Image.open(G + f'walk_{i}.png').convert('RGBA') for i in range(6)]
GW = Cast(G + 'girl', [], x=0, floor=0, scale=HB * ZMAX / 465, cycles={'walk': walk}, sway=0.2, bob=0, pop=0, shadow=False)

# front-view walk / hurry cycles (768x1370 canvas, feet baseline y=1345 like the pose pack). Registered on that FIXED
# baseline (not each frame's own alpha bottom) so the passing frames keep their authored lift instead of being pulled down.
FRONT_BASE, WALK_FPS_F, HURRY_FPS = 1345, 6.0, 11.0
def _front_cycle(name, files):
    k = HB * ZMAX / 1274                   # same scale as the front pose pack
    for i, f in enumerate(files):
        im = Image.open(G + f).convert('RGBA'); im = im.resize((int(im.width * k), int(im.height * k)), Image.LANCZOS)
        GIRL.P[f'{name}{i}'] = (im, (im.width / 2, FRONT_BASE * k), k)
_front_cycle('fwalk', [f'front_walk_{i}.png' for i in range(4)])     # 0,2 contact; 1,3 passing
_front_cycle('fhurry', [f'front_hurry_{i}.png' for i in range(6)])

def _side_step_frac():
    """step length / figure height of the side walk sheet: distance between the two feet at contact (walk_0)"""
    a = np.array(walk[0])[..., 3] > 40; ys, xs = np.where(a); y1 = ys.max(); band = a[y1 - 25:y1 + 1].any(0)
    cols = np.where(band)[0]; gaps = np.where(np.diff(cols) > 8)[0]
    if len(gaps) == 0: return 0.36
    l, r = cols[:gaps[0] + 1], cols[gaps[0] + 1:]
    return (r.mean() - l.mean()) / (ys.max() - ys.min())
SIDE_STEP = _side_step_frac()             # ~0.36 of her height

def flutter(im, t, amp, seed=0.0):
    """living-pose warp: hair + dupatta tips (right of the body, above the knees) ripple in the wind"""
    a = np.array(im); h, w = a.shape[:2]
    bx0, _, bx1, _ = alpha_bbox(im); cx = bx0 + (bx1 - bx0) * 0.52
    xs, ys = np.meshgrid(np.arange(w, dtype=np.float32), np.arange(h, dtype=np.float32))
    wgt = np.clip((xs - cx) / (w * 0.22), 0, 1) ** 1.4 * np.clip((h * 0.72 - ys) / (h * 0.1), 0, 1)
    ph = xs / h * 2 * math.pi * 2.2 - t * 13 + seed
    mx = xs - amp * 0.5 * wgt * np.sin(ys / h * 2 * math.pi * 3 - t * 11 + seed)
    my = ys - amp * wgt * np.sin(ph)
    out = cv2.remap(a, mx.astype(np.float32), my.astype(np.float32), cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0, 0))
    return Image.fromarray(out)

def draw_cast(fr, cast, t, pose, sx, sy, k, rot=0, dy=0, flut=0.0, flip=False, sq=(1, 1)):
    """draw a Cast pose at screen (sx,sy) with extra scale k (<=1); optional living warp"""
    cast.x, cast.floor = sx, sy
    if flut > 0 and pose in cast.P:
        im, piv, kk = cast.P[pose]
        cast.P[pose] = (flutter(im, t, flut / max(k, 0.3)), piv, kk)
        cast.draw(fr, t, pose, rot=rot, dy=dy, sq=(k * sq[0], k * sq[1]), flip=flip)
        cast.P[pose] = (im, piv, kk)
    else:
        cast.draw(fr, t, pose, rot=rot, dy=dy, sq=(k * sq[0], k * sq[1]), flip=flip)

def shadow(fr, x, y, rx, ry, op=0.28):
    ov = np.zeros(fr.shape[:2], np.float32)
    cv2.ellipse(ov, (int(x), int(y)), (max(1, int(rx)), max(1, int(ry))), 0, 0, 360, 1.0, -1, cv2.LINE_AA)
    ov = cv2.GaussianBlur(ov, (0, 0), max(1, ry * 0.6))[..., None] * op
    fr[:] = fr * (1 - ov) + np.array([60, 40, 50], np.float32) * ov

# ---- vehicles: (file, world width near lane, speed px/s, whoosh, bob)
VK = {'car': ('car', 380, 1000, 'whoosh_car', 1.5), 'auto': ('auto_rickshaw', 330, 920, 'whoosh_auto', 3.0),
      'scooter': ('scooter_rider', 250, 950, 'whoosh_bike', 2.5), 'bike': ('motorbike', 255, 1000, 'whoosh_bike', 2.5),
      'bus': ('bus', 950, 880, 'whoosh_bus', 1.2)}
VIMG = {}
for k, (f, w_, *_r) in VK.items():
    im = Image.open(ST + f + '.png').convert('RGBA'); bb = alpha_bbox(im); im = im.crop((bb[0], bb[1], bb[2] + 1, bb[3] + 1))
    VIMG[k] = im.resize((int(w_ * ZMAX), int(im.height * w_ * ZMAX / im.width)), Image.LANCZOS)
ZX = 1630                                 # where vehicles pass the girl
LANES = {'near': dict(base=NEAR_BASE, dir=-1, k=1.0), 'far': dict(base=FAR_BASE, dir=+1, k=0.9)}
BLOCK = {'far': [(3.0, 4.75, 1380, 1880)],                      # gap while she steps across the far lane
         'near': [(8.1, 10.95, 1330, 1930)]}                    # 'Gap mila...' -> she hurries across the near lane
FORCED = [('near', 'bus', 5.85, False), ('far', 'auto', 7.42, True), ('near', 'car', 2.2, True), ('far', 'bike', 0.9, True),
          ('near', 'scooter', 6.8, False), ('near', 'car', 7.55, True), ('far', 'scooter', 5.35, False), ('far', 'bus', 1.75, False),
          ('far', 'car', 6.0, False), ('near', 'auto', 7.25, False), ('near', 'auto', 3.6, False), ('near', 'scooter', 4.3, True)]

def vx(v, t): return ZX + v['dir'] * v['speed'] * (t - v['tc'])

def build_traffic(seed=5):
    rng = random.Random(seed); out = []
    def ok(c):
        L = LANES[c['lane']]
        for (a, b, x0, x1) in BLOCK[c['lane']]:
            for t in np.arange(a, b, 0.02):
                x = vx(c, t); hw = c['w'] / 2
                if x + hw > x0 and x - hw < x1: return False
        for o in out:
            if o['lane'] != c['lane']: continue
            for t in np.arange(0, T_CUT, 0.04):
                d = abs(vx(c, t) - vx(o, t))
                if d < (c['w'] + o['w']) / 2 + 50 and -500 < vx(c, t) < PW + 500: return False
        return True
    def mk(lane, kind, tc, honk):
        f, w_, sp, wh, bob = VK[kind]; k = LANES[lane]['k']
        return dict(lane=lane, kind=kind, tc=tc, speed=sp * rng.uniform(0.96, 1.04) * (0.92 if lane == 'far' else 1), w=w_ * k,
                    dir=LANES[lane]['dir'], base=LANES[lane]['base'], k=k, honk=honk, wh=wh, bob=bob, ph=rng.uniform(0, 6))
    for lane, kind, tc, honk in FORCED:
        c = mk(lane, kind, tc, honk)
        if ok(c): out.append(c)
    kinds = ['car'] * 4 + ['auto'] * 4 + ['scooter'] * 3 + ['bike'] * 3 + ['bus']
    for lane in ('near', 'far'):
        tc = -2.0
        while tc < T_CUT + 2.5:
            tc += rng.uniform(0.22, 0.5)
            c = mk(lane, rng.choice(kinds), tc, rng.random() < 0.18)
            if ok(c): out.append(c)
    return out
TRAFFIC = build_traffic()

def draw_vehicle(fr, v, t, cam):
    L, T, z = cam
    x = vx(v, t); im = VIMG[v['kind']]
    k = v['k'] * z / ZMAX; w_, h_ = im.width * k, im.height * k
    sx, sy = (x - L) * z, (v['base'] - T) * z
    if sx + w_ / 2 < -50 or sx - w_ / 2 > W + 50: return
    bob = v['bob'] * z * abs(math.sin(t * 17 + v['ph']))
    shadow(fr, sx, sy - 2 * z, w_ * 0.46, 9 * z, 0.32)
    img = im.resize((max(2, int(w_)), max(2, int(h_))), Image.BILINEAR)
    if v['dir'] < 0: img = img.transpose(Image.FLIP_LEFT_RIGHT)
    a = np.array(img).astype(np.float32); pm = a.copy(); pm[..., :3] *= a[..., 3:4] / 255
    blur = int(clamp(v['speed'] * z / FPS * 0.35, 1, 70))     # motion blur along travel
    if blur > 2:
        pad = np.zeros((pm.shape[0], blur, 4), np.float32); pm = np.concatenate([pad, pm, pad], 1)
        pm = cv2.blur(pm, (blur, 1))
    al = np.clip(pm[..., 3:4], 1e-3, 255); rgb = pm[..., :3] / al * 255
    out = np.concatenate([np.clip(rgb, 0, 255), pm[..., 3:4]], 2).astype(np.uint8)
    rot = 0.6 * math.sin(t * 9 + v['ph']) if v['kind'] in ('auto', 'scooter', 'bike') else 0
    pim = Image.fromarray(out)
    place_pivot(fr, pim, sx, sy - bob, (pim.width / 2, pim.height - 2), rot)
    # speed streaks behind it
    tail = sx - v['dir'] * w_ * 0.55
    r = random.Random(int(t * FPS) * 7 + int(v['tc'] * 100))
    for i in range(3):
        yy = sy - h_ * r.uniform(0.15, 0.75); ln = r.uniform(60, 160) * z
        cv2.line(fr, (int(tail), int(yy)), (int(tail - v['dir'] * ln), int(yy)), (245, 245, 250), max(1, int(2 * z)), cv2.LINE_AA)

T_STOP = 2.0                              # reaches the zebra on the far footpath

def girl_state(t):
    """world (x, y), pose name, cast, rot, dy.  Side-view walk ALONG the far footpath; front poses
    (hard cuts) stepping DOWN-screen across each lane toward camera."""
    if t < T_STOP:                        # walk cycle along the far footpath; cadence tied to ground speed / stride
        u = t / T_STOP; x = P_START[0] + (P_FARK[0] - P_START[0]) * u
        speed = (P_FARK[0] - P_START[0]) / T_STOP                   # world px/s
        step = SIDE_STEP * HB * depth(FARK_Y)                       # world px per step at her size on the footpath
        fps = 3.0 * speed / step                                    # 6-frame sheet = 2 steps -> 3 frames per step
        ph = t * fps
        return (x, FARK_Y), GW.cycle('walk', t, fps), GW, -1.5, -3 * abs(math.sin(ph * math.pi / 3))
    if t < T_WALK0:                       # stops at the far kerb, sizes up the traffic
        return P_FARK, seq(t, [(T_STOP, 'look'), (2.75, 'worried')]), GIRL, 0, 0
    if t < T_MEDIAN:                      # walks across the far lane toward camera: front walk cycle at 6 fps
        u = (t - T_WALK0) / (T_MEDIAN - T_WALK0); y = FARK_Y + (MED_Y - FARK_Y) * u
        ph = (t - T_WALK0) * WALK_FPS_F                              # frame phase; odd frames are passing frames
        dy = -2.5 * (1 - math.cos(math.pi * (ph - 0.5))) / 2         # small rise peaking mid passing frame
        return (X_CROSS, y), GIRL.cycle('fwalk', t - T_WALK0, WALK_FPS_F), GIRL, 0.8 * math.sin(math.pi * ph / 2), dy
    if t < T_HURRY0:                      # stuck on the median
        pose = seq(t, [(T_MEDIAN, 'worried'), (5.0, 'flinch'), (6.15, 'worried'), (6.85, 'impatient'), (7.5, 'flinch'),
                       (8.05, 'look'), (T_GO, 'go')])
        dy = 0
        if pose == 'flinch': k = t - (5.0 if t < 7 else 7.5); dy = 7 * math.sin(k * 60) * math.exp(-k * 6)
        if pose == 'impatient': dy = -5 * abs(math.sin(t * 9))              # foot tapping bounce
        return P_MED, pose, GIRL, 0, dy
    x_ = clamp((t - T_HURRY0) / (T_CUT - T_HURRY0))
    u = x_ ** 1.35                        # hurries down across the near lane and out (mild accel: legs never pump on the spot)
    x = P_MED[0] + (P_EXIT[0] - P_MED[0]) * u; y = P_MED[1] + (P_EXIT[1] - P_MED[1]) * u
    ph = (t - T_HURRY0) * HURRY_FPS       # 6-frame hurry cycle = 2 steps
    return (x, y), GIRL.cycle('fhurry', t - T_HURRY0, HURRY_FPS), GIRL, 1.2 * math.sin(math.pi * ph / 3), -4 * abs(math.sin(math.pi * ph / 3))

def street_cam(t):
    """(L, T, z) of the view in world px"""
    if t < T_MEDIAN:
        u = ease(t / T_STOP); cx = 1380 + 270 * u; z = 1.0; cy = 540
        if t > T_WALK0:
            k = ease((t - T_WALK0) / (T_MEDIAN - T_WALK0)); z = 1.0 + 0.22 * k; cy = 540 + 200 * k
    elif t < T_HURRY0:
        k = (t - T_MEDIAN) / (T_HURRY0 - T_MEDIAN); z = 1.8 + 0.12 * ease(k); cx = X_CROSS + 30; cy = 735
    else:
        (gx, gy), *_ = girl_state(t); z = 1.92; cx = X_CROSS + 30; cy = 735 + (gy - P_MED[1]) * 0.5
    L = clamp(cx - W / 2 / z, 0, PW - W / z); T = clamp(cy - H / 2 / z, 0, 1080 - H / z)
    return L, T, z

def street_frame(t, step):
    L, T, z = street_cam(t)
    if T_MEDIAN < t < T_HURRY0:             # rumble shake when big ones pass close
        for v in TRAFFIC:
            if v['kind'] == 'bus' and abs(vx(v, t) - ZX) < 500: L += 2.5 * math.sin(t * 70) / z; T += 1.5 * math.cos(t * 61) / z
    M = np.array([[z, 0, -L * z], [0, z, -T * z]], np.float32)
    fr = cv2.warpAffine(PAN, M, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
    cam = (L, T, z)
    (gx, gy), pose, cast, rot, dy = girl_state(t)
    # wind on hair: from vehicles passing close
    wind = sum(math.exp(-abs(vx(v, t) - gx) / 350) * v['speed'] / 900 for v in TRAFFIC if abs(v['base'] - gy) < 300)
    flut = (2.5 + 9 * min(1.5, wind)) * z
    dk = depth(gy) * z / ZMAX
    gsx, gsy = (gx - L) * z, (gy - T) * z
    def draw_girl():
        shadow(fr, gsx, gsy - 2, 70 * dk * ZMAX, 9 * dk * ZMAX)
        draw_cast(fr, cast, t, pose, gsx, gsy, dk, rot=rot, dy=dy * z, flut=flut if cast is GIRL else 0)
    layers = [(v['base'], 0, v) for v in TRAFFIC] + [(gy, 1, None), (FAR_BASE + 2, 2, None)]
    for base, kind, v in sorted(layers, key=lambda e: (e[0], e[1])):
        if kind == 1: draw_girl()
        elif kind == 2:
            pl = cv2.warpAffine(PLANTS, M, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT)
            al = pl[..., 3:4] / 255; fr[:] = fr * (1 - al) + pl[..., :3] * al
        else: draw_vehicle(fr, v, t, cam)
    # 'go' beat: action lines + pop
    if T_GO <= t < T_GO + 0.35:
        hx, hy = gsx, gsy - HB * dk * ZMAX * 1.05; a = 1 - (t - T_GO) / 0.35
        for ang in range(-150, -20, 26):
            r = math.radians(ang); r0, r1 = 40 * z, (70 + 50 * (1 - a)) * z
            cv2.line(fr, (int(hx + r0 * math.cos(r)), int(hy + r0 * math.sin(r))), (int(hx + r1 * math.cos(r)), int(hy + r1 * math.sin(r))),
                     (40, 40, 60), max(2, int(3 * z)), cv2.LINE_AA)
    return fr

# ------------------------------------------------------------------ tapri (filled in once assets exist)
TAPRI = None
def tapri_frame(t, step):
    global TAPRI
    if TAPRI is None:
        import tapri_shot as TS                    # kept in its own module so the street part can render alone
        TAPRI = TS.Shot(HERE, T_CUT, VO_AT, T_HIFI, EV, GIRL, draw_cast, shadow)
    return TAPRI.frame(t, step)

# ------------------------------------------------------------------ finishing: gouache paper grain
def paper_texture(seed=11):
    rs = np.random.RandomState(seed); tex = np.zeros((H, W), np.float32)
    for sc, amp in ((3, 0.5), (9, 0.35), (40, 0.25)):
        n = cv2.resize(rs.randn(H // sc + 2, W // sc + 2).astype(np.float32), (W, H), interpolation=cv2.INTER_CUBIC); tex += n * amp
    fib = cv2.GaussianBlur(rs.randn(H, W).astype(np.float32), (0, 0), 0.7)
    fib = cv2.filter2D(fib, -1, np.ones((1, 9), np.float32) / 9)          # faint horizontal paper fibres
    tex = tex / tex.std() * 0.035 + fib / fib.std() * 0.018
    return (1 + tex)[..., None]
PAPER = paper_texture()
FINISH = make_finish(W, H, vignette=0.14, grain=2.2)

def frame(t, step):
    fr = street_frame(t, step) if t < T_CUT else tapri_frame(t, step)
    fr = fr * PAPER
    fr = fr * 0.97 + np.array([238, 244, 250], np.float32) * 0.03       # warm paper lift
    if t < 0.35: fr *= t / 0.35
    if t > DUR - 0.6: fr *= max(0, (DUR - t) / 0.6)
    return FINISH(fr, step, flicker=0.006)

# ------------------------------------------------------------------ audio
SR = 44100
def wav(name):
    w = wave.open(AU + name + '.wav'); a = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768
    return a

def street_events():
    ev = []
    for v in TRAFFIC:
        tc = v['tc']
        if tc > T_CUT - 0.3 or tc < -0.5: continue
        d = len(wav(v['wh'])) / SR
        g = (0.42 if T_MEDIAN < tc < T_HURRY0 + 0.6 else 0.28) * (0.8 if v['lane'] == 'far' else 1)
        ev.append((max(0, tc - d / 2), v['wh'], g))
        if v['honk']:
            hn = {'bus': 'horn_truck', 'auto': 'horn_auto', 'car': 'horn_car_long' if tc < 3 else 'horn_car', 'scooter': 'horn_bike', 'bike': 'horn_bike'}[v['kind']]
            ev.append((max(0, tc - 0.45), hn, 0.34))
    ev += [(0.3, 'horn_car', 0.22), (4.9, 'horn_truck', 0.4), (2.9, 'cycle_bell', 0.2), (0.2, 'footsteps_walk', 0.45), (T_WALK0, 'footsteps_walk', 0.45), (T_GO, 'whoosh_air', 0.5),
           (T_HURRY0, 'footsteps_hurry', 0.6)]
    return ev

import audio_mix

def tapri_events():
    """construct the tapri shot (fills EV with its SFX cues) and return EV"""
    global TAPRI
    if TAPRI is None:
        import tapri_shot as TS
        TAPRI = TS.Shot(HERE, T_CUT, VO_AT, T_HIFI, EV, GIRL, draw_cast, shadow)
    return [e for e in EV if e[0] >= T_CUT - 0.1]

def build_audio(path, stems_dir=None):
    """loudness-aware mix (audio_mix.py): VO lead at -16 LUFS, ducked beds/SFX, cheer dropped"""
    return audio_mix.build(DUR, AU, VT, VO_AT, street_events() + tapri_events(), T_CUT, path, stems_dir)

def loudnorm_filter(wav_path):
    """two-pass loudnorm (linear) to -16 LUFS / -1.5 dBTP; returns (filter string, pass-1 json).
    LRA=20: the VO-led mix has ~13 LU range (quiet beds in the gaps); with LRA=11 loudnorm silently falls back to dynamic."""
    meas = subprocess.run(['ffmpeg', '-i', wav_path, '-af', 'loudnorm=I=-16:TP=-1.5:LRA=20:print_format=json', '-f', 'null', '-'], capture_output=True, text=True).stderr
    d = json.loads(meas[meas.rindex('{'):meas.rindex('}') + 1])
    ln = (f"loudnorm=I=-16:TP=-1.5:LRA=20:measured_I={d['input_i']}:measured_TP={d['input_tp']}:measured_LRA={d['input_lra']}"
          f":measured_thresh={d['input_thresh']}:offset={d['target_offset']}:linear=true:print_format=json")
    return ln, d

if __name__ == '__main__':
    if '--audio-only' in sys.argv:              # mix.wav + stems + loudness report, no video
        mix = HERE + '/mix.wav'; vo, bed, env = build_audio(mix, HERE + '/stems')
        ln, d1 = loudnorm_filter(mix)
        out = subprocess.run(['ffmpeg', '-y', '-hide_banner', '-i', mix, '-af', ln, '-ar', '44100', '/tmp/zebra_mix_ln.wav'], capture_output=True, text=True).stderr
        d2 = json.loads(out[out.rindex('{'):out.rindex('}') + 1])
        r = audio_mix.verify(vo, bed, env, '/tmp/zebra_mix_ln.wav')
        r['loudnorm_type'] = d2['normalization_type']; r['pass1_I'], r['pass1_TP'] = d1['input_i'], d1['input_tp']
        for k, v in r.items(): print(f'{k:20s} {v}')
        sys.exit()
    PREV = [float(x) for x in os.environ.get('PREVIEW', '').split(',') if x]
    if PREV:
        os.makedirs(HERE + '/pv', exist_ok=True)
        for tp in PREV:
            st = int(tp * FPS); cv2.imwrite(f'{HERE}/pv/pv_{tp:05.2f}.jpg', frame(tp, st), [cv2.IMWRITE_JPEG_QUALITY, 88])
        sys.exit()
    END = float(os.environ.get('END', DUR))
    tmpv, tmpa = '/tmp/zebra_video.mp4', '/tmp/zebra_audio.wav'
    proc = ffmpeg_writer(tmpv, W, H, fps=FPS, out_fps=24, crf=21)
    for step in range(int(END * FPS)):
        t = step / FPS; proc.stdin.write(frame(t, step).tobytes())
        if step % 48 == 0: print('t', round(t, 1), flush=True)
    proc.stdin.close(); proc.wait()
    build_audio(tmpa)
    out = os.environ.get('OUT', HERE + '/final.mp4')
    # two-pass loudnorm to -16 LUFS; encode in /tmp (the workspace FS can fail on the faststart rewrite), then copy.
    # ~5.8 Mbps keeps 18 s of grainy 1080p under 15 MB.
    ln, _ = loudnorm_filter(tmpa)
    subprocess.run(['ffmpeg', '-y', '-v', 'error', '-i', tmpv, '-i', tmpa, '-map', '0:v', '-map', '1:a', '-af', ln, '-c:v', 'libx264', '-preset', 'medium',
                    '-b:v', '5800k', '-maxrate', '7000k', '-bufsize', '12000k', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '160k', '-ar', '48000',
                    '-shortest', '-movflags', '+faststart', '/tmp/zebra_final.mp4'], check=True)
    subprocess.run(['cp', '/tmp/zebra_final.mp4', out], check=True)
    print('done', out)
