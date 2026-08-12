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
