"""Multi-angle contact sheet for the Clawd model.

    blender --background --python angles.py

Reuses mascot.py's scene (imported, so its own render is skipped) and orbits
the camera. Two purposes:

1. Proof the model is real 3D geometry rather than a front-facing cheat.
2. Diagnostic. Every reference for Clawd is front-facing, so width and height
   are measured but DEPTH IS INVENTED -- the side and back views are the only
   place that guess becomes visible. Judge those angles as authored, not
   accurate.

One Blender launch builds the scene once and renders every view, which is far
cheaper than N launches. Res and samples are dropped since these are for
reading silhouettes, not for presentation.
"""

import os
import sys
from math import radians, sin, cos

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bpy                                    # noqa: E402
from mathutils import Vector                  # noqa: E402

import mascot                                 # noqa: E402  (builds the scene)

OUTDIR = os.environ.get(
    "CLAWD_ANGLES_OUT",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "out", "angles"))
os.makedirs(OUTDIR, exist_ok=True)

scene = bpy.context.scene
scene.render.resolution_x = 640
scene.render.resolution_y = 640
scene.cycles.samples = 128
scene.cycles.adaptive_threshold = 0.015

cam = mascot.cam
LOOK = mascot.LOOK

#         name          azimuth  elevation  distance
VIEWS = [("1_front",        0.0,       6.0,     10.2),
         ("2_three_quarter", 40.0,     12.0,     10.2),
         ("3_side",         90.0,       8.0,     10.2),
         ("4_back",        180.0,       8.0,     10.2),
         ("5_top_down",     25.0,      58.0,     10.2)]

for name, az_deg, el_deg, dist in VIEWS:
    az, el = radians(az_deg), radians(el_deg)
    horiz = dist * cos(el)
    cam.location = (horiz * sin(az),
                    -horiz * cos(az),
                    LOOK[2] + dist * sin(el))
    cam.rotation_euler = (Vector(LOOK) - cam.location).to_track_quat(
        "-Z", "Y").to_euler()

    # The backdrop plane sits at y=+9. Past ~110 degrees of azimuth the camera
    # ends up behind it and it occludes the subject entirely (the first run of
    # this script rendered a solid black "back" view for exactly this reason).
    mascot.backdrop.hide_render = abs(az_deg) > 110.0

    scene.render.filepath = os.path.join(OUTDIR, f"{name}.png")
    print(f"[angles] {name}: az={az_deg} el={el_deg}", flush=True)
    bpy.ops.render.render(write_still=True)

print("[angles] done", flush=True)
