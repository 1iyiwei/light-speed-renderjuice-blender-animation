"""Clean up light_speed.blend and set up the base scene.

Run headless from the project root (saves the .blend in place):

    blender -b light_speed.blend --python scripts/setup_scene.py

Safe to re-run: existing objects are reused, not duplicated.
"""

import math

import bpy
import mathutils

STARMAP = "//assets/starmap_2020_8k.exr"

# Names of the plane's root empty, camera, and light.
RIG = "F15"
# Child of the rig holding the plane's meshes and flames, so the plane can be
# turned or banked while the rig, and the camera on it, keep facing the
# direction of travel.
AIRFRAME = "Airframe"
CAMERA = "ChaseCam"
SUN = "Sun"


def remove_leftovers():
    """Delete the old Kitbash cargo plane and the unused spaceship data."""
    for obj in [o for o in bpy.data.objects if o.name.startswith("KB3D")]:
        bpy.data.objects.remove(obj, do_unlink=True)
    for coll in [c for c in bpy.data.collections if c.name.startswith("KB3D")]:
        bpy.data.collections.remove(coll)
    for name in ("Spaceship_1", "Thruster"):
        mat = bpy.data.materials.get(name)
        if mat:
            bpy.data.materials.remove(mat)
    for img in [i for i in bpy.data.images if "Energy Beams_Thrusters" in i.name]:
        bpy.data.images.remove(img)
    bpy.data.orphans_purge(do_local_ids=True, do_linked_ids=True, do_recursive=True)


def get_collection(name):
    coll = bpy.data.collections.get(name)
    if coll is None:
        coll = bpy.data.collections.new(name)
        bpy.context.scene.collection.children.link(coll)
    return coll


def move_to_collection(obj, coll):
    for c in list(obj.users_collection):
        if c != coll:
            c.objects.unlink(obj)
    if obj.name not in coll.objects:
        coll.objects.link(obj)


def get_empty(name, coll, size):
    obj = bpy.data.objects.get(name)
    if obj is None:
        obj = bpy.data.objects.new(name, None)
        obj.empty_display_type = "ARROWS"
        obj.empty_display_size = size
    move_to_collection(obj, coll)
    return obj


def setup_plane():
    """Group the F-15 meshes under F15 > Airframe so the plane moves as a unit."""
    coll = get_collection("F15")
    rig = get_empty(RIG, coll, 5)
    airframe = get_empty(AIRFRAME, coll, 3)
    airframe.parent = rig
    for obj in [o for o in bpy.context.scene.objects if o.type == "MESH" and o.users_collection[0].name in ("F15", "Collection")]:
        move_to_collection(obj, coll)
        if obj.parent in (None, rig):
            world = obj.matrix_world.copy()
            obj.parent = airframe
            obj.matrix_world = world
    return rig


def look_at(obj, target):
    direction = mathutils.Vector(target) - obj.location
    obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()


def setup_camera_and_light(rig):
    coll = get_collection("CameraLights")

    cam = bpy.data.objects.get(CAMERA)
    if cam is None:
        cam = bpy.data.objects.new(CAMERA, bpy.data.cameras.new(CAMERA))
    move_to_collection(cam, coll)
    cam.data.lens = 35
    cam.data.clip_end = 1000
    # Behind, above and a little to the side, looking level along the flight
    # path (the plane faces -Y). Level puts the direction of travel, where the
    # relativistic sky collapses into a starbow, at the lens center, just past
    # the nose, so the plane reads as flying into it; the height shows the
    # afterburner plumes trailing toward the camera.
    cam.location = (2.5, 32, 8.5)
    look_at(cam, (2.5, 0, 8.5))
    cam.data.shift_y = -0.06
    # Ride along with the plane: the camera is in the plane's rest frame.
    cam.parent = rig
    bpy.context.scene.camera = cam

    sun = bpy.data.objects.get(SUN)
    if sun is None:
        sun = bpy.data.objects.new(SUN, bpy.data.lights.new(SUN, "SUN"))
    move_to_collection(sun, coll)
    sun.data.energy = 4
    # From behind, above and left of the chase camera: lights the side of the
    # plane we see, and the near faces of the Earth and Moon we fly toward.
    toward_sun = mathutils.Vector((0.35, 0.55, 0.75))
    sun.rotation_euler = (-toward_sun).to_track_quat("-Z", "Y").to_euler()

    # The default collection is empty once everything has been moved out.
    default = bpy.data.collections.get("Collection")
    if default and not default.objects and not default.children:
        bpy.data.collections.remove(default)


def setup_world():
    """Star map as the environment.

    Leaves the world alone once build_sky_shader.py has taken it over.
    """
    world = bpy.context.scene.world or bpy.data.worlds.new("World")
    bpy.context.scene.world = world
    world.use_nodes = True
    nodes, links = world.node_tree.nodes, world.node_tree.links
    if "Aberration" in nodes:
        return
    env = nodes.get("Starmap") or nodes.new("ShaderNodeTexEnvironment")
    env.name = env.label = "Starmap"
    env.location = (-400, 300)
    env.image = bpy.data.images.load(STARMAP, check_existing=True)
    links.new(env.outputs["Color"], nodes["Background"].inputs["Color"])
    for img in [i for i in bpy.data.images if i.users == 0]:
        bpy.data.images.remove(img)


remove_leftovers()
rig = setup_plane()
setup_camera_and_light(rig)
setup_world()
bpy.ops.wm.save_mainfile()
