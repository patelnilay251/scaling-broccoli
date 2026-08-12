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
import stage                                  # noqa: E402  (restages it)

OUTDIR = os.environ.get(
    "CLAWD_ANGLES_OUT",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "out", "angles"))
os.makedirs(OUTDIR, exist_ok=True)

stage.light_studio()

scene = bpy.context.scene
scene.render.engine = "BLENDER_EEVEE"     # EEVEE: no grain, seconds per view
scene.eevee.taa_render_samples = 32       # stills, so spend the extra samples
scene.eevee.use_ssr = False
scene.render.resolution_x = 640
scene.render.resolution_y = 640

cam = mascot.cam
LOOK = mascot.LOOK

#         name              azimuth  elevation  distance
VIEWS = [("1_front",            0.0,       6.0,     10.2),
         ("2_three_quarter",   35.0,      10.0,     10.2),
         ("3_side",            90.0,       8.0,     10.2),
         ("4_rear_quarter",   140.0,      10.0,     10.2),
         ("5_back",           180.0,       8.0,     10.2),
         ("6_low_hero",        22.0,      -4.0,      9.6),
         ("7_high_three_q",   -38.0,      34.0,     10.6),
         ("8_top_down",        25.0,      62.0,     10.2)]

for name, az_deg, el_deg, dist in VIEWS:
    az, el = radians(az_deg), radians(el_deg)
    horiz = dist * cos(el)
    cam.location = (horiz * sin(az),
                    -horiz * cos(az),
                    LOOK[2] + dist * sin(el))
    cam.rotation_euler = (Vector(LOOK) - cam.location).to_track_quat(
        "-Z", "Y").to_euler()

    # No backdrop toggle here any more. stage.light_studio() hides the plane
    # outright, and re-enabling it per view is what made front views render a
    # near-black background: the un-hidden plane still wore mascot.py's dark
    # material. The world is the background in every view now.

    scene.render.filepath = os.path.join(OUTDIR, f"{name}.png")
    print(f"[angles] {name}: az={az_deg} el={el_deg}", flush=True)
    bpy.ops.render.render(write_still=True)

print("[angles] done", flush=True)
