"""Walk cycle for Clawd: a four-leg wave gait, rendered as a seamless loop.

    blender --background --python walk.py

Frames land in out/walk/f000.png ...; assemble with:

    CLAWD_ANIM_OUT=out/walk CLAWD_GIF_BASE=walk python3 make_gif.py

Gait
----
Clawd's four legs sit in a single row (see README -- that comes from the
source sprite, not from anatomy). A sequential WAVE gait suits that: each leg
is offset a quarter cycle from its neighbour, so a ripple travels along the
row. It reads as crustacean rather than quadruped, which is the right instinct
for something whose official emoji is a crab.

Walking happens in place -- a treadmill. Translating the body would carry it
out of frame within a couple of seconds and break the loop.

Every motion function is periodic and continuous at the cycle boundary, so
frame 48 equals frame 0 and the loop closes with no seam. That is checked
numerically at import time by _assert_loops() rather than assumed.
"""

import os
import sys
import math
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bpy                                     # noqa: E402
import mascot                                  # noqa: E402  builds the scene

OUTDIR = os.environ.get(
    "CLAWD_WALK_OUT",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "out", "walk"))
os.makedirs(OUTDIR, exist_ok=True)

FRAMES = int(os.environ.get("CLAWD_FRAMES", "48"))
RES = int(os.environ.get("CLAWD_ANIM_RES", "512"))

DUTY = 0.40         # fraction of a leg's cycle spent in the air
LIFT = 0.17         # how high a foot rises
SWING = 0.11        # fore/aft travel, in -Y (towards camera) = forwards
BODY_BOB = 0.035    # two bobs per loop, from the gait
BODY_SWAY = 0.022   # one lateral sway per loop
ARM_LAG = 0.7       # radians; follow-through on the claws
BLINK_AT = (0.35,)


def leg_lift(phase):
    """0 while planted, a smooth arc while swinging. Continuous at 0 and 1."""
    if phase < DUTY:
        return LIFT * math.sin(math.pi * phase / DUTY)
    return 0.0


def leg_swing(phase):
    """Forward during the swing, then a linear sweep back during stance."""
    if phase < DUTY:
        return SWING * -math.cos(math.pi * phase / DUTY)      # back -> front
    return SWING * (1.0 - 2.0 * (phase - DUTY) / (1.0 - DUTY))  # front -> back


def blink_scale(phase):
    for centre in BLINK_AT:
        dist = abs(((phase - centre + 0.5) % 1.0) - 0.5)
        if dist < 0.022:
            return 0.10
        if dist < 0.042:
            return 0.55
    return 1.0


def _assert_loops():
    """The seam is the one thing that is invisible per-frame and obvious in
    playback, so verify continuity instead of trusting the algebra."""
    for fn in (leg_lift, leg_swing):
        start, end = fn(0.0), fn(0.9999)
        assert abs(start - end) < 1e-3, f"{fn.__name__} discontinuous: {start} vs {end}"


_assert_loops()

scene = bpy.context.scene
scene.render.engine = "BLENDER_EEVEE"
scene.eevee.taa_render_samples = 32
scene.eevee.use_gtao = True
scene.eevee.use_ssr = True
scene.render.resolution_x = RES
scene.render.resolution_y = RES
scene.render.image_settings.file_format = "PNG"

body = bpy.data.objects["Body"]
arms = [bpy.data.objects["ArmL"], bpy.data.objects["ArmR"]]
eyes = [bpy.data.objects["EyeL"], bpy.data.objects["EyeR"]]
legs = [bpy.data.objects[f"Leg{i}"] for i in range(4)]

rest = {obj.name: obj.location.copy()
        for obj in [body] + arms + eyes + legs}
rest_eye_sz = {obj.name: obj.scale.z for obj in eyes}

print(f"[walk] engine={scene.render.engine} frames={FRAMES} res={RES} "
      f"gait=wave duty={DUTY}", flush=True)

started = time.time()
for frame in range(FRAMES):
    phase = frame / FRAMES

    # legs: a quarter-cycle offset each, so the wave travels along the row
    for i, leg in enumerate(legs):
        leg_phase = (phase + i * 0.25) % 1.0
        leg.location.z = rest[leg.name].z + leg_lift(leg_phase)
        leg.location.y = rest[leg.name].y - leg_swing(leg_phase)

    # body: two bobs per loop (one per leg pair), one lateral sway
    bob = BODY_BOB * math.sin(4.0 * math.pi * phase)
    sway = BODY_SWAY * math.sin(2.0 * math.pi * phase)
    arm_bob = BODY_BOB * math.sin(4.0 * math.pi * phase - ARM_LAG)

    body.location.z = rest[body.name].z + bob
    body.location.x = rest[body.name].x + sway
    for obj in eyes:
        obj.location.z = rest[obj.name].z + bob
        obj.location.x = rest[obj.name].x + sway
    for obj in arms:
        obj.location.z = rest[obj.name].z + arm_bob
        obj.location.x = rest[obj.name].x + sway

    shut = blink_scale(phase)
    for obj in eyes:
        obj.scale.z = rest_eye_sz[obj.name] * shut

    scene.render.filepath = os.path.join(OUTDIR, f"f{frame:03d}.png")
    bpy.ops.render.render(write_still=True)

    if frame % 8 == 0 or frame == FRAMES - 1:
        per = (time.time() - started) / (frame + 1)
        print(f"[walk] frame {frame + 1}/{FRAMES}  {per:.1f}s/frame  "
              f"eta {per * (FRAMES - frame - 1) / 60.0:.1f}min", flush=True)

print(f"[walk] done in {(time.time() - started) / 60.0:.1f}min -> {OUTDIR}",
      flush=True)
