"""Walk cycle for Clawd: a four-leg wave gait, rendered as a seamless loop.

    blender --background --python walk.py

Frames land in out/walk/f000.png ...; assemble with:

    CLAWD_ANIM_OUT=out/walk CLAWD_GIF_BASE=walk python3 make_gif.py

Gait
----
Clawd's four legs sit in a single row (see README -- that comes from the source
sprite, not from anatomy). A sequential WAVE gait suits that: each leg is
offset a quarter cycle from its neighbour, so a ripple travels along the row.
It reads as crustacean rather than quadruped, which is the right instinct for
something whose official emoji is a crab.

Walking happens in place -- a treadmill. Translating the body would carry it
out of frame within a couple of seconds and break the loop.

Four things make the step actually legible, all learned from the first
version looking wrong:

1. TALLER STANCE. The body is raised and the legs lengthened at runtime, so
   there is ~0.94 of visible leg instead of 0.62. Lifting a foot always
   shortens the visible leg by the lift amount, so the taller the stance, the
   less that reads as "leg retracting into body".
2. LIGHT STAGE. On the original near-black floor, the gap under a raised foot
   was dark-on-dark and invisible. On a light floor it reads instantly. This
   mattered more than any animation change.
3. THREE-QUARTER CAMERA. A walk reads best from the side, but from the side
   all four legs overlap into one silhouette (the legs share a depth). 32
   degrees of azimuth shows the wave travelling along the row AND the fore/aft
   swing at the same time.
4. BIGGER AMPLITUDES. Lift, swing and lateral sway are all roughly doubled;
   the first pass was too timid to read at 512 pixels.

Every motion function is periodic and continuous at the cycle boundary, so
frame 48 equals frame 0 and the loop closes with no seam. That is checked
numerically by _assert_loops() rather than assumed.
"""

import os
import sys
import math
import time
from math import radians, sin, cos

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bpy                                     # noqa: E402
from mathutils import Vector                   # noqa: E402

import mascot                                  # noqa: E402  builds the scene
import stage                                   # noqa: E402  restages it

OUTDIR = os.environ.get(
    "CLAWD_WALK_OUT",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "out", "walk"))
os.makedirs(OUTDIR, exist_ok=True)

FRAMES = int(os.environ.get("CLAWD_FRAMES", "48"))
RES = int(os.environ.get("CLAWD_ANIM_RES", "512"))

DUTY = 0.42         # fraction of a leg's cycle spent in the air
LIFT = 0.20         # foot rise
SWING = 0.15        # fore/aft travel in Y (-Y is towards camera)
# STAND was 0.32 at one point, which gave plenty of visible leg for the lift
# to read against -- and made Clawd spindly. Stubby legs are on-brand, so the
# stance stays low and the WADDLE carries the walk instead.
STAND = 0.14
BODY_BOB = 0.05     # two bobs per loop, one per leg pair
BODY_SWAY = 0.075   # lateral waddle -- the primary motion for a stubby walk
ARM_LAG = 0.7       # radians of follow-through on the claws
BLINK_AT = (0.34,)

# three-quarter view: shows the leg wave and the fore/aft swing together
CAM_AZ, CAM_EL, CAM_DIST = radians(32.0), radians(8.0), 9.8
LOOK = (0.0, 0.0, 1.40)


def leg_lift(phase):
    """0 while planted, a smooth arc while swinging. Continuous at 0 and 1."""
    if phase < DUTY:
        return LIFT * math.sin(math.pi * phase / DUTY)
    return 0.0


def leg_swing(phase):
    """Forward during the swing, then a linear sweep back during stance."""
    if phase < DUTY:
        return SWING * -math.cos(math.pi * phase / DUTY)       # back -> front
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
    """The seam is invisible per-frame and obvious in playback, so verify
    continuity numerically instead of trusting the algebra."""
    for fn in (leg_lift, leg_swing):
        start, end = fn(0.0), fn(0.9999)
        assert abs(start - end) < 1e-3, (
            f"{fn.__name__} discontinuous across the loop: {start} vs {end}")


_assert_loops()

stage.light_studio()

scene = bpy.context.scene
scene.render.engine = "BLENDER_EEVEE"
scene.eevee.taa_render_samples = 32
scene.eevee.use_ssr = False          # matte floor now; reflections cost time
scene.render.resolution_x = RES
scene.render.resolution_y = RES
scene.render.image_settings.file_format = "PNG"

body = bpy.data.objects["Body"]
arms = [bpy.data.objects["ArmL"], bpy.data.objects["ArmR"]]
eyes = [bpy.data.objects["EyeL"], bpy.data.objects["EyeR"]]
legs = [bpy.data.objects[f"Leg{i}"] for i in range(4)]

# --- taller stance -------------------------------------------------------
# Raise everything attached to the body, then stretch the legs down to meet
# the floor again. Scaling a leg's Z scales about its own centre, so the
# centre has to move too or the foot would punch through the ground.
for obj in [body] + arms + eyes:
    obj.location.z += STAND

LEG_REST_H = 0.80                                  # from mascot.rounded_box
leg_height = LEG_REST_H + STAND + 0.14             # +14 buried in the body
for leg in legs:
    leg.scale.z = leg_height / LEG_REST_H
    leg.location.z = leg_height / 2.0 - 0.04       # foot just under the floor

rest = {obj.name: obj.location.copy()
        for obj in [body] + arms + eyes + legs}
rest_eye_sz = {obj.name: obj.scale.z for obj in eyes}

# --- camera --------------------------------------------------------------
cam = mascot.cam
horiz = CAM_DIST * cos(CAM_EL)
cam.location = (horiz * sin(CAM_AZ), -horiz * cos(CAM_AZ),
                LOOK[2] + CAM_DIST * sin(CAM_EL))
cam.rotation_euler = (Vector(LOOK) - cam.location).to_track_quat(
    "-Z", "Y").to_euler()

visible_leg = rest[body.name].z - 1.0 - 0.0        # body bottom above ground
print(f"[walk] engine={scene.render.engine} frames={FRAMES} res={RES} "
      f"gait=wave duty={DUTY} lift={LIFT} visible_leg={visible_leg:.2f} "
      f"stage=light cam_az=32", flush=True)

started = time.time()
for frame in range(FRAMES):
    phase = frame / FRAMES

    # legs: a quarter-cycle offset each, so the wave travels along the row
    for i, leg in enumerate(legs):
        leg_phase = (phase + i * 0.25) % 1.0
        leg.location.z = rest[leg.name].z + leg_lift(leg_phase)
        leg.location.y = rest[leg.name].y - leg_swing(leg_phase)

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
