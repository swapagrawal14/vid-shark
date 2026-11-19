"""Tapri shot for scene.py: friends wave -> close-up chai pour (the stall's own kettle, cut out
of the background and tilted) -> kulhads + sip with steam -> big hi-fi -> everyone laughs.
All characters are generated pose packs (tapri/poses/<name>_<pose>.png), registered on one canvas."""
import math, random
import numpy as np, cv2
from PIL import Image
from motion import ease, ease_out, back, squash, paste, place_pivot, clamp, xform
from posepack import Cast, seq, alpha_bbox, despill_edge     # despill_edge moved to the engine

W, H = 1920, 1080
S = 1080 / 768                                     # tapri_bg source px -> world px
ZT = 2.0                                           # sprites prescaled for the close-up
KETTLE_TILT = 0.0                                  # kettle stays still on the stove (chai pours from the spout)


def star(fr, x, y, r, col=(80, 210, 250)):
    pts = [(x + (r if i % 2 == 0 else r * 0.45) * math.cos(i * math.pi / 5 - math.pi / 2),
            y + (r if i % 2 == 0 else r * 0.45) * math.sin(i * math.pi / 5 - math.pi / 2)) for i in range(10)]
    p = np.array(pts, np.int32); cv2.fillPoly(fr, [p], col, cv2.LINE_AA); cv2.polylines(fr, [p], True, (40, 30, 50), 2, cv2.LINE_AA)


class Shot:
    def __init__(self, here, t0, vo_at, t_hifi, ev, girl_unused, draw_cast, shadow):
        self.t0, self.vo, self.th, self.ev, self.draw_cast, self.shadow = t0, vo_at, t_hifi, ev, draw_cast, shadow
        TP, G = here + '/tapri/', here + '/girl/'
        bg = cv2.imread(TP + 'tapri_bg.png')
        # --- cut the kettle out of the plate so it can tilt and pour
        x0, y0, x1, y1 = 765, 246, 900, 380
        crop = bg[y0:y1, x0:x1].astype(np.int32); b, g, r = crop[..., 0], crop[..., 1], crop[..., 2]
        m = ~((b > r + 45) & (b > 110))                       # not the blue wall
        yy, xx = np.mgrid[y0:y1, x0:x1]
        low = yy >= 358                                         # stove band: kettle bottom = rounded ellipse
        ell = ((xx - 831) / 62.0) ** 2 + ((yy - 358) / 14.0) ** 2 <= 1
        m = np.where(low, ell, m)
        m &= ~((xx >= 797) & (xx <= 819) & (yy < 292) & (r > 120))   # tent pole behind the handle
        m = cv2.morphologyEx(m.astype(np.uint8), cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
        n, lab, st, _ = cv2.connectedComponentsWithStats(m, 8)
        keep = np.zeros_like(m)
        for k in range(1, n):
            if st[k, cv2.CC_STAT_AREA] > 60: keep[lab == k] = 1
        # take the kettle's dark ink outline into the matte (the wall test leaves it out, so the edge was the light body = grey rim)
        L_ = crop.mean(2)
        keep = (keep | (cv2.dilate(keep, np.ones((5, 5), np.uint8)) & (L_ < 95) & ~((b > r + 45) & (b > 110) & (L_ > 70)))).astype(np.uint8)
        full = np.zeros(bg.shape[:2], np.uint8); full[y0:y1, x0:x1] = keep
        # defringe: the binary mask's 1-px border is a blend of the dark outline and the blue wall, and a blurred alpha
        # over it read as a grey rim. Pull the matte in by 1 px, rebuild the edge colours from the solid interior
        # (normalised 5x5 average of core pixels only), and feather the alpha just slightly.
        core = cv2.erode(keep, np.ones((3, 3), np.uint8))
        rgb = bg[y0:y1, x0:x1][..., ::-1].astype(np.float32)
        cw = cv2.blur(core.astype(np.float32), (5, 5))[..., None]
        fill = cv2.blur(rgb * core[..., None], (5, 5)) / np.maximum(cw, 1e-3)
        rgb = np.where((core[..., None] == 0) & (cw > 0), fill, rgb)
        alpha = cv2.GaussianBlur(core.astype(np.float32) * 255, (0, 0), 0.6)
        rgba = np.dstack([np.clip(rgb, 0, 255), alpha])
        self.kettle = Image.fromarray(rgba.astype(np.uint8), 'RGBA')
        self.k_piv_src = (885 - x0, 366 - y0); self.k_at = (885, 366); self.k_spout = (892 - x0, 305 - y0)   # spout mouth
        # fill the hole with plain painted wall copied from further left (keeps the gouache grain)
        # Only needed if the kettle ever moves off its own pixels. With KETTLE_TILT = 0 the plate stays untouched, so the
        # cutout lands on identical pixels: no seam, no ring, and the tent pole behind the lid stays intact.
        if KETTLE_TILT:
            hole = cv2.dilate(full, np.ones((5, 5), np.uint8)).astype(bool); lowh = hole.copy(); hole[366:, :] = False; lowh[:366, :] = False
            ys_, xs_ = np.where(hole); bg[ys_, xs_] = bg[ys_, xs_ - 400]
            bg = cv2.inpaint(bg, lowh.astype(np.uint8), 4, cv2.INPAINT_TELEA)
        self.BG = cv2.resize(bg, (int(round(bg.shape[1] * S)), 1080), interpolation=cv2.INTER_LANCZOS4).astype(np.float32)
        kp = self.kettle.resize((int(self.kettle.width * S * ZT), int(self.kettle.height * S * ZT)), Image.LANCZOS)
        self.kettleZ = kp
        # props
        ku = Image.open(TP + 'props/prop_kulhad.png').convert('RGBA'); bb = alpha_bbox(ku); ku = ku.crop((bb[0], bb[1], bb[2] + 1, bb[3] + 1))
        self.kulhad = ku.resize((int(ku.width * 46 * S * ZT / ku.height), int(46 * S * ZT)), Image.LANCZOS)   # ~46 src px tall
        stm = Image.open(TP + 'props/prop_steam.png').convert('RGBA'); bb = alpha_bbox(stm); self.steam = stm.crop((bb[0], bb[1], bb[2] + 1, bb[3] + 1))
        # cast (world px at z=1; HB = on-screen height at z=1)
        def mk(name, poses, hb, phase):
            prefix = (G + 'girl') if name == 'girl' else (TP + 'poses/' + name)
            im = Image.open(f'{prefix}_{poses[0]}.png').convert('RGBA'); bx = alpha_bbox(im)
            return Cast(prefix, poses, x=0, floor=0, scale=hb * ZT / (bx[3] - bx[1]), phase=phase, sway=0.6, bob=0, pop=0.07, shadow=False)
        FP = ['idle', 'wave', 'excited', 'kulhad', 'hifi', 'laugh']
        self.C = {'meera': mk('meera', FP, 545, 1.1), 'rohan': mk('rohan', FP, 610, 2.3),
                  'girl': mk('girl', ['idle', 'wave', 'sip', 'hifi', 'laugh', 'go'], 560, 0.3), 'kabir': mk('kabir', FP, 600, 3.7)}
        for nm in ('meera', 'rohan', 'kabir'):          # green-screen fringe on the friends' cut-outs: despill + 1 px alpha erode on the edge ring
            c = self.C[nm]
            for k, (im, piv, sc) in list(c.P.items()): c.P[k] = (despill_edge(im), piv, sc)
        # hi-fi registration: Rohan's raised right-side hand meets her raised left-side hand
        # Palm contact points in pose-source px (768x1370 canvas): outer edge of Rohan's raised right palm and of
        # her raised left palm, at mid-palm height. Measured on rohan_hifi.png / girl_hifi.png.
        self.R_PALM, self.G_PALM = (688, 118), (62, 128)
        self.X = {'meera': 255, 'rohan': 505, 'girl': 505 + 300, 'kabir': 505 + 300 + 240}
        self.FLOOR = 1045
        self.pours = []
        tc = t0
        self.TW = tc                                 # wave
        self.TPOUR = vo_at[5] - 0.05                 # cut to the pour close-up on 'Doston ke saath...'
        self.TBACK = vo_at[5] + 1.55                 # back to the group for kulhads + sip
        self.TLAUGH = t_hifi + 0.75
        self._register_hifi()
        ev += [(t0 + 0.05, 'whoosh_air', 0.3), (self.TPOUR + 0.1, 'kulhad_clink', 0.5), (self.TPOUR + 0.35, 'chai_pour', 0.8),
               (self.TBACK + 0.2, 'kulhad_cheers', 0.55), (t_hifi - 0.04, 'hifi_clap_sparkle', 0.95), (t_hifi + 0.1, 'cheer_yay', 0.3),
               (self.TLAUGH + 0.05, 'laugh_group', 0.4)]

    # ---------------------------------------------------------------- helpers
    def cam(self, t):
        if self.TPOUR <= t < self.TBACK:
            k = ease((t - self.TPOUR) / (self.TBACK - self.TPOUR)); z = 2.0 + 0.1 * k; cx, cy = 1265, 470
        else:
            z = 1.0 + 0.035 * ease((t - self.t0) / 7); cx, cy = 905, 545
        L = clamp(cx - W / 2 / z, 0, self.BG.shape[1] - W / z); T = clamp(cy - H / 2 / z, 0, 1080 - H / z)
        if self.th <= t < self.th + 0.35:
            a = 1 - (t - self.th) / 0.35; L += 9 * a * math.sin(t * 90) / z; T += 6 * a * math.cos(t * 77) / z
        return L, T, z

    def steam_puffs(self, fr, sx, sy, scale, t, alpha=1.0, n=2):
        """steam prop rising + swaying from an anchor (screen px), on a loop"""
        h = int(170 * scale); w = int(self.steam.width * h / self.steam.height)
        base = np.array(self.steam.resize((max(2, w), max(2, h)), Image.BILINEAR)).astype(np.float32)
        ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)
        for i in range(n):
            ph = ((t * 0.65) + i / n) % 1.0
            mx = xs + 10 * scale * (1 - ys / h) * np.sin(ys / h * 9 - t * 4 + i * 2)
            im = cv2.remap(base, mx.astype(np.float32), ys, cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0, 0))
            im[..., 3] *= alpha * 0.85 * math.sin(ph * math.pi) ** 1.2
            k = 0.8 + 0.4 * ph
            paste(fr, xform(Image.fromarray(im.astype(np.uint8)), k, k), sx + (i - 0.5) * 12 * scale, sy - h * k / 2 - ph * 60 * scale)

    # ---------------------------------------------------------------- acting
    def act(self, name, t):
        """pose + per-frame acting offsets (dx, rot, dy, squash) for one character"""
        th = self.th
        pose = seq(t, {
            'meera': [(0, 'idle'), (self.t0 + 0.05, 'wave'), (self.t0 + 0.9, 'excited'), (self.TBACK + 0.05, 'kulhad'), (th - 0.1, 'excited'), (self.TLAUGH + 0.1, 'laugh')],
            'rohan': [(0, 'idle'), (self.t0 + 0.15, 'wave'), (self.TBACK + 0.15, 'kulhad'), (th - 0.22, 'hifi'), (self.TLAUGH, 'laugh')],
            'girl': [(0, 'wave'), (self.t0 + 0.55, 'idle'), (self.TBACK, 'sip'), (th - 0.22, 'hifi'), (self.TLAUGH + 0.05, 'laugh')],
            'kabir': [(0, 'idle'), (self.t0 + 0.25, 'wave'), (self.t0 + 1.0, 'excited'), (self.TBACK + 0.25, 'kulhad'), (th - 0.1, 'excited'), (self.TLAUGH + 0.18, 'laugh')],
        }[name])
        cst = self.C[name]; dx = 0; rot = 0; dy = 0; sq = (1, 1)
        if th - 0.22 <= t < th + 0.5 and name in ('rohan', 'girl'):   # anticipation lean -> impact squash
            k = t - (th - 0.22); lean = ease(clamp(k / 0.22)) * (1 - ease(clamp((t - th - 0.15) / 0.35)))
            dx = (14 if name == 'rohan' else -14) * lean; rot = (-2.5 if name == 'rohan' else 2.5) * lean
            if t >= th: sq = squash(t - th, 0.07, 22, 6)
            if name == 'girl': dy = -self.hop * lean                  # she's shorter: hops up onto her toes to meet his palm
        if pose == 'laugh': dy = -6 * abs(math.sin(t * 11 + cst.phase))
        if pose == 'wave': rot += 1.8 * math.sin(t * 12 + cst.phase)
        if pose == 'excited': dy = -8 * abs(math.sin(t * 8 + cst.phase))
        return pose, dx, rot, dy, sq

    def _register_hifi(self):
        """Place her (and Kabir) so the two palms actually touch on the impact frame. Dry-runs the real draw at
        z=1 (world == screen) INCLUDING the lean (+-2.5 deg about the feet, ~50 px at hand height), the cast sway,
        the pose-cut pop and the impact squash, then shifts her by the x residual and sets her hop to the y residual
        (her palm sits ~50 px lower than his: she is shorter). Leaves a few px of palm overlap."""
        dummy = np.zeros((H, W, 3), np.float32); OVERLAP = 8; self.hop = 0.0
        for _ in range(4):
            p = {}
            for name, pt in (('rohan', self.R_PALM), ('girl', self.G_PALM)):
                cst = self.C[name]; cst.last = None
                for tt in (self.th - 0.22, self.th):                 # first draw sets the pose-cut time, as in the render
                    pose, dx, rot, dy, sq = self.act(name, tt)
                    self.draw_cast(dummy, cst, tt, pose, self.X[name] + dx, self.FLOOR, 1 / ZT, rot=rot, dy=dy, sq=sq)
                p[name] = cst.world(pt); cst.last = None
            shift = p['rohan'][0] - OVERLAP - p['girl'][0]
            self.X['girl'] += shift; self.X['kabir'] += shift
            self.hop += p['girl'][1] - p['rohan'][1]                  # vertical: her hop height closes the palm-height gap
        self.hifi_dy = p['girl'][1] - p['rohan'][1]                  # residual (world px), for checks

    # ---------------------------------------------------------------- frame
    def frame(self, t, step):
        L, T, z = self.cam(t)
        M = np.array([[z, 0, -L * z], [0, z, -T * z]], np.float32)
        fr = cv2.warpAffine(self.BG, M, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
        sc = lambda x, y: ((x - L) * z, (y - T) * z)
        # --- kettle: stays still on the stove (tilt 0); chai pours straight out of the spout
        tilt = KETTLE_TILT
        kim = self.kettleZ.resize((max(2, int(self.kettleZ.width * z / ZT)), max(2, int(self.kettleZ.height * z / ZT))), Image.BILINEAR)
        kk = z / ZT * S * ZT
        piv = (self.k_piv_src[0] * kk, self.k_piv_src[1] * kk)
        px, py = sc(self.k_at[0] * S, self.k_at[1] * S)
        place_pivot(fr, kim, px, py, piv, tilt)
        tip = sc((self.k_at[0] - self.k_piv_src[0] + self.k_spout[0]) * S, (self.k_at[1] - self.k_piv_src[1] + self.k_spout[1]) * S)
        # kulhad on the counter (pops in at the start of the close-up)
        cupx, cupy = sc(932 * S, 421 * S)
        if self.TPOUR <= t < self.TBACK:
            kp = back(clamp((t - self.TPOUR) / 0.25))
            cim = self.kulhad.resize((max(2, int(self.kulhad.width * z / ZT * kp)), max(2, int(self.kulhad.height * z / ZT * kp))), Image.BILINEAR)
            paste(fr, cim, cupx, cupy - cim.height / 2)
            mouth = (cupx, cupy - cim.height * 0.9)
            pk = t - self.TPOUR
            if 0.45 < pk < 1.35:                         # chai stream: leaves the spout mouth level, falls in a parabola into the cup
                on = clamp((pk - 0.45) / 0.08) * clamp((1.35 - pk) / 0.1)
                pts = []
                for i in range(20):
                    u = i / 19
                    pts.append((tip[0] + (mouth[0] - tip[0]) * u, tip[1] + (mouth[1] - tip[1]) * u ** 2))
                P = np.array(pts, np.int32); wob = 1 + 0.15 * math.sin(t * 40)
                cv2.polylines(fr, [P], False, (40, 85, 150), max(2, int(7 * z * wob * on)), cv2.LINE_AA)
                cv2.polylines(fr, [P + np.array([-1, 0])], False, (110, 170, 225), max(1, int(2 * z * on)), cv2.LINE_AA)
                rr = random.Random(step)
                for _ in range(4):                       # splash droplets at the cup
                    cv2.circle(fr, (int(mouth[0] + rr.uniform(-18, 18) * z), int(mouth[1] - rr.uniform(0, 14) * z)), max(2, int(2.5 * z)), (60, 110, 170), -1, cv2.LINE_AA)
            # steam curls up from the hot kettle's spout through the close-up
            self.steam_puffs(fr, tip[0], tip[1] + 2 * z, z * 0.45, t, alpha=clamp(pk / 0.4) * clamp((self.TBACK - t) / 0.2))
        # --- characters
        for name in ('meera', 'rohan', 'girl', 'kabir'):
            cst = self.C[name]; pose, dx, rot, dy, sq = self.act(name, t)
            sx, sy = sc(self.X[name] + dx, self.FLOOR)
            self.shadow(fr, sx, sy - 3, 95 * z, 12 * z, 0.3)
            self.draw_cast(fr, cst, t, pose, sx, sy, z / ZT, rot=rot, dy=dy * z, sq=sq, flut=(2.0 * z if name == 'girl' else 0))
            if name == 'girl' and pose == 'sip':
                c = cst.world((350, 335)); self.steam_puffs(fr, c[0], c[1], z * 0.6, t, alpha=clamp((t - self.TBACK) / 0.3))
            if name == 'girl' and pose == 'hifi': self.hand = cst.world(self.G_PALM)
            if name == 'rohan' and pose == 'hifi': self.rhand = cst.world(self.R_PALM)
        # --- hi-fi FX
        th = self.th
        if th <= t < th + 1.2 and hasattr(self, 'hand'):
            hx = (self.hand[0] + self.rhand[0]) / 2; hy = (self.hand[1] + self.rhand[1]) / 2
            k = t - th
            if k < 0.3:
                a = 1 - k / 0.3
                for ang in range(0, 360, 30):
                    r = math.radians(ang + 15); r0, r1 = 45 + 90 * k, 90 + 220 * k
                    cv2.line(fr, (int(hx + r0 * math.cos(r)), int(hy + r0 * math.sin(r))), (int(hx + r1 * math.cos(r)), int(hy + r1 * math.sin(r))),
                             (255, 255, 255), max(2, int(9 * a)), cv2.LINE_AA)
            for i in range(5):
                ang = t * 4.5 + i * 2 * math.pi / 5; rad = 70 + 90 * ease_out(min(1, k / 0.4))
                al = 1 - clamp((k - 0.8) / 0.4)
                if al > 0: star(fr, hx + rad * math.cos(ang), hy - 30 + 0.45 * rad * math.sin(ang), int(20 * al * back(min(1, k / 0.25))) + 1,
                                ((80, 210, 250), (120, 180, 255), (230, 230, 120))[i % 3])
        if th <= t < th + 2 / 24: fr[:] = fr * 0.35 + 255 * 0.65         # white flash frames
        return fr
