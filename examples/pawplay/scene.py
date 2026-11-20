"""Paw Playlists: ~18 s 'social media intro' pin brought to life, in a hand-drawn Korean-doodle look.

Pose packs (AI key poses, hard cuts) for five animals peeking in from the edges: frog (top-left), dog (left),
crow (right), cat (bottom, with a separate swaying tail) and a hamster that drops onto the title.
Heads track a bouncing music note, blinks at offset times, staggered title pop, button press, end hold.
A whole-frame line boil (3 noise fields cycled at 10 fps) gives the hand-made wobble.

    python3 prep.py                              # clean cut-outs -> assets/clean/
    PREVIEW=2,5,7,9.7,13.6,17 python3 scene.py   # stills -> pv/
    python3 audio.py                             # sfx + music bed -> mix.wav (uses the cue list below)
    python3 ../../engine/chunkrender.py scene.py --chunks 6 --audio mix.wav --loudnorm --out final.mp4
"""
import math, os, sys
import numpy as np, cv2
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '../../engine'))
from motion import ease, ease_out, ease_in, back, elastic, clamp, squash, make_finish

W, H, FPS, DUR = 1920, 1080, 24, 18.0
BG = (169, 195, 214)                  # dusty blue (RGB)
INK = (43, 43, 51)                    # charcoal outline (RGB)
MINT = (159, 220, 184)
CL = os.path.join(HERE, 'assets', 'clean')
FONT = os.path.join(HERE, '../../fonts/Fredoka.ttf')


# ---------------------------------------------------------------- fast affine blit (RGBA float, premultiplied)
def load_rgba(path, scale=1.0, extend_bottom=0, shear=0.0, follow=False):
    im = Image.open(path).convert('RGBA')
    if extend_bottom:      # edge peekers are cropped flat at the bottom: continue the body below the frame
        a = np.array(im)
        if follow:         # continue the left outline along its own measured slope (no kink, no stair-step)
            al = a[..., 3]; ys = np.arange(a.shape[0] - 40, a.shape[0] - 2)
            xs = np.array([np.argmax(al[y] > 128) for y in ys], np.float32)
            slope = float(np.polyfit(ys, xs, 1)[0])              # px right per row at the crop line
            tmpl = a[-3].astype(np.float32); xi = np.arange(a.shape[1], dtype=np.float32)
            rows = []
            for r in range(1, extend_bottom + 3):
                off = slope * r
                row = np.stack([np.interp(xi - off, xi, tmpl[:, c], left=0, right=tmpl[-1, c]) for c in range(4)], -1)
                rows.append(row)
            a = np.vstack([a[:-2], np.stack(rows).clip(0, 255).astype(np.uint8)])
        else:
            last = a[-1]; rows = []
            for r in range(1, extend_bottom + 1):  # shear > 0 slants the continued outline down-right (body widens)
                rows.append(np.roll(last, int(r * shear), 0) if shear else last)
                if shear: rows[-1][:int(r * shear)] = 0
            a = np.vstack([a, np.stack(rows)])
        im = Image.fromarray(a, 'RGBA')
    if scale != 1.0: im = im.resize((round(im.width * scale), round(im.height * scale)), Image.LANCZOS)
    a = np.array(im).astype(np.float32)
    a[..., :3] *= a[..., 3:4] / 255.0
    return a[..., [2, 1, 0, 3]].copy()            # premultiplied BGRA


def blit(fr, src, anchor, at, sx=1.0, sy=1.0, rot=0.0, alpha=1.0):
    """place src so its pixel `anchor` lands on screen point `at`, scaled (sx, sy; negative sx = flip)
    and rotated rot degrees (CCW) about the anchor."""
    if alpha <= 0.003: return
    h, w = src.shape[:2]
    a = math.radians(rot); c, s = math.cos(a), math.sin(a)
    A = np.array([[c * sx, s * sy], [-s * sx, c * sy]], np.float32)
    t = np.array(at, np.float32) - A @ np.array(anchor, np.float32)
    corners = np.array([[0, 0], [w, 0], [0, h], [w, h]], np.float32) @ A.T + t
    x0, y0 = np.floor(corners.min(0)).astype(int); x1, y1 = np.ceil(corners.max(0)).astype(int)
    X0, Y0, X1, Y1 = max(x0, 0), max(y0, 0), min(x1, W), min(y1, H)
    if X1 <= X0 or Y1 <= Y0: return
    M = np.hstack([A, (t - [X0, Y0])[:, None]]).astype(np.float32)
    out = cv2.warpAffine(src, M, (X1 - X0, Y1 - Y0), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=0)
    if alpha < 1: out *= alpha
    al = out[..., 3:4] / 255.0
    reg = fr[Y0:Y1, X0:X1]
    reg *= (1 - al); reg += out[..., :3]


# ---------------------------------------------------------------- pose-pack actor (hard cuts + living pose)
class Actor:
    def __init__(self, name, poses, scale, anchor, at, flip=False, phase=0.0, head=None, extend_bottom=0, shear=0.0, follow=False):
        self.P = {p: load_rgba(f'{CL}/{name}_{p}.png', scale, extend_bottom, shear, follow) for p in poses}
        self.k, self.anchor, self.at, self.flip, self.phase = scale, (anchor[0] * scale, anchor[1] * scale), at, flip, phase
        self.head = head or at                     # screen x/y of the head at rest (for look tracking)
        self.last, self.cut = None, -9

    def draw(self, fr, t, pose, dx=0, dy=0, rot=0, sq=(1, 1), alpha=1.0, live=1.0):
        if pose != self.last:
            if self.last is not None and not ({pose, self.last} <= {'master', 'blink', 'look_l', 'look_r'}):
                self.cut = t                       # body pop only on expression changes, not eye flicks
            self.last = pose
        kc = t - self.cut
        px, py = squash(kc, 0.05, 22, 7) if kc < 0.6 else (1, 1)
        br = 0.008 * math.sin(t * 2.3 + self.phase) * live
        r = rot + 0.8 * math.sin(t * 1.7 + self.phase) * live
        bob = 3.0 * math.sin(t * 2.6 + self.phase) * live
        sx = px * sq[0] * (1 - br * 0.5) * (-1 if self.flip else 1)
        sy = py * sq[1] * (1 + br)
        img = self.P[pose]
        anc = self.anchor
        blit(fr, img, anc, (self.at[0] + dx, self.at[1] + dy + bob), sx, sy, r, alpha)


def look(head_x, target_x, flip=False, dead=110):
    d = target_x - head_x
    if abs(d) < dead: return 'master'
    p = 'look_r' if d > 0 else 'look_l'
    if flip: p = 'look_l' if p == 'look_r' else 'look_r'      # mirrored sprite: its 'left' is screen right
    return p


def blinking(t, start, every, dur=0.13):
    if t < start: return False
    return ((t - start) % every) < dur


# ---------------------------------------------------------------- cast + layout
POSES = ['master', 'blink', 'look_l', 'look_r', 'happy', 'mouth_open']
FROG = Actor('frog', POSES, 0.6, anchor=(615, 420), at=(345, 215), flip=True, phase=0.3)
DOG = Actor('dog', POSES, 0.66, anchor=(1110, 300), at=(440, 720), phase=1.1, extend_bottom=500)
CROW = Actor('crow', POSES, 0.8, anchor=(470, 300), at=(1590, 430), phase=2.0, extend_bottom=420, follow=True)
CAT = Actor('cat', POSES, 0.62, anchor=(330, 300), at=(905, 905), phase=0.7)
HAM = Actor('hamster', POSES, 0.37, anchor=(691, 706), at=(0, 0), phase=1.6)
# heads (screen) for gaze: frog face, dog eye, crow eye, cat face, hamster face (set after title layout)
HEADX = dict(frog=345, dog=300, crow=1650, cat=905)
TAIL = load_rgba(f'{CL}/cat_tail.png', 0.42)
TAIL_BASE = (700 * 0.42, 684 * 0.42)              # tail root in scaled source px
NOTES = [load_rgba(f'{CL}/note{i}.png') for i in range(3)]

# ---------------------------------------------------------------- title, subline, button (font-rendered type)
def _font(size, weight):
    f = ImageFont.truetype(FONT, size); f.set_variation_by_name(weight); return f

TITLE = 'Paw Playlists'
TF = _font(178, 'Bold')
TITLE_Y = 470                                       # vertical centre of the title line
_tw = TF.getlength(TITLE)
LETTERS = []                                        # (rgba, anchor, screen_x, ink_top, char)
for i, ch in enumerate(TITLE):
    if ch == ' ': continue
    x_left = 960 - _tw / 2 + TF.getlength(TITLE[:i])
    pad = 24; asc, desc = TF.getmetrics()
    im = Image.new('RGBA', (int(TF.getlength(ch)) + 2 * pad, asc + desc + 2 * pad), (0, 0, 0, 0))
    ImageDraw.Draw(im).text((pad, pad), ch, font=TF, fill=(255, 255, 255, 255), stroke_width=6, stroke_fill=INK + (255,))
    a = np.array(im); ys = np.where(a[..., 3].max(1) > 40)[0]
    base_y = pad + asc                              # baseline in glyph px
    rgba = a.astype(np.float32); rgba[..., :3] *= rgba[..., 3:4] / 255; rgba = rgba[..., [2, 1, 0, 3]].copy()
    sx = x_left - pad + im.width / 2                 # screen x of glyph-canvas centre
    base_screen = TITLE_Y + asc * 0.36              # baseline on screen
    LETTERS.append(dict(img=rgba, anchor=(im.width / 2, base_y), x=sx, base=base_screen,
                        top=base_screen - (base_y - ys.min()), ch=ch, i=i))

def _img(im):
    a = np.array(im).astype(np.float32); a[..., :3] *= a[..., 3:4] / 255; return a[..., [2, 1, 0, 3]].copy()

SUB = 'A playlist for your pet, picked from the music you love.'
SF = _font(40, 'Medium')
_s = Image.new('RGBA', (int(SF.getlength(SUB)) + 20, 70), (0, 0, 0, 0))
ImageDraw.Draw(_s).text((10, 8), SUB, font=SF, fill=INK + (255,))
SUBIMG = _img(_s); SUB_AT = (960, 600)

BF = _font(27, 'SemiBold'); BTXT = 'GET STARTED'
_bw, _bh = 300, 76
_b = Image.new('RGBA', (_bw + 16, _bh + 16), (0, 0, 0, 0)); _d = ImageDraw.Draw(_b)
_d.rounded_rectangle((8, 8, 8 + _bw, 8 + _bh), radius=_bh // 2, fill=INK + (255,))
# letter-spaced label
_sp = 3; _lw = sum(BF.getlength(c) for c in BTXT) + _sp * (len(BTXT) - 1); _x = 8 + (_bw - _lw) / 2
for c in BTXT:
    _d.text((_x, 8 + _bh / 2), c, font=BF, fill=MINT + (255,), anchor='lm'); _x += BF.getlength(c) + _sp
BTN = _img(_b); BTN_AT = (960, 700)

# hamster sits on the letter nearest x=1010
SEAT = min(LETTERS, key=lambda L: abs(L['x'] - 1010) + (0 if L['ch'] in 'lPyt' else 400))
HAM.at = (SEAT['x'], SEAT['top'] + 6)
HEADX['hamster'] = SEAT['x']

# ---------------------------------------------------------------- timeline (seconds)
T_FROG, T_DOG, T_CROW, T_CAT = 0.45, 1.25, 2.05, 2.85
T_TITLE, T_LET = 3.8, 0.075
T_SUB, T_BTN = 5.0, 5.55
T_HAM_DROP, T_HAM_LAND = 6.35, 6.8
HAM_BOUNCES = [(6.8, 0.0), (7.12, 70.0), (7.42, 24.0), (7.62, 0)]   # (land time, apex height of hop before it)
# bouncing music note: frog's mouth -> dog's nose -> hamster's head -> crow's beak -> off right.
# Each hop is a quadratic Bezier (key, control): the controls route the note AROUND the title / subline / button
# (the dog -> hamster hop loops up the left side and over the title). note_clear() checks it.
NOTE_KEYS = [(8.0, (375, 290)), (8.8, (372, 672)), (9.7, (None, None)), (10.6, (1628, 398)), (11.5, (2050, 120))]
NOTE_CTRL = [(130, 470), (60, 20), (1380, -120), (1850, 150)]     # control point of each hop
T_SING = 12.3
T_PRESS = 13.5
ENTER = 0.6

def hop_y(t):
    """hamster y offset (negative = up) during drop and hops"""
    if t < T_HAM_DROP: return -900
    if t < T_HAM_LAND: return -900 * (1 - ease_in((t - T_HAM_DROP) / (T_HAM_LAND - T_HAM_DROP)))
    for (t0, _), (t1, h) in zip(HAM_BOUNCES, HAM_BOUNCES[1:]):
        if t0 <= t < t1:
            u = (t - t0) / (t1 - t0); return -h * 4 * u * (1 - u)
    return 0.0

def ham_land_t(t):
    lands = [T_HAM_LAND] + [b[0] for b in HAM_BOUNCES[1:-1]] + [HAM_BOUNCES[-1][0]]
    past = [x for x in lands if x <= t]
    return t - past[-1] if past else 9

def note_pos(t):
    keys = [(k[0], (HAM.at[0], HAM.at[1] - 300) if k[1][0] is None else k[1]) for k in NOTE_KEYS]
    if t < keys[0][0] or t > keys[-1][0]: return None
    for (t0, p0), (t1, p1), c in zip(keys, keys[1:], NOTE_CTRL):
        if t0 <= t <= t1:
            u = ease((t - t0) / (t1 - t0)) * 0.35 + 0.65 * (t - t0) / (t1 - t0)
            x = (1 - u) ** 2 * p0[0] + 2 * u * (1 - u) * c[0] + u * u * p1[0]
            y = (1 - u) ** 2 * p0[1] + 2 * u * (1 - u) * c[1] + u * u * p1[1]
            return x, y, u, t0, t1
    return None


# text the notes must never cross (ink boxes + margin): title, subline, button
TEXT_BOXES = [(415, 385, 1505, 585), (462, 565, 1458, 635), (797, 652, 1123, 750)]

def text_fade(x, y, hw, hh, pad=26):
    """1 when a note's box (centre x, y, half sizes) is >= pad px clear of all text, fading to 0 at contact"""
    d = 1e9
    for x0, y0, x1, y1 in TEXT_BOXES:
        dx = max(x0 - (x + hw), (x - hw) - x1, 0); dy = max(y0 - (y + hh), (y - hh) - y1, 0)
        d = min(d, math.hypot(dx, dy) if (dx or dy) else 0)
    return clamp(d / pad, 0, 1)


def bonked(t, who_t, win=0.55):
    return 0 <= t - who_t < win

# ---------------------------------------------------------------- SFX cue list (same constants as the visuals)
def cues():
    c = []
    for t0, k in ((T_FROG, 'boing'), (T_DOG, 'whoosh'), (T_CROW, 'whoosh'), (T_CAT, 'boing')):
        c += [(t0, 'whoosh'), (t0 + ENTER * 0.72, 'pop'), (t0 + ENTER * 0.72, k)]
    for L in LETTERS: c.append((T_TITLE + L['i'] * T_LET, 'pop'))
    c += [(T_SUB, 'swish'), (T_BTN, 'pop'), (T_HAM_DROP, 'fall')]
    c += [(T_HAM_LAND, 'boing'), (T_HAM_LAND, 'squish')] + [(b[0], 'boing_small') for b in HAM_BOUNCES[1:3]]
    for t0, _ in NOTE_KEYS[1:4]: c.append((t0, 'bonk'))
    c += [(NOTE_KEYS[0][0], 'pop')]
    c += [(T_SING, 'chord'), (T_PRESS, 'click'), (T_PRESS + 0.08, 'pop'), (T_PRESS + 0.25, 'sparkle')]
    for name, (st, ev) in BLINKS.items():
        t = st
        while t < DUR - 0.2: c.append((t, 'tick')); t += ev
    for k in range(N_FLOAT): c.append((FLOAT_T0 + k * FLOAT_EVERY, 'plip'))
    return sorted(c)

BLINKS = dict(frog=(1.7, 3.1), dog=(2.3, 2.7), crow=(3.1, 3.4), cat=(4.2, 2.9), hamster=(7.9, 2.5))
FLOAT_T0, FLOAT_EVERY, N_FLOAT = 1.6, 0.9, 18
FLOAT_SRC = [(375, 300), (330, 640), (1660, 560), (860, 850), None]
FLOAT_DRIFT = [(-30, 110), (-45, 110), (45, 110), (-62, 80), (0, 110)]   # px/s sideways (away from the text), px/s up

# ---------------------------------------------------------------- line boil: 3 smooth displacement fields
_rs = np.random.RandomState(11)
_gx, _gy = np.meshgrid(np.arange(W, dtype=np.float32), np.arange(H, dtype=np.float32))
BOIL = []
for _ in range(3):
    f = []
    for _ax in range(2):
        n = cv2.resize(_rs.randn(H // 24 + 2, W // 24 + 2).astype(np.float32), (W, H), interpolation=cv2.INTER_CUBIC)
        f.append(n / (np.abs(n).max() + 1e-6) * 1.6)
    BOIL.append((_gx + f[0], _gy + f[1]))

FINISH = make_finish(W, H, vignette=0.0, grain=2.2, n=6, seed=5)
BGF = np.empty((H, W, 3), np.float32); BGF[:] = BG[::-1]


def gaze_target(t, who):
    """x the character is looking at"""
    np_ = note_pos(t)
    if np_: return np_[0]
    if T_PRESS - 0.2 <= t < T_PRESS + 1.6: return BTN_AT[0]
    if T_HAM_DROP <= t < 8.0: return HAM.at[0]
    if T_TITLE <= t < T_HAM_DROP:
        i = int(clamp((t - T_TITLE) / T_LET, 0, len(TITLE) - 1)); return 960 - _tw / 2 + TF.getlength(TITLE[:i])
    if t >= 14.8:   # end hold: glance at each other now and then
        return {'frog': 1600, 'dog': 1600, 'crow': 330, 'cat': 1010, 'hamster': 330}[who] if int(t / 1.4) % 3 == 1 else HEADX[who]
    return HEADX[who]


def pose_for(t, who, bonk_t=None, flip=False):
    if bonk_t is not None and bonked(t, bonk_t): return 'happy'
    if T_PRESS <= t < T_PRESS + 0.9: return 'happy'
    if T_SING <= t < T_SING + 0.95: return 'mouth_open'
    # sing on alternating beats while the note travels (only the one it just left)
    st, ev = BLINKS[who]
    if blinking(t, st, ev): return 'blink'
    return look(HEADX[who], gaze_target(t, who), flip)


def enter(t, t0, dur=ENTER):
    u = (t - t0) / dur
    return clamp(u, 0, 1), back(u, 1.6) if u > 0 else 0.0


def frame(t, step):
    fr = BGF.copy()
    # ---- frog (top-left, slides down-right out of the corner)
    if t >= T_FROG:
        u, e = enter(t, T_FROG)
        land = t - (T_FROG + ENTER * 0.72)
        sq = squash(land, 0.07, 18, 6) if land > 0 else (1, 1)
        pose = 'mouth_open' if 7.75 <= t < 8.15 else pose_for(t, 'frog', None, flip=True)
        FROG.draw(fr, t, pose, dx=-430 * (1 - e), dy=-430 * (1 - e), rot=-14 * (1 - e), sq=sq)
    # ---- cat tail (behind cat) + cat (rises from bottom)
    if t >= T_CAT:
        u, e = enter(t, T_CAT, 0.7)
        dy = 620 * (1 - e)
        land = t - (T_CAT + 0.5)
        sq = squash(land, 0.06, 16, 6) if land > 0 else (1, 1)
        sway = 9 * math.sin(t * 2.4) + 4 * math.sin(t * 4.1 + 1)
        tail_root = (1395, 1000 + dy)
        _tail(fr, tail_root, sway)
        CAT.draw(fr, t, pose_for(t, 'cat'), dy=dy, sq=sq)
    # ---- dog (left edge)
    if t >= T_DOG:
        u, e = enter(t, T_DOG)
        land = t - (T_DOG + ENTER * 0.72)
        sq = squash(land, 0.06, 18, 6) if land > 0 else (1, 1)
        DOG.draw(fr, t, pose_for(t, 'dog', NOTE_KEYS[1][0]), dx=-760 * (1 - e), rot=6 * (1 - e), sq=sq)
    # ---- crow (right edge)
    if t >= T_CROW:
        u, e = enter(t, T_CROW)
        land = t - (T_CROW + ENTER * 0.72)
        sq = squash(land, 0.06, 18, 6) if land > 0 else (1, 1)
        CROW.draw(fr, t, pose_for(t, 'crow', NOTE_KEYS[3][0]), dx=760 * (1 - e), rot=-6 * (1 - e), sq=sq)
    # ---- title letters (staggered pop); the seat letter dips when the hamster lands
    for L in LETTERS:
        t0 = T_TITLE + L['i'] * T_LET
        if t < t0: continue
        s = back((t - t0) / 0.32, 2.2)
        sx = sy = max(s, 0.001)
        if L is SEAT and t >= T_HAM_LAND:
            k = ham_land_t(t); sx_, sy_ = squash(k, 0.10, 20, 6); sx *= sx_; sy *= sy_
        wob = 2.5 * math.sin(t * 3 + L['i'] * 0.9) if t > t0 + 0.4 else 0
        blit(fr, L['img'], L['anchor'], (L['x'], L['base'] + wob * 0.6), sx, sy, wob * 0.4)
    # ---- subline + button
    if t >= T_SUB:
        u = ease_out((t - T_SUB) / 0.45)
        blit(fr, SUBIMG, (SUBIMG.shape[1] / 2, SUBIMG.shape[0] / 2), (SUB_AT[0], SUB_AT[1] + 30 * (1 - u)), alpha=u)
    if t >= T_BTN:
        s = back((t - T_BTN) / 0.35, 2.0)
        if t >= T_PRESS:
            k = t - T_PRESS
            press = 1 - 0.14 * math.exp(-k * 9) * (1 if k < 0.09 else math.cos((k - 0.09) * 22))
            sxb, syb = press * (1 + 0.04 * math.exp(-k * 8)), press
        else:
            sxb = syb = 1.0
        blit(fr, BTN, (BTN.shape[1] / 2, BTN.shape[0] / 2), BTN_AT, s * sxb, s * syb)
    # ---- hamster drop + bounces (feet on the seat letter)
    if t >= T_HAM_DROP:
        y = hop_y(t)
        k = ham_land_t(t)
        sq = squash(k, 0.16, 20, 6) if (t >= T_HAM_LAND and k < 0.7 and y > -1) else ((0.9, 1.12) if y < -1 else (1, 1))
        pose = 'happy' if (T_HAM_LAND <= t < T_HAM_LAND + 0.5) else pose_for(t, 'hamster', NOTE_KEYS[2][0])
        HAM.draw(fr, t, pose, dy=y, sq=sq, live=0.5)
    # ---- bouncing music note + floating notes
    np_ = note_pos(t)
    if np_:
        x, y, u, t0, t1 = np_
        k = t - t0
        sxn, syn = squash(k, 0.18, 20, 6) if k < 0.5 else (1, 1)
        blit(fr, NOTES[1], (NOTES[1].shape[1] / 2, NOTES[1].shape[0] / 2), (x, y), 0.42 * sxn, 0.42 * syn, 12 * math.sin(t * 6))
    for kf in range(N_FLOAT):
        p = float_note(t, kf)
        if p: n = NOTES[kf % 3]; blit(fr, n, (n.shape[1] / 2, n.shape[0] / 2), p[:2], p[2], p[2], p[3], p[4])
    # burst of notes from the button press: fans out sideways from the button ends, clear of the label/subline
    for p in burst_notes(t):
        n = NOTES[p[3] % 3]; blit(fr, n, (n.shape[1] / 2, n.shape[0] / 2), p[:2], 0.13, 0.13, 0, p[2])
    # ---- line boil (10 fps, 3 fields) + paper grain
    mx, my = BOIL[int(t * 10) % 3]
    fr = cv2.remap(fr, mx, my, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
    return FINISH(fr, int(t * 10), flicker=0.0)


def float_note(t, kf):
    """(x, y, scale, rot, alpha) of floating note kf, or None. Fades out before touching any text."""
    t0 = FLOAT_T0 + kf * FLOAT_EVERY; age = t - t0
    if not (0 <= age < 2.4): return None
    j = kf % len(FLOAT_SRC); src = FLOAT_SRC[j]
    if src is None:
        if t0 < T_HAM_LAND: return None
        src = (HAM.at[0], HAM.at[1] - 200)
    a = min(1, age / 0.25) * (1 - clamp((age - 1.6) / 0.8))
    sc = 0.16 * back(min(1, age / 0.35))
    vx, vy = FLOAT_DRIFT[j]
    nx = src[0] + 26 * math.sin(age * 3 + kf) + vx * age
    ny = src[1] - vy * age
    a *= text_fade(nx, ny, 30, 30)
    return nx, ny, sc, 10 * math.sin(age * 4 + kf), a


def burst_notes(t):
    out = []
    if not (T_PRESS <= t < T_PRESS + 1.4): return out
    age = t - T_PRESS
    for j, deg in enumerate((180, 160, 140, 0, 20, 40)):
        ang = math.radians(deg); r = 120 + 200 * ease_out(age / 1.0)
        x, y = BTN_AT[0] + r * math.cos(ang) * 1.5, BTN_AT[1] + 20 + r * math.sin(ang)
        al = (1 - clamp((age - 0.8) / 0.6)) * min(1, age / 0.08) * text_fade(x, y, 24, 24, 14)
        out.append((x, y, al, j))
    return out


def note_clear(dt=1 / 48):
    """QA: worst overlap of any visible note with the text boxes over the whole timeline (0 = clean)"""
    bad = []
    hw, hh = NOTES[1].shape[1] / 2 * 0.42, NOTES[1].shape[0] / 2 * 0.42
    for i in range(int(DUR / dt)):
        t = i * dt; p = note_pos(t)
        if p and text_fade(p[0], p[1], hw * 0.8, hh * 0.85, 1) < 1: bad.append(('hero', round(t, 2), int(p[0]), int(p[1])))
        for kf in range(N_FLOAT):
            q = float_note(t, kf)
            if q and q[4] > 0.02 and text_fade(q[0], q[1], 28, 28, 1) < 1: bad.append(('float', kf, round(t, 2)))
        for q in burst_notes(t):
            if q[2] > 0.02 and text_fade(q[0], q[1], 22, 22, 1) < 1: bad.append(('burst', round(t, 2)))
    return bad


def _tail(fr, root, sway_deg):
    """bend the tail along its length (rotation grows toward the tip) instead of one rigid rotate"""
    h, w = TAIL.shape[:2]
    bx, by = TAIL_BASE
    ys = np.arange(h, dtype=np.float32)
    frac = np.clip((by - ys) / by, 0, 1)                 # 0 at root, 1 at tip
    ang = np.radians(sway_deg) * frac ** 1.6
    # horizontal offset accumulated along the tail (small-angle bend)
    off = np.cumsum((np.sin(ang))[::-1])[::-1] * 0.9
    off -= off[int(by)] if int(by) < h else 0
    mapx = (np.arange(w, dtype=np.float32)[None, :] - off[:, None]).astype(np.float32)
    mapy = np.repeat(ys[:, None], w, 1)
    bent = cv2.remap(TAIL, mapx, mapy, cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=0)
    blit(fr, bent, (bx, by), root, 1, 1, 0)


if __name__ == '__main__':
    pv = os.environ.get('PREVIEW')
    if pv:
        os.makedirs(os.path.join(HERE, 'pv'), exist_ok=True)
        for s in pv.split(','):
            t = float(s); fr = frame(t, int(t * FPS))
            cv2.imwrite(os.path.join(HERE, 'pv', f'pv_{t:05.2f}.jpg'), fr, [cv2.IMWRITE_JPEG_QUALITY, 92])
            print('pv', t)
    else:
        print('render with: python3 ../../engine/chunkrender.py scene.py --chunks 6 --audio mix.wav --loudnorm --out final.mp4')
