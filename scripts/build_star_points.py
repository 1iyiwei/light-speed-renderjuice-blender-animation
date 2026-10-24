"""Build the catalog star field in light_speed.blend.

Run headless from the project root, after build_sky_shader.py (saves the .blend
in place):

    blender -b light_speed.blend --python scripts/build_star_points.py

Stars are points, so they must not be squeezed or stretched like a texture:
ahead of the plane they should pile up into a sparkling cluster, behind it they
should thin out, never blur into a glow or blow up into blobs. So the bright
stars come from the HYG catalog as instanced points (Geometry Nodes), and the
world shader only shows the Milky Way background (which has those stars
removed).

Each star at star-frame direction d (angle t to the motion direction) is moved
to the direction seen from the plane,
    cos t' = (cos t + beta) / (1 + beta cos t),
with Doppler factor D = gamma (1 + beta cos t). A point source's flux
scales by D ** (k - 2): surface brightness goes as D ** k (see
build_sky_shader.py), and the solid angle around it shrinks by D ** 2. Its
color is a blackbody at D times its temperature.

The look controls (beaming, exposure compensation, color shift, sky rotation)
are read via drivers from the world's DopplerShift and SkyRotation nodes, and
speed from F15["beta"], so stars and background always agree.
"""

import csv
import math
import os
import sys

import bpy

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build_sky_shader import MAX_BETA, MOTION, RIG, Builder, new_group  # noqa: E402

CATALOG = "//assets/hygdata_v41.csv"
MAG_LIMIT = 10.0
# Star-frame radiance x solid angle per unit flux 10 ** (-0.4 mag), measured
# from the NASA SVS maps (starmap minus milkyway around stars of mag < 5).
FLUX_SCALE = 2.9e-4
# Angular radius of each star, in pixels at the current camera and resolution.
STAR_SIZE_PX = 0.6
# Stars sit on a sphere around the camera, inside its clip_end.
SPHERE_RADIUS = 900.0

OBJECT = "Stars"
MESH = "StarCatalog"


def temperature(ci):
    """Blackbody temperature from B-V color index (Ballesteros 2012)."""
    return 4600.0 * (1.0 / (0.92 * ci + 1.7) + 1.0 / (0.92 * ci + 0.62))


def build_catalog_mesh():
    """Catalog stars as vertices on the unit sphere, in the star map's frame.

    The NASA maps are centered on RA 0h with RA increasing to the left, which
    is Blender's equirectangular mapping of the usual (cos dec cos ra,
    cos dec sin ra, sin dec).
    """
    positions, flux, temp = [], [], []
    with open(bpy.path.abspath(CATALOG), newline="") as f:
        for row in csv.DictReader(f):
            if row["proper"] == "Sol":
                continue
            mag = float(row["mag"])
            if mag > MAG_LIMIT:
                continue
            ra = math.radians(float(row["ra"]) * 15.0)
            dec = math.radians(float(row["dec"]))
            positions.append((math.cos(dec) * math.cos(ra), math.cos(dec) * math.sin(ra), math.sin(dec)))
            flux.append(10.0 ** (-0.4 * mag))
            temp.append(temperature(float(row["ci"]) if row["ci"] else 0.65))

    old = bpy.data.meshes.get(MESH)
    mesh = bpy.data.meshes.new(MESH)
    mesh.from_pydata(positions, [], [])
    for name, values in (("flux", flux), ("temperature", temp)):
        mesh.attributes.new(name, "FLOAT", "POINT").data.foreach_set("value", values)
    if old:
        old.user_remap(mesh)
        bpy.data.meshes.remove(old)
    mesh.name = MESH
    print(f"Star catalog: {len(positions)} stars brighter than mag {MAG_LIMIT}")
    return mesh


def build_material():
    mat = bpy.data.materials.get("StarEmission") or bpy.data.materials.new("StarEmission")
    mat.use_nodes = True
    tree = mat.node_tree
    tree.nodes.clear()
    b = Builder(tree)
    radiance = b.node("ShaderNodeAttribute", -600, -100, attribute_type="INSTANCER", attribute_name="star_radiance")
    temp = b.node("ShaderNodeAttribute", -600, 100, attribute_type="INSTANCER", attribute_name="star_temperature")
    body = b.node("ShaderNodeBlackbody", -350, 100)
    emit = b.node("ShaderNodeEmission", -100, 0)
    out = b.node("ShaderNodeOutputMaterial", 150, 0)
    b.link(temp.outputs["Fac"], body.inputs["Temperature"])
    b.link(body.outputs["Color"], emit.inputs["Color"])
    b.link(radiance.outputs["Fac"], emit.inputs["Strength"])
    b.link(emit.outputs["Emission"], out.inputs["Surface"])
    return mat


def build_node_group(material):
    group = new_group("RelativisticStars", "GeometryNodeTree")
    group.interface.new_socket("Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
    group.interface.new_socket("Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")

    def add_input(name, kind, default=None, lo=None, hi=None):
        socket = group.interface.new_socket(name, in_out="INPUT", socket_type=kind)
        if default is not None:
            socket.default_value = default
        if lo is not None:
            socket.min_value, socket.max_value = lo, hi
        return socket

    add_input("Camera", "NodeSocketObject")
    add_input("Beta", "NodeSocketFloat", 0.0, 0.0, MAX_BETA)
    add_input("Direction", "NodeSocketVector", MOTION)
    add_input("Sky Rotation", "NodeSocketVector")
    add_input("Beaming", "NodeSocketFloat", 3.0, 0.0, 4.0)
    add_input("Exposure Compensation", "NodeSocketFloat", 0.5, 0.0, 1.0)
    add_input("Color Shift", "NodeSocketFloat", 1.0, 0.0, 1.0)
    add_input("Flux Scale", "NodeSocketFloat", FLUX_SCALE)
    add_input("Star Radius", "NodeSocketFloat", 2e-4)
    add_input("Sphere Radius", "NodeSocketFloat", SPHERE_RADIUS)

    b = Builder(group)
    inp = b.node("NodeGroupInput", -2000, 0)
    out = b.node("NodeGroupOutput", 1600, 0)
    beta = inp.outputs["Beta"]

    def attr(name, y):
        n = b.node("GeometryNodeInputNamedAttribute", -1800, y, data_type="FLOAT")
        n.inputs["Name"].default_value = name
        return n.outputs["Attribute"]

    # Star-frame direction: undo the sky rotation the world applies to its
    # lookup vector, so stars and Milky Way stay registered.
    unrotate = b.node("ShaderNodeVectorRotate", -1600, 400, rotation_type="EULER_XYZ", invert=True)
    b.link(b.node("GeometryNodeInputPosition", -1800, 400).outputs["Position"], unrotate.inputs["Vector"])
    b.link(inp.outputs["Sky Rotation"], unrotate.inputs["Rotation"])
    d = b.vmath("NORMALIZE", unrotate.outputs["Vector"], x=-1400, y=400)
    n = b.vmath("NORMALIZE", inp.outputs["Direction"], x=-1400, y=200)
    cos_star = b.vmath("DOT_PRODUCT", d, n, x=-1200, y=300)

    # cos t' = (cos t + beta) / (1 + beta cos t)
    beta_cos = b.math("MULTIPLY", beta, cos_star, x=-1000, y=100)
    cos_obs = b.math("DIVIDE", b.math("ADD", cos_star, beta, x=-1000, y=300), b.math("ADD", 1.0, beta_cos, x=-850, y=100), x=-700, y=250)
    sin_obs = b.math("SQRT", b.math("MAXIMUM", b.math("SUBTRACT", 1.0, b.math("POWER", cos_obs, 2.0, x=-550, y=450), x=-400, y=450), 0.0, x=-250, y=450), x=-100, y=450)
    along = b.vmath("SCALE", n, x=-1000, y=600, scale=cos_star)
    perp = b.vmath("NORMALIZE", b.vmath("SUBTRACT", d, along, x=-800, y=600), x=-600, y=600)
    seen = b.vmath("ADD", b.vmath("SCALE", n, x=100, y=350, scale=cos_obs), b.vmath("SCALE", perp, x=100, y=550, scale=sin_obs), x=300, y=450)

    # D = gamma (1 + beta cos t), D_max = gamma (1 + beta)
    gamma = b.math("DIVIDE", 1.0, b.math("SQRT", b.math("SUBTRACT", 1.0, b.math("POWER", beta, 2.0, x=-1200, y=-200), x=-1050, y=-200), x=-900, y=-200), x=-750, y=-200)
    doppler = b.math("MULTIPLY", gamma, b.math("ADD", 1.0, beta_cos, x=-750, y=-50), x=-450, y=-100)
    peak = b.math("MULTIPLY", gamma, b.math("ADD", 1.0, beta, x=-750, y=-350), x=-600, y=-300)

    # flux gain = (D / D_max ** c) ** k / D ** 2, as the world's beaming per solid angle
    beaming = inp.outputs["Beaming"]
    exposure = b.math("POWER", peak, inp.outputs["Exposure Compensation"], x=-450, y=-300)
    gain = b.math("DIVIDE",
                  b.math("POWER", b.math("DIVIDE", doppler, exposure, x=-300, y=-200), beaming, x=-150, y=-200),
                  b.math("POWER", doppler, 2.0, x=-150, y=-350), x=0, y=-250)
    # Emission radiance of a disk of angular radius r carrying that flux.
    radius = inp.outputs["Star Radius"]
    disk = b.math("MULTIPLY", math.pi, b.math("POWER", radius, 2.0, x=0, y=-500), x=150, y=-500)
    flux = b.math("MULTIPLY", attr("flux", -600), inp.outputs["Flux Scale"], x=0, y=-650)
    radiance = b.math("DIVIDE", b.math("MULTIPLY", flux, gain, x=200, y=-350), disk, x=350, y=-400)
    shifted_temp = b.math("MULTIPLY", attr("temperature", -800), b.math("POWER", doppler, inp.outputs["Color Shift"], x=0, y=-850), x=350, y=-750)

    # Place the stars on a sphere around the camera.
    camera = b.node("GeometryNodeObjectInfo", -400, 800, transform_space="RELATIVE")
    b.link(inp.outputs["Camera"], camera.inputs["Object"])
    position = b.vmath("ADD", camera.outputs["Location"], b.vmath("SCALE", seen, x=500, y=600, scale=inp.outputs["Sphere Radius"]), x=700, y=650)
    set_pos = b.node("GeometryNodeSetPosition", 900, 200)
    b.link(inp.outputs["Geometry"], set_pos.inputs["Geometry"])
    b.link(position, set_pos.inputs["Position"])

    geometry = set_pos.outputs["Geometry"]
    for name, value, y in (("star_radiance", radiance, -100), ("star_temperature", shifted_temp, -300)):
        store = b.node("GeometryNodeStoreNamedAttribute", 1050, y, data_type="FLOAT", domain="POINT")
        store.inputs["Name"].default_value = name
        b.link(geometry, store.inputs["Geometry"])
        b.link(value, store.inputs["Value"])
        geometry = store.outputs["Geometry"]

    sphere = b.node("GeometryNodeMeshIcoSphere", 1050, -550)
    sphere.inputs["Subdivisions"].default_value = 1
    set_mat = b.node("GeometryNodeSetMaterial", 1250, -550)
    set_mat.inputs["Material"].default_value = material
    b.link(sphere.outputs["Mesh"], set_mat.inputs["Geometry"])
    instance = b.node("GeometryNodeInstanceOnPoints", 1400, 0)
    b.link(geometry, instance.inputs["Points"])
    b.link(set_mat.outputs["Geometry"], instance.inputs["Instance"])
    b.link(b.math("MULTIPLY", radius, inp.outputs["Sphere Radius"], x=1250, y=-350), instance.inputs["Scale"])
    b.link(instance.outputs["Instances"], out.inputs["Geometry"])
    return group


def add_driver(obj, path, index, id_type, target, data_path):
    obj.driver_remove(path, index)
    driver = obj.driver_add(path, index).driver
    driver.type = "AVERAGE"
    var = driver.variables.new()
    var.type = "SINGLE_PROP"
    var.targets[0].id_type = id_type
    var.targets[0].id = target
    var.targets[0].data_path = data_path


def star_radius(scene):
    """STAR_SIZE_PX pixels as an angle, for the scene camera at full resolution."""
    cam = scene.camera.data
    fov = 2.0 * math.atan(cam.sensor_width / (2.0 * cam.lens))
    return STAR_SIZE_PX * fov / scene.render.resolution_x


def build_object(mesh, group):
    scene = bpy.context.scene
    obj = bpy.data.objects.get(OBJECT)
    if obj is None:
        obj = bpy.data.objects.new(OBJECT, mesh)
    obj.data = mesh
    coll = bpy.data.collections.get("Sky") or bpy.data.collections.new("Sky")
    if coll.name not in scene.collection.children:
        scene.collection.children.link(coll)
    for c in list(obj.users_collection):
        c.objects.unlink(obj)
    coll.objects.link(obj)
    obj.visible_shadow = False

    obj.modifiers.clear()
    mod = obj.modifiers.new("StarField", "NODES")
    mod.node_group = group
    ids = {s.name: s.identifier for s in group.interface.items_tree if s.in_out == "INPUT"}
    mod[ids["Camera"]] = scene.camera
    mod[ids["Star Radius"]] = star_radius(scene)

    path = lambda name: f'modifiers["StarField"]["{ids[name]}"]'  # noqa: E731
    world = scene.world
    add_driver(obj, path("Beta"), -1, "OBJECT", bpy.data.objects[RIG], '["beta"]')
    for name in ("Beaming", "Exposure Compensation", "Color Shift"):
        add_driver(obj, path(name), -1, "WORLD", world, f'node_tree.nodes["DopplerShift"].inputs["{name}"].default_value')
    for i in range(3):
        add_driver(obj, path("Sky Rotation"), i, "WORLD", world, f'node_tree.nodes["SkyRotation"].inputs["Rotation"].default_value[{i}]')
    return obj


def build_bloom():
    """Compositor bloom, so brighter stars look bigger, as in a real camera.

    Without it tone mapping clips every star brighter than about mag 4 to the
    same white dot. Keeps the node's settings when re-run.
    """
    scene = bpy.context.scene
    scene.use_nodes = True
    tree = scene.node_tree
    glare = tree.nodes.get("StarBloom")
    if glare is None:
        glare = tree.nodes.new("CompositorNodeGlare")
        glare.name = glare.label = "StarBloom"
        glare.glare_type = "BLOOM"
        glare.inputs["Threshold"].default_value = 2.0
        glare.inputs["Strength"].default_value = 0.5
        glare.inputs["Size"].default_value = 0.4
    layers = next(n for n in tree.nodes if n.bl_idname == "CompositorNodeRLayers")
    composite = next(n for n in tree.nodes if n.bl_idname == "CompositorNodeComposite")
    glare.location = (layers.location.x + 300, layers.location.y)
    tree.links.new(layers.outputs["Image"], glare.inputs["Image"])
    tree.links.new(glare.outputs["Image"], composite.inputs["Image"])


if __name__ == "__main__":
    mesh = build_catalog_mesh()
    build_object(mesh, build_node_group(build_material()))
    build_bloom()
    bpy.ops.wm.save_mainfile()
