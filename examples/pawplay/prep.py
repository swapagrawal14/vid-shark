"""Clean the generated cut-outs once -> assets/clean/*.png (QA gate B):
despill the chroma-green edge ring, strip the white sticker border the tail came back with,
slice notes.png into one PNG per note. Run after generating assets (see README)."""
import glob, os, sys
import numpy as np, cv2
from PIL import Image
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '../../engine'))
from posepack import despill_edge, green_fringe, alpha_coverage

A = 'assets'; C = os.path.join(A, 'clean'); os.makedirs(C, exist_ok=True)

def strip_white_border(im):
    a = np.array(im.convert('RGBA')); al = a[..., 3]
    light = (a[..., :3].min(-1) > 205) & (al > 0)
    outside = (al < 20).astype(np.uint8)
    # light pixels connected to the transparent outside = sticker border
    reg = (light | outside.astype(bool)).astype(np.uint8)
    n, lab = cv2.connectedComponents(reg)
    outs = set(np.unique(lab[outside.astype(bool)])) - {0}
    border = np.isin(lab, list(outs)) & light
    a[..., 3][border] = 0
    return Image.fromarray(a, 'RGBA')

for f in sorted(glob.glob(f'{A}/*.png')):
    n = os.path.basename(f)
    if n.startswith('frog_src_') or n == 'notes.png': continue
    im = Image.open(f).convert('RGBA')
    if n == 'cat_tail.png': im = strip_white_border(im)
    if not n.startswith('frog_'): im = despill_edge(im)
    bb = im.getbbox(); im = im.crop((0, 0, im.width, im.height))   # keep canvas (registration)
    im.save(f'{C}/{n}')
    print(f'{n:22s} cov={alpha_coverage(im):.2f} fringe={green_fringe(im):.3f}')

# notes -> note0..2 (connected blobs, left to right)
im = despill_edge(Image.open(f'{A}/notes.png').convert('RGBA')); a = np.array(im)
m = (a[..., 3] > 20).astype(np.uint8); m = cv2.dilate(m, np.ones((15, 15), np.uint8))
n, lab, st, _ = cv2.connectedComponentsWithStats(m)
blobs = sorted([st[i] for i in range(1, n) if st[i][4] > 2000], key=lambda s: s[0])
for i, (x, y, w, h, _) in enumerate(blobs[:3]):
    Image.fromarray(a[y:y + h, x:x + w]).save(f'{C}/note{i}.png'); print('note', i, w, h)
