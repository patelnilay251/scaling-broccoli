"""Pack each action's frames into a horizontal sprite strip.

    python3 spritesheet.py

Writes:
    sprites/<action>.png     one horizontal strip per action
    sprites/manifest.json    frame count / size / duration per action

Plain CPython with Pillow, no Blender.

A strip is how these get consumed by a status-line pet, a game engine, or
anything that steps an offset: one file per action, one decode, no container
format in the way. All eight total ~2.6MB at 160px cells, against 19MB for the
equivalent GIFs.

The frames carry an opaque background, not alpha, and it is not even one flat
colour -- a grey sky region (~213) sits above a cream floor (~240). So no
single backdrop colour will hide the cell edges; sampling a corner pixel and
hoping was tried and does not work.

Genuinely transparent sprites need a second render pass with
`film_transparent` and the floor hidden. Note the tradeoff before reaching for
it: EEVEE has no shadow catcher (that is Cycles-only), so alpha sprites lose
the ground shadow entirely rather than keeping it over transparency.
"""

import json
import os

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
FRAMEROOT = os.path.join(HERE, "out")
SPRITEDIR = os.path.join(HERE, "sprites")
CELL = int(os.environ.get("CLAWD_CELL", "160"))     # px per frame in the strip
FPS = 24.0

ACTIONS = ["idle", "walk", "jump", "wave", "look", "dance", "sleep",
           "turntable"]

os.makedirs(SPRITEDIR, exist_ok=True)

manifest = {"cell": CELL, "fps": FPS, "actions": {}}
page_bg = None

for action in ACTIONS:
    framedir = os.path.join(FRAMEROOT, action)
    if not os.path.isdir(framedir):
        print(f"  skip {action}: no frames at {framedir}")
        continue
    names = sorted(f for f in os.listdir(framedir) if f.endswith(".png"))
    if not names:
        print(f"  skip {action}: empty")
        continue

    frames = [Image.open(os.path.join(framedir, n)).convert("RGB")
              .resize((CELL, CELL), Image.LANCZOS) for n in names]

    if page_bg is None:                            # sample once, from a corner
        page_bg = "#%02x%02x%02x" % frames[0].getpixel((2, 2))

    sheet = Image.new("RGB", (CELL * len(frames), CELL))
    for i, frame in enumerate(frames):
        sheet.paste(frame, (i * CELL, 0))

    path = os.path.join(SPRITEDIR, f"{action}.png")
    sheet.save(path, optimize=True)
    manifest["actions"][action] = {
        "frames": len(frames),
        "width": sheet.width,
        "duration_ms": int(round(1000.0 * len(frames) / FPS)),
    }
    print(f"  {action}: {len(frames)} frames, {sheet.width}x{CELL}, "
          f"{os.path.getsize(path) / 1024.0:.0f} KB")

manifest["page_bg"] = page_bg
with open(os.path.join(SPRITEDIR, "manifest.json"), "w") as fh:
    json.dump(manifest, fh, indent=2)
