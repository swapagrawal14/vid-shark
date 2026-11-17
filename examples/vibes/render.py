"""70s groovy poster style + deadpan dark humour: 'Good Vibes Only'.
Built from a single style reference (a 70s 'Hey Mr DJ' print). Guy meditates, serene,
while the phone rings (landlord), a cloud rains on him (career), and lightning
fries the sunflower. 12 fps stepped motion for the retro print feel."""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.join(HERE, '..'))
from common import *
FPS = 12; PRE = 0.3; VO = vo_info(HERE); DUR = PRE + VO + 1.3
# sentence starts measured from the VO's own pauses (more exact than word_time for deadpan delivery)
S = [x + PRE for x in (0.15, 2.1, 3.2, 4.35, 5.6, 7.15, 8.8, 10.05, 11.35, 12.6)]
tVibes, tEyes, tBreathe, tPhone, tLandlord, tCloud, tCareer, tSun, tDead, tNamaste = S
tStrike = tDead - 0.35
GUY = load(HERE, 'guy', 0.6); PHONE = load(HERE, 'phone', 0.4); CLOUD = load(HERE, 'cloud', 0.6)
PLANT = load(HERE, 'plant', 0.5); TITLE = load(HERE, 'title', 0.5)
FLOOR = 950; GX = 960; PLX = 1480
# charred plant: same alpha, colours crushed to soot
_a = np.array(PLANT).astype(np.float32); _g = _a[..., :3].mean(2, keepdims=True)
_a[..., :3] = _g * 0.25 + np.array([40, 34, 34]) * 0.75; BURNT = Image.fromarray(_a.astype(np.uint8))
EV = []; rng = random.Random(4); rain = []; smoke = []
def once(t, at, name):
    if abs(t - at) < 0.5 / FPS: EV.append((t, name))
def bolt(fr, x0, y0, x1, y1, seed):
    r = random.Random(seed); pts = [(x0, y0)]
    for i in range(1, 8): f = i / 8; pts.append((x0 + (x1 - x0) * f + r.uniform(-40, 40), y0 + (y1 - y0) * f))
    pts.append((x1, y1)); P = np.array(pts, np.int32)
    cv2.polylines(fr, [P], False, (0, 0, 0), 26, cv2.LINE_AA); cv2.polylines(fr, [P], False, (90, 240, 255), 14, cv2.LINE_AA)
def draw(fr, t, step):
    global rain, smoke
    # ---- sunflower (right). trembles when named, gets struck, droops charred
    if t < tStrike:
        tr = 3 * math.sin(step * 2.6) if t > tSun else 2 * math.sin(t * 2)
        place_pivot(fr, PLANT, PLX, FLOOR, (PLANT.width / 2, PLANT.height), tr, shadow=(0.25, 6, 10, 6))
    else:
        k = back((t - tStrike - 0.25) / 0.6, 1.3); rot = -38 * k + 1.5 * math.sin(t * 3)
        place_pivot(fr, BURNT, PLX, FLOOR, (PLANT.width / 2, PLANT.height), rot, shadow=(0.25, 6, 10, 6))
        if t < tStrike + 2.5 and step % 2 == 0: smoke.append([PLX - 60 + rng.uniform(-30, 30), FLOOR - 380, rng.uniform(16, 26), 0])
    ns = []
    for s_ in smoke:
        s_[1] -= 6; s_[0] += 2; s_[2] += 1.2; s_[3] += 1
        if s_[3] < 22:
            c = (int(s_[0]), int(s_[1])); r_ = int(s_[2])
            ov = fr.copy(); cv2.circle(ov, c, r_, (70, 70, 80), -1, cv2.LINE_AA); cv2.circle(ov, c, r_, (0, 0, 0), 4, cv2.LINE_AA)
            a = 0.7 * (1 - s_[3] / 22); fr[:] = fr * (1 - a) + ov * a; ns.append(s_)
    smoke = ns
    # ---- guy: unbothered meditation. breathes, big inhale on 'breathe in', smug bounce on 'Namaste'
    br = 0.012 * math.sin(t * 2.2)
    if tBreathe < t < tBreathe + 1.6: br += 0.06 * math.sin((t - tBreathe) / 1.6 * math.pi)
    bx, by = 1 - br * 0.5, 1 + br
    if t > tNamaste: sx_, sy_ = squash(t - tNamaste, 0.07, 14, 5); bx *= sx_; by *= sy_
    g = xform(GUY, bx, by)
    sh = Image.new('RGBA', (GUY.width + 120, 70), (0, 0, 0, 0)); ImageDraw.Draw(sh).ellipse([20, 15, GUY.width + 100, 55], fill=(60, 20, 10, 110))
    paste(fr, sh.filter(ImageFilter.GaussianBlur(8)), GX, FLOOR - 4)
    paste(fr, g, GX, FLOOR - g.height / 2)
    # ---- phone hops in from the left and rings, harder for the landlord
    if t > tPhone - 0.5:
        k = back((t - tPhone + 0.5) / 0.5); px = -250 + (560 + 250) * k; py = FLOOR - PHONE.height / 2; rot = 0
        ringing = tPhone + 0.2 < t < tCloud - 0.2
        if ringing:
            amp = 9 if t > tLandlord else 5
            rot = amp * (1 if step % 2 else -1); py -= (14 if t > tLandlord else 6) * (step % 2)
            for i, rr in enumerate((90, 125, 160)):
                if (step // 2 + i) % 3 != 2:
                    for sgn in (-1, 1):
                        cv2.ellipse(fr, (int(px), int(py - 40)), (rr + 20, rr), 0, -90 + sgn * 55 - 18, -90 + sgn * 55 + 18, (0, 0, 0), 9, cv2.LINE_AA)
            if step % 6 == 0: EV.append((t, 'ring'))
        place_pivot(fr, PHONE, px, FLOOR, (PHONE.width / 2, PHONE.height), rot, shadow=(0.25, 6, 8, 4))
        once(t, tPhone - 0.5, 'whoosh'); once(t, tPhone, 'boing')
    # ---- the career cloud: slides over him and rains on him only, then goes for the sunflower
    if t > tCloud - 0.6:
        k = back((t - tCloud + 0.6) / 0.7)
        cx = 2300 + (GX - 2300) * k
        if t > tSun: cx = GX + (PLX - 70 - GX) * ease((t - tSun) / 0.8)
        cy = 230 + 10 * math.sin(t * 3)
        sx_ = 1 + 0.03 * math.sin(t * 5)
        if tStrike - 0.15 < t < tStrike + 0.2: sx_ *= 1.12   # winds up
        c = xform(CLOUD, sx_, 2 - sx_); paste(fr, c, cx, cy)
        once(t, tCloud - 0.6, 'whoosh')
        if t > tCloud + 0.2 and t < DUR - 0.3:
            for _ in range(4): rain.append([cx + rng.uniform(-170, 170), cy + 100, rng.uniform(26, 34)])
            if step % 3 == 0: EV.append((t, 'plip'))
        if tStrike <= t < tStrike + 0.25:
            bolt(fr, cx - 40, cy + 110, PLX - 20, FLOOR - 420, step)
        once(t, tStrike, 'thunder')
    nr = []
    for d_ in rain:
        d_[1] += d_[2]
        if d_[1] < FLOOR:
            cv2.line(fr, (int(d_[0]), int(d_[1])), (int(d_[0] - 4), int(d_[1] + 28)), (0, 0, 0), 9, cv2.LINE_AA)
            cv2.line(fr, (int(d_[0]), int(d_[1])), (int(d_[0] - 4), int(d_[1] + 28)), (235, 170, 70), 5, cv2.LINE_AA); nr.append(d_)
    rain = nr
    # lightning flash
    if tStrike <= t < tStrike + 0.17: fr[:] = fr * 0.35 + 255 * 0.65
    # ---- title: 'GOOD VIBES ONLY' pops in on the first line, cracks back in on Namaste
    if tVibes < t < tEyes + 0.6 or t > tNamaste:
        t0 = tVibes if t < tNamaste else tNamaste
        k = int((t - t0) * 12); s = pop_scale(k)
        if t < tNamaste and t > tEyes: s *= 1 - ease((t - tEyes) / 0.6)
        if s > 0.02: paste(fr, xform(TITLE, s, s, 4 * math.sin(t * 2)), 330, 300)
        once(t, t0, 'pop')
if __name__ == '__main__':
    run(HERE, DUR, FPS, draw, EV, PRE, jitter=True)
