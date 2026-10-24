"""Build an asteroid field between the Earth and the Moon in light_speed.blend.

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
from build_sky_shader import MOTION, RIG, Builder, new_group  # noqa: E402

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
        rocks.append((center, radius, rotation, stretch))
    return rocks


def points_mesh(rocks):
    mesh = bpy.data.meshes.new("AsteroidPoints")
    mesh.from_pydata([tuple(r[0]) for r in rocks], [], [])
    mesh.attributes.new("radius", "FLOAT", "POINT").data.foreach_set("value", [r[1] for r in rocks])
    for name, index in (("rotation", 2), ("stretch", 3)):
        attr = mesh.attributes.new(name, "FLOAT_VECTOR", "POINT")
        attr.data.foreach_set("vector", [c for r in rocks for c in r[index]])
    old = bpy.data.meshes.get("AsteroidPoints")
    if old and old != mesh:
        old.user_remap(mesh)
        bpy.data.meshes.remove(old)
    mesh.name = "AsteroidPoints"
    return mesh


def build_field_group(material):
    """Points -> lumpy rocks (km), realized so the relativistic transform can move each vertex."""
    group = new_group("AsteroidField", "GeometryNodeTree")
    group.interface.new_socket("Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
    group.interface.new_socket("Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
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
    set_mat.inputs["Material"].default_value = material
    b.link(lumpy.outputs["Geometry"], set_mat.inputs["Geometry"])

    instance = b.node("GeometryNodeInstanceOnPoints", 100, 0)
    b.link(inp.outputs["Geometry"], instance.inputs["Points"])
    b.link(set_mat.outputs["Geometry"], instance.inputs["Instance"])
    b.link(attr("rotation", "FLOAT_VECTOR", -100), instance.inputs["Rotation"])
    b.link(b.vmath("SCALE", attr("stretch", "FLOAT_VECTOR", -250), x=-500, y=-200, scale=attr("radius", "FLOAT", -350)), instance.inputs["Scale"])
    realize = b.node("GeometryNodeRealizeInstances", 400, 0)
    b.link(instance.outputs["Instances"], realize.inputs["Geometry"])
    b.link(realize.outputs["Geometry"], out.inputs["Geometry"])
    return group


def build_material(rig):
    """Dusty grey rock, sunlit in the stars' frame, then Doppler-shifted like everything else."""
    mat = bpy.data.materials.get("AsteroidSurface") or bpy.data.materials.new("AsteroidSurface")
    mat.use_nodes = True
    mat.use_backface_culling = True
    tree = mat.node_tree
    tree.nodes.clear()
    b = Builder(tree)
    normal = b.node("ShaderNodeAttribute", -1100, 0, attribute_type="GEOMETRY", attribute_name="rest_normal")
    sun = bpy.data.objects["Sun"]
    toward_sun = (sun.matrix_world.to_3x3() @ mathutils.Vector((0.0, 0.0, 1.0))).normalized()
    lambert = b.math("MAXIMUM", b.vmath("DOT_PRODUCT", b.vmath("NORMALIZE", normal.outputs["Vector"], x=-900, y=0), tuple(toward_sun), x=-700, y=0), 0.0, x=-550, y=0)
    lit = b.vmath("SCALE", ALBEDO, x=-350, y=100, scale=b.math("MULTIPLY", lambert, SUN_RADIANCE, x=-450, y=0))
    shift = add_doppler_shift(b, rig, lit, -100, 100)
    emit = b.node("ShaderNodeEmission", 150, 100)
    b.link(shift.outputs["Color"], emit.inputs["Color"])
    b.link(emit.outputs["Emission"], b.node("ShaderNodeOutputMaterial", 350, 100).inputs["Surface"])
    return mat


def build(rig):
    scene = bpy.context.scene
    mesh = points_mesh(scatter(rig, scene))
    field = build_field_group(build_material(rig))
    body = bpy.data.node_groups["RelativisticBody"]

    obj = bpy.data.objects.get("Asteroids") or bpy.data.objects.new("Asteroids", mesh)
    obj.data = mesh
    coll = bpy.data.collections["Sky"]
    for c in list(obj.users_collection):
        c.objects.unlink(obj)
    coll.objects.link(obj)
    obj.visible_shadow = False

    obj.modifiers.clear()
    obj.modifiers.new("AsteroidField", "NODES").node_group = field
    mod = obj.modifiers.new("RelativisticBody", "NODES")
    mod.node_group = body
    ids = {s.name: s.identifier for s in body.interface.items_tree if s.in_out == "INPUT"}
    mod[ids["Camera"]] = scene.camera
    mod[ids["Center"]] = (0.0, 0.0, 0.0)
    for socket, prop in (("Beta", "beta"), ("Distance", "distance_km")):
        add_driver(obj, f'modifiers["RelativisticBody"]["{ids[socket]}"]', "v", [("v", "OBJECT", rig, f'["{prop}"]')])


if __name__ == "__main__":
    build(bpy.data.objects[RIG])
    bpy.ops.wm.save_mainfile()
