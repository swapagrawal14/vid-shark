"""Bablu ki Metro - random scene 2: 'Personal Mausam' (rain walk test).
Uses vid-shark engine: posepack.Cast (key poses + cycles), sheets.slice_sheet (walk/run sheets)."""
import os, sys, math, json, wave, subprocess, random
import numpy as np, cv2
from PIL import Image
sys.path.insert(0, '/workspace/tools/vid-shark/engine')
from motion import ease, ease_out, ease_in, squash, xform, paste, make_finish, ffmpeg_writer, clamp
from posepack import Cast, seq, alpha_bbox
from sheets import slice_sheet
import sfx as SX
HERE = os.path.dirname(os.path.abspath(__file__)); VO = HERE + '/../vo/'
W, H, FPS = 1920, 1080, 24

def dur(f): return float(subprocess.check_output(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', f]).decode())
VO_AT = [2.0, 7.1, 11.0, 20.4]
VOD = [dur(VO + f's2_{i:02d}.wav') for i in range(4)]
T_STOP, T_GO = 2.6, 8.6                    # Bablu stops to gloat, walks again
T_CUT = 10.2                               # hard cut to the medium shot
T_FOG0, T_FOG1 = 10.6, 13.0
T_GROPE = 12.4
T_BONK = VO_AT[2] + VOD[2] + 0.5
T_DIZZY = T_BONK + 0.45
DUR = VO_AT[3] + VOD[3] + 1.4

# ---------------- world ----------------
BG = cv2.imread(HERE + '/bg_street.png'); s = 1080 / BG.shape[0]
BG = cv2.resize(BG, (int(BG.shape[1] * s), 1080), interpolation=cv2.INTER_LANCZOS4).astype(np.float32)
BWW = BG.shape[1]; FLOOR = 1012
walk = slice_sheet(HERE + '/bablu_walk_sheet.png', 6); walk = [walk[i] for i in (1, 2, 4, 5)]
run = slice_sheet(HERE + '/uncle_run_sheet.png', 4)
WALK_H = np.mean([alpha_bbox(f)[3] - alpha_bbox(f)[1] for f in walk])
SIDE_H = 826; HB = 370
BA = Cast(HERE + '/bablu_side', ['smug', 'grope', 'dizzy'], x=0, floor=FLOOR, scale=HB / SIDE_H,
          cycles={}, phase=0.4, sway=0.5, bob=1.5)
BAW = Cast(HERE + '/bablu_side', ['smug'], x=0, floor=FLOOR, scale=HB / WALK_H, cycles={'walk': walk}, sway=0.3, bob=0, pop=0)
UN = Cast(HERE + '/bablu_side', ['smug'], x=0, floor=FLOOR - 14, scale=345 / 540, cycles={'run': run}, sway=0, bob=0, pop=0)
LP = Image.open(HERE + '/lamppost.png').convert('RGBA'); bb = alpha_bbox(LP); LP = LP.crop((bb[0], bb[1], bb[2] + 1, bb[3] + 1))
LP = LP.resize((int(LP.width * 700 / LP.height), 700), Image.LANCZOS); POST_X = 2650
DOME_SIDE, DOME_WALK = (456, 336), None
WB = alpha_bbox(walk[0]); DOME_WALK = ((WB[0] + WB[2]) / 2 + 5, WB[1] + 95)
RNG = np.random.RandomState(3)
DROPS = np.c_[RNG.uniform(0, W + 300, 420), RNG.uniform(0, H, 420), RNG.uniform(0.6, 1.0, 420)]
EV = []

def bablu_state(t):
    """world x, pose name, which cast, rot, dy"""
    v = 175
    if t < T_STOP: x = 380 + v * t; return x, BAW.cycle('walk', t, 6), BAW, 0, 0
    if t < T_GO: return 380 + v * T_STOP, 'smug', BA, 0, 0
    if t < T_CUT: x = 380 + v * T_STOP + v * (t - T_GO); return x, BAW.cycle('walk', t, 6), BAW, 0, 0
    x0 = 1750
    if t < T_GROPE: return x0 + v * (t - T_CUT), BAW.cycle('walk', t, 6), BAW, 0, 0
    xg = x0 + v * (T_GROPE - T_CUT); stop = POST_X - 70
    if t < T_BONK:
        k = t - T_GROPE; x = min(stop, xg + 70 * k)   # slow blind shuffle
        return x, 'grope', BA, 2.5 * math.sin(k * 3.2), -6 * abs(math.sin(k * 3.2))
    if t < T_DIZZY:
        k = t - T_BONK; return stop - 40 * ease_out(k / 0.2), 'grope', BA, 6 * math.exp(-k * 6), 0
    return stop - 70, 'dizzy', BA, 0, 0

def cam(t):
    """left, top, zoom of the view in world px"""
    if t < T_CUT:
        bx = bablu_state(t)[0]; z = 1.0
        return clamp(bx - 760, 0, BWW - W), 0, z
    z = 1.75; vw, vh = W / z, H / z
    bx = bablu_state(t)[0]; cx = bx + 120
    return clamp(cx - vw / 2, 0, BWW - vw), FLOOR + 40 - vh, z

def fog(t):
    if t < T_FOG0: return 0
    if t < T_DIZZY + 0.3: return ease((t - T_FOG0) / (T_FOG1 - T_FOG0))
    return 1 - ease((t - T_DIZZY - 0.3) / 2.5)

def rain_amt(t): return ease((t - 1.0) / 3.0)

def draw_fog(view, cast, pose, t, f):
    if f <= 0.01: return
    k = cast.P[pose][2]
    if pose.startswith('walk'): c = cast.world(DOME_WALK); rx, ry = 76 * k, 92 * k
    else: c = cast.world(DOME_SIDE); rx, ry = 128 * k, 150 * k
    ov = np.zeros_like(view); m = np.zeros(view.shape[:2], np.float32)
    cv2.ellipse(m, (int(c[0]), int(c[1])), (int(rx), int(ry)), 0, 0, 360, 1.0, -1, cv2.LINE_AA)
    m = cv2.GaussianBlur(m, (0, 0), 4) * 0.78 * f
    view[:] = view * (1 - m[..., None]) + np.array([248, 240, 244], np.float32) * m[..., None]
    r = random.Random(7)
    for i in range(int(10 * f)):
        a = r.uniform(0, 6.28); d = r.uniform(0.2, 0.8)
        x = c[0] + math.cos(a) * rx * d; y = c[1] + math.sin(a) * ry * d + (t * 12 * r.uniform(0.3, 1)) % 20
        cv2.circle(view, (int(x), int(y)), max(2, int(5 * k / 0.45)), (255, 250, 252), -1, cv2.LINE_AA)

def draw_rain(fr, t, z):
    a = rain_amt(t)
    if a <= 0: return
    fr *= 1 - 0.07 * a; fr += np.array([150, 120, 130], np.float32) * 0.07 * a
    n = int(len(DROPS) * a); L = 38 * z ** 0.5
    for i in range(n):
        x0, y0, sp = DROPS[i]
        y = (y0 + t * 1500 * sp) % (H + 80) - 40; x = (x0 - t * 260 * sp) % (W + 300) - 150
        cv2.line(fr, (int(x), int(y)), (int(x - 7), int(y + L * sp)), (250, 235, 235), 2, cv2.LINE_AA)
    for i in range(int(40 * a)):              # splashes on the pavement
        r = random.Random(i * 31 + int(t * 8)); x = r.uniform(0, W); y = (FLOOR + r.uniform(-5, 50) - cam(t)[1]) * z
        cv2.ellipse(fr, (int(x), int(y)), (int(9 * z ** 0.5), int(3 * z ** 0.5)), 0, 180, 360, (250, 240, 240), 2, cv2.LINE_AA)

def star(fr, x, y, r, col=(80, 210, 250)):
    pts = [(x + (r if i % 2 == 0 else r * 0.45) * math.cos(i * math.pi / 5 - math.pi / 2), y + (r if i % 2 == 0 else r * 0.45) * math.sin(i * math.pi / 5 - math.pi / 2)) for i in range(10)]
    p = np.array(pts, np.int32); cv2.fillPoly(fr, [p], col, cv2.LINE_AA); cv2.polylines(fr, [p], True, (40, 30, 50), 2, cv2.LINE_AA)

def frame(t, step):
    L, T, z = cam(t)
    if T_BONK <= t < T_BONK + 0.5: L += 14 * math.sin((t - T_BONK) * 70) * (1 - (t - T_BONK) / 0.5)
    vw, vh = int(math.ceil(W / z)) + 2, int(math.ceil(H / z)) + 2
    Li, Ti = int(L), int(max(0, T))
    view = BG[Ti:Ti + vh, Li:Li + vw].copy()
    ox, oy = -Li, -Ti
    # uncle runs right->left behind Bablu during the gloat
    if 6.3 < t < 9.6:
        ux = 2350 - 640 * (t - 6.3); UN.x = ux + ox; UN.floor = FLOOR - 14 + oy
        UN.draw(view, t, UN.cycle('run', t, 12), dy=-10 * abs(math.sin(t * 12 * math.pi / 2)))
        if step % 6 == 0: EV.append((t, 'dab'))
    # lamppost
    paste(view, LP, POST_X + ox, FLOOR - LP.height / 2 + 6 + oy)
    x, pose, cast, rot, dy = bablu_state(t)
    cast.x, cast.floor = x + ox, FLOOR + oy
    sq = (1, 1)
    if T_BONK <= t < T_DIZZY: k = t - T_BONK; sq = (0.9 + 0.1 * ease(k / 0.3), 1.04 - 0.04 * ease(k / 0.3))
    cast.draw(view, t, pose, rot, dy=dy, sq=sq)
    if pose.startswith('walk') and int(t * 6) != int((t - 1 / FPS) * 6) and int(t * 6) % 2 == 0: EV.append((t, 'dab'))
    draw_fog(view, cast, pose, t, fog(t))
    if t >= T_DIZZY:
        c = cast.world(DOME_SIDE); k = cast.P[pose][2]
        for i in range(4):
            a = t * 5 + i * 1.57; star(view, c[0] + 150 * k * math.cos(a), c[1] - 170 * k + 30 * k * math.sin(a), 14)
    if T_BONK <= t < T_BONK + 0.3:
        c = (POST_X - 18 + ox, cast.world(DOME_SIDE)[1]); al = 1 - (t - T_BONK) / 0.3
        for ang in range(-60, 61, 30):
            a = math.radians(180 + ang); cv2.line(view, (int(c[0] + 20 * math.cos(a)), int(c[1] + 20 * math.sin(a))), (int(c[0] + 70 * math.cos(a)), int(c[1] + 70 * math.sin(a))), (255, 255, 255), 5, cv2.LINE_AA)
    fx, fy = L - Li, T - Ti
    M = np.array([[z, 0, -fx * z], [0, z, -fy * z]], np.float32)
    fr = cv2.warpAffine(view, M, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
    draw_rain(fr, t, z)
    if T_BONK <= t < T_BONK + 0.12: fr[:] = fr * 0.6 + 255 * 0.4
    if t < 0.4: fr *= t / 0.4
    if t > DUR - 0.8: fr *= max(0, (DUR - t) / 0.8)
    return fr

def clang():
    t = np.arange(int(1.2 * SX.SR)) / SX.SR
    s = sum(np.sin(2 * np.pi * f * t) * np.exp(-t * d) * a for f, d, a in [(523, 3, .25), (1187, 4, .15), (1873, 6, .1), (2911, 9, .06)])
    return (s + np.random.randn(len(t)) * np.exp(-t * 40) * .3) * .6
def rain_noise(n):
    x = np.random.RandomState(1).randn(n).astype(np.float32)
    x = np.convolve(x, np.ones(6) / 6, 'same'); return x * 0.05

def build_audio():
    SX.FX['clang'] = clang
    EV.append((1.0, 'thunder')); EV.append((6.4, 'whoosh')); EV.append((T_BONK, 'clang')); EV.append((T_BONK + 0.05, 'boing'))
    EV.append((T_GROPE, 'squish')); EV.append((T_STOP, 'tick'))
    N = int(DUR * SX.SR); vo = np.zeros(N, np.float32)
    for i, st in enumerate(VO_AT):
        a = np.frombuffer(subprocess.check_output(['ffmpeg', '-v', 'error', '-i', VO + f's2_{i:02d}.wav', '-f', 'f32le', '-ac', '1', '-ar', str(SX.SR), '-']), np.float32)
        j = int(st * SX.SR); L = min(len(a), N - j); vo[j:j + L] += a[:L]
    ev = [(t, k) for t, k in EV if k != 'dab'] + [(t, 'dab') for t, k in EV if k == 'dab'][::1]
    m = SX.mix(DUR, vo=vo, vo_at=0, events=ev, bed=True)
    bt = np.arange(N) / SX.SR; rn = rain_noise(N) * np.clip((bt - 1.0) / 3.0, 0, 1)
    m = m + rn; m /= max(1, np.abs(m).max() / .95)
    with wave.open(HERE + '/s2_audio.wav', 'wb') as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SX.SR); w.writeframes((m * 32767).astype(np.int16).tobytes())

if __name__ == '__main__':
    finish = make_finish(W, H, vignette=0.12, grain=1.6)
    PREV = [float(x) for x in os.environ.get('PREVIEW', '').split(',') if x]
    if PREV:
        for tp in sorted(PREV):
            st = int(tp * FPS); cv2.imwrite(f'{HERE}/sp_{tp:05.1f}.jpg', finish(frame(tp, st), st))
        print('bonk', T_BONK, 'dur', DUR); sys.exit()
    proc = ffmpeg_writer('/tmp/s2_video.mp4', W, H, fps=FPS, out_fps=24, crf=19)
    for step in range(int(DUR * FPS)):
        t = step / FPS; proc.stdin.write(finish(frame(t, step), step).tobytes())
    proc.stdin.close(); proc.wait(); build_audio()
    subprocess.run(['ffmpeg', '-y', '-v', 'error', '-i', '/tmp/s2_video.mp4', '-i', HERE + '/s2_audio.wav', '-af', 'loudnorm=I=-16:TP=-1.5', '-c:v', 'copy', '-c:a', 'aac', '-b:a', '192k', '-ar', '48000', '-shortest', '-movflags', '+faststart', '/tmp/s2_final.mp4'], check=True)
    subprocess.run(['cp', '/tmp/s2_final.mp4', HERE + '/s2_final.mp4'], check=True); print('done')
