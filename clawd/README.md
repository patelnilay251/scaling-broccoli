# Clawd in 3D

A smooth 3D interpretation of Clawd — the Claude Code mascot — built entirely
from Python in headless Blender. No GUI, no manual modelling, no `.blend` file:
the scene is constructed from scratch on every run and path-traced to a PNG.

![Clawd](reference-render.png)

## Running it

Needs Blender on `PATH` (developed against **4.0.2** from Ubuntu `noble/universe`):

```bash
apt-get install -y blender          # run apt-get update first if fetches 404
blender --background --python mascot.py
```

Output goes to `out/clawd.png`, or override with `CLAWD_OUT=/path/to.png`.

For a five-angle contact sheet (front / three-quarter / side / back / top):

```bash
blender --background --python angles.py     # -> out/angles/*.png
```

`angles.py` imports `mascot.py` to reuse the scene, so one Blender launch
renders every view. `mascot.py` guards its own render behind
`if __name__ == "__main__"` to make that work.

Roughly 4–5 minutes for the hero render on 4 CPU cores; the angle sheet is
faster because it drops resolution and samples.

### Walk cycle

![Clawd walk cycle](walk.gif)

```bash
blender --background --python walk.py                                  # -> out/walk/
CLAWD_ANIM_OUT=out/walk CLAWD_GIF_BASE=walk python3 make_gif.py        # -> walk.gif
```

A sequential **wave gait**: each leg is offset a quarter cycle from its
neighbour so a ripple travels along the row, plus two body bobs per loop, a
lateral sway, and claw follow-through. The legs sit in a single row because
that is what the sprite shows, and a wave suits that shape far better than a
quadruped trot — it reads as crustacean, which is apt for a crab.

Walking is in place. Translating the body would carry it out of frame in about
two seconds and break the loop.

One honest limitation: because each leg's top is buried inside the body,
raising a leg *shortens its visible length* rather than lifting a foot clear
of the ground. It reads as the leg retracting into the body — a legitimate
cartoon convention, but a subtler effect than a true step. Making it stronger
means either a larger `LIFT`, or bobbing the body in counter-phase so the
planted legs appear to push off.

`_assert_loops()` verifies numerically at import that the motion functions are
continuous across the cycle boundary. A seam is invisible frame-by-frame and
obvious in playback, so it is checked rather than assumed.

## Exporting the model

```bash
apt-get install -y python3-numpy            # the glTF exporter needs it
blender --background --python export_glb.py  # -> out/clawd.glb
```

`clawd.glb` is committed at the top level — 9 objects, 9,804 triangles, 212 KB,
glTF 2.0, loadable in three.js, `<model-viewer>`, Godot, or anything else that
reads the format. Only the character is exported; the floor, backdrop, lights
and camera are staging for the stills and would be unhelpful in someone else's
scene. Modifiers are applied on export, so the Bevel that does all the rounding
is baked into the delivered mesh rather than lost.

Note the exporter fails with `ModuleNotFoundError: No module named 'numpy'`
without that package. Blender here runs its own Python **3.12.3**, which is not
the `python3` on `PATH` — `python3-numpy` from apt lands somewhere Blender can
see it, but a `pip install` into a different interpreter will not.

## Animation

![Clawd idle loop](idle.gif)

A seamless 48-frame idle loop — breathing bob, arm follow-through, two blinks:

```bash
apt-get install -y libegl1 libgl1-mesa-dri libglx-mesa0 libgbm1   # see below
blender --background --python animate.py     # -> out/idle/f000.png ...
python3 make_gif.py                          # -> idle.gif + idle.webp
```

About 8 s/frame at 512², so ~6 minutes for the loop. Motion is computed per
frame in Python rather than keyframed: procedural sine motion is periodic by
definition, so the loop closes seamlessly with no F-curve interpolation to
fight. Frames are gitignored; only the assembled GIF/WebP are committed.

### Animation renders in EEVEE, and why

Measured here at 480² with matched settings: **EEVEE ~18 s/frame, Cycles
~21–25 s/frame**. Effectively a tie — there is no GPU, so EEVEE rasterises
through Mesa's llvmpipe on the same 4 cores. Speed is *not* the reason to
pick it.

The reason is noise. EEVEE is rasterised and has no Monte Carlo grain at all,
so frames are temporally stable. Cycles' grain re-randomises every frame and
visibly crawls during playback; the normal fix is a denoiser, which this build
does not have. Hence EEVEE for animation, Cycles for hero stills.

### EEVEE on a headless box

EEVEE needs a GL context, which a headless container has no obvious way to
provide. It works anyway because Blender ships with EGL support compiled in
and falls back to **surfaceless EGL** — no X server and no Xvfb required. The
libraries are not installed by default, which presents as:

```
Couldn't open libEGL.so.1: cannot open shared object file
```

Installing `libegl1 libgl1-mesa-dri libglx-mesa0 libgbm1` fixes it. Expect
this on stderr afterwards:

```
EGL Error (0x3001): EGL_NOT_INITIALIZED ...
EGL Error (0x3009): EGL_BAD_MATCH ...
Managed to successfully fallback to surfaceless EGL rendering!
```

Those errors are the fallback working as designed, not a broken build.

## Proportions: hand-tuned, informed by the SVG

The mascot's canonical SVG `<rect>` list is:

```
bdy         x=11  y=0   w=85  h=65      -> body 1.31:1
left-hand   x=0   y=21  w=22  h=23     right-hand  x=85  y=21  w=22  h=23
right-eyes  x=21  y=11  w=11  h=11     left-eyes   x=75  y=11  w=11  h=11
leg1..4     x=11, 32, 64, 85    y=60   w=11  h=26
```

A version built strictly to those numbers, scaled through a single `UNIT`
constant, is in the git history. It is more literally accurate and looks
worse: the 1.31:1 body reads cramped once it is lit and shaded, where the
flat sprite it came from has no shading to contend with. The committed
proportions are therefore **hand-tuned** — a wider **1.5:1** body, with eyes
and legs sized by eye.

What is taken from the SVG and not up for debate: the eyes are **square**
(vertical slots read as an appliance, not a creature), and the four legs form
a **row with a centre gap**, matching both the rect list and the terminal
sprite's bottom row `▘▘ ▝▝` — not a 2×2 grid.

So: silhouette and topology follow the source, exact ratios follow the eye.

## Depth is authored, not derived

**Every published reference for Clawd is front-facing.** There is no side view,
no turnaround, no 3D source. So width and height at least have a source to
argue with, while the depth axis has none — `BODY_D` and the arm depth are
pure authorial choice, marked `AUTHORED` in the source.

This has a visible consequence: because all four legs sit at the same depth,
the side view collapses them into a single silhouette. That is faithful to a
flat sprite and implausible as a creature. Spreading the legs front-to-back
would look better in 3D and be less true to the source — a design decision,
not a bug, and deliberately left as-is.

## Two Blender gotchas worth recording

**Base Color is linear.** Feeding sRGB hex straight into a Principled BSDF
desaturates everything. `srgb_to_linear()` handles the conversion.

**The default view transform will shift a brand colour.** Blender 4.x defaults
to AgX, a filmic tone map that is lovely for photography and wrong for brand
accuracy — it visibly pushes the terracotta off-hue. The scene forces
`view_transform = "Standard"`. The tradeoff is no highlight rolloff, so an
over-bright key light clips hard to white instead of rolling off gracefully;
the lighting is dialled back to suit.

Also: Ubuntu's Blender is compiled **without** OpenImageDenoise, so setting
`cycles.use_denoising = True` raises `RuntimeError: Build without
OpenImageDenoiser` rather than warning. Samples plus a tight adaptive
threshold do the job instead.

## Colours

Anthropic brand values — `#d97757` body, `#141413` eyes and stage. The
mascot's own SVG uses `#DD775B`, a hair warmer; the brand value is used here
deliberately.
