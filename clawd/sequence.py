"""A choreographed sequence: Clawd wakes, looks around, walks, jumps, waves,
dances, settles. One continuous shot with a moving camera.

    blender --background --python sequence.py     # -> out/sequence/f####.png
    python3 encode.py                             # -> sequence.mp4 + .webp

This is the piece the looping actions could not be: continuous motion with
transitions, rather than eight isolated cycles.

Three things make it a sequence rather than a playlist
------------------------------------------------------
1. POSE BLENDING. At each beat change the outgoing action keeps advancing its
   own phase while the incoming one starts, and the two poses are cross-faded
   over BLEND frames. Because a pose is only scalars and short lists (see
   Rig.snapshot), that cross-fade is a plain lerp -- which is the payoff for
   having the rig accumulate a pose instead of writing straight to Blender.

2. NATIVE CADENCE. Each action keeps its own designed period, so a beat plays
   however many cycles fit its length. A 48-frame walk over an 84-frame beat
   runs 1.75 strides at the speed it was tuned for, rather than being stretched
   to fill the slot.

3. ONE STANCE THROUGHOUT. set_stand() rewrites the rest pose, so switching it
   mid-shot would jump the whole body. Every beat therefore shares SEQ_STAND,
   a compromise between the per-action values (walk wanted 0.14, jump 0.10).

The camera eases continuously from each beat's framing to the next, and the
final beat returns to the opening framing so a looping player cuts cleanly.
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bpy                                     # noqa: E402

import actions                                 # noqa: E402  rig + registry
from actions import Rig, ACTIONS, blend_pose, smoothstep, place_camera  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
OUTDIR = os.environ.get("CLAWD_SEQ_OUT", os.path.join(HERE, "out", "sequence"))
os.makedirs(OUTDIR, exist_ok=True)

RES = int(os.environ.get("CLAWD_SEQ_RES", "512"))
SAMPLES = int(os.environ.get("CLAWD_SEQ_SAMPLES", "16"))
# STRIDE > 1 renders every Nth frame -- a cheap preview of the whole arc,
# covering every beat and camera move for a fraction of the frames.
STRIDE = int(os.environ.get("CLAWD_SEQ_STRIDE", "1"))
# Sharding for parallel rendering (CI splits the shot across runners). Every
# frame's pose and camera are computed purely from its index -- nothing carries
# over between frames -- so any subset can be rendered independently and the
# results merged. Filenames use the GLOBAL frame number, so merging is a copy.
SHARD = int(os.environ.get("CLAWD_SHARD", "0"))
SHARDS = int(os.environ.get("CLAWD_SHARDS", "1"))
FPS = 24
BLEND = 9                    # frames of cross-fade at each beat change
SEQ_STAND = 0.12             # one stance for the whole shot

#  action    frames   camera at the START of this beat: az, el, dist, look_z
BEATS = [
    ("sleep", 60, (-20.0,  3.0,  8.8, 1.28)),   # asleep, low and close
    ("look",  54, ( -6.0,  8.0,  8.6, 1.40)),   # wakes, glances about
    ("walk",  84, ( 34.0,  9.0,  9.9, 1.42)),   # sets off, camera swings round
    ("jump",  42, ( 18.0,  5.0, 10.7, 1.52)),   # pulls back for the hop
    ("wave",  42, (  4.0,  7.0,  8.7, 1.44)),   # pushes in to front-on
    ("dance", 60, (-30.0, 11.0,  9.5, 1.44)),   # orbits the other way
    ("idle",  44, (-20.0,  3.0,  8.8, 1.28)),   # returns to the opening frame
]

TOTAL = sum(b[1] for b in BEATS)
STARTS = []
_acc = 0
for _b in BEATS:
    STARTS.append(_acc)
    _acc += _b[1]


def beat_at(frame):
    """Index of the beat containing this global frame, and the local offset."""
    for i in range(len(BEATS) - 1, -1, -1):
        if frame >= STARTS[i]:
            return i, frame - STARTS[i]
    return 0, frame


def pose_of(rig, action, local):
    """Evaluate an action at its native cadence and snapshot the result."""
    period = ACTIONS[action][1]
    rig.clear()
    ACTIONS[action][0](rig, (local % period) / period)
    return rig.snapshot()


def camera_for(index, t):
    """Ease from this beat's framing to the next one's across the beat."""
    here = BEATS[index][2]
    nxt = BEATS[min(index + 1, len(BEATS) - 1)][2]
    k = smoothstep(t)
    az, el, dist, look_z = (a + (b - a) * k for a, b in zip(here, nxt))
    actions.LOOK = (0.0, 0.0, look_z)
    place_camera(az, el, dist)


scene = actions.setup_render(res=RES, samples=SAMPLES)
rig = Rig()
rig.set_stand(SEQ_STAND)

print(f"[seq] {len(BEATS)} beats, {TOTAL} frames, {TOTAL / FPS:.1f}s at {FPS}fps, "
      f"res={RES} samples={SAMPLES} stand={SEQ_STAND} blend={BLEND} "
      f"shard={SHARD}/{SHARDS}", flush=True)

started = time.time()
todo = list(range(0, TOTAL, STRIDE))[SHARD::SHARDS]   # balanced interleave
for count, frame in enumerate(todo):
    index, local = beat_at(frame)
    action, length, _cam = BEATS[index]

    pose = pose_of(rig, action, local)

    # Cross-fade from the previous beat, whose action keeps advancing so the
    # outgoing motion does not freeze mid-stride while it fades out.
    if index > 0 and local < BLEND:
        prev_action, prev_length, _ = BEATS[index - 1]
        prev = pose_of(rig, prev_action, prev_length + local)
        pose = blend_pose(prev, pose, smoothstep((local + 1) / (BLEND + 1)))

    rig.load(pose)
    rig.apply()
    camera_for(index, local / length)

    scene.render.filepath = os.path.join(OUTDIR, f"f{frame:04d}.png")
    bpy.ops.render.render(write_still=True)

    if count % 24 == 0 or count == len(todo) - 1:
        per = (time.time() - started) / (count + 1)
        print(f"[seq] {count + 1}/{len(todo)} (frame {frame}, {action})  "
              f"{per:.1f}s/frame  "
              f"eta {per * (len(todo) - count - 1) / 60.0:.1f}min", flush=True)

print(f"[seq] done in {(time.time() - started) / 60.0:.1f}min -> {OUTDIR}",
      flush=True)
