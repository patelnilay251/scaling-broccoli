"""Mux a rendered PNG sequence into an MP4 and an animated WebP.

    python3 encode.py                    # out/sequence -> sequence.mp4/.webp
    CLAWD_SEQ_OUT=out/walk python3 encode.py

Two outputs because they serve different jobs:

* MP4 (H.264) -- the portable video. Encoded by BLENDER, because the only
  ffmpeg on this box is Playwright's, which ships libvpx and no libx264, so it
  can produce WebM but not H.264. Blender's bundled ffmpeg does have H264, so
  the mux runs through Blender's sequencer rather than a shell pipe.
* Animated WebP -- previews inline in far more places than a video file, at a
  tenth the size of the equivalent GIF and with full colour rather than 256.

A ~390-frame GIF is deliberately not produced: at 512px it would run past
15MB, which is not a sensible thing to commit.
"""

import glob
import os
import subprocess
import sys

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
FRAMEDIR = os.environ.get("CLAWD_SEQ_OUT", os.path.join(HERE, "out", "sequence"))
BASE = os.environ.get("CLAWD_SEQ_BASE", os.path.basename(FRAMEDIR.rstrip("/")))
FPS = int(os.environ.get("CLAWD_FPS", "24"))

frames = sorted(glob.glob(os.path.join(FRAMEDIR, "*.png")))
if not frames:
    sys.exit(f"no frames in {FRAMEDIR} -- run sequence.py first")

mp4_path = os.path.join(HERE, f"{BASE}.mp4")
webp_path = os.path.join(HERE, f"{BASE}.webp")

# --------------------------------------------------------------------------
# MP4, via Blender's sequencer (its ffmpeg has H264; Playwright's does not)
# --------------------------------------------------------------------------
MUX = r"""
import bpy, os, sys
framedir, out, fps = sys.argv[-3], sys.argv[-2], int(sys.argv[-1])
names = sorted(f for f in os.listdir(framedir) if f.endswith(".png"))

scene = bpy.context.scene
scene.sequence_editor_create()
strip = scene.sequence_editor.sequences.new_image(
    "seq", os.path.join(framedir, names[0]), channel=1, frame_start=1)
for n in names[1:]:
    strip.elements.append(n)

first = bpy.data.images.load(os.path.join(framedir, names[0]))
scene.render.resolution_x, scene.render.resolution_y = first.size
scene.render.resolution_percentage = 100
scene.frame_start, scene.frame_end = 1, len(names)
scene.render.fps = fps

scene.render.image_settings.file_format = "FFMPEG"
scene.render.ffmpeg.format = "MPEG4"
scene.render.ffmpeg.codec = "H264"
scene.render.ffmpeg.constant_rate_factor = "HIGH"
scene.render.ffmpeg.ffmpeg_preset = "GOOD"
scene.render.ffmpeg.gopsize = 12
scene.render.filepath = out
bpy.ops.render.render(animation=True)
print("MUXED", out)
"""

script = os.path.join(HERE, ".mux_tmp.py")
with open(script, "w") as fh:
    fh.write(MUX)
try:
    proc = subprocess.run(
        ["blender", "--background", "--python", script, "--",
         FRAMEDIR, mp4_path, str(FPS)],
        capture_output=True, text=True, timeout=900)
    if "MUXED" not in proc.stdout:
        print("MP4 mux failed:\n" + proc.stdout[-1500:] + proc.stderr[-800:])
finally:
    os.remove(script)

# Blender appends a frame range to the filename; normalise it back.
if not os.path.exists(mp4_path):
    for cand in glob.glob(os.path.join(HERE, f"{BASE}*.mp4")):
        os.rename(cand, mp4_path)
        break

# --------------------------------------------------------------------------
# animated WebP
# --------------------------------------------------------------------------
images = [Image.open(f).convert("RGB") for f in frames]
images[0].save(webp_path, save_all=True, append_images=images[1:],
               duration=int(round(1000.0 / FPS)), loop=0, quality=86,
               method=4)

for path in (mp4_path, webp_path):
    if os.path.exists(path):
        print(f"{os.path.basename(path)}: {len(frames)} frames, "
              f"{images[0].size[0]}x{images[0].size[1]}, {FPS}fps, "
              f"{os.path.getsize(path) / 1024.0:.0f} KB")
    else:
        print(f"{os.path.basename(path)}: NOT PRODUCED")
