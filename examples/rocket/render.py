"""Paper cut-out sample: rocket launch. Countdown numbers slam in, rocket rumbles, paper smoke billows, launch with camera follow, stars streak."""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.join(HERE, '..'))
from common import *
FPS = 12   # stepped "paper" motion
TXT = json.load(open(HERE + '/../lines.json'))['rocket']
PRE = 0.3; VO = vo_info(HERE); DUR = PRE + VO + 0.8
T = lambda w: word_time(TXT, w, VO, PRE)
t3, t2, t1, tRoar, tSmoke, tUp, tHills, tClouds, tStars = T('Three'), T('two'), T('one.'), T('engines'), T('smoke'), T('up she'), T('past the hills'), T('past the clouds'), T('stars')
RS = 0.62; ROCK = load(HERE, 'rocket', RS); CLD = load(HERE, 'cloud', 0.13); BIGC = load(HERE, 'cloud', 0.45)
PADX, PADY = 960 * 1.0, 935   # rocket base on pad (screen)
EV = []
rng = random.Random(4); puffs = []
NUMS = {3: label('3', 260, (250, 205, 70), stroke=10, stroke_fill=(40, 30, 60)), 2: label('2', 260, (250, 205, 70), stroke=10, stroke_fill=(40, 30, 60)), 1: label('1', 260, (250, 205, 70), stroke=10, stroke_fill=(40, 30, 60))}
def paper_shadow(im, dx=10, dy=12): return shadow_of(im, 0.45, 4), dx, dy
def flame(fr, x, y, s, t):
    for i, (col, sc) in enumerate([((40, 90, 230), 1.0), ((40, 170, 250), 0.7), ((150, 235, 255), 0.4)]):
        h = (90 + 30 * math.sin(t * 40 + i)) * s * sc; w = 38 * s * sc
        pts = np.array([(x - w, y), (x - w * 0.5, y + h * 0.6), (x, y + h), (x + w * 0.5, y + h * 0.6), (x + w, y)], np.int32)
        cv2.fillPoly(fr, [pts], col, cv2.LINE_AA)
def draw(fr, t, step):
    global puffs
    lift = 0.0
    if t > tUp: lift = 380 * (t - tUp) ** 2 + 150 * (t - tUp)
    base_top = PADY - ROCK.height / 2
    cam = max(0.0, lift - (base_top - 380))  # camera follows once rocket reaches upper third
    shake = 0
    if tRoar < t < tUp + 0.6: shake = 5 * math.sin(step * 2.3)
    # shift background down as camera rises (parallax)
    if cam > 0:
        M = np.float32([[1, 0, 0], [0, 1, cam]]); fr[:] = cv2.warpAffine(fr, M, (W, H), borderMode=cv2.BORDER_CONSTANT, borderValue=(78, 45, 30))
        # streaking paper stars once high
    if t > tHills:
        k = min(1, (t - tHills) / 0.6) * (1.6 if t > tStars else 1)
        for i in range(22):
            r_ = random.Random(i); x = r_.uniform(80, W - 80); y = (r_.uniform(0, H) + (t * 900 * k) ) % (H + 200) - 100
            L = 40 * k
            s = 8 + (i % 4) * 4
            cv2.line(fr, (int(x), int(y - s)), (int(x), int(y - s - L)), (110, 180, 220), 3, cv2.LINE_AA)
            pts = np.array([(x, y - s), (x + s * 0.3, y - s * 0.3), (x + s, y), (x + s * 0.3, y + s * 0.3), (x, y + s), (x - s * 0.3, y + s * 0.3), (x - s, y), (x - s * 0.3, y - s * 0.3)], np.int32)
            cv2.fillPoly(fr, [pts], (90, 210, 250), cv2.LINE_AA)
    # passing clouds after hills
    if t > tClouds - 0.6:
        k = (t - tClouds + 0.6)
        for i, (x0, sp) in enumerate([(380, 1.0), (1500, 1.25), (800, 0.8)]):
            y = -350 + k * 1100 * sp - i * 250
            if -400 < y < H + 400:
                im = BIGC; s, dx, dy = paper_shadow(im); paste(fr, s, x0 + dx, y + dy); paste(fr, im, x0, y)
    # smoke puffs
    if tRoar - 0.2 < t < tUp + 0.8 and step % 1 == 0:
        for _ in range(2 if t > tSmoke else 1):
            side = rng.choice([-1, 1]); puffs.append(dict(x=PADX + side * rng.uniform(20, 60), y=PADY - 10 + cam, vx=side * rng.uniform(10, 26), vy=rng.uniform(-6, 2), s=rng.uniform(0.6, 1.0), age=0, rot=rng.uniform(-30, 30)))
        EV.append((t, 'whoosh')) if step % 4 == 0 else None
    np_ = []
    for p in puffs:
        p['age'] += 1; p['x'] += p['vx']; p['y'] += p['vy']; p['vx'] *= 0.9; p['vy'] -= 0.3; p['s'] *= 1.035; p['y'] += 0 if t < tUp else 0
        if p['age'] < 20:
            im = xform(CLD, p['s'], p['s'], p['rot']); paste(fr, shadow_of(im, 0.35, 3), p['x'] + 6, p['y'] + 8); paste(fr, im, p['x'], p['y']); np_.append(p)
    puffs = np_
    # rocket
    if t < 0.7: ry = -400 + (PADY - ROCK.height / 2 + 400) * ease_in(t / 0.7); sx, sy = 1, 1.06
    else:
        ry = PADY - ROCK.height / 2; sx, sy = squash(t - 0.7, 0.05, 16, 6) if t < 1.6 else (1, 1)
        if abs(t - 0.7) < 0.5 / FPS: EV.append((t, 'squish'))
    if tRoar < t < tUp: sx, sy = 1 + 0.02 * math.sin(step * 3), 1 - 0.03 * abs(math.sin(step * 1.7))   # anticipation crouch
    ry = ry - lift + cam
    rot = math.sin(step * 2.1) * 1.2 if tRoar < t < tUp + 1 else 0
    if t > tRoar: flame(fr, PADX + shake, ry + ROCK.height / 2 - 30, 1.2 + 1.0 * ease((t - tUp) / 0.5), t)
    im = xform(ROCK, sx, sy, rot); s, dx, dy = paper_shadow(im, 14, 16)
    paste(fr, s, PADX + shake + dx, ry + dy); paste(fr, im, PADX + shake, ry + ROCK.height * (1 - sy) / 2)
    # countdown
    for n, tn in ((3, t3), (2, t2), (1, t1)):
        nxt = {3: t2, 2: t1, 1: tRoar}[n]
        if tn <= t < nxt + 0.15:
            k = int((t - tn) * FPS); s = pop_scale(k) * (1 - 0.6 * ease((t - (nxt - 0.05)) / 0.2)); rr = (n - 2) * 8
            paste(fr, xform(NUMS[n], s, s, rr), 1450, 420)
            if k == 0: EV.append((t, 'pop'))
    if abs(t - tUp) < 0.5 / FPS: EV.append((t, 'boing'))
if __name__ == '__main__':
    run(HERE, DUR, FPS, draw, EV, PRE, jitter=True)
