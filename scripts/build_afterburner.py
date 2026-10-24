"""Build the F-15's afterburner and retro-rocket flames in light_speed.blend.

Run headless from the project root (saves the .blend in place):

    blender -b light_speed.blend --python scripts/build_afterburner.py

Relativity makes the sky contract toward the direction of travel, which the
eye reads as moving backward; a burning engine is the unmistakable "pushing
forward" cue. (No jet could get anywhere near light speed; artistic license.)

Each flame is a transparent cone with an additive emission shader: hot
blue-white at the nozzle cooling to orange, shock diamonds (the bright rings in
a supersonic exhaust), and flickering 4D noise flowing down the plume. It is
in the plane's own frame, so no relativistic effects apply. F15["thrust"]
scales brightness and length (animated by animate_speed.py).

Braking means thrusting toward where the plane is going. Rather than flipping
the plane (which no aircraft does), two forward-facing retro-rockets on the
sides of the nose take over: F15["burn_direction"] (+1 accelerating, -1
braking) picks which pair burns. From the chase camera the retro plumes reach
forward past the nose toward the bright point ahead, unmistakably braking.

Safe to re-run: flames, materials and lights are rebuilt.
"""

import math
import os
import sys

import bmesh
import bpy
import mathutils

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build_sky_shader import AIRFRAME, RIG, Builder  # noqa: E402

# Nozzle exits (meters): the afterburners measured from orthographic renders
# of the model; the retro-rockets mirror them forward, on the sides of the nose
# where it is still wide enough (half-width 0.64 m at y = -7). `yaw` turns a
# flame from pointing backward (+Y) to forward; `cant` angles it outward from
# the centerline and `pitch` up (degrees). The retro plumes are canted like an
# airliner's thrust reversers: pointing straight ahead they would hide behind
# the cockpit from the chase camera; canted, they splay into a V on both sides
# of the nose (cos 12 deg ~ 98% of the thrust still points forward; more
# cant reads as sideways, since the camera sees the forward part end-on). `burns`
# is the share of thrust a flame gets, from the burn direction d.
ENGINES = {
    "Afterburner": {"nozzles": {"L": (0.67, 8.6, 2.35), "R": (-0.67, 8.6, 2.35)}, "yaw": 0.0, "cant": 0.0, "pitch": 0.0,
                    "radius": 0.42, "tail_radius": 0.18, "length": 6.0, "burns": "max(d, 0)", "light": 400.0},
    "Retro": {"nozzles": {"L": (0.66, -7.0, 2.25), "R": (-0.66, -7.0, 2.25)}, "yaw": math.pi, "cant": 12.0, "pitch": 8.0,
              "radius": 0.24, "tail_radius": 0.12, "length": 6.0, "burns": "max(-d, 0)", "light": 300.0},
}
SHOCK_DIAMONDS = 5
# Peak emission; above ~10 the core clips to white and hides the shock diamonds.
FLAME_STRENGTH = 6.0


def flame_mesh(name, radius, tail_radius, length):
    """Open cone from the nozzle (local origin) along local +Y."""
    mesh = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=False, segments=48,
                          radius1=radius, radius2=tail_radius, depth=length)
    # create_cone is centered on Z; put the nozzle at the origin, then turn +Z into +Y.
    bmesh.ops.translate(bm, verts=bm.verts, vec=(0, 0, length / 2))
    bmesh.ops.rotate(bm, verts=bm.verts, matrix=mathutils.Matrix.Rotation(-math.pi / 2, 3, "X"))
    bm.to_mesh(mesh)
    bm.free()
    for poly in mesh.polygons:
        poly.use_smooth = True
    old = bpy.data.meshes.get(name)
    if old and old != mesh:
        old.user_remap(mesh)
        bpy.data.meshes.remove(old)
    mesh.name = name
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


def flame_material(name, rig, length, burns):
    mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
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
    t = b.math("DIVIDE", xyz.outputs["Y"], length, x=-1200, y=200)
    cooling = b.math("SUBTRACT", 1.0, b.math("MINIMUM", b.math("MAXIMUM", t, 0.0, x=-1050, y=350), 1.0, x=-900, y=350), x=-750, y=350)

    time = b.node("ShaderNodeValue", -1600, -300, name="Time", label="Time (s)")
    fps = bpy.context.scene.render.fps
    add_driver(time.outputs[0], "default_value", f"frame / {fps}")
    thrust = b.node("ShaderNodeValue", -1600, -450, name="Thrust", label="Thrust")
    add_driver(thrust.outputs[0], "default_value", f"thrust * {burns}",
               [("thrust", "OBJECT", rig, '["thrust"]'), ("d", "OBJECT", rig, '["burn_direction"]')])

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


def get_object(name, data, coll, parent):
    obj = bpy.data.objects.get(name)
    if obj is not None and obj.data != data:
        bpy.data.objects.remove(obj)
        obj = None
    if obj is None:
        obj = bpy.data.objects.new(name, data)
    for c in list(obj.users_collection):
        c.objects.unlink(obj)
    coll.objects.link(obj)
    obj.parent = parent
    obj.matrix_parent_inverse.identity()
    return obj


def build(rig):
    for name, value, desc in (("thrust", 1.0, "Afterburner and retro-rocket brightness and length"),
                              ("burn_direction", 1.0, "+1 accelerating (afterburners), -1 braking (retro-rockets)")):
        if name not in rig:
            rig[name] = value
        rig.id_properties_ui(name).update(description=desc)

    coll = bpy.data.collections.get("F15")
    airframe = bpy.data.objects[AIRFRAME]
    burn = [("thrust", "OBJECT", rig, '["thrust"]'), ("d", "OBJECT", rig, '["burn_direction"]')]
    for engine, spec in ENGINES.items():
        mesh = flame_mesh(f"{engine}Flame", spec["radius"], spec["tail_radius"], spec["length"])
        mesh.materials.append(flame_material(engine, rig, spec["length"], spec["burns"]))
        for side, location in spec["nozzles"].items():
            flame = get_object(f"{engine}.{side}", mesh, coll, airframe)
            flame.location = location
            # Local +Y is the plume; pitch it up, then turn it, outward on its own side.
            outward = math.copysign(math.radians(spec["cant"]), location[0])
            flame.rotation_euler = (math.radians(spec["pitch"]), 0.0, spec["yaw"] + (outward if spec["yaw"] else -outward))
            flame.visible_shadow = False
            add_driver(flame, "scale", "0.4 + 0.6 * thrust", burn[:1], index=1)

            # Light from the plume onto the plane, a little way down the plume.
            name = f"{engine}Light.{side}"
            light = bpy.data.lights.get(name) or bpy.data.lights.new(name, "POINT")
            light.color = (1.0, 0.55, 0.25)
            light.shadow_soft_size = 0.3
            # Shadows from the plume glow add nothing visible, and four more
            # shadow-casting lights overflow EEVEE's shadow pool.
            light.use_shadow = False
            lamp = get_object(name, light, coll, flame)
            lamp.location = (0.0, 1.2, 0.0)
            add_driver(light, "energy", f"{spec['light']} * thrust * {spec['burns']}", burn)


if __name__ == "__main__":
    build(bpy.data.objects[RIG])
    bpy.ops.wm.save_mainfile()
