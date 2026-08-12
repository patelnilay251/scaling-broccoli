"""Idle-loop animation for Clawd: a slow breathing bob, arm follow-through,
and a couple of blinks. Renders a seamless 48-frame loop.

    blender --background --python animate.py

Frames land in out/idle/f000.png ... and are assembled into a GIF by
make_gif.py afterwards (Blender's PNG output is the expensive part; muxing
is free, so the two steps are separate).

Why EEVEE and not Cycles
------------------------
Measured on this 4-core, GPU-less box at 480x480: EEVEE ~18s/frame, Cycles
~21-25s/frame. Comparable. The reason to pick EEVEE is not speed, it is that
EEVEE is rasterised and therefore has NO Monte Carlo noise. Cycles' grain is
different on every frame, so it crawls during playback -- normally fixed with
a denoiser, which this Blender build does not have (see README). EEVEE is
temporally stable by construction.

EEVEE needs a GL context, which a headless box lacks. It works here only
because libEGL is installed and Blender falls back to surfaceless EGL; expect
`EGL_NOT_INITIALIZED` followed by "Managed to successfully fallback to
surfaceless EGL rendering!" on stderr. Those lines are normal, not failures.
Requires: apt-get install -y libegl1 libgl1-mesa-dri libglx-mesa0 libgbm1

Motion is computed per frame in Python and rendered immediately, rather than
laid down as keyframes. Procedural sine motion is periodic by definition, so
the loop closes seamlessly with no F-curve interpolation to fight.
"""

import os
import sys
import math
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bpy                                     # noqa: E402
import mascot                                  # noqa: E402  builds the scene

OUTDIR = os.environ.get(
    "CLAWD_ANIM_OUT",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "out", "idle"))
os.makedirs(OUTDIR, exist_ok=True)

FRAMES = int(os.environ.get("CLAWD_FRAMES", "48"))   # 48 @ 24fps = 2s loop
RES = int(os.environ.get("CLAWD_ANIM_RES", "512"))

BOB = 0.05          # metres of vertical travel; leg tops are buried 0.14
                    # into the body, so this cannot open a gap at the hips
ARM_LAG = 0.65      # radians of phase lag -> classic follow-through
BLINK_AT = (0.28, 0.72)

scene = bpy.context.scene
scene.render.engine = "BLENDER_EEVEE"           # 4.0 id; EEVEE Next is 4.2+
scene.eevee.taa_render_samples = 32             # AA only -- no light noise
scene.eevee.use_gtao = True                     # ambient occlusion
scene.eevee.use_ssr = True                      # the floor needs reflections
scene.render.resolution_x = RES
scene.render.resolution_y = RES
scene.render.image_settings.file_format = "PNG"

body = bpy.data.objects["Body"]
arms = [bpy.data.objects["ArmL"], bpy.data.objects["ArmR"]]
eyes = [bpy.data.objects["EyeL"], bpy.data.objects["EyeR"]]

# Legs deliberately excluded: they stay planted while the body breathes.
bobbing = [body] + arms + eyes
rest_z = {obj.name: obj.location.z for obj in bobbing}
rest_eye_sz = {obj.name: obj.scale.z for obj in eyes}


def blink_scale(phase):
    """1.0 fully open, ~0.1 shut. Wrapped distance keeps the loop seamless."""
    for centre in BLINK_AT:
        dist = abs(((phase - centre + 0.5) % 1.0) - 0.5)
        if dist < 0.022:
            return 0.10
        if dist < 0.042:
            return 0.55
    return 1.0


print(f"[anim] engine={scene.render.engine} frames={FRAMES} res={RES} "
      f"samples={scene.eevee.taa_render_samples}", flush=True)

started = time.time()
for frame in range(FRAMES):
    phase = frame / FRAMES
    angle = 2.0 * math.pi * phase

    body_bob = BOB * math.sin(angle)
    arm_bob = BOB * math.sin(angle - ARM_LAG)

    body.location.z = rest_z[body.name] + body_bob
    for obj in eyes:
        obj.location.z = rest_z[obj.name] + body_bob
    for obj in arms:
        obj.location.z = rest_z[obj.name] + arm_bob

    shut = blink_scale(phase)
    for obj in eyes:
        obj.scale.z = rest_eye_sz[obj.name] * shut

    scene.render.filepath = os.path.join(OUTDIR, f"f{frame:03d}.png")
    bpy.ops.render.render(write_still=True)

    if frame % 8 == 0 or frame == FRAMES - 1:
        per = (time.time() - started) / (frame + 1)
        print(f"[anim] frame {frame + 1}/{FRAMES}  {per:.1f}s/frame  "
              f"eta {per * (FRAMES - frame - 1) / 60.0:.1f}min", flush=True)

print(f"[anim] done in {(time.time() - started) / 60.0:.1f}min -> {OUTDIR}",
      flush=True)
