"""Claude mascot, rebuilt as smooth 3D geometry and rendered headless.

    blender --background --python mascot.py

Design notes
------------
* Proportions are lifted from the pixel reference: body 1.5x wider than tall,
  eyes as tall thin slots at ~21-54% of body height, side nubs at ~62% down,
  stubby legs. Sharp pixels become heavily bevelled rounded boxes -- the
  "squircle" read is what makes it feel polished rather than blocky.
* Colours are Anthropic brand: #d97757 body, #141413 eyes/floor.
* Base Color sockets are LINEAR. Feeding sRGB hex straight in desaturates
  everything, so convert.
* View transform is Standard, not the 4.x default AgX. AgX is a filmic tone
  map -- lovely for photography, but it shifts a brand hue off-brand.
* No denoiser in Ubuntu's build, so noise is beaten down with samples plus
  a tight adaptive threshold (the flat dark background converges early and
  costs almost nothing).
"""

import os
import sys
from math import radians, sin, cos

import bpy
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.environ.get("CLAWD_OUT", os.path.join(HERE, "out", "clawd.png"))
os.makedirs(os.path.dirname(OUT), exist_ok=True)

TERRACOTTA = "#d97757"   # Anthropic orange
INK = "#141413"          # Anthropic dark


# --------------------------------------------------------------------------
# colour
# --------------------------------------------------------------------------
def srgb_to_linear(channel):
    c = channel / 255.0
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def hex_rgba(code, alpha=1.0):
    code = code.lstrip("#")
    r, g, b = (int(code[i:i + 2], 16) for i in (0, 2, 4))
    return (srgb_to_linear(r), srgb_to_linear(g), srgb_to_linear(b), alpha)


# --------------------------------------------------------------------------
# scene helpers
# --------------------------------------------------------------------------
def clear_scene():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for coll in (bpy.data.meshes, bpy.data.materials, bpy.data.lights,
                 bpy.data.cameras):
        for item in list(coll):
            coll.remove(item)


def set_input(bsdf, names, value):
    """Principled socket names shuffled in 4.x -- try each candidate."""
    for name in names:
        socket = bsdf.inputs.get(name)
        if socket is not None:
            socket.default_value = value
            return True
    return False


def material(name, hex_code, roughness=0.45, metallic=0.0, specular=0.5):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    set_input(bsdf, ["Base Color"], hex_rgba(hex_code))
    set_input(bsdf, ["Roughness"], roughness)
    set_input(bsdf, ["Metallic"], metallic)
    set_input(bsdf, ["Specular IOR Level", "Specular"], specular)
    return mat


def smooth(obj, angle=40.0):
    """Shade smooth + auto-smooth. auto_smooth vanished in 4.1, so guard it."""
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.shade_smooth()
    mesh = obj.data
    if hasattr(mesh, "use_auto_smooth"):
        mesh.use_auto_smooth = True
        mesh.auto_smooth_angle = radians(angle)


def rounded_box(name, size, location, bevel, segments=10, subsurf=0, mat=None):
    """Cube -> baked non-uniform scale -> uniform bevel. Baking the scale
    first is what keeps the bevel even on all axes."""
    bpy.ops.mesh.primitive_cube_add(size=2.0, location=location)
    obj = bpy.context.active_object
    obj.name = name
    obj.scale = (size[0] / 2.0, size[1] / 2.0, size[2] / 2.0)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)

    bev = obj.modifiers.new("Bevel", "BEVEL")
    bev.width = bevel
    bev.segments = segments
    bev.limit_method = "ANGLE"
    bev.angle_limit = radians(30.0)

    if subsurf:
        sub = obj.modifiers.new("Subdivision", "SUBSURF")
        sub.levels = subsurf
        sub.render_levels = subsurf

    smooth(obj)
    if mat:
        obj.data.materials.append(mat)
    return obj


def area_light(name, location, target, energy, size, size_y=None,
               color=(1.0, 1.0, 1.0)):
    data = bpy.data.lights.new(name, type="AREA")
    data.energy = energy
    data.color = color
    if size_y is None:
        data.shape = "SQUARE"
        data.size = size
    else:
        data.shape = "RECTANGLE"
        data.size = size
        data.size_y = size_y
    obj = bpy.data.objects.new(name, data)
    bpy.context.collection.objects.link(obj)
    obj.location = location
    direction = Vector(target) - Vector(location)
    obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
    return obj


clear_scene()

skin = material("Terracotta", TERRACOTTA, roughness=0.38, specular=0.5)
ink = material("Ink", INK, roughness=0.16, specular=0.6)
ground = material("Ground", INK, roughness=0.30, specular=0.5)

# --------------------------------------------------------------------------
# Geometry. These are hand-tuned proportions, chosen by eye over the
# SVG-derived ones because they simply read better in 3D.
#
# For reference, the mascot's canonical SVG <rect> list is:
#
#   bdy         x=11  y=0   w=85  h=65        -> body 1.31:1
#   left-hand   x=0   y=21  w=22  h=23     right-hand  x=85 y=21 w=22 h=23
#   right-eyes  x=21  y=11  w=11  h=11     left-eyes   x=75 y=11 w=11 h=11
#   leg1..4     x=11, 32, 64, 85    y=60   w=11  h=26
#
# Building strictly to those numbers (see git history) produced a narrower
# 1.31:1 body that looked cramped once lit and shaded, so the wider 1.5:1
# body below is a deliberate departure. What IS taken from the SVG: eyes are
# square rather than slots, and the legs are a row with a centre gap.
#
# DEPTH (Y) is authored regardless of which set is used -- every published
# reference is front-facing, so nothing constrains it. BODY_D and the arm
# depth are pure invention.
# --------------------------------------------------------------------------
BODY_W, BODY_D, BODY_H = 3.0, 1.8, 2.0   # 1.5:1; depth is AUTHORED
# Body bottom must clear the ground or the overlap swallows the legs -- an
# earlier pass left only half a leg showing.
BODY_Z = 1.62                      # bottom lands at 0.62, top at 2.62
FRONT = -BODY_D / 2.0              # front face plane

rounded_box("Body", (BODY_W, BODY_D, BODY_H), (0.0, 0.0, BODY_Z),
            bevel=0.42, segments=12, mat=skin)

# arms: Clawd is a crab (the official emoji is the crab), so the side stubs
# are claws, not ears.
for sign in (-1.0, 1.0):
    rounded_box(f"Arm{'L' if sign < 0 else 'R'}", (0.74, 0.62, 0.58),
                (sign * 1.66, 0.0, 1.44), bevel=0.18, segments=8, mat=skin)

# four legs in a ROW with a centre gap, matching the terminal sprite's bottom
# row (`▘▘ ▝▝`) and the pixel reference -- not a 2x2 grid.
for i, leg_x in enumerate((-1.02, -0.52, 0.52, 1.02)):
    rounded_box(f"Leg{i}", (0.34, 0.34, 0.80),
                (leg_x, 0.0, 0.36), bevel=0.15, segments=8, mat=skin)

# eyes: SQUARE, per the references. Vertical slots were the single biggest
# reason earlier passes read as an appliance instead of a creature.
for sign in (-1.0, 1.0):
    rounded_box(f"Eye{'L' if sign < 0 else 'R'}", (0.34, 0.14, 0.34),
                (sign * 0.85, FRONT, 2.04),
                bevel=0.075, segments=8, mat=ink)

# --------------------------------------------------------------------------
# stage
# --------------------------------------------------------------------------
bpy.ops.mesh.primitive_plane_add(size=60.0, location=(0.0, 0.0, 0.0))
bpy.context.active_object.name = "Floor"
bpy.context.active_object.data.materials.append(ground)

bpy.ops.mesh.primitive_plane_add(size=40.0, location=(0.0, 9.0, 0.0))
backdrop = bpy.context.active_object
backdrop.name = "Backdrop"
backdrop.rotation_euler = (radians(90.0), 0.0, 0.0)
backdrop.data.materials.append(ground)

# --------------------------------------------------------------------------
# three-point studio light: soft key, cool fill, warm rim for separation
# --------------------------------------------------------------------------
LOOK = (0.0, 0.0, 1.45)   # half the subject height, so the frame is centred
# Standard view transform has no highlight rolloff, so an over-hot key clips
# to flat white instead of rolling off. Softer + dimmer + more frontal.
area_light("Key", (-5.2, -6.4, 5.4), LOOK, energy=850.0,
           size=9.0, color=(1.0, 0.96, 0.91))
area_light("Fill", (5.8, -4.4, 3.2), LOOK, energy=360.0,
           size=8.0, color=(0.80, 0.87, 1.0))
area_light("Rim", (2.4, 5.4, 4.4), LOOK, energy=820.0,
           size=4.5, color=(1.0, 0.88, 0.76))
area_light("Top", (0.0, -0.6, 8.0), LOOK, energy=300.0, size=6.0)

world = bpy.data.worlds["World"]
world.use_nodes = True
world.node_tree.nodes["Background"].inputs["Color"].default_value = hex_rgba(
    "#0b0b0a")
world.node_tree.nodes["Background"].inputs["Strength"].default_value = 1.0

# --------------------------------------------------------------------------
# camera: 85mm, gentle 3/4 so the rounding reads without losing the icon
# --------------------------------------------------------------------------
# 70mm at 9.8 -> ~5.05-unit frame for a ~4.12-unit subject: 19% margin.
# v2 at 11.0 was safe but left too much dead space; v1 at 85mm/9.4 clipped.
AZ, EL, DIST = radians(10.0), radians(6.0), 10.2
cam_data = bpy.data.cameras.new("Camera")
cam_data.lens = 70.0
cam = bpy.data.objects.new("Camera", cam_data)
bpy.context.collection.objects.link(cam)
horiz = DIST * cos(EL)
cam.location = (horiz * sin(AZ), -horiz * cos(AZ), LOOK[2] + DIST * sin(EL))
cam.rotation_euler = (Vector(LOOK) - cam.location).to_track_quat(
    "-Z", "Y").to_euler()

scene = bpy.context.scene
scene.camera = cam

# --------------------------------------------------------------------------
# render
# --------------------------------------------------------------------------
scene.render.engine = "CYCLES"
scene.cycles.device = "CPU"
scene.cycles.samples = 256
scene.cycles.use_denoising = False          # not compiled into this build
scene.cycles.use_adaptive_sampling = True
scene.cycles.adaptive_threshold = 0.010     # v1 at 384/0.006 was oversampled
scene.cycles.max_bounces = 6

scene.render.resolution_x = 1080
scene.render.resolution_y = 1080
scene.render.image_settings.file_format = "PNG"
scene.render.filepath = OUT

# Standard, not AgX -- keep #d97757 actually #d97757
scene.view_settings.view_transform = "Standard"
scene.view_settings.look = "None"

# Guarded so other scripts can `import mascot` to reuse the scene without
# triggering the hero render (angles.py does exactly that).
if __name__ == "__main__":
    print(f"[mascot] objects={len(bpy.data.objects)} "
          f"samples={scene.cycles.samples} "
          f"view={scene.view_settings.view_transform} "
          f"threads={scene.render.threads}", flush=True)

    bpy.ops.render.render(write_still=True)
    print("[mascot] done", flush=True)
    sys.stdout.flush()
