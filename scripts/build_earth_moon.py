"""Build the real-scale Earth and Moon in light_speed.blend.

Run headless from the project root, after animate_speed.py (saves the .blend
in place):

    blender -b light_speed.blend --python scripts/build_earth_moon.py

Stars are too far away to stream past, so on their own the shot has no sense
of forward motion. Nearby objects do stream backward past the plane, and at
real scale the numbers work out in real time: the plane skims over the Earth
in the first half second and passes the Moon at about 2.2 s (beta ~ 0.79).

Positions are in km in the stars' frame (where Earth and Moon are at rest),
with the plane starting at the origin and flying along MOTION; F15["distance_km"]
(baked by animate_speed.py) says how far it has gone. Because the bodies are at
rest in that frame, the light reaching the plane from a point on them simply
comes from that point's current direction (no light-travel-time correction).
Each vertex is then moved like a star (build_star_points.py): aberrated to its
direction as seen from the plane, and placed on a shell between NEAR and FAR
meters from the camera, ordered by the log of its true distance so the bodies
hide each other, the stars and the background correctly while staying within
the camera's clip range.

Surfaces are lit in the stars' frame (texture x sunlight on the undistorted
normal), then Doppler-shifted and beamed by the world's RelativisticDopplerShift
node group, with the same look controls as the sky.

Safe to re-run: meshes, node group and materials are rebuilt.
"""

import math
import os
import sys

import bmesh
import bpy
import mathutils

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build_sky_shader import MAX_BETA, MOTION, RIG, Builder, new_group  # noqa: E402

# Centers in km, stars' frame, relative to the plane's start. The plane starts
# about 1,300 km above the Earth, which lies ahead and below with its limb just
# under the horizon; the Moon (384,400 km from the Earth) is passed about
# 28,000 km away, up and to the right of the flight path.
EARTH_CENTER = (0.0, -4000.0, -6600.0)
MOON_CENTER = (-30000.0, -387000.0, 8000.0)
# Each body's texture is turned so that a geographic point (lat, lon, degrees)
# faces `up` and the compass heading there (degrees from north) points along
# `forward` (projected onto the surface).
BODIES = {
    # The plane starts over the Atlantic, flying east toward West Africa.
    "Earth": {"center": EARTH_CENTER, "radius": 6371.0, "segments": 512,
              "texture": "//assets/world.200412.3x5400x2700.jpg",
              "orient": ((18.0, -38.0, 90.0), tuple(-c for c in EARTH_CENTER), MOTION),
              "atmosphere": 6371.0 + 120.0},
    # Near side (lat 0, lon 0) toward the Earth, north up.
    "Moon": {"center": MOON_CENTER, "radius": 1737.4, "segments": 256,
             "texture": "//assets/lroc_color_poles_4k.tif",
             "orient": ((0.0, 0.0, 0.0), tuple(e - m for e, m in zip(EARTH_CENTER, MOON_CENTER)), (0.0, 0.0, 1.0))},
}
# Shell (meters from the camera) the bodies are drawn on: in front of the
# stars (900 m), behind the plane, inside the camera's clip_end.
NEAR, FAR = 300.0, 850.0
LOG_NEAR, LOG_FAR = 2.0, 6.0  # log10 of true distances (km) mapped to NEAR, FAR
# Diffuse radiance of a white surface under the scene's sun (irradiance / pi).
SUN_RADIANCE = 4.0 / math.pi
ATMOSPHERE_STRENGTH = 1.5


def orientation(geo, up, forward):
    """Rotation taking geographic point geo = (lat, lon, heading) to `up`, heading along `forward`.

    The sphere's UVs put north at +Z and longitude 0 at +X, east toward +Y.
    """
    lat, lon, heading = (math.radians(a) for a in geo)
    point = mathutils.Vector((math.cos(lat) * math.cos(lon), math.cos(lat) * math.sin(lon), math.sin(lat)))
    east = mathutils.Vector((-math.sin(lon), math.cos(lon), 0.0))
    north = point.cross(east)
    course = math.cos(heading) * north + math.sin(heading) * east
    geo_frame = mathutils.Matrix((point, course, point.cross(course))).transposed()
    up = mathutils.Vector(up).normalized()
    forward = mathutils.Vector(forward)
    forward = (forward - forward.dot(up) * up).normalized()
    target = mathutils.Matrix((up, forward, up.cross(forward))).transposed()
    return target @ geo_frame.transposed()


def sphere_mesh(name, radius, segments, orient):
    """UV sphere in km, centered on the origin, with a UV map for equirect textures."""
    mesh = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bm.loops.layers.uv.new("UVMap")
    bmesh.ops.create_uvsphere(bm, u_segments=segments, v_segments=segments // 2, radius=radius, calc_uvs=True)
    bmesh.ops.rotate(bm, verts=bm.verts, matrix=orientation(*orient))
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


def build_node_group():
    group = new_group("RelativisticBody", "GeometryNodeTree")
    face = group.interface
    face.new_socket("Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
    face.new_socket("Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    face.new_socket("Camera", in_out="INPUT", socket_type="NodeSocketObject")
    beta = face.new_socket("Beta", in_out="INPUT", socket_type="NodeSocketFloat")
    beta.min_value, beta.max_value = 0.0, MAX_BETA
    face.new_socket("Distance", in_out="INPUT", socket_type="NodeSocketFloat")
    face.new_socket("Direction", in_out="INPUT", socket_type="NodeSocketVector").default_value = MOTION
    face.new_socket("Center", in_out="INPUT", socket_type="NodeSocketVector")

    b = Builder(group)
    inp = b.node("NodeGroupInput", -2000, 0)
    out = b.node("NodeGroupOutput", 1800, 0)
    beta = inp.outputs["Beta"]

    # Where the vertex is relative to the plane, in the stars' frame (km).
    n = b.vmath("NORMALIZE", inp.outputs["Direction"], x=-1800, y=-200)
    plane = b.vmath("SCALE", n, x=-1600, y=-200, scale=inp.outputs["Distance"])
    world = b.vmath("ADD", b.node("GeometryNodeInputPosition", -1800, 200).outputs["Position"], inp.outputs["Center"], x=-1600, y=200)
    rel = b.vmath("SUBTRACT", world, plane, x=-1400, y=100)
    dist = b.vmath("LENGTH", rel, x=-1200, y=-100)
    d = b.vmath("NORMALIZE", rel, x=-1200, y=200)
    cos_star = b.vmath("DOT_PRODUCT", d, n, x=-1000, y=100)

    # Aberration, as for the stars: cos t' = (cos t + beta) / (1 + beta cos t)
    beta_cos = b.math("MULTIPLY", beta, cos_star, x=-800, y=-100)
    cos_obs = b.math("DIVIDE", b.math("ADD", cos_star, beta, x=-800, y=100), b.math("ADD", 1.0, beta_cos, x=-650, y=-100), x=-500, y=50)
    sin_obs = b.math("SQRT", b.math("MAXIMUM", b.math("SUBTRACT", 1.0, b.math("POWER", cos_obs, 2.0, x=-350, y=250), x=-200, y=250), 0.0, x=-50, y=250), x=100, y=250)
    along = b.vmath("SCALE", n, x=-800, y=450, scale=cos_star)
    perp = b.vmath("NORMALIZE", b.vmath("SUBTRACT", d, along, x=-600, y=450), x=-400, y=450)
    seen = b.vmath("ADD", b.vmath("SCALE", n, x=300, y=150, scale=cos_obs), b.vmath("SCALE", perp, x=300, y=350, scale=sin_obs), x=500, y=250)

    # D = gamma (1 + beta cos t)
    gamma = b.math("DIVIDE", 1.0, b.math("SQRT", b.math("SUBTRACT", 1.0, b.math("POWER", beta, 2.0, x=-800, y=-400), x=-650, y=-400), x=-500, y=-400), x=-350, y=-400)
    doppler = b.math("MULTIPLY", gamma, b.math("ADD", 1.0, beta_cos, x=-350, y=-250), x=-200, y=-300)

    # Shell radius from log10(true distance), clamped to [NEAR, FAR].
    remap = b.node("ShaderNodeMapRange", 100, -150, clamp=True)
    b.link(b.math("LOGARITHM", dist, 10.0, x=-100, y=-150), remap.inputs["Value"])
    for socket, value in (("From Min", LOG_NEAR), ("From Max", LOG_FAR), ("To Min", NEAR), ("To Max", FAR)):
        remap.inputs[socket].default_value = value
    camera = b.node("GeometryNodeObjectInfo", 300, 600, transform_space="RELATIVE")
    b.link(inp.outputs["Camera"], camera.inputs["Object"])
    position = b.vmath("ADD", camera.outputs["Location"], b.vmath("SCALE", seen, x=700, y=200, scale=remap.outputs["Result"]), x=900, y=300)

    # Keep the undistorted normal for lighting, and D for the Doppler shift.
    geometry = inp.outputs["Geometry"]
    for name, value, kind, y in (("rest_normal", b.node("GeometryNodeInputNormal", 700, -500).outputs["Normal"], "FLOAT_VECTOR", -300),
                                 ("rest_view", d, "FLOAT_VECTOR", -400),
                                 ("doppler", doppler, "FLOAT", -500)):
        store = b.node("GeometryNodeStoreNamedAttribute", 1000, y, data_type=kind, domain="POINT")
        store.inputs["Name"].default_value = name
        b.link(geometry, store.inputs["Geometry"])
        b.link(value, store.inputs["Value"])
        geometry = store.outputs["Geometry"]
    set_pos = b.node("GeometryNodeSetPosition", 1400, 0)
    b.link(geometry, set_pos.inputs["Geometry"])
    b.link(position, set_pos.inputs["Position"])
    b.link(set_pos.outputs["Geometry"], out.inputs["Geometry"])
    return group


def add_driver(owner, path, expression, variables, index=-1):
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


def add_doppler_shift(b, rig, color, x, y):
    """The world's RelativisticDopplerShift group, fed this surface's D and the sky's look controls."""
    scene = bpy.context.scene
    shift = b.node("ShaderNodeGroup", x, y, node_tree=bpy.data.node_groups["RelativisticDopplerShift"])
    b.link(color, shift.inputs["Color"])
    b.link(b.node("ShaderNodeAttribute", x - 300, y - 300, attribute_type="GEOMETRY", attribute_name="doppler").outputs["Fac"], shift.inputs["Doppler"])
    peak = b.node("ShaderNodeValue", x - 300, y - 500, name="Peak Doppler", label="Peak Doppler")
    add_driver(peak.outputs[0], "default_value", "(1 + b) / sqrt(1 - b * b)", [("b", "OBJECT", rig, '["beta"]')])
    b.link(peak.outputs[0], shift.inputs["Peak Doppler"])
    for socket in ("Beaming", "Exposure Compensation", "Color Shift"):
        add_driver(shift.inputs[socket], "default_value", "v",
                   [("v", "WORLD", scene.world, f'node_tree.nodes["DopplerShift"].inputs["{socket}"].default_value')])
    return shift


def build_material(name, texture, rig):
    mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    mat.use_nodes = True
    tree = mat.node_tree
    tree.nodes.clear()
    b = Builder(tree)

    image = b.node("ShaderNodeTexImage", -900, 300, image=bpy.data.images.load(texture, check_existing=True))
    image.interpolation = "Cubic"
    normal = b.node("ShaderNodeAttribute", -1100, 0, attribute_type="GEOMETRY", attribute_name="rest_normal")
    sun = bpy.data.objects["Sun"]
    toward_sun = (sun.matrix_world.to_3x3() @ mathutils.Vector((0.0, 0.0, 1.0))).normalized()
    lambert = b.math("MAXIMUM", b.vmath("DOT_PRODUCT", b.vmath("NORMALIZE", normal.outputs["Vector"], x=-900, y=0), tuple(toward_sun), x=-700, y=0), 0.0, x=-550, y=0)
    lit = b.vmath("SCALE", image.outputs["Color"], x=-350, y=200, scale=b.math("MULTIPLY", lambert, SUN_RADIANCE, x=-400, y=0))

    shift = add_doppler_shift(b, rig, lit, -100, 100)

    emit = b.node("ShaderNodeEmission", 150, 100)
    b.link(shift.outputs["Color"], emit.inputs["Color"])
    out = b.node("ShaderNodeOutputMaterial", 350, 100)
    b.link(emit.outputs["Emission"], out.inputs["Surface"])
    mat.use_backface_culling = True
    return mat


def build_atmosphere_material(rig):
    """Additive blue haze, strongest where we look through the shell edge-on."""
    mat = bpy.data.materials.get("EarthAtmosphere") or bpy.data.materials.new("EarthAtmosphere")
    mat.use_nodes = True
    mat.surface_render_method = "BLENDED"
    mat.use_backface_culling = True
    tree = mat.node_tree
    tree.nodes.clear()
    b = Builder(tree)
    normal = b.vmath("NORMALIZE", b.node("ShaderNodeAttribute", -1300, 0, attribute_type="GEOMETRY", attribute_name="rest_normal").outputs["Vector"], x=-1100, y=0)
    view = b.node("ShaderNodeAttribute", -1300, -200, attribute_type="GEOMETRY", attribute_name="rest_view").outputs["Vector"]
    # Edge-on through the shell (normal across the line of sight) glows most.
    facing = b.math("ABSOLUTE", b.vmath("DOT_PRODUCT", normal, view, x=-900, y=-100), x=-750, y=-100)
    rim = b.math("POWER", b.math("SUBTRACT", 1.0, facing, x=-600, y=-100), 4.0, x=-450, y=-100)
    sun = bpy.data.objects["Sun"]
    toward_sun = (sun.matrix_world.to_3x3() @ mathutils.Vector((0.0, 0.0, 1.0))).normalized()
    # Sunlit side only, with a little scattering past the terminator.
    day = b.math("MULTIPLY_ADD", b.vmath("DOT_PRODUCT", normal, tuple(toward_sun), x=-900, y=150), 0.8, 0.25, x=-750, y=150)
    day = b.math("MAXIMUM", day, 0.0, x=-600, y=150)
    glow = b.vmath("SCALE", (0.3, 0.55, 1.0), x=-250, y=50, scale=b.math("MULTIPLY", b.math("MULTIPLY", rim, day, x=-450, y=100), ATMOSPHERE_STRENGTH, x=-350, y=100))
    shift = add_doppler_shift(b, rig, glow, -50, 50)
    emit = b.node("ShaderNodeEmission", 200, 50)
    b.link(shift.outputs["Color"], emit.inputs["Color"])
    add = b.node("ShaderNodeAddShader", 400, 0)
    b.link(b.node("ShaderNodeBsdfTransparent", 200, -100).outputs["BSDF"], add.inputs[0])
    b.link(emit.outputs["Emission"], add.inputs[1])
    b.link(add.outputs["Shader"], b.node("ShaderNodeOutputMaterial", 600, 0).inputs["Surface"])
    return mat


def build_body(name, spec, group, rig):
    mesh = sphere_mesh(name, spec["radius"], spec["segments"], spec["orient"])
    mesh.materials.clear()
    mesh.materials.append(build_material(f"{name}Surface", spec["texture"], rig))
    place_object(name, mesh, spec, group, rig)
    if "atmosphere" in spec:
        shell = sphere_mesh(f"{name}Atmosphere", spec["atmosphere"], spec["segments"], spec["orient"])
        shell.materials.clear()
        shell.materials.append(build_atmosphere_material(rig))
        place_object(f"{name}Atmosphere", shell, spec, group, rig)


def place_object(name, mesh, spec, group, rig):
    scene = bpy.context.scene

    obj = bpy.data.objects.get(name) or bpy.data.objects.new(name, mesh)
    obj.data = mesh
    coll = bpy.data.collections["Sky"]
    for c in list(obj.users_collection):
        c.objects.unlink(obj)
    coll.objects.link(obj)
    obj.visible_shadow = False

    obj.modifiers.clear()
    mod = obj.modifiers.new("RelativisticBody", "NODES")
    mod.node_group = group
    ids = {s.name: s.identifier for s in group.interface.items_tree if s.in_out == "INPUT"}
    mod[ids["Camera"]] = scene.camera
    mod[ids["Center"]] = spec["center"]
    for socket, prop in (("Beta", "beta"), ("Distance", "distance_km")):
        add_driver(obj, f'modifiers["RelativisticBody"]["{ids[socket]}"]', "v", [("v", "OBJECT", rig, f'["{prop}"]')])


if __name__ == "__main__":
    rig = bpy.data.objects[RIG]
    group = build_node_group()
    for name, spec in BODIES.items():
        build_body(name, spec, group, rig)
    bpy.ops.wm.save_mainfile()
