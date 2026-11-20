"""Key a flat magenta (#FF00FF) background out of a generated image -> RGBA cut-out.
Used for the frog: its green is too close to #00FF00 for a chroma-green key."""
import sys, numpy as np, cv2
from PIL import Image

def key_magenta(src, dst):
    a = np.array(Image.open(src).convert('RGB')).astype(np.int16)
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    # magenta-ness: R and B high, G low
    m = np.minimum(r, b) - g
    bg = (m > 90).astype(np.uint8)
    # keep only background connected to the border (protects interior pinks/reds)
    bgc = bg.astype(bool)   # frog has no pink/magenta, so key every magenta pixel (incl. enclosed pockets)
    alpha = np.where(bgc, 0, 255).astype(np.uint8)
    # soft edge: partial alpha where magenta-ish on the boundary, then despill
    soft = np.clip(255 - (m.clip(0, 255) - 30) * 255 / 60, 0, 255).astype(np.uint8)
    ring = cv2.dilate(bgc.astype(np.uint8), np.ones((5, 5), np.uint8)).astype(bool) & ~bgc
    alpha[ring] = np.minimum(alpha[ring], soft[ring])
    out = a.copy()
    lim = np.maximum(g, 0)
    out[..., 0] = np.where(ring, np.minimum(r, np.maximum(g, b * 0 + g) + 40), r)
    out[..., 2] = np.where(ring, np.minimum(b, g + 40), b)
    rgba = np.dstack([out.clip(0, 255).astype(np.uint8), cv2.erode(alpha, np.ones((3, 3), np.uint8))])
    Image.fromarray(rgba, 'RGBA').save(dst)

if __name__ == '__main__':
    for s in sys.argv[1:]: key_magenta(s, s.replace('_src_', '_'))
