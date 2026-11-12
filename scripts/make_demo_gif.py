"""Assemble PNG frames into the README demo GIF (Pillow only)."""
import sys
from pathlib import Path
from PIL import Image

frames_dir, out = Path(sys.argv[1]), Path(sys.argv[2])
imgs = [Image.open(p).convert("RGB") for p in sorted(frames_dir.glob("*.png"))]
w = 960
imgs = [i.resize((w, round(i.height * w / i.width)), Image.LANCZOS) for i in imgs]
pal = [i.quantize(colors=128, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE) for i in imgs]
pal[0].save(out, save_all=True, append_images=pal[1:], duration=450, loop=0, optimize=True)
print(out, round(out.stat().st_size / 1e6, 2), "MB", len(imgs), "frames")
