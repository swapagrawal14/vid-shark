"""Bablu ki Metro - Scene 1, pose-pack version (rigpop-motion method: drawn key poses, hard cuts,
living-pose warp: breath, sway, train lean, pop on every cut, camera shake on impacts)."""
import os, sys, math, subprocess
import numpy as np, cv2
from PIL import Image
sys.path.insert(0, '/workspace/tools/vid-shark/engine')
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from motion import ease, ease_in, ease_out, squash, xform, paste, shadow_of, camera, make_finish, ffmpeg_writer, clamp
import ep1 as E
W, H, FPS = 1920, 1080, 24
s = E.s; BONKS = E.BONKS; TB = E.T_BRAKE; TP0 = E.T_PAPER0; TP1 = E.T_PAPER1; TSH = E.T_SHAKE
TFG, TFL = E.T_FLY_GO, E.T_FLY_LAND; DUR = E.DUR; EV = E.EV; TFLASH = E.T_FLASH
FLY = E.FLY; BFLY = E.BFLY; PAPER = E.PAPER
FLOOR = 1050

class Cast:
    def __init__(self, name, x, sc, poses, phase):
        self.name, self.x, self.sc, self.phase = name, x, sc, phase
        self.P = {}
        for p in poses:
            im = Image.open(f'{HERE}/poses/{name}_{p}.png').convert('RGBA')
            a = np.array(im)[..., 3] > 40; ys, xs = np.where(a)
            k = sc
            if name == 'woman' and p == 'startled': k = sc * 920 / 898
            im = im.resize((int(im.width * k), int(im.height * k)), Image.LANCZOS)
            # pivot = feet bottom, x of image centre (all keys are registered in one frame)
            self.P[p] = (im, (im.width / 2, ys.max() * k), k)
        self.last = None; self.cut_t = 0

    def world(self, t, ip, pose):
        """image point (in source 960x1102 px) -> world, for the current transform"""
        im, piv, k = self.P[pose]; rot, sx, sy, dx, dy = self.xf
        vx, vy = (ip[0] * k - piv[0]) * sx, (ip[1] * k - piv[1]) * sy
        a = math.radians(-rot)
        return self.x + dx + vx * math.cos(a) - vy * math.sin(a), FLOOR + dy + vx * math.sin(a) + vy * math.cos(a)

    def draw(self, fr, t, pose, extra_rot=0, dy=0, dx=0, sq=(1, 1)):
        if pose != self.last: self.cut_t = t; self.last = pose
        im, piv, k = self.P[pose]
        # living pose: breath, gentle sway, train lean, a pop on each cut
        br = 0.007 * math.sin(t * 2.2 + self.phase)
        rot = 0.7 * math.sin(t * 1.9 + self.phase) + extra_rot + lean(t)
        kc = t - self.cut_t; px, py = squash(kc, 0.06, 22, 7) if kc < 0.6 else (1, 1)
        sx, sy = px * sq[0] * (1 - br * 0.4), py * sq[1] * (1 + br)
        self.xf = (rot, sx, sy, dx - lean(t) * 2.5, dy + 2.5 * math.sin(t * 2.6 + self.phase))
        sh = np.zeros((44, im.width + 40, 4), np.uint8); cv2.ellipse(sh, (sh.shape[1] // 2, 22), (im.width // 3, 12), 0, 0, 360, (70, 40, 60, 70), -1, cv2.LINE_AA)
        paste(fr, Image.fromarray(sh), self.x + dx, FLOOR - 4)
        img = xform(im, sx, sy) if (abs(sx - 1) > 1e-3 or abs(sy - 1) > 1e-3) else im
        piv2 = (piv[0] * img.width / im.width, piv[1] * img.height / im.height)
        E.place_pivot(fr, img, self.x + self.xf[3], FLOOR + self.xf[4], piv2, rot)

def lean(t):
    if t < TB: return 0
    k = t - TB; return -10 * math.exp(-k * 2.0) * math.cos(k * 5.0) if k < 3.5 else 0

BA = Cast('bablu', 975, 0.88, ['idle', 'wave', 'proud', 'lookup', 'worried', 'flinch', 'smug', 'flail', 'grope', 'slump'], 0.6)
WO = Cast('woman', 555, 0.76, ['idle', 'sideeye', 'startled', 'giggle', 'photo'], 0.0)
UN = Cast('uncle', 1410, 0.85, ['read', 'armsup', 'hands', 'shrug', 'idle', 'lookup', 'zen'], 1.2)
DOME_I = (450, 330); UHEAD_I = (480, 182); PAPER_I = (480, 520); PHONE_I = (670, 350)

def seq(t, table, default):
    cur = default
    for t0, p in table:
        if t >= t0: cur = p
    return cur

def bablu_pose(t):
    tab = [(0, 'idle'), (0.85, 'wave'), (2.6, 'idle'), (3.4, 'proud'), (7.3, 'idle'), (8.0, 'lookup'), (12.3, 'worried')]
    for b in BONKS: tab += [(b, 'flinch'), (b + 0.5, 'worried')]
    tab += [(E.T_SMUG, 'smug'), (s[6] - 0.05, 'idle'), (TB, 'flail'), (TB + 1.4, 'worried'), (TP1, 'grope'), (s[9] + 0.4, 'slump')]
    tab.sort(); p = seq(t, tab, 'idle')
    rot = 0; dy = 0
    if p == 'wave': rot = 2 * math.sin(t * 9); dy = -14 * abs(math.sin(t * 6))
    if p == 'proud': rot = -1.5 + 1.2 * math.sin(t * 3)
    if p == 'smug': rot = 2.5 * math.sin((t - E.T_SMUG) * 4) * math.exp(-(t - E.T_SMUG) * 0.6)
    if p == 'flail': rot = 4 * math.sin(t * 19)
    if p == 'grope':
        rot = 1.5 * math.sin(t * 5)
        if TSH <= t < TSH + 1.6: rot += 4 * math.sin((t - TSH) * 15) * (1 - (t - TSH) / 1.6)
    if p == 'flinch': rot = 3 * math.exp(-(t - max(b for b in BONKS if b <= t)) * 6)
    return p, rot, dy

def woman_pose(t):
    tab = [(0, 'idle')]
    for b in BONKS: tab += [(b + 0.05, 'sideeye'), (b + 0.75 if b != BONKS[-1] else s[5] + 1.6, 'idle')]
    tab += [(TB, 'startled'), (TB + 1.3, 'idle'), (TP1 - 0.3, 'sideeye'), (TP1 + 0.6, 'giggle'), (TFLASH - 0.8, 'photo'), (TFLASH + 0.7, 'giggle')]
    tab.sort(); p = seq(t, tab, 'idle')
    dy = 3 * math.sin(t * 28) if p == 'giggle' else 0
    return p, 0, dy

def uncle_pose(t):
    tab = [(0, 'read'), (TB, 'armsup'), (TB + 0.9, 'hands'), (TP1 + 1.7, 'shrug'), (TP1 + 3.1, 'idle'), (TFL - 0.35, 'lookup'), (s[10] + 0.1, 'zen')]
    p = seq(t, tab, 'read'); rot = 0
    if p == 'read': rot = 0.8 * math.sin(t * 1.3)
    if p == 'shrug': rot = 1.5 * math.sin((t - TP1 - 1.7) * 6)
    return p, rot, 0

STATE = {}
# ---------------- props (same choreography as the cut the user saw) ----------------
def paper_xy(t):
    dc = STATE['dome']
    if t < TP1:
        u = (t - TP0) / (TP1 - TP0); st = STATE['p0']
        x = st[0] + (dc[0] - st[0]) * ease(u) + 40 * math.sin(u * 9); y = st[1] + (dc[1] - st[1]) * ease(u) - 330 * math.sin(u * math.pi)
        return (x, y), 200 * u + 25 * math.sin(u * 12), 1 - 0.05 * u
    k = t - TP1
    return (dc[0], dc[1] + 10), 372 + BA.xf[0] + 4 * math.sin(k * 3) * math.exp(-k), 0.95 * squash(k, 0.08, 20, 6)[0]
def draw_paper(fr, t):
    (x, y), r, sc = paper_xy(t)
    if t < TP1:
        u = t - TP0; f = 0.55 + 0.45 * abs(math.cos(u * 5)); im = xform(PAPER, sc * f, sc, r)
        if int(u * 24) % 8 == 0: EV.append((t, 'flap'))
    else: im = xform(PAPER, sc, sc, r)
    paste(fr, shadow_of(im, 0.15, 8), x + 8, y + 12); paste(fr, im, x, y)

def draw_bfly(fr, t):
    if t >= TP1: return
    dc = STATE['dome']; fast = t > 8.0
    a = t * (2.4 if fast else 1.1); rx = 80 if fast else 50
    x = dc[0] + rx * math.cos(a); y = dc[1] - 30 + 40 * math.sin(a * 1.6)
    if BONKS[0] - 0.05 < t < BONKS[2] + 1.0: x += 7 * math.sin(t * 40); y += 5 * math.cos(t * 37)
    flap = abs(math.sin(t * (16 if fast else 7))) * 0.7 + 0.3
    paste(fr, xform(BFLY, flap * 1.3, 1.3, 10 * math.sin(t * 4)), x, y)

def fly_xy(t):
    dc = STATE['dome']; hit = (dc[0] - 150, dc[1])
    if t < E.T_FLY_IN: return None
    if t < BONKS[0] - 0.35:
        u = (t - E.T_FLY_IN) / (BONKS[0] - 0.35 - E.T_FLY_IN)
        return (-100 + (hit[0] - 140 + 100) * ease_out(u), 300 + (hit[1] - 300) * u + 40 * math.sin(t * 9)), 8 * math.sin(t * 12), (1, 1), 0
    for i, b in enumerate(BONKS):
        nxt = BONKS[i + 1] - 0.35 if i < 2 else b + 0.6
        if t < nxt:
            if t < b:
                u = ease_in((t - (b - 0.35)) / 0.35); return (hit[0] - 140 + 140 * u, hit[1] + 20 * math.sin(t * 15)), -10 * u, (1, 1), 0
            k = t - b; sx, sy = squash(k, 0.25, 22, 7)
            return (hit[0] - 140 * ease_out(k / 0.3), hit[1] + 20 * math.sin(k * 20) * math.exp(-k * 4)), 15 * math.exp(-k * 4), (sy, sx), (i + 1) * 0.33
    k0 = lambda k: (hit[0] - 120 + 50 * math.cos(k * 2.2), hit[1] - 110 + 25 * math.sin(k * 2.2))
    if t < TFG:
        k = t - BONKS[2] - 0.6; x, y = k0(k); return (x, y + 6 * math.sin(t * 15)), 12 * math.sin(k * 3), (1, 1), 1
    uh = STATE['uhead']; land = (uh[0], uh[1] - 22); st = k0(TFG - BONKS[2] - 0.6)
    if t < TFL:
        u = ease((t - TFG) / (TFL - TFG))
        return (st[0] + (land[0] - st[0]) * u, st[1] + (land[1] - st[1]) * u - 160 * math.sin(u * math.pi)), 10 * math.sin(t * 14), (1, 1), max(0, 1 - u * 2)
    k = t - TFL; sx, sy = squash(k, 0.15, 18, 6)
    return land, 2 * math.sin(t * 20), (sx, sy), 0
def draw_fly(fr, t, step):
    r = fly_xy(t)
    if not r: return
    (x, y), rot, (sx, sy), dz = r; landed = t > TFL
    flap = 1 if landed else 0.75 + 0.25 * math.sin(t * 90)
    if landed and t > s[10]: rot += 6 * math.sin(t * 9)
    im = xform(FLY, sx, sy * flap, rot); paste(fr, shadow_of(im, 0.15, 6), x + 6, y + 10); paste(fr, im, x, y)
    if dz > 0:
        for i in range(3): a = t * 6 + i * 2.09; E.star(fr, x + 55 * math.cos(a), y - 50 + 14 * math.sin(a), 11 * min(1, dz * 2))
    if not landed and step % 12 == 0: EV.append((t, 'buzz'))

def draw_fx(fr, t):
    dc = STATE['dome']
    for b in BONKS:
        k = t - b
        if 0 <= k < 0.35:
            al = 1 - k / 0.35; ov = fr.copy(); hx, hy = dc[0] - 125, dc[1]
            cv2.ellipse(ov, (int(dc[0]), int(dc[1])), (int(140 + 40 * k / 0.35), int(175 + 40 * k / 0.35)), 0, 0, 360, (255, 255, 255), 6, cv2.LINE_AA)
            for ang in (-40, 0, 40):
                a = math.radians(180 + ang); cv2.line(ov, (int(hx), int(hy)), (int(hx - 50 * math.cos(a)), int(hy - 50 * math.sin(a))), (255, 255, 255), 6, cv2.LINE_AA)
            fr[:] = fr * (1 - 0.8 * al) + ov * 0.8 * al
    if 0.9 < t < 2.5:
        k = t - 0.9
        for i, (ox, oy) in enumerate([(-190, -90), (180, -130), (200, 40), (-200, 60)]):
            sz = max(0, math.sin(k * 4 + i)) * 22
            if sz > 2: E.star(fr, dc[0] + ox, dc[1] + oy, sz, (120, 230, 255))
    k = t - TFLASH
    if 0 <= k < 0.5:
        ph = STATE['phone']; ov = fr.copy(); cv2.circle(ov, (int(ph[0]), int(ph[1])), int(40 + 220 * k), (255, 255, 255), -1, cv2.LINE_AA)
        a = (1 - k / 0.5) * 0.85; fr[:] = fr * (1 - a) + ov * a
        if k < 0.2: fr[:] = fr * (1 - 0.3 * (1 - k / 0.2)) + 255 * 0.3 * (1 - k / 0.2)

BG = cv2.imread(E.A + 'bg.png'); BG = cv2.resize(BG, (int(W * 1.06), int(H * 1.06)), interpolation=cv2.INTER_LANCZOS4)
def frame(t, step):
    shake = 10 * (1 - (t - TB)) if TB < t < TB + 1.0 else 0
    for b in BONKS:
        if b <= t < b + 0.15: shake = max(shake, 3)
    fr = camera(BG, W, H, t, DUR, step, zoom=0.03, drift=5, jitter=0.6 + shake)
    p, r, dy = woman_pose(t); WO.draw(fr, t, p, r, dy); STATE['phone'] = WO.world(t, PHONE_I, p)
    p, r, dy = bablu_pose(t); BA.draw(fr, t, p, r, dy); STATE['dome'] = BA.world(t, DOME_I, p)
    draw_bfly(fr, t)
    if t >= TP1: draw_paper(fr, t)
    draw_fx(fr, t)
    p, r, dy = uncle_pose(t); UN.draw(fr, t, p, r, dy); STATE['uhead'] = UN.world(t, UHEAD_I, p)
    if t < TP0: STATE['p0'] = UN.world(t, PAPER_I, 'read')
    elif t < TP1: draw_paper(fr, t)
    draw_fly(fr, t, step)
    if t < 0.4: fr *= t / 0.4
    if t > DUR - 0.6: fr *= max(0, (DUR - t) / 0.6)
    return fr

if __name__ == '__main__':
    finish = make_finish(W, H, vignette=0.12, grain=1.6)
    PREV = [float(x) for x in os.environ.get('PREVIEW', '').split(',') if x]
    if PREV:
        tt = 0
        for tp in sorted(PREV):
            while tt < tp: frame(tt, int(tt * FPS)); tt += 0.5
            st = int(tp * FPS); cv2.imwrite(f'{HERE}/pc_{tp:05.1f}.jpg', finish(frame(tp, st), st))
        sys.exit()
    proc = ffmpeg_writer('/tmp/ep1c_video.mp4', W, H, fps=FPS, out_fps=24, crf=19)
    for step in range(int(DUR * FPS)):
        t = step / FPS; proc.stdin.write(finish(frame(t, step), step).tobytes())
    proc.stdin.close(); proc.wait()
    E.build_audio()
    subprocess.run(['ffmpeg', '-y', '-v', 'error', '-i', '/tmp/ep1c_video.mp4', '-i', HERE + '/ep1_audio.wav', '-map', '0:v', '-map', '1:a', '-af', 'loudnorm=I=-16:TP=-1.5', '-c:v', 'copy', '-c:a', 'aac', '-b:a', '192k', '-ar', '48000', '-shortest', '-movflags', '+faststart', '/tmp/ep1c_final.mp4'], check=True)
    subprocess.run(['cp', '/tmp/ep1c_final.mp4', HERE + '/ep1c_final.mp4'], check=True)
    print('done')
