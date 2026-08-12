"""Action library for Clawd. One rig, many named moves, one renderer.

    blender --background --python actions.py                 # render all
    CLAWD_ACTION=jump blender --background --python actions.py   # just one

Frames land in out/<action>/f000.png ...; assemble each with:

    CLAWD_ANIM_OUT=out/jump CLAWD_GIF_BASE=jump python3 make_gif.py

Why a rig instead of another script
-----------------------------------
The first two animations each poked object locations directly, which meant
every new move re-derived the same problems: keeping the eyes stuck to a face
that is moving, keeping legs planted while the body sways, and not letting a
squash tear the parts apart. `Rig` accumulates a pose and applies it once, so
an action is a pure function of phase and the awkward bookkeeping lives in one
place.

Squash and stretch is the case that justifies it. The eyes, arms and body are
separate objects, so scaling the body alone slides the face out from under the
eyes. Rig.apply() re-derives every attached part's position from the body's
current scale, so squash just works.

All actions are periodic: pose(0) == pose(1), so every loop closes seamlessly.
_assert_loops() checks that numerically for each registered action instead of
trusting the arithmetic.
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

HERE = os.path.dirname(os.path.abspath(__file__))
RES = int(os.environ.get("CLAWD_ANIM_RES", "512"))
ONLY = os.environ.get("CLAWD_ACTION", "").strip()

# default camera: three-quarter, so both the leg row and fore/aft motion show
CAM_AZ, CAM_EL, CAM_DIST = 32.0, 8.0, 9.8
LOOK = (0.0, 0.0, 1.40)

LEG_REST_H = 0.80          # from mascot.rounded_box


# --------------------------------------------------------------------------
# rig
# --------------------------------------------------------------------------
class Rig:
    def __init__(self):
        self.body = bpy.data.objects["Body"]
        self.arms = [bpy.data.objects["ArmL"], bpy.data.objects["ArmR"]]
        self.eyes = [bpy.data.objects["EyeL"], bpy.data.objects["EyeR"]]
        self.legs = [bpy.data.objects[f"Leg{i}"] for i in range(4)]
        self.parts = [self.body] + self.arms + self.eyes + self.legs
        self.rest = {o.name: o.location.copy() for o in self.parts}
        self.rest_scale = {o.name: o.scale.copy() for o in self.parts}
        self.clear()

    # -- stance ----------------------------------------------------------
    def set_stand(self, amount):
        """Raise the torso and lengthen the legs to meet the floor again.

        Scaling a leg's Z scales about its own centre, so the centre has to
        move too or the foot punches through the ground.
        """
        for obj in [self.body] + self.arms + self.eyes:
            self.rest[obj.name].z += amount
        height = LEG_REST_H + amount + 0.14        # +0.14 buried in the body
        for leg in self.legs:
            self.rest_scale[leg.name].z = height / LEG_REST_H
            self.rest[leg.name].z = height / 2.0 - 0.04

    # -- pose accumulation ------------------------------------------------
    def clear(self):
        self.dx = self.dy = self.dz = 0.0
        self.squash_amt = 0.0
        self.blink_amt = 1.0
        self.eye_dx = 0.0
        self.eye_scale = 1.0
        self.arm_dz = [0.0, 0.0]
        self.arm_dx = [0.0, 0.0]
        self.leg_lift = [0.0] * 4
        self.leg_swing = [0.0] * 4
        self.leg_stretch = [0.0] * 4

    def torso(self, dz=0.0, dx=0.0, dy=0.0):
        self.dz += dz
        self.dx += dx
        self.dy += dy

    def squash(self, amount):
        """Positive squashes (shorter, wider); negative stretches."""
        self.squash_amt += amount

    def blink(self, amount):
        self.blink_amt = min(self.blink_amt, amount)

    def look(self, dx):
        self.eye_dx += dx

    def widen(self, scale):
        self.eye_scale *= scale

    def arm(self, index, dz=0.0, dx=0.0):
        self.arm_dz[index] += dz
        self.arm_dx[index] += dx

    def leg(self, index, lift=0.0, swing=0.0):
        self.leg_lift[index] += lift
        self.leg_swing[index] += swing

    def leg_planted(self, index, body_dz):
        """Keep this foot on the ground while the hip rises with the body.

        Legs are rigid boxes, so a rising body leaves two bad options:
        translate the leg (the foot leaves the ground) or leave it (the leg
        tears off at the hip). Stretching is the third, correct one -- the
        poor man's IK. Without this, `jump` rendered the legs as four capsules
        floating under an airborne body.
        """
        self.leg_stretch[index] += body_dz

    # -- write to Blender -------------------------------------------------
    def apply(self):
        sz = 1.0 - self.squash_amt
        sxy = 1.0 + self.squash_amt * 0.5

        base = self.rest[self.body.name]
        self.body.scale = (sxy, sxy, sz)
        self.body.location = (base.x + self.dx, base.y + self.dy,
                              base.z + self.dz)
        bx, by, bz = self.body.location

        # Everything attached to the body has its offset re-derived from the
        # body's current scale, so a squash never tears the parts apart.
        for eye in self.eyes:
            rest = self.rest[eye.name]
            eye.location = (bx + (rest.x - base.x) * sxy + self.eye_dx,
                            by + (rest.y - base.y) * sxy,
                            bz + (rest.z - base.z) * sz)
            s = self.rest_scale[eye.name]
            eye.scale = (s.x * self.eye_scale, s.y,
                         s.z * self.eye_scale * self.blink_amt)

        for i, arm in enumerate(self.arms):
            rest = self.rest[arm.name]
            arm.location = (bx + (rest.x - base.x) * sxy + self.arm_dx[i],
                            by + (rest.y - base.y) * sxy,
                            bz + (rest.z - base.z) * sz + self.arm_dz[i])

        # Legs do NOT follow torso sway -- that contrast is exactly what makes
        # a waddle read as a waddle. Vertical follow is opt-in per action, via
        # leg() to travel with the body or leg_planted() to stretch instead.
        for i, leg in enumerate(self.legs):
            rest = self.rest[leg.name]
            rest_s = self.rest_scale[leg.name]
            height = LEG_REST_H * rest_s.z
            stretch = self.leg_stretch[i]
            if abs(stretch) > 1e-6:
                foot = rest.z - height / 2.0        # hold the foot still
                leg.scale = (rest_s.x, rest_s.y,
                             rest_s.z * (height + stretch) / height)
                leg_z = foot + (height + stretch) / 2.0 + self.leg_lift[i]
            else:
                leg.scale = rest_s
                leg_z = rest.z + self.leg_lift[i]
            leg.location = (rest.x, rest.y - self.leg_swing[i], leg_z)


# --------------------------------------------------------------------------
# shared shaping helpers
# --------------------------------------------------------------------------
def arc(t):
    """0 -> 1 -> 0 over t in [0,1]; zero and flat-ish at both ends."""
    return math.sin(math.pi * max(0.0, min(1.0, t)))


def blink_at(phase, centres, shut=0.10):
    for centre in centres:
        dist = abs(((phase - centre + 0.5) % 1.0) - 0.5)
        if dist < 0.022:
            return shut
        if dist < 0.042:
            return 0.55
    return 1.0


def wave_gait(rig, phase, duty=0.42, lift=0.20, swing=0.15):
    """Sequential wave: each leg a quarter cycle behind its neighbour."""
    for i in range(4):
        p = (phase + i * 0.25) % 1.0
        if p < duty:
            rig.leg(i, lift=lift * math.sin(math.pi * p / duty),
                    swing=swing * -math.cos(math.pi * p / duty))
        else:
            rig.leg(i, swing=swing * (1.0 - 2.0 * (p - duty) / (1.0 - duty)))


# --------------------------------------------------------------------------
# actions: each takes (rig, phase) and must satisfy pose(0) == pose(1)
# --------------------------------------------------------------------------
def act_idle(rig, p):
    a = 2.0 * math.pi * p
    rig.torso(dz=0.05 * math.sin(a))
    for i in (0, 1):
        rig.arm(i, dz=0.05 * math.sin(a - 0.65) - 0.05 * math.sin(a))
    rig.blink(blink_at(p, (0.28, 0.72)))


def act_walk(rig, p):
    a = 2.0 * math.pi * p
    wave_gait(rig, p)
    rig.torso(dz=0.05 * math.sin(2.0 * a), dx=0.075 * math.sin(a))
    for i in (0, 1):
        rig.arm(i, dz=0.05 * math.sin(2.0 * a - 0.7) - 0.05 * math.sin(2.0 * a))
    rig.blink(blink_at(p, (0.34,)))


def act_jump(rig, p):
    """Anticipation crouch, launch, airborne arc, landing squash, settle."""
    if p < 0.18:                                    # crouch
        k = arc(p / 0.18)
        rig.squash(0.17 * k)
        rig.torso(dz=-0.13 * k)
    elif p < 0.54:                                  # airborne
        h = arc((p - 0.18) / 0.36)
        rise = 1.05 * h
        rig.torso(dz=rise)
        rig.squash(-0.11 * h)                       # stretch in the air
        for i in range(4):
            # travel WITH the body, then tuck on top of that. Lifting only by
            # the tuck left the legs floating under an airborne body.
            rig.leg(i, lift=rise + 0.30 * h)
        rig.widen(1.0 + 0.18 * h)
    elif p < 0.72:                                  # land
        k = arc((p - 0.54) / 0.18)
        rig.squash(0.22 * k)
        rig.torso(dz=-0.15 * k)
    else:                                           # damped settle
        c = (p - 0.72) / 0.28
        rig.torso(dz=0.06 * arc(c) * (1.0 - c))
    rig.blink(blink_at(p, (0.90,)))


def act_wave(rig, p):
    """Raise the right claw and rock it. Translated, not rotated: the arm's
    origin is its own centre, so rotating it would swing the shoulder end out
    of the body rather than pivoting at it."""
    up = arc(min(1.0, p / 0.82))
    rig.arm(1, dz=0.42 * up, dx=0.10 * up)
    rig.arm(1, dx=0.13 * up * math.sin(6.0 * math.pi * p))
    rig.torso(dz=0.03 * math.sin(2.0 * math.pi * p), dx=-0.03 * up)
    rig.blink(blink_at(p, (0.55,)))


def act_look(rig, p):
    """Glance left, then right, then centre. The eyes are separate objects
    sitting on a flat face, so they can slide across it -- within +/-0.4
    before they would run off the edge."""
    swing = 0.27 * math.sin(2.0 * math.pi * p)
    rig.look(swing)
    rig.torso(dx=0.035 * math.sin(2.0 * math.pi * p),
              dz=0.02 * math.sin(4.0 * math.pi * p))
    rig.blink(blink_at(p, (0.24, 0.74)))


def act_dance(rig, p):
    """Two-beat bounce with squash on the landings and alternating legs."""
    a = 2.0 * math.pi * p
    beat = abs(math.sin(a))                         # two peaks per loop
    rise = 0.24 * beat
    rig.torso(dz=rise, dx=0.11 * math.sin(a))
    rig.squash(0.10 * (1.0 - beat) - 0.05 * beat)
    for i in range(4):
        lifted = (i % 2 == 0) == (math.sin(a) >= 0.0)
        if lifted:
            rig.leg(i, lift=rise + 0.15 * beat)     # comes up with the body
        else:
            rig.leg_planted(i, rise)                # foot down, leg stretches
    rig.arm(0, dz=0.20 * max(0.0, math.sin(a)))
    rig.arm(1, dz=0.20 * max(0.0, -math.sin(a)))
    rig.blink(blink_at(p, (0.48,)))


def act_sleep(rig, p):
    """Slow deep breathing, eyes shut throughout."""
    a = 2.0 * math.pi * p
    rig.torso(dz=0.035 * math.sin(a))
    rig.squash(0.045 * math.sin(a))
    rig.blink(0.08)
    for i in (0, 1):
        rig.arm(i, dz=0.035 * math.sin(a - 0.9) - 0.035 * math.sin(a))


def act_turntable(rig, p):
    """Static rest pose -- the camera does the moving (see CAMERAS)."""
    rig.blink(blink_at(p, (0.5,)))


def cam_orbit(p):
    return (360.0 * p, CAM_EL, CAM_DIST)


# name -> (pose fn, frames, stand offset, camera fn or None)
ACTIONS = {
    "idle":      (act_idle, 48, 0.0, None),
    "walk":      (act_walk, 48, 0.14, None),
    "jump":      (act_jump, 42, 0.10, None),
    "wave":      (act_wave, 40, 0.0, None),
    "look":      (act_look, 44, 0.0, None),
    "dance":     (act_dance, 36, 0.12, None),
    "sleep":     (act_sleep, 48, 0.0, None),
    "turntable": (act_turntable, 48, 0.0, cam_orbit),
}


def _assert_loops():
    """A seam is invisible frame-by-frame and glaring in playback. Compare the
    pose accumulated at phase 0 against phase ~1 for every action."""
    probe = Rig()
    for name, (fn, _frames, _stand, _cam) in ACTIONS.items():
        snaps = []
        for phase in (0.0, 0.99999):
            probe.clear()
            fn(probe, phase)
            snaps.append((probe.dx, probe.dy, probe.dz, probe.squash_amt,
                          probe.eye_dx, tuple(probe.leg_lift),
                          tuple(probe.leg_swing), tuple(probe.leg_stretch),
                          tuple(probe.arm_dz)))
        for a, b in zip(*(list(_flatten(s)) for s in snaps)):
            assert abs(a - b) < 2e-3, f"action '{name}' does not loop: {a} vs {b}"


def _flatten(seq):
    for item in seq:
        if isinstance(item, tuple):
            yield from item
        else:
            yield item


def place_camera(az_deg, el_deg, dist):
    cam = mascot.cam
    az, el = radians(az_deg), radians(el_deg)
    horiz = dist * cos(el)
    cam.location = (horiz * sin(az), -horiz * cos(az),
                    LOOK[2] + dist * sin(el))
    cam.rotation_euler = (Vector(LOOK) - cam.location).to_track_quat(
        "-Z", "Y").to_euler()


_assert_loops()

stage.light_studio()

scene = bpy.context.scene
scene.render.engine = "BLENDER_EEVEE"
# 16, not 32. Measured: 4.7s/frame vs 8.1s, for a mean absolute difference of
# 0.08/255 across 5.5% of pixels -- imperceptible, and it halves a 350-frame
# batch. Resolution is NOT the lever here: 320px cost 6.7s against 512px's
# 8.1s, so per-frame overhead dominates pixel count.
scene.eevee.taa_render_samples = 16
scene.eevee.use_ssr = False
scene.render.resolution_x = RES
scene.render.resolution_y = RES
scene.render.image_settings.file_format = "PNG"

selected = [ONLY] if ONLY else list(ACTIONS)
missing = [n for n in selected if n not in ACTIONS]
if missing:
    sys.exit(f"unknown action(s): {missing}; known: {sorted(ACTIONS)}")

total_started = time.time()
for name in selected:
    pose_fn, frames, stand, cam_fn = ACTIONS[name]
    outdir = os.path.join(HERE, "out", name)
    os.makedirs(outdir, exist_ok=True)

    rig = Rig()                                  # fresh rest pose each action
    if stand:
        rig.set_stand(stand)
    place_camera(CAM_AZ, CAM_EL, CAM_DIST)

    started = time.time()
    print(f"[act] {name}: {frames} frames, stand={stand}", flush=True)
    for frame in range(frames):
        phase = frame / frames
        rig.clear()
        pose_fn(rig, phase)
        rig.apply()
        if cam_fn is not None:
            place_camera(*cam_fn(phase))

        scene.render.filepath = os.path.join(outdir, f"f{frame:03d}.png")
        bpy.ops.render.render(write_still=True)

    per = (time.time() - started) / frames
    print(f"[act] {name} done: {per:.1f}s/frame, "
          f"{(time.time() - started) / 60.0:.1f}min", flush=True)

print(f"[act] ALL done in {(time.time() - total_started) / 60.0:.1f}min",
      flush=True)
