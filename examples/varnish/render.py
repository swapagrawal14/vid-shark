import os, sys, math, random, subprocess, json
import numpy as np, cv2
from PIL import Image, ImageDraw, ImageFilter
HERE = os.path.dirname(os.path.abspath(__file__))
os.environ.setdefault('MOTION_ROOT', os.path.abspath(os.path.join(HERE, '..', '..')))
exec(open(os.path.join(os.environ['MOTION_ROOT'], 'engine', 'claylib.py')).read())
V = HERE + '/assets/'
W, H, FPS = 1920, 1080, 12

def ld(p): return Image.open(V + p).convert('RGBA')
BG = cv2.resize(cv2.imread(V + 'bg_set.png'), None, fx=1.5, fy=1.5, interpolation=cv2.INTER_LANCZOS4)
ARCH = ld('c_arch_c.png'); TEETH = Image.open(V + 'teeth_mask.png').convert('L')
BRUSH = ld('c_brush_c.png').transpose(Image.FLIP_LEFT_RIGHT)
GAUZE = ld('c_gauze_c.png'); CLOCK = ld('c_clock_c.png')

AS = 0.75  # arch scale
ARCH_S = ARCH.resize((int(ARCH.width * AS), int(ARCH.height * AS)), Image.LANCZOS)
TEETH_S = TEETH.resize(ARCH_S.size, Image.LANCZOS)
ACX, ACY = 1090, 690  # arch centre on screen
AX0, AY0 = ACX - ARCH_S.width // 2, ACY - ARCH_S.height // 2
# varnish-coated version of arch
def make_varnished():
    a = np.array(ARCH_S).astype(np.float32)
    m = np.array(TEETH_S).astype(np.float32)[..., None] / 255
    tint = np.array([255, 205, 95], np.float32)
    lum = a[..., :3].mean(2, keepdims=True)
    coated = a[..., :3] * 0.55 + tint * 0.45
    spec = np.clip((lum - 200) / 55, 0, 1) * 70
    coated = coated + spec
    out = a.copy(); out[..., :3] = a[..., :3] * (1 - m) + coated * m
    return out.clip(0, 255)
VARN = make_varnished()
ARCH_NP = np.array(ARCH_S).astype(np.float32)
_n = cv2.GaussianBlur(np.random.randn(*ARCH_NP.shape[:2]).astype(np.float32), (0, 0), 1.4) * 7 + cv2.GaussianBlur(np.random.randn(*ARCH_NP.shape[:2]).astype(np.float32), (0, 0), 6) * 10
for _c in range(3): ARCH_NP[..., _c] = np.clip(ARCH_NP[..., _c] + _n, 0, 255)
VARN[..., :3] = np.clip(VARN[..., :3] + _n[..., None] * 0.6, 0, 255)
TEETH_NP = np.array(TEETH_S).astype(np.float32) / 255

# brush path along labial surfaces (arch-local coords, original 1157x650 space)
PATH0 = [(1000,260),(880,310),(770,350),(660,380),(545,400),(425,410),(310,395),(210,370),(130,340),(80,300),(90,240),(130,190),(220,150),(330,110),(440,60)]
PATH = [(AX0 + x * AS, AY0 + y * AS) for x, y in PATH0]
seg = [math.dist(PATH[i], PATH[i+1]) for i in range(len(PATH)-1)]; TOT = sum(seg)
def path_at(u):
    d = max(0, min(1, u)) * TOT
    for i, L in enumerate(seg):
        if d <= L: f = d / L; return (PATH[i][0] + (PATH[i+1][0]-PATH[i][0]) * f, PATH[i][1] + (PATH[i+1][1]-PATH[i][1]) * f)
        d -= L
    return PATH[-1]

vo = float(subprocess.check_output(['ffprobe','-v','error','-show_entries','format=duration','-of','csv=p=0',V+'vo.wav']))
txt = "First, fluoride varnish. Five percent sodium fluoride, that's twenty-two thousand six hundred ppm. Dry the teeth with gauze, then paint a thin layer with a small brush. It sets on contact with saliva. Advise soft food, and no brushing for four to six hours. Repeat every three to six months in high-risk patients."
PRE = 0.35
def T(word): return PRE + vo * txt.find(word) / len(txt)
DUR = PRE + vo + 0.9
tFive, tDry, tPaint, tSets, tSoft, tRep = T('Five percent'), T('Dry the teeth'), T('then paint'), T('It sets'), T('Advise'), T('Repeat')
print('times', tFive, tDry, tPaint, tSets, tSoft, tRep, DUR)

def ease(x): x = max(0, min(1, x)); return x * x * (3 - 2 * x)
def back(x):
    x = max(0, min(1, x)); c = 1.9
    return 1 + (c + 1) * (x - 1) ** 3 + c * (x - 1) ** 2

items = [
    (make_item('Fluoride Varnish', 'head', '01'), 0.25, (70, 60)),
    (make_item('5% NaF  ·  22,600 ppm', 'chip'), tFive, (80, 190)),
    (make_item('Dry the teeth with gauze', 'chip'), tDry, (80, 285)),
    (make_item('Paint a thin layer', 'chip'), tPaint, (80, 380)),
    (make_item('Sets on contact with saliva', 'chip'), tSets, (80, 475)),
    (make_item('Soft food, no brushing 4–6 h', 'chip'), tSoft, (80, 570)),
    (make_item('Every 3–6 months (high risk)', 'chip'), tRep, (80, 665)),
]
SFX = []  # (time, kind)
for it in items: SFX.append((it[1], 'pop'))

def shadow_of(im, op=0.35, blur=9):
    a = np.array(im)[..., 3]
    s = Image.new('RGBA', im.size, (40, 22, 12, 0)); s.putalpha(Image.fromarray((a * op).astype(np.uint8)).filter(ImageFilter.GaussianBlur(blur)))
    return s

def paste(fr, im, cx, cy):
    a = np.array(im).astype(np.float32); h, w = a.shape[:2]
    x, y = int(round(cx - w / 2)), int(round(cy - h / 2))
    X0, Y0 = max(x, 0), max(y, 0); X1, Y1 = min(x + w, W), min(y + h, H)
    if X1 <= X0 or Y1 <= Y0: return
    sub = a[Y0-y:Y1-y, X0-x:X1-x]; al = sub[..., 3:4] / 255
    fr[Y0:Y1, X0:X1] = fr[Y0:Y1, X0:X1] * (1 - al) + sub[..., 2::-1] * al

def xform(im, sx=1, sy=1, rot=0):
    w, h = im.size
    im2 = im.resize((max(1, int(w * sx)), max(1, int(h * sy))), Image.BICUBIC)
    return im2.rotate(rot, resample=Image.BICUBIC, expand=True) if abs(rot) > 0.01 else im2

def place_pivot(fr, im, px, py, pivot, rot, shadow=None):
    # place image so that pivot (in image coords) lands on (px,py), rotated by rot degrees around pivot
    w, h = im.size
    cx0, cy0 = w / 2, h / 2
    vx, vy = cx0 - pivot[0], cy0 - pivot[1]
    a = math.radians(-rot)
    rx, ry = vx * math.cos(a) - vy * math.sin(a), vx * math.sin(a) + vy * math.cos(a)
    im2 = xform(im, rot=rot)
    if shadow: paste(fr, shadow_of(im2, *shadow[:2]), px + rx + shadow[2], py + ry + shadow[3])
    paste(fr, im2, px + rx, py + ry)

BRS = 0.62
BRUSH_S = BRUSH.resize((int(BRUSH.width * BRS), int(BRUSH.height * BRS)), Image.LANCZOS)
TIP = (60 * BRS, 342 * BRS)
GZ = GAUZE.resize((int(GAUZE.width * 0.27), int(GAUZE.height * 0.27)), Image.LANCZOS)
CK = CLOCK.resize((int(CLOCK.width * 0.36), int(CLOCK.height * 0.36)), Image.LANCZOS)

reveal = np.zeros(ARCH_S.size[::-1], np.float32)
drops = []
rng = random.Random(5)
vign = np.clip(1 - 0.28 * (((np.mgrid[0:H, 0:W][1] - W/2) / (W/2)) ** 2 + ((np.mgrid[0:H, 0:W][0] - H/2) / (H/2)) ** 2) ** 1.2, 0.6, 1)[..., None]
grains = [cv2.GaussianBlur(np.random.randn(H, W).astype(np.float32), (0, 0), 0.8)[..., None] * 3.5 for _ in range(6)]

def background(step, t):
    z = 1.0 + 0.06 * ease(t / DUR)
    bh, bw = BG.shape[:2]; sc = max(W / bw, H / bh) * z
    vw, vh = W / sc, H / sc
    x0 = (bw - vw) * 0.5 + 6 * math.sin(t * 0.4); y0 = (bh - vh) * 0.5
    j = random.Random(step)
    M = np.array([[sc, 0, -x0 * sc + j.uniform(-1.5, 1.5)], [0, sc, -y0 * sc + j.uniform(-1.5, 1.5)]], np.float32)
    return cv2.warpAffine(BG, M, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT).astype(np.float32)

PREV = [int(x) for x in os.environ.get('PREVIEW', '').split(',') if x]
N = int(DUR * FPS)
proc = None if PREV else subprocess.Popen(['ffmpeg','-y','-loglevel','error','-f','rawvideo','-pix_fmt','bgr24','-s',f'{W}x{H}','-r',str(FPS),'-i','-','-vf','fps=24','-c:v','libx264','-preset','medium','-crf','20','-pix_fmt','yuv420p',HERE + '/out_video.mp4'], stdin=subprocess.PIPE)
yy, xx = np.mgrid[0:ARCH_S.height, 0:ARCH_S.width]
landed = False
for step in range(N):
    t = step / FPS
    j = random.Random(step * 7)
    fr = background(step, t)
    # ---- arch drop-in with squash ----
    u = t / 0.75
    if u < 1:
        ay = ACY - 700 * (1 - ease(u) ) ** 1 * (1 - u)
        sx, sy = 1, 1
    else:
        k = t - 0.75
        sq = math.exp(-k * 5) * math.sin(k * 16)
        ay = ACY; sx, sy = 1 + 0.06 * sq, 1 - 0.06 * sq
        if not landed: SFX.append((0.75, 'squish')); landed = True
    # final happy bounce
    if t > DUR - 1.4:
        k = t - (DUR - 1.4); b = math.sin(min(k, 0.6) / 0.6 * math.pi) * 18
        ay -= b
    # brush painting -> reveal
    if tPaint <= t <= tSets:
        u = (t - tPaint) / (tSets - tPaint - 0.2)
        bx, by = path_at(u)
        cv2.circle(reveal, (int(bx - AX0), int(by - AY0)), int(46 * AS / 0.75), 1.0, -1)
    coat = np.clip(cv2.GaussianBlur(reveal, (0, 0), 6), 0, 1)[..., None] * TEETH_NP[..., None]
    arch_now = ARCH_NP * (1 - coat) + VARN * coat
    arch_now[..., 3] = ARCH_NP[..., 3]
    aim = Image.fromarray(arch_now.astype(np.uint8))
    aim = xform(aim, sx, sy, j.uniform(-0.25, 0.25))
    # contact shadow
    sh = Image.new('RGBA', (int(ARCH_S.width * 1.05) + 120, 210), (50, 25, 10, 0))
    m_ = Image.new('L', sh.size, 0); ImageDraw.Draw(m_).ellipse([60, 60, sh.width - 60, sh.height - 60], fill=120); sh.putalpha(m_.filter(ImageFilter.GaussianBlur(20)))
    hgt = max(0, ACY - ay)
    if hgt < 400: paste(fr, sh, ACX + 10, ACY + ARCH_S.height * 0.42)
    paste(fr, aim, ACX + j.uniform(-1, 1), ay + ARCH_S.height * (1 - sy) / 2)
    # ---- gauze ----
    if tDry - 0.6 <= t <= tPaint + 0.3:
        if t < tDry:
            k = ease((t - (tDry - 0.6)) / 0.6); gx, gy = -200 + (PATH[3][0] + 200) * k, PATH[3][1] - 160 * (1 - k)
            if step == int((tDry - 0.6) * FPS): SFX.append((t, 'whoosh'))
        elif t < tPaint - 0.3:
            u = (t - tDry) / (tPaint - 0.3 - tDry)
            pu = 0.2 + 0.6 * (0.5 - 0.5 * math.cos(u * math.pi * 3))
            gx, gy = path_at(pu); gx += math.sin(t * 22) * 10
            if j.random() < 0.5:
                drops.append(dict(x=gx + j.uniform(-30, 30), y=gy - 20, vx=j.uniform(-6, 6), vy=j.uniform(-14, -6), life=0, kind='fly'))
        else:
            k = ease((t - (tPaint - 0.3)) / 0.6); gx, gy = path_at(0.5); gx -= 900 * k; gy -= 200 * k
            if step == int((tPaint - 0.3) * FPS): SFX.append((t, 'whoosh'))
        gim = xform(GZ, 1 + 0.04 * math.sin(t * 20), 1 - 0.04 * math.sin(t * 20), 8 * math.sin(t * 6))
        paste(fr, shadow_of(gim, 0.3, 10), gx + 18, gy + 30)
        paste(fr, gim, gx, gy - 25)
    # ---- brush ----
    if tFive - 0.2 <= t <= tSoft + 0.6:
        hover = (PATH[0][0] + 80, PATH[0][1] - 230)
        if t < tFive + 0.5:
            k = back((t - (tFive - 0.2)) / 0.7); bx, by = 2300 + (hover[0] - 2300) * k, -300 + (hover[1] + 300) * k; rot = -10 * (1 - k)
            if step == int((tFive - 0.2) * FPS): SFX.append((t, 'whoosh'))
        elif t < tPaint:
            bx, by = hover[0] + 6 * math.sin(t * 5), hover[1] + 10 * math.sin(t * 3); rot = 4 * math.sin(t * 2)
            if t > tPaint - 0.4:
                k = ease((t - (tPaint - 0.4)) / 0.4); bx = hover[0] + (PATH[0][0] - hover[0]) * k; by = hover[1] + (PATH[0][1] - hover[1]) * k
        elif t < tSets:
            u = (t - tPaint) / (tSets - tPaint - 0.2)
            bx, by = path_at(u); dab = abs(math.sin(t * 9)) * 10; by -= dab; rot = 6 * math.sin(t * 9)
            if step % 3 == 0: SFX.append((t, 'dab'))
        elif t < tSoft:
            bx, by = path_at(1); bx += 40; by -= 140 * ease((t - tSets) / 0.5); rot = 0
        else:
            k = ease((t - tSoft) / 0.6); bx, by = path_at(1); bx += 40 + 900 * k; by -= 140 + 500 * k; rot = -20 * k
            if step == int(tSoft * FPS): SFX.append((t, 'whoosh'))
        place_pivot(fr, BRUSH_S, bx + j.uniform(-1, 1), by + j.uniform(-1, 1), TIP, rot + j.uniform(-0.6, 0.6), shadow=(0.28, 8, 26, 46))
    # ---- saliva drops ----
    if tSets <= t <= tSets + 1.6 and step % 2 == 0:
        x = PATH[j.randint(1, len(PATH) - 3)][0] + j.uniform(-20, 20)
        drops.append(dict(x=x, y=ACY - 520, vx=0, vy=18, life=0, kind='saliva'))
        SFX.append((t + 0.4, 'plip'))
    nd = []
    for d_ in drops:
        d_['life'] += 1
        if d_['kind'] == 'fly':
            d_['x'] += d_['vx']; d_['y'] += d_['vy']; d_['vy'] += 3
            if d_['life'] < 8:
                r = 7; img = Image.new('RGBA', (30, 30), (0, 0, 0, 0)); dd = ImageDraw.Draw(img)
                dd.ellipse([15 - r, 15 - r * 1.2, 15 + r, 15 + r * 1.2], fill=(150, 200, 235, 220)); dd.ellipse([11, 10, 15, 14], fill=(255, 255, 255, 230))
                paste(fr, img, d_['x'], d_['y']); nd.append(d_)
        else:
            # find target y: nearest path point by x
            tgt = min(PATH[:-4], key=lambda p: abs(p[0] - d_['x']))[1] - 10
            if d_['y'] < tgt:
                d_['y'] += d_['vy']; d_['vy'] += 4
                r = 11; img = Image.new('RGBA', (40, 50), (0, 0, 0, 0)); dd = ImageDraw.Draw(img)
                dd.ellipse([20 - r, 25 - r * 1.35, 20 + r, 25 + r], fill=(140, 195, 235, 230)); dd.ellipse([14, 16, 20, 22], fill=(255, 255, 255, 235))
                paste(fr, img, d_['x'], d_['y']); nd.append(d_)
            elif d_.get('splat', 0) < 6:
                d_['splat'] = d_.get('splat', 0) + 1; s = d_['splat']
                img = Image.new('RGBA', (90, 60), (0, 0, 0, 0)); dd = ImageDraw.Draw(img)
                a_ = int(220 * (1 - s / 6))
                dd.ellipse([45 - 14 - s * 3, 30 - 6, 45 + 14 + s * 3, 30 + 6], fill=(140, 195, 235, a_))
                # sparkle
                cx, cy = 45, 14 - s * 2; L = 6 + s * 2
                dd.line([cx - L, cy, cx + L, cy], fill=(255, 250, 220, a_), width=3); dd.line([cx, cy - L, cx, cy + L], fill=(255, 250, 220, a_), width=3)
                paste(fr, img, d_['x'], tgt); nd.append(d_)
    drops = nd
    # ---- clock ----
    if t >= tSoft - 0.1:
        k = (t - (tSoft - 0.1)) * FPS
        sc = pop_scale(int(k)) if k < 6 else 1.0
        cim = xform(CK, sc, sc, j.uniform(-0.5, 0.5))
        cx, cy = 1700, 300
        paste(fr, shadow_of(cim, 0.3, 10), cx + 14, cy + 22)
        paste(fr, cim, cx, cy)
        if sc > 0.9:
            speed = 2.2 if t < tRep else 9.0
            ang = (t - tSoft) * speed * 2 * math.pi / 3
            hand = Image.new('RGBA', (CK.width, CK.height), (0, 0, 0, 0)); hd = ImageDraw.Draw(hand)
            c0 = (CK.width / 2, CK.height / 2); Lm, Lh = CK.width * 0.33, CK.width * 0.22
            ah = ang / 12
            for L, a_, wdt in ((Lh, ah, 13), (Lm, ang, 9)):
                hd.line([c0, (c0[0] + L * math.sin(a_), c0[1] - L * math.cos(a_))], fill=(84, 52, 40, 255), width=wdt)
                hd.ellipse([c0[0] + L * math.sin(a_) - wdt / 2, c0[1] - L * math.cos(a_) - wdt / 2, c0[0] + L * math.sin(a_) + wdt / 2, c0[1] - L * math.cos(a_) + wdt / 2], fill=(84, 52, 40, 255))
            hd.ellipse([c0[0] - 14, c0[1] - 14, c0[0] + 14, c0[1] + 14], fill=(226, 112, 86, 255))
            paste(fr, hand, cx, cy)
            if step % 6 == 0: SFX.append((t, 'tick'))
    # ---- text plates ----
    for im, ts, (ax, ay2) in items:
        if t < ts: continue
        k = int((t - ts) * FPS); sc = pop_scale(k)
        wob = math.sin(step * 0.9 + ts) * 0.5
        im2 = xform(im, sc * (1 + 0.01 * math.sin(step * 1.3 + ts)), sc * (1 - 0.01 * math.sin(step * 1.3 + ts)), wob)
        cy = ay2 + im.height / 2 + (max(0, 6 - k) * 3)
        paste(fr, im2, ax + im.width / 2 + j.uniform(-1, 1), cy)
    fr *= 1 + j.uniform(-0.015, 0.015)
    if t < 0.4: fr *= t / 0.4
    out = np.clip(fr * vign + grains[step % 6], 0, 255).astype(np.uint8)
    if PREV:
        if step in PREV: cv2.imwrite(HERE + f'/pv_{step}.jpg', out)
        if step > max(PREV): break
        continue
    proc.stdin.write(out.tobytes())
if proc: proc.stdin.close(); proc.wait()
json.dump(dict(dur=DUR, sfx=SFX, pre=PRE), open(HERE + '/sfx.json', 'w'))
print('done', N)
