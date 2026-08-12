"""Assemble the rendered idle frames into a looping GIF (and WebP).

    python3 make_gif.py

Plain CPython, not Blender -- needs Pillow (`pip install pillow`). Kept
separate from animate.py because the frames are the expensive part and muxing
is nearly free; re-running this to retime or recolour costs seconds.

GIF is capped at 256 colours, so smooth terracotta gradients band a little.
An animated WebP is written alongside at full colour depth for when that
matters; GIF is kept because it previews inline nearly everywhere.
"""

import os
import sys

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
FRAMEDIR = os.environ.get("CLAWD_ANIM_OUT", os.path.join(HERE, "out", "idle"))
FPS = float(os.environ.get("CLAWD_FPS", "24"))

frames = sorted(f for f in os.listdir(FRAMEDIR) if f.endswith(".png"))
if not frames:
    sys.exit(f"no frames in {FRAMEDIR} -- run animate.py first")

images = [Image.open(os.path.join(FRAMEDIR, f)).convert("RGB") for f in frames]
duration = int(round(1000.0 / FPS))

gif_path = os.path.join(HERE, "idle.gif")

# One SHARED palette for every frame. Quantising each frame independently
# shifts colours slightly frame to frame, which defeats GIF's inter-frame
# delta compression and bloats the file (~4.7MB for 48 frames when I did it
# that way). Likewise `disposal=2` forces a full redraw per frame -- leaving
# it at the default lets unchanged background pixels be skipped entirely.
palette_src = Image.new("RGB", (len(images) * 8, images[0].size[1]))
for i, im in enumerate(images):                 # sample every frame's colours
    palette_src.paste(im.resize((8, im.size[1])), (i * 8, 0))
palette = palette_src.quantize(colors=128, method=Image.MEDIANCUT)

quantised = [im.quantize(palette=palette, dither=Image.FLOYDSTEINBERG)
             for im in images]
quantised[0].save(
    gif_path,
    save_all=True,
    append_images=quantised[1:],
    duration=duration,
    loop=0,
    optimize=True,
)

webp_path = os.path.join(HERE, "idle.webp")
images[0].save(webp_path, save_all=True, append_images=images[1:],
               duration=duration, loop=0, quality=88, method=4)

for path in (gif_path, webp_path):
    print(f"{os.path.basename(path)}: {len(images)} frames, "
          f"{images[0].size[0]}x{images[0].size[1]}, "
          f"{duration}ms/frame ({FPS:g}fps), "
          f"{os.path.getsize(path) / 1024.0:.0f} KB")
