"""Slice an AI-generated sprite sheet (one row of N frames, e.g. a walk/run cycle) into
registered frames: same canvas, feet on one baseline, torso centred, so the cycle doesn't jitter.

    from sheets import slice_sheet
    walk = slice_sheet('bablu_walk_sheet.png', n=6)      # list of RGBA PIL images

Prompt tip that works: pass a blank WIDE canvas (e.g. 2400x700 green) as the FIRST reference
image so the model draws a wide sheet, the character's key pose as the SECOND reference, and ask
for 'exactly N frames in one horizontal row, evenly spaced, same size, feet on one baseline,
strict side view facing RIGHT, solid #00FF00 background, no ground line'.
"""
import numpy as np
from PIL import Image


def _clean_ground_lines(a, frac=0.3):
    """remove floor lines the model sometimes draws: rows holding one unbroken run of
    alpha longer than frac of the width (characters in a sheet are separated by gaps)"""
    m = a > 40; W = m.shape[1]
    for y in range(m.shape[0]):
        r = m[y]
        if r.sum() < frac * W: continue
        d = np.diff(np.concatenate([[0], r.astype(np.int8), [0]]))
        st, en = np.where(d == 1)[0], np.where(d == -1)[0]
        if (en - st).max() > frac * W: a[y] = 0
    return a


def slice_sheet(path, n, thr=40, pad=20):
    """n = number of frames in the row. Every connected blob of ink is assigned to the
    frame cell its centre falls in, so arms/feet crossing a cell edge stay with their body."""
    import cv2
    im = Image.open(path).convert('RGBA'); arr = np.array(im)
    arr[..., 3] = _clean_ground_lines(arr[..., 3].copy())
    m = (arr[..., 3] > thr).astype(np.uint8)
    cnt, lab, stats, cents = cv2.connectedComponentsWithStats(m, 8)
    xs_all = np.where(m.any(axis=0))[0]; X0, X1 = xs_all.min(), xs_all.max() + 1
    cell = (X1 - X0) / n
    owner = np.zeros(cnt, int) - 1
    for k in range(1, cnt):
        if stats[k, cv2.CC_STAT_AREA] < 30: continue
        owner[k] = min(n - 1, int((cents[k][0] - X0) // cell))
    raw = []
    for c in range(n):
        keep = np.isin(lab, np.where(owner == c)[0])
        sub = arr.copy(); sub[..., 3] = np.where(keep, sub[..., 3], 0)
        ys, xs = np.where(sub[..., 3] > thr)
        raw.append(sub[ys.min():ys.max() + 1, xs.min():xs.max() + 1])
    frames = []
    for sub in raw:
        a = sub[..., 3] > thr; h = a.shape[0]
        top = a[: int(h * 0.55)]; xs = np.where(top)[1]
        cx = xs.mean() if len(xs) else a.shape[1] / 2      # torso/head centre = registration x
        frames.append((sub, cx))
    Hm = max(f[0].shape[0] for f in frames)
    half = int(max(max(cx, f.shape[1] - cx) for f, cx in frames)) + pad
    out = []
    for sub, cx in frames:
        c = np.zeros((Hm + pad, half * 2, 4), np.uint8)
        h, w = sub.shape[:2]; ox = int(round(half - cx)); oy = Hm + pad - h
        c[oy:oy + h, ox:ox + w] = sub
        out.append(Image.fromarray(c))
    return out
