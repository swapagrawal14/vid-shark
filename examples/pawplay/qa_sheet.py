"""Contact sheet of cut-outs over the scene blue + QA numbers (alpha coverage, green fringe)."""
import sys, glob, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '../../engine'))
from PIL import Image, ImageDraw, ImageFont
from posepack import alpha_coverage, green_fringe
BLUE = (169, 195, 214)
def sheet(files, out, cell=360, cols=6):
    rows = (len(files) + cols - 1) // cols
    S = Image.new('RGB', (cols * cell, rows * (cell + 30)), BLUE); d = ImageDraw.Draw(S)
    for i, f in enumerate(files):
        im = Image.open(f).convert('RGBA'); im.thumbnail((cell - 10, cell - 10))
        x, y = (i % cols) * cell, (i // cols) * (cell + 30)
        S.paste(im, (x + (cell - im.width) // 2, y + (cell - im.height) // 2), im)
        full = Image.open(f)
        d.text((x + 6, y + cell + 4), f'{os.path.basename(f)[:-4]} cov={alpha_coverage(full):.2f} fr={green_fringe(full):.2f}', fill=(0, 0, 0))
    S.save(out); print(out, S.size)
if __name__ == '__main__':
    sheet(sorted(f for a in sys.argv[2:] for f in glob.glob(a)), sys.argv[1])
