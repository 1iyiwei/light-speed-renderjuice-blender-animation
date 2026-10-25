"""Build an asteroid (and RenderJuice can) field between the Earth and the Moon in light_speed.blend.

Run headless from the project root, after build_earth_moon.py (saves the .blend
in place):

    blender -b light_speed.blend --python scripts/build_asteroids.py

Forward motion reads from things streaming outward past you. Beyond the Moon
the plane is so fast (gamma in the hundreds by Mars) that anything passes in a
fraction of a frame, so this is the stretch where it can work: rocks scattered
along the first ~400,000 km, timed to pass steadily over the first seconds of
thrust. Early on they spray outward from the direction of travel; as beta
climbs, aberration bends them forward and squeezes them toward the starbow.

The density is artistic license (the real space between Earth and Moon is
nearly empty); their motion is real scale. Rocks are at rest in the stars'
frame and go through the same RelativisticBody transform as the Earth and
Moon, after a first modifier builds them (in km) from points.

A share of the rocks are RenderJuice cans instead (CAN_FRACTION): the
contest sponsor's energy drink, tumbling past at real-scale motion (their size
is a joke: thousands of km tall, to stay visible like the rocks). Everything
tumbles slowly on Earth's clock (the stars' frame, where the field is at rest).

Safe to re-run: the field is regenerated from SEED.
"""

import math
import os
import random
import sys

import bpy
import mathutils

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build_earth_moon import EARTH_CENTER, SUN_RADIANCE, add_doppler_shift, add_driver  # noqa: E402
from build_sky_shader import MOTION, RIG, Builder, Interface, new_group  # noqa: E402

SEED = 7
COUNT = 700
# Seconds after the start of the shot over which rocks pass (uniformly).
PASS_START_S, PASS_END_S = 1.15, 4.3
# Closest-approach distance from the flight path (km), log-uniform.
MISS_MIN, MISS_MAX = 1500.0, 40000.0
# Rock radius as a fraction of its miss distance, so each one is visible
# (about 1 to 3.5 degrees across at closest approach, about half that while
# still in frame) as it goes by.
SIZE_MIN, SIZE_MAX = 0.01, 0.03
ALBEDO = (0.4, 0.37, 0.33)
EARTH_CLEARANCE = 7000.0  # km from the Earth's center
# Cans: share of the field, size relative to a rock, and proportions (a can
# is 1 unit tall). Colors from the RenderJuice logo.
CAN_FRACTION = 0.3
CAN_SCALE = 2.5
CAN_RADIUS = 0.27
# Deep enough to stay purple through the AgX view transform.
CAN_PURPLE = (0.2, 0.06, 0.65)
CAN_RIM = (0.6, 0.55, 0.78)
# One big can floating ahead during the ignition hold, label toward the
# camera; the moment thrust starts it whips past. (center in km, height in
# km, starting rotation, spin)
# Between the Earth's limb (about 5 degrees below level there; beyond the
# horizon the Earth hides it) and the top of the frame (only ~8 degrees above
# level, the camera being shifted down), and far enough ahead to stay through
# the ignition ramp at the end of the hold.
# It starts with the logo toward the camera and turns, over the hold, to
# show the rest of the wordmark.
HERO_CANS = [((-5000.0, -15000.0, 150.0), 2100.0, (0.1, 0.2, -0.5 * math.pi - 0.25), (0.05, 0.08, -0.4))]
LABEL = "//assets/RenderJuice-Logo-Pack/RenderJuice-Local-Wordmarks/horizontal-large/renderjuice-lockup-white-transparent.png"
LABEL_ASPECT = 3020 / 960  # the wordmark image's width / height
# Tumbling (radians per second of Earth time), rocks and cans.
ROCK_SPIN, CAN_SPIN = 0.3, 1.5


def scatter(rig, scene):
    """Rock centers (km, stars' frame) and per-rock radius, rotation and stretch."""
    distance = next(fc for fc in rig.animation_data.action.fcurves if fc.data_path == '["distance_km"]')
    n = mathutils.Vector(MOTION).normalized()
    side = n.orthogonal().normalized()
    up = n.cross(side)
    earth = mathutils.Vector(EARTH_CENTER)
    rng = random.Random(SEED)
    rocks = []
    while len(rocks) < COUNT:
        frame = scene.frame_start + rng.uniform(PASS_START_S, PASS_END_S) * scene.render.fps
        miss = math.exp(rng.uniform(math.log(MISS_MIN), math.log(MISS_MAX)))
        angle = rng.uniform(0.0, 2.0 * math.pi)
        center = distance.evaluate(frame) * n + miss * (math.cos(angle) * side + math.sin(angle) * up)
        if (center - earth).length < EARTH_CLEARANCE:
            continue
        radius = miss * rng.uniform(SIZE_MIN, SIZE_MAX)
        rotation = [rng.uniform(0.0, 2.0 * math.pi) for _ in range(3)]
        stretch = [rng.uniform(0.6, 1.3) for _ in range(3)]
        rocks.append([center, radius, rotation, stretch])
    # Which are cans, and how everything tumbles, from a separate stream so
    # the rocks' layout does not change.
    rng = random.Random(SEED + 1)
    for rock in rocks:
        can = rng.random() < CAN_FRACTION
        spin = CAN_SPIN if can else ROCK_SPIN
        if can:
            rock[1] *= CAN_SCALE
            rock[3] = [1.0, 1.0, 1.0]
        rock += [float(can), [rng.uniform(-spin, spin) for _ in range(3)]]
    for center, height, rotation, spin in HERO_CANS:
        rocks.append([mathutils.Vector(center), height, list(rotation), [1.0, 1.0, 1.0], 1.0, list(spin)])
    return rocks


def points_mesh(rocks):
    mesh = bpy.data.meshes.new("AsteroidPoints")
    mesh.from_pydata([tuple(r[0]) for r in rocks], [], [])
    mesh.attributes.new("radius", "FLOAT", "POINT").data.foreach_set("value", [r[1] for r in rocks])
    mesh.attributes.new("can", "FLOAT", "POINT").data.foreach_set("value", [r[4] for r in rocks])
    for name, index in (("rotation", 2), ("stretch", 3), ("spin", 5)):
        attr = mesh.attributes.new(name, "FLOAT_VECTOR", "POINT")
        attr.data.foreach_set("vector", [c for r in rocks for c in r[index]])
    old = bpy.data.meshes.get("AsteroidPoints")
    if old and old != mesh:
        old.user_remap(mesh)
        bpy.data.meshes.remove(old)
    mesh.name = "AsteroidPoints"
    return mesh


def build_field_group(rock_material, can_material, rim_material):
    """Points -> lumpy rocks and cans (km), realized so the relativistic transform can move each vertex."""
    group = new_group("AsteroidField", "GeometryNodeTree")
    face = Interface(group)
    face.new_socket("Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
    face.new_socket("Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    face.new_socket("Time", in_out="INPUT", socket_type="NodeSocketFloat")
    face.done()
    b = Builder(group)
    inp = b.node("NodeGroupInput", -1200, 0)
    out = b.node("NodeGroupOutput", 800, 0)

    def attr(name, kind, y):
        n = b.node("GeometryNodeInputNamedAttribute", -800, y, data_type=kind)
        n.inputs["Name"].default_value = name
        return n.outputs["Attribute"]

    # One lumpy unit rock; rotation and stretch make each instance different.
    rock = b.node("GeometryNodeMeshIcoSphere", -1000, -400)
    rock.inputs["Subdivisions"].default_value = 3
    noise = b.node("ShaderNodeTexNoise", -1000, -650)
    noise.inputs["Scale"].default_value = 1.2
    noise.inputs["Detail"].default_value = 3.0
    bump = b.vmath("SCALE", b.node("GeometryNodeInputNormal", -1000, -850).outputs["Normal"], x=-800, y=-750,
                   scale=b.math("MULTIPLY", b.math("SUBTRACT", noise.outputs["Fac"], 0.5, x=-850, y=-600), 0.8, x=-700, y=-600))
    lumpy = b.node("GeometryNodeSetPosition", -500, -400)
    b.link(rock.outputs["Mesh"], lumpy.inputs["Geometry"])
    b.link(bump, lumpy.inputs["Offset"])
    set_mat = b.node("GeometryNodeSetMaterial", -300, -400)
    set_mat.inputs["Material"].default_value = rock_material
    b.link(lumpy.outputs["Geometry"], set_mat.inputs["Geometry"])

    # One unit can (1 tall, centered): a body with its label coordinates,
    # and narrower rims at both ends.
    body = b.node("GeometryNodeMeshCylinder", -1000, -1100)
    body.inputs["Vertices"].default_value = 48
    body.inputs["Radius"].default_value = CAN_RADIUS
    body.inputs["Depth"].default_value = 1.0
    # The cylinder's own UV map (per face corner, so its seam stays sharp): on
    # the side, u runs around from the seam at +X and v from 0.5 at the top to
    # 1 at the bottom. Label coordinates: u around (label centered at u = 0.5,
    # the -X side), height 0 at the bottom to 1 at the top.
    uv = b.node("ShaderNodeSeparateXYZ", -800, -1300)
    b.link(body.outputs["UV Map"], uv.inputs["Vector"])
    label_uv = b.node("ShaderNodeCombineXYZ", -200, -1300)
    b.link(uv.outputs["X"], label_uv.inputs["X"])
    b.link(b.math("MULTIPLY", b.math("SUBTRACT", 1.0, uv.outputs["Y"], x=-600, y=-1400), 2.0, x=-450, y=-1400), label_uv.inputs["Y"])
    store = b.node("GeometryNodeStoreNamedAttribute", 0, -1100, data_type="FLOAT_VECTOR", domain="CORNER")
    store.inputs["Name"].default_value = "can_uv"
    b.link(body.outputs["Mesh"], store.inputs["Geometry"])
    b.link(label_uv.outputs["Vector"], store.inputs["Value"])
    body_mat = b.node("GeometryNodeSetMaterial", 200, -1100)
    body_mat.inputs["Material"].default_value = can_material
    b.link(store.outputs["Geometry"], body_mat.inputs["Geometry"])
    # Rims: open rings standing on the body's ends, sharing no surface with it.
    # (Any surface inside or flush with another would z-fight: everything far
    # away is drawn on a shell hundreds of meters out, where the depth buffer
    # resolves only tens of centimeters.)
    rim = b.node("GeometryNodeMeshCylinder", -1000, -1600, fill_type="NONE")
    rim.inputs["Vertices"].default_value = 48
    rim.inputs["Radius"].default_value = 0.9 * CAN_RADIUS
    rim.inputs["Depth"].default_value = 0.03
    rim_mat = b.node("GeometryNodeSetMaterial", 200, -1600)
    rim_mat.inputs["Material"].default_value = rim_material
    b.link(rim.outputs["Mesh"], rim_mat.inputs["Geometry"])
    can = b.node("GeometryNodeJoinGeometry", 400, -1300)
    b.link(body_mat.outputs["Geometry"], can.inputs["Geometry"])
    for z in (0.515, -0.515):
        lift = b.node("GeometryNodeTransform", 300, -1600 - 150 * (z < 0))
        lift.inputs["Translation"].default_value = (0.0, 0.0, z)
        b.link(rim_mat.outputs["Geometry"], lift.inputs["Geometry"])
        b.link(lift.outputs["Geometry"], can.inputs["Geometry"])

    # Tumbling: the starting orientation plus spin x Earth time.
    rotation = b.vmath("ADD", attr("rotation", "FLOAT_VECTOR", -100),
                       b.vmath("SCALE", attr("spin", "FLOAT_VECTOR", -150), x=-500, y=-50, scale=inp.outputs["Time"]), x=-300, y=-100)
    scale = b.vmath("SCALE", attr("stretch", "FLOAT_VECTOR", -250), x=-500, y=-200, scale=attr("radius", "FLOAT", -350))
    is_can = b.math("GREATER_THAN", attr("can", "FLOAT", -500), 0.5, x=-500, y=-500)
    instanced = b.node("GeometryNodeJoinGeometry", 600, 0)
    for shape, selection, y in ((set_mat.outputs["Geometry"], b.math("SUBTRACT", 1.0, is_can, x=-300, y=-500), 100),
                                (can.outputs["Geometry"], is_can, -200)):
        instance = b.node("GeometryNodeInstanceOnPoints", 100, y)
        b.link(inp.outputs["Geometry"], instance.inputs["Points"])
        b.link(selection, instance.inputs["Selection"])
        b.link(shape, instance.inputs["Instance"])
        b.link(rotation, instance.inputs["Rotation"])
        b.link(scale, instance.inputs["Scale"])
        b.link(instance.outputs["Instances"], instanced.inputs["Geometry"])
    realize = b.node("GeometryNodeRealizeInstances", 800, 0)
    b.link(instanced.outputs["Geometry"], realize.inputs["Geometry"])
    b.link(realize.outputs["Geometry"], out.inputs["Geometry"])
    return group


def label_albedo(b):
    """Purple can with the white RenderJuice wordmark wrapped around its front half."""
    uv = b.node("ShaderNodeSeparateXYZ", -1300, 400)
    b.link(b.node("ShaderNodeAttribute", -1500, 400, attribute_type="GEOMETRY", attribute_name="can_uv").outputs["Vector"], uv.inputs["Vector"])
    # The label spans half the circumference; its height keeps the image's aspect.
    height = (math.pi * CAN_RADIUS) / LABEL_ASPECT
    coord = b.node("ShaderNodeCombineXYZ", -900, 400)
    b.link(b.math("DIVIDE", b.math("SUBTRACT", uv.outputs["X"], 0.25, x=-1100, y=450), 0.5, x=-1000, y=450), coord.inputs["X"])
    b.link(b.math("ADD", b.math("DIVIDE", b.math("SUBTRACT", uv.outputs["Y"], 0.5, x=-1100, y=350), height, x=-1000, y=350), 0.5, x=-900, y=300), coord.inputs["Y"])
    label = b.node("ShaderNodeTexImage", -700, 400, image=bpy.data.images.load(LABEL, check_existing=True), extension="CLIP")
    b.link(coord.outputs["Vector"], label.inputs["Vector"])
    mix = b.node("ShaderNodeMix", -450, 300, data_type="RGBA")
    b.link(label.outputs["Alpha"], mix.inputs["Factor"])
    mix.inputs["A"].default_value = (*CAN_PURPLE, 1.0)
    b.link(label.outputs["Color"], mix.inputs["B"])
    return mix.outputs["Result"]


def build_material(rig, name, albedo):
    """A surface sunlit in the stars' frame, then Doppler-shifted like everything else.

    albedo is a color, or a function building the albedo socket.
    """
    mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    mat.use_nodes = True
    mat.use_backface_culling = True
    tree = mat.node_tree
    tree.nodes.clear()
    b = Builder(tree)
    normal = b.node("ShaderNodeAttribute", -1100, 0, attribute_type="GEOMETRY", attribute_name="rest_normal")
    sun = bpy.data.objects["Sun"]
    toward_sun = (sun.matrix_world.to_3x3() @ mathutils.Vector((0.0, 0.0, 1.0))).normalized()
    lambert = b.math("MAXIMUM", b.vmath("DOT_PRODUCT", b.vmath("NORMALIZE", normal.outputs["Vector"], x=-900, y=0), tuple(toward_sun), x=-700, y=0), 0.0, x=-550, y=0)
    color = albedo(b) if callable(albedo) else albedo
    lit = b.vmath("SCALE", color, x=-350, y=100, scale=b.math("MULTIPLY", lambert, SUN_RADIANCE, x=-450, y=0))
    shift = add_doppler_shift(b, rig, lit, -100, 100)
    emit = b.node("ShaderNodeEmission", 150, 100)
    b.link(shift.outputs["Color"], emit.inputs["Color"])
    b.link(emit.outputs["Emission"], b.node("ShaderNodeOutputMaterial", 350, 100).inputs["Surface"])
    return mat


def build(rig):
    scene = bpy.context.scene
    mesh = points_mesh(scatter(rig, scene))
    field = build_field_group(build_material(rig, "AsteroidSurface", ALBEDO),
                              build_material(rig, "CanSurface", label_albedo),
                              build_material(rig, "CanRim", CAN_RIM))
    body = bpy.data.node_groups["RelativisticBody"]

    obj = bpy.data.objects.get("Asteroids") or bpy.data.objects.new("Asteroids", mesh)
    obj.data = mesh
    coll = bpy.data.collections["Sky"]
    for c in list(obj.users_collection):
        c.objects.unlink(obj)
    coll.objects.link(obj)
    obj.parent = None
    obj.visible_shadow = False

    obj.modifiers.clear()
    shapes = obj.modifiers.new("AsteroidField", "NODES")
    shapes.node_group = field
    time = next(s.identifier for s in field.interface.items_tree if s.name == "Time")
    add_driver(obj, f'modifiers["AsteroidField"]["{time}"]', "v", [("v", "OBJECT", rig, '["earth_time_s"]')])
    mod = obj.modifiers.new("RelativisticBody", "NODES")
    mod.node_group = body
    ids = {s.name: s.identifier for s in body.interface.items_tree if s.in_out == "INPUT"}
    mod[ids["Camera"]] = scene.camera
    mod[ids["Center"]] = (0.0, 0.0, 0.0)
    for socket, prop in (("Rapidity", "rapidity"), ("Distance", "distance_km")):
        add_driver(obj, f'modifiers["RelativisticBody"]["{ids[socket]}"]', "v", [("v", "OBJECT", rig, f'["{prop}"]')])


if __name__ == "__main__":
    build(bpy.data.objects[RIG])
    bpy.ops.wm.save_mainfile()
