"""Export just the mascot as a self-contained .glb.

    blender --background --python export_glb.py

Writes out/clawd.glb -- loadable in three.js, model-viewer, Godot, Blender
itself, or anything else that speaks glTF 2.0.

Only the character is exported. The floor, backdrop, lights and camera are
staging for the stills and would be actively unhelpful in someone else's
scene. Modifiers are applied on export, so the Bevel that does all the
rounding is baked into the delivered mesh rather than lost.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bpy                                     # noqa: E402
import mascot                                  # noqa: E402  builds the scene

OUT = os.environ.get(
    "CLAWD_GLB",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "out",
                 "clawd.glb"))
os.makedirs(os.path.dirname(OUT), exist_ok=True)

PARTS = (["Body", "ArmL", "ArmR", "EyeL", "EyeR"]
         + [f"Leg{i}" for i in range(4)])

bpy.ops.object.select_all(action="DESELECT")
exported = []
for name in PARTS:
    obj = bpy.data.objects.get(name)
    if obj is None:
        print(f"[glb] WARNING missing object: {name}", flush=True)
        continue
    obj.select_set(True)
    exported.append(obj)

if not exported:
    sys.exit("[glb] nothing to export")

bpy.context.view_layer.objects.active = exported[0]

# Triangle count after modifiers, so the delivered size is a known quantity.
depsgraph = bpy.context.evaluated_depsgraph_get()
tris = 0
for obj in exported:
    mesh = obj.evaluated_get(depsgraph).to_mesh()
    mesh.calc_loop_triangles()
    tris += len(mesh.loop_triangles)
    obj.evaluated_get(depsgraph).to_mesh_clear()

bpy.ops.export_scene.gltf(
    filepath=OUT,
    export_format="GLB",
    use_selection=True,
    export_apply=True,          # bake Bevel/Subdivision into the mesh
    export_yup=True,            # glTF is Y-up; Blender is Z-up
)

size = os.path.getsize(OUT) if os.path.exists(OUT) else 0
print(f"[glb] exported {len(exported)} objects, {tris} triangles, "
      f"{size / 1024.0:.0f} KB -> {OUT}", flush=True)
