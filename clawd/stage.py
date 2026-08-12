"""Alternative lighting/staging setups, applied over mascot.py's scene.

Import mascot first, then call one of these to restage it:

    import mascot, stage
    stage.light_studio()

Why this exists
---------------
The original stage is near-black with a hard rim light, which suits a moody
product still and makes a friendly mascot look ominous. It also actively hurts
animation: a foot lifted off a dark floor produces a dark gap against dark
ground, so the step is invisible. On a light floor the same gap reads instantly.

Brand values: #faf9f5 light, #e8e6dc light grey, #141413 dark.
"""

from math import radians

import bpy

from mascot import hex_rgba, set_input


def _material(name, hex_code, roughness):
    mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    set_input(bsdf, ["Base Color"], hex_rgba(hex_code))
    set_input(bsdf, ["Roughness"], roughness)
    set_input(bsdf, ["Metallic"], 0.0)
    return mat


def _ensure_sun(energy=2.6, angle=0.10):
    """A sun, not another area light, is what grounds the character.

    Area lamps fall off with distance, so at ~9 units from the subject they
    lose to a bright world and their contact shadow washes out. A sun's
    irradiance is distance-independent and its rays are parallel, so it throws
    a definite shadow at any scale. `angle` is the apparent disc size --
    it controls shadow softness directly.
    """
    sun = bpy.data.objects.get("Sun")
    if sun is None:
        data = bpy.data.lights.new("Sun", type="SUN")
        sun = bpy.data.objects.new("Sun", data)
        bpy.context.collection.objects.link(sun)
    sun.data.energy = energy
    sun.data.angle = angle
    sun.data.use_shadow = True
    # from upper front-left, matching the key's direction
    sun.rotation_euler = (radians(52.0), 0.0, radians(38.0))
    return sun


def light_studio(world_strength=0.45):
    """Bright, friendly, brand-light staging with soft shadows.

    The bright world does most of the lifting, so the lamps drop to a fraction
    of their dark-stage energies. The rim light is nearly switched off: rim
    exists to separate a subject from a dark background, and on a light
    background it only adds glare.
    """
    scene = bpy.context.scene

    # Matte-ish floor. The dark stage used roughness 0.30, which mirrored the
    # lamps into a blown hotspot; 0.62 keeps a soft sheen without the glare.
    floor = bpy.data.objects.get("Floor")
    if floor is not None:
        floor.data.materials.clear()
        floor.data.materials.append(_material("GroundLight", "#e8e6dc", 0.62))

    backdrop = bpy.data.objects.get("Backdrop")
    if backdrop is not None:
        backdrop.data.materials.clear()
        backdrop.data.materials.append(
            _material("BackdropLight", "#faf9f5", 0.90))

    world = bpy.data.worlds["World"]
    world.use_nodes = True
    bg = world.node_tree.nodes["Background"]
    bg.inputs["Color"].default_value = hex_rgba("#faf9f5")
    bg.inputs["Strength"].default_value = world_strength

    # Lamps: the key has to stay strong enough to throw a visible contact
    # shadow. A bright world with weak lamps lights everything evenly and the
    # character reads as floating -- grounding it needs directional light and
    # a world dim enough for the shadow to have contrast.
    energies = {"Key": 190.0, "Fill": 95.0, "Rim": 35.0, "Top": 55.0}
    # Emitter size controls shadow softness, and it is easy to overdo: at
    # size 8+ the key's shadow was so diffuse it disappeared entirely and the
    # character read as floating. The key stays comparatively small so it
    # actually grounds the subject; the fills stay large and soft.
    sizes = {"Key": 4.0, "Fill": 10.0, "Rim": 6.0, "Top": 8.0}
    for name, energy in energies.items():
        obj = bpy.data.objects.get(name)
        if obj is None:
            continue
        obj.data.energy = energy
        obj.data.color = (1.0, 1.0, 1.0)
        obj.data.size = sizes.get(name, 6.0)
        obj.data.use_shadow = True

    _ensure_sun()

    # EEVEE needs these explicitly for the soft look; harmless under Cycles.
    if hasattr(scene, "eevee"):
        scene.eevee.use_gtao = True
        scene.eevee.gtao_distance = 0.35        # tighter = stronger contact
        scene.eevee.gtao_factor = 1.0
        scene.eevee.use_soft_shadows = True
        scene.eevee.shadow_cube_size = "2048"
        scene.eevee.shadow_cascade_size = "2048"

    return scene
