"""3D toy sample: seed to sprout. Pot slides in, seed drops and bounces, watering can tilts and rains, sun rises and beams, sprout grows with leaf wiggle."""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.join(HERE, '..'))
from common import *
FPS = 24
TXT = json.load(open(HERE + '/../lines.json'))['sprout']
PRE = 0.3; VO = vo_info(HERE); DUR = PRE + VO + 1.4
T = lambda w: word_time(TXT, w, VO, PRE)
tTiny, tSeed, tWater, tSun, tGrow = T('tiny'), T('Drop'), T('water'), T('sun'), T('watch')
POT = load(HERE, 'pot', 0.78); SPR = load(HERE, 'sprout', 0.88); CAN = load(HERE, 'can', 0.42); SUN = load(HERE, 'sun', 0.42)
PX, PY = 900, 760
SOILX, SOILY = PX - POT.width / 2 + 307 * 0.78, PY - POT.height / 2 + 105 * 0.78
CPIV = (CAN.width * 0.6, CAN.height * 0.5); CTIP = (0, 168 * 0.42)
EV = [(0.3, 'whoosh'), (0.9, 'squish')]
rng = random.Random(9); drops = []
TITLE = label('seed to sprout', 84, (90, 70, 160), stroke=8, stroke_fill=(255, 255, 255))
def draw(fr, t, step):
    global drops
    # sun rises
    if t > tSun - 0.3:
        k = ease_out((t - tSun + 0.3) / 0.9); sx, sy = 1500, 520 - 330 * k
        ang = (t - tSun) * 25
        if k > 0.6:
            ov = fr.copy()
            for i in range(8):
                a = math.radians(ang + i * 45); L1, L2 = 150, 210 + 20 * math.sin(t * 6 + i)
                cv2.line(ov, (int(sx + L1 * math.cos(a)), int(sy + L1 * math.sin(a))), (int(sx + L2 * math.cos(a)), int(sy + L2 * math.sin(a))), (120, 220, 255), 16, cv2.LINE_AA)
            fr[:] = fr * 0.45 + ov * 0.55
        paste(fr, xform(SUN, 1 + 0.03 * math.sin(t * 5), 1 - 0.03 * math.sin(t * 5), 8 * math.sin(t * 2)), sx, sy)
        if abs(t - (tSun - 0.3)) < 0.5 / FPS: EV.append((t, 'whoosh'))
        # warm glow on scene
        g = 0.08 * ease((t - tSun) / 1.0); fr[:] = fr * (1 + g)
    # pot slides in from right with overshoot
    if t < 0.9: px = 2300 + (PX - 2300) * back(t / 0.9); sx_, sy_ = 1, 1
    else: px = PX; sx_, sy_ = squash(t - 0.9, 0.05, 18, 6)
    sh = Image.new('RGBA', (POT.width + 100, 80), (0, 0, 0, 0)); ImageDraw.Draw(sh).ellipse([30, 20, POT.width + 70, 60], fill=(60, 40, 40, 90))
    paste(fr, sh.filter(ImageFilter.GaussianBlur(10)), px, PY + POT.height / 2 - 18)
    paste(fr, xform(POT, sx_, sy_), px, PY + POT.height * (1 - sy_) / 2)
    # sprout grows (behind pot rim)
    if t > tGrow - 0.4:
        g = max(0.05, back((t - tGrow + 0.4) / 1.6, 1.2))
        sw = 1 + 0.06 * math.sin(t * 7) * (1 - min(g, 1) * 0.5)
        crop = xform(SPR, g * sw, g, 0)
        paste(fr, crop, SOILX + (px - PX), SOILY + 6 - crop.height / 2)
        if abs(t - (tGrow - 0.4)) < 0.5 / FPS: EV.append((t, 'boing'))
        if g > 0.97 and abs(t - (tGrow + 1.3)) < 0.5 / FPS: EV.append((t, 'pop'))
    # seed drop
    if tSeed < t < tWater + 0.3:
        u = (t - tSeed) / 0.5
        if u < 1: y = 80 + (SOILY - 80) * ease_in(u); rot = u * 360
        else: k = t - tSeed - 0.5; y = SOILY - 40 * abs(math.sin(min(k, 0.6) / 0.6 * math.pi)) * math.exp(-k * 3); rot = 360
        im = Image.new('RGBA', (70, 70), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
        d.ellipse([10, 20, 60, 52], fill=(70, 110, 150, 255)); d.ellipse([18, 25, 34, 33], fill=(150, 190, 220, 255))
        paste(fr, im.rotate(rot), SOILX, y)
        if abs(u - 1) < 0.5 / FPS / 0.5: EV.append((t, 'plip'))
    # watering can
    if tWater - 0.6 < t < tSun + 0.6:
        home = (SOILX + 330, SOILY - 260)
        if t < tWater: k = back((t - tWater + 0.6) / 0.6); cx, cy, rot = home[0] + 900 * (1 - k), home[1] - 200 * (1 - k), 0
        elif t < tSun - 0.1: cx, cy = home[0] + 4 * math.sin(t * 8), home[1]; rot = 32 * ease((t - tWater) / 0.4)
        else: k = ease((t - tSun + 0.1) / 0.6); cx, cy, rot = home[0] + 900 * k, home[1] - 200 * k, 32 * (1 - k)
        place_pivot(fr, CAN, cx, cy, CPIV, rot, shadow=(0.18, 12, 20, 30))
        vx, vy = rot_vec(CTIP[0] - CPIV[0], CTIP[1] - CPIV[1], rot); tx, ty = cx + vx, cy + vy
        if tWater + 0.3 < t < tSun - 0.1:
            for _ in range(3): drops.append([tx + rng.uniform(-10, 10), ty + rng.uniform(-8, 8), rng.uniform(-5, -1), rng.uniform(0, 3)])
            if step % 12 == 0: EV.append((t, 'pour'))
    nd = []
    for d_ in drops:
        d_[0] += d_[2]; d_[1] += d_[3]; d_[3] += 1.8
        if d_[1] < SOILY + 6:
            cv2.ellipse(fr, (int(d_[0]), int(d_[1])), (5, 8), 0, 0, 360, (240, 190, 120), -1, cv2.LINE_AA); cv2.circle(fr, (int(d_[0] - 1), int(d_[1] - 2)), 2, (255, 255, 255), -1, cv2.LINE_AA); nd.append(d_)
    drops = nd
    # title at end
    if t > tGrow + 1.4:
        k = int((t - tGrow - 1.4) * 12); s = pop_scale(k); paste(fr, xform(TITLE, s, s, 2 * math.sin(t * 2)), 470, 330)
        if k == 0: EV.append((t, 'pop'))
if __name__ == '__main__':
    run(HERE, DUR, FPS, draw, EV, PRE)
