"""Build the F-15's afterburner flames in light_speed.blend.

Run headless from the project root (saves the .blend in place):

    blender -b light_speed.blend --python scripts/build_afterburner.py

Relativity makes the sky contract toward the direction of travel, which the
eye reads as moving backward; a burning engine is the unmistakable "pushing
forward" cue. (No jet could get anywhere near light speed; artistic license.)

Each flame is a transparent cone with an additive emission shader: hot
blue-white at the nozzle cooling to orange, shock diamonds (the bright rings in
a supersonic exhaust), and flickering 4D noise flowing down the plume. It is
in the plane's own frame, so no relativistic effects apply. F15["thrust"]
(default 1) scales brightness and length; keyframe it for an ignition.

Safe to re-run: flames, material and lights are rebuilt.
"""

import math
import os
import sys

import bmesh
import bpy
import mathutils

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build_sky_shader import RIG, Builder  # noqa: E402

# Nozzle exits, measured from orthographic renders of the model (meters).
NOZZLES = {"L": (0.67, 8.6, 2.35), "R": (-0.67, 8.6, 2.35)}
NOZZLE_RADIUS = 0.42
TAIL_RADIUS = 0.18
LENGTH = 6.0
SHOCK_DIAMONDS = 5
# Peak emission; above ~10 the core clips to white and hides the shock diamonds.
FLAME_STRENGTH = 6.0


def flame_mesh():
    """Open cone from the nozzle (local origin) along local +Y."""
    mesh = bpy.data.meshes.new("AfterburnerFlame")
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=False, segments=48,
                          radius1=NOZZLE_RADIUS, radius2=TAIL_RADIUS, depth=LENGTH)
    # create_cone is centered on Z; put the nozzle at the origin, then turn +Z into +Y.
    bmesh.ops.translate(bm, verts=bm.verts, vec=(0, 0, LENGTH / 2))
    bmesh.ops.rotate(bm, verts=bm.verts, matrix=mathutils.Matrix.Rotation(-math.pi / 2, 3, "X"))
    bm.to_mesh(mesh)
    bm.free()
    for poly in mesh.polygons:
        poly.use_smooth = True
    old = bpy.data.meshes.get("AfterburnerFlame")
    if old and old != mesh:
        old.user_remap(mesh)
        bpy.data.meshes.remove(old)
    mesh.name = "AfterburnerFlame"
    return mesh


def add_driver(owner, path, expression, variables=(), index=-1):
    owner.driver_remove(path, index)
    driver = owner.driver_add(path, index).driver
    driver.type = "SCRIPTED"
    for name, id_type, target, data_path in variables:
        var = driver.variables.new()
        var.name = name
        var.targets[0].id_type = id_type
        var.targets[0].id = target
        var.targets[0].data_path = data_path
    driver.expression = expression
    assert driver.is_simple_expression, expression


def flame_material(rig):
    mat = bpy.data.materials.get("Afterburner") or bpy.data.materials.new("Afterburner")
    mat.use_nodes = True
    mat.use_backface_culling = False
    # Dithered transparency would discard the fully transparent surface along
    # with its emission; blended keeps it as an additive glow.
    mat.surface_render_method = "BLENDED"
    tree = mat.node_tree
    tree.nodes.clear()
    b = Builder(tree)

    coord = b.node("ShaderNodeTexCoord", -1600, 0)
    xyz = b.node("ShaderNodeSeparateXYZ", -1400, 200)
    b.link(coord.outputs["Object"], xyz.inputs["Vector"])
    # t: 0 at the nozzle, 1 at the tail.
    t = b.math("DIVIDE", xyz.outputs["Y"], LENGTH, x=-1200, y=200)
    cooling = b.math("SUBTRACT", 1.0, b.math("MINIMUM", b.math("MAXIMUM", t, 0.0, x=-1050, y=350), 1.0, x=-900, y=350), x=-750, y=350)

    time = b.node("ShaderNodeValue", -1600, -300, name="Time", label="Time (s)")
    fps = bpy.context.scene.render.fps
    add_driver(time.outputs[0], "default_value", f"frame / {fps}")
    thrust = b.node("ShaderNodeValue", -1600, -450, name="Thrust", label="Thrust")
    add_driver(thrust.outputs[0], "default_value", "thrust", [("thrust", "OBJECT", rig, '["thrust"]')])

    # Turbulence flowing down the plume.
    flow = b.vmath("MULTIPLY", coord.outputs["Object"], (3.0, 0.7, 3.0), x=-1200, y=-100)
    flow = b.vmath("SUBTRACT", flow, b.vmath("SCALE", (0.0, 1.0, 0.0), x=-1200, y=-300, scale=b.math("MULTIPLY", time.outputs[0], 12.0, x=-1350, y=-300)), x=-1000, y=-150)
    noise = b.node("ShaderNodeTexNoise", -800, -150, noise_dimensions="4D")
    noise.inputs["Scale"].default_value = 1.5
    noise.inputs["Detail"].default_value = 4.0
    b.link(flow, noise.inputs["Vector"])
    b.link(b.math("MULTIPLY", time.outputs[0], 3.0, x=-1000, y=-350), noise.inputs["W"])
    flicker = b.math("MULTIPLY_ADD", noise.outputs["Fac"], 1.6, 0.2, x=-600, y=-150)

    # Shock diamonds: narrow bright bands, fading down the plume.
    phase = b.math("MULTIPLY", t, 2 * math.pi * SHOCK_DIAMONDS, x=-1000, y=550)
    bands = b.math("POWER", b.math("MULTIPLY_ADD", b.math("COSINE", phase, x=-850, y=550), 0.5, 0.5, x=-700, y=550), 6.0, x=-550, y=550)
    diamonds = b.math("MULTIPLY_ADD", b.math("MULTIPLY", bands, cooling, x=-400, y=550), 2.0, 1.0, x=-250, y=550)

    # Brighter where we look through more of the plume (its middle).
    facing = b.node("ShaderNodeLayerWeight", -800, 150)
    core = b.math("POWER", b.math("SUBTRACT", 1.0, facing.outputs["Facing"], x=-600, y=150), 2.0, x=-450, y=150)

    ramp = b.node("ShaderNodeValToRGB", -600, 800)
    stops = ramp.color_ramp.elements
    stops[0].position, stops[0].color = 0.0, (0.75, 0.85, 1.0, 1.0)
    stops[1].position, stops[1].color = 1.0, (0.5, 0.06, 0.01, 1.0)
    for pos, color in ((0.12, (0.45, 0.6, 1.0, 1.0)), (0.35, (1.0, 0.55, 0.18, 1.0)), (0.7, (0.9, 0.25, 0.05, 1.0))):
        stop = stops.new(pos)
        stop.color = color
    b.link(t, ramp.inputs["Fac"])

    strength = b.node("ShaderNodeValue", -1600, -600, name="Strength", label="Strength")
    strength.outputs[0].default_value = FLAME_STRENGTH
    falloff = b.math("POWER", cooling, 1.5, x=-600, y=350)
    intensity = b.math("MULTIPLY", b.math("MULTIPLY", falloff, diamonds, x=-100, y=400), b.math("MULTIPLY", flicker, core, x=-300, y=0), x=50, y=250)
    intensity = b.math("MULTIPLY", intensity, b.math("MULTIPLY", strength.outputs[0], thrust.outputs[0], x=-1400, y=-550), x=200, y=150)

    emit = b.node("ShaderNodeEmission", 400, 300)
    b.link(ramp.outputs["Color"], emit.inputs["Color"])
    b.link(intensity, emit.inputs["Strength"])
    add = b.node("ShaderNodeAddShader", 600, 200)
    b.link(b.node("ShaderNodeBsdfTransparent", 400, 50).outputs["BSDF"], add.inputs[0])
    b.link(emit.outputs["Emission"], add.inputs[1])
    out = b.node("ShaderNodeOutputMaterial", 800, 200)
    b.link(add.outputs["Shader"], out.inputs["Surface"])
    return mat


def get_object(name, data, coll, rig):
    obj = bpy.data.objects.get(name)
    if obj is not None and obj.data != data:
        bpy.data.objects.remove(obj)
        obj = None
    if obj is None:
        obj = bpy.data.objects.new(name, data)
    for c in list(obj.users_collection):
        c.objects.unlink(obj)
    coll.objects.link(obj)
    obj.parent = rig
    obj.matrix_parent_inverse.identity()
    return obj


def build(rig):
    if "thrust" not in rig:
        rig["thrust"] = 1.0
    rig.id_properties_ui("thrust").update(min=0.0, soft_max=1.5, description="Afterburner brightness and length")

    coll = bpy.data.collections.get("F15")
    mesh = flame_mesh()
    mesh.materials.append(flame_material(rig))
    for side, location in NOZZLES.items():
        flame = get_object(f"Afterburner.{side}", mesh, coll, rig)
        flame.location = location
        flame.visible_shadow = False
        add_driver(flame, "scale", "0.4 + 0.6 * thrust", [("thrust", "OBJECT", rig, '["thrust"]')], index=1)

        # Light from the plume onto the tail and stabilizers.
        name = f"AfterburnerLight.{side}"
        light = bpy.data.lights.get(name) or bpy.data.lights.new(name, "POINT")
        light.color = (1.0, 0.55, 0.25)
        light.shadow_soft_size = 0.4
        lamp = get_object(name, light, coll, rig)
        lamp.location = (location[0], location[1] + 1.2, location[2])
        add_driver(light, "energy", "400 * thrust", [("thrust", "OBJECT", rig, '["thrust"]')])


if __name__ == "__main__":
    build(bpy.data.objects[RIG])
    bpy.ops.wm.save_mainfile()
