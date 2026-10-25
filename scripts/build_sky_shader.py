"""Build the relativistic sky shader in light_speed.blend.

Run headless from the project root (saves the .blend in place):

    blender -b light_speed.blend --python scripts/build_sky_shader.py

The camera rides along with the plane, so everything relativistic happens
in the world shader: we see the star map as it appears to an observer moving
along a direction with rapidity phi (speed beta = tanh phi, gamma = cosh phi).
Working in rapidity rather than beta keeps the math exact near light speed,
where 1 - beta is below single-precision resolution.

* Aberration: a direction at angle t to the motion in the stars' frame is seen
  from the plane at angle t', where
      tan(t' / 2) = exp(-phi) tan(t / 2),
  which crowds the sky toward the direction of travel. (Equivalent to the
  textbook cos t' = (cos t + beta) / (1 + beta cos t).)
* Doppler factor: D = gamma (1 + beta cos t)
                    = exp(phi) cos^2(t / 2) + exp(-phi) sin^2(t / 2),
  > 1 ahead (blue), < 1 behind and to the side (red); looking sideways from
  the plane it is 1 / gamma.
* Color shift: a blackbody at temperature T is seen as one at D T, so the
  pixel color is tinted by Blackbody(D T_ref) / Blackbody(T_ref).
* Beaming: intensity scales by D ** k (k = 3 for specific intensity, 4 for
  total power).
* Exposure compensation (artistic, not physics): divide by the peak Doppler
  factor D_max ** (k c), where D_max = exp(phi) is straight ahead and
  c in [0, 1]. With c = 1 the forward point keeps its rest brightness and the
  rest of the sky dims, like a camera auto-exposing for the bright spot.

Speed is the custom property "rapidity" on the F15 empty (animated by
animate_speed.py); the shader reads it via a driver. Safe to re-run: the node
groups and world nodes are rebuilt from scratch, keeping hand-tuned values of
the look controls (pass `-- --reset` to go back to the defaults).
"""

import sys

import bpy

RIG = "F15"
AIRFRAME = "Airframe"  # child of RIG holding the plane, made by setup_scene.py
# The Milky Way without its bright stars; those are drawn as points by
# build_star_points.py.
STARMAP = "//assets/milkyway_2020_8k.exr"
# The Milky Way map is brighter than the background of the combined NASA star
# map; this brings it back to that level.
MILKY_WAY_STRENGTH = 0.6
# The plane faces -Y and flies along it.
MOTION = (0.0, -1.0, 0.0)
MAX_BETA = 0.9999
# Upper bound for the rapidity property and sockets (gamma ~ 11,000).
MAX_RAPIDITY = 10.0


class Builder:
    """Small helper for wiring node trees."""

    def __init__(self, tree):
        self.tree = tree

    def node(self, kind, x, y, **props):
        n = self.tree.nodes.new(kind)
        n.location = (x, y)
        for key, value in props.items():
            setattr(n, key, value)
        return n

    def link(self, src, dst):
        self.tree.links.new(src, dst)

    def math(self, op, a, b=None, c=None, x=0, y=0):
        n = self.node("ShaderNodeMath", x, y, operation=op)
        for socket, value in zip(n.inputs, (a, b, c)):
            if value is None:
                continue
            if isinstance(value, bpy.types.NodeSocket):
                self.link(value, socket)
            else:
                socket.default_value = value
        return n.outputs[0]

    def vmath(self, op, a, b=None, x=0, y=0, scale=None):
        n = self.node("ShaderNodeVectorMath", x, y, operation=op)
        for socket, value in zip(n.inputs, (a, b)):
            if value is None:
                continue
            if isinstance(value, bpy.types.NodeSocket):
                self.link(value, socket)
            else:
                socket.default_value = value
        if scale is not None:
            self.link(scale, n.inputs["Scale"])
        return n.outputs["Value" if op in ("DOT_PRODUCT", "LENGTH", "DISTANCE") else "Vector"]


def new_group(name, tree_type="ShaderNodeTree"):
    """A node group with no nodes, rebuilt in place if it exists.

    Declare its sockets with Interface, which keeps existing ones: deleting a
    socket would cut the links into and out of every node using the group,
    and reset their input values.
    """
    group = bpy.data.node_groups.get(name)
    if group is None or group.bl_idname != tree_type:
        return bpy.data.node_groups.new(name, tree_type)
    group.nodes.clear()
    return group


class Interface:
    """Declares a node group's sockets, reusing existing ones with the same name, direction and type."""

    def __init__(self, group):
        self.group = group
        self.kept = []

    def new_socket(self, name, in_out, socket_type):
        for item in self.group.interface.items_tree:
            if (item.item_type == "SOCKET" and item.name == name and item.in_out == in_out
                    and item.socket_type == socket_type and item not in self.kept):
                self.kept.append(item)
                return item
        item = self.group.interface.new_socket(name, in_out=in_out, socket_type=socket_type)
        self.kept.append(item)
        return item

    def done(self):
        """Remove sockets that were not declared (left over from an earlier version)."""
        for item in [i for i in self.group.interface.items_tree if i.item_type == "SOCKET" and i not in self.kept]:
            self.group.interface.remove(item)


def boost(b, d, n, phi, to_star_frame, x=0, y=0):
    """Aberrate unit direction d about the unit motion direction n, by rapidity phi.

    Forward (to_star_frame False): d is a direction in the stars' frame, the
    result is where it is seen from the plane. Inverse: d is a view direction
    from the plane, the result is the star-frame direction it looks at.
    Returns (direction, Doppler factor D).

    The half-angle form tan(t'/2) = exp(-phi) tan(t/2), with tan of the half
    angle as |d - n| / |d + n|, never subtracts nearly equal numbers, so it
    stays accurate for gamma in the thousands.
    """
    away = b.vmath("LENGTH", b.vmath("SUBTRACT", d, n, x=x, y=y + 200), x=x + 150, y=y + 200)
    toward = b.vmath("LENGTH", b.vmath("ADD", d, n, x=x, y=y + 50), x=x + 150, y=y + 50)
    half = b.math("ARCTAN2", away, toward, x=x + 300, y=y + 250)
    factor = b.math("EXPONENT", phi if to_star_frame else b.math("MULTIPLY", phi, -1.0, x=x, y=y - 100), x=x + 150, y=y - 100)
    new_half = b.math("ARCTAN2", b.math("MULTIPLY", away, factor, x=x + 300, y=y + 100), toward, x=x + 450, y=y + 150)

    # Keep the azimuth around the motion axis: rebuild from the new angle.
    perp = b.vmath("NORMALIZE", b.vmath("SUBTRACT", d, b.vmath("SCALE", n, x=x, y=y + 400, scale=b.vmath("DOT_PRODUCT", d, n, x=x - 150, y=y + 400)), x=x + 150, y=y + 400), x=x + 300, y=y + 400)
    angle = b.math("MULTIPLY", new_half, 2.0, x=x + 600, y=y + 150)
    direction = b.vmath("ADD",
                        b.vmath("SCALE", n, x=x + 750, y=y + 300, scale=b.math("COSINE", angle, x=x + 750, y=y + 150)),
                        b.vmath("SCALE", perp, x=x + 750, y=y + 450, scale=b.math("SINE", angle, x=x + 750, y=y + 50)),
                        x=x + 900, y=y + 350)

    # D = exp(phi) cos^2(t/2) + exp(-phi) sin^2(t/2), t the star-frame angle.
    star_half = new_half if to_star_frame else half
    grow = b.math("EXPONENT", phi, x=x + 450, y=y - 250)
    shrink = b.math("EXPONENT", b.math("MULTIPLY", phi, -1.0, x=x + 300, y=y - 400), x=x + 450, y=y - 400)
    cos2 = b.math("POWER", b.math("COSINE", star_half, x=x + 600, y=y - 50), 2.0, x=x + 750, y=y - 50)
    sin2 = b.math("POWER", b.math("SINE", star_half, x=x + 600, y=y - 200), 2.0, x=x + 750, y=y - 200)
    doppler = b.math("ADD", b.math("MULTIPLY", grow, cos2, x=x + 900, y=y - 100), b.math("MULTIPLY", shrink, sin2, x=x + 900, y=y - 300), x=x + 1050, y=y - 200)
    return direction, doppler


def build_aberration():
    """View direction in the moving frame -> direction in the star frame."""
    group = new_group("RelativisticAberration")
    face = Interface(group)
    face.new_socket("View", in_out="INPUT", socket_type="NodeSocketVector")
    phi = face.new_socket("Rapidity", in_out="INPUT", socket_type="NodeSocketFloat")
    phi.min_value, phi.max_value = 0.0, MAX_RAPIDITY
    motion = face.new_socket("Direction", in_out="INPUT", socket_type="NodeSocketVector")
    motion.default_value = MOTION
    face.new_socket("Vector", in_out="OUTPUT", socket_type="NodeSocketVector")
    face.new_socket("Doppler", in_out="OUTPUT", socket_type="NodeSocketFloat")
    face.new_socket("Peak Doppler", in_out="OUTPUT", socket_type="NodeSocketFloat")
    face.done()

    b = Builder(group)
    inp = b.node("NodeGroupInput", -1200, 0)
    out = b.node("NodeGroupOutput", 600, 0)
    phi = inp.outputs["Rapidity"]
    v = b.vmath("NORMALIZE", inp.outputs["View"], x=-1000, y=200)
    n = b.vmath("NORMALIZE", inp.outputs["Direction"], x=-1000, y=-100)
    star_dir, doppler = boost(b, v, n, phi, to_star_frame=True, x=-800, y=0)
    b.link(star_dir, out.inputs["Vector"])
    b.link(doppler, out.inputs["Doppler"])
    b.link(b.math("EXPONENT", phi, x=300, y=-500), out.inputs["Peak Doppler"])
    return group


def build_doppler_shift():
    """Tint and brighten a color by the Doppler factor."""
    group = new_group("RelativisticDopplerShift")
    face = Interface(group)
    face.new_socket("Color", in_out="INPUT", socket_type="NodeSocketColor")
    doppler = face.new_socket("Doppler", in_out="INPUT", socket_type="NodeSocketFloat")
    doppler.default_value = 1.0
    shift = face.new_socket("Color Shift", in_out="INPUT", socket_type="NodeSocketFloat")
    shift.default_value, shift.min_value, shift.max_value = 1.0, 0.0, 1.0
    beaming = face.new_socket("Beaming", in_out="INPUT", socket_type="NodeSocketFloat")
    beaming.default_value, beaming.min_value, beaming.max_value = 3.0, 0.0, 4.0
    peak = face.new_socket("Peak Doppler", in_out="INPUT", socket_type="NodeSocketFloat")
    peak.default_value = 1.0
    comp = face.new_socket("Exposure Compensation", in_out="INPUT", socket_type="NodeSocketFloat")
    comp.default_value, comp.min_value, comp.max_value = 0.5, 0.0, 1.0
    ref = face.new_socket("Reference Temperature", in_out="INPUT", socket_type="NodeSocketFloat")
    ref.default_value = 6500.0
    face.new_socket("Color", in_out="OUTPUT", socket_type="NodeSocketColor")
    face.done()

    b = Builder(group)
    inp = b.node("NodeGroupInput", -900, 0)
    out = b.node("NodeGroupOutput", 700, 0)
    doppler = inp.outputs["Doppler"]
    ref = inp.outputs["Reference Temperature"]

    seen = b.node("ShaderNodeBlackbody", -500, 200)
    b.link(b.math("MULTIPLY", ref, doppler, x=-700, y=200), seen.inputs["Temperature"])
    rest = b.node("ShaderNodeBlackbody", -500, 0)
    b.link(ref, rest.inputs["Temperature"])
    tint = b.vmath("DIVIDE", seen.outputs["Color"], rest.outputs["Color"], x=-300, y=150)

    mix = b.node("ShaderNodeMix", -100, 150, data_type="VECTOR")
    b.link(inp.outputs["Color Shift"], mix.inputs["Factor"])
    mix.inputs["A"].default_value = (1.0, 1.0, 1.0)
    b.link(tint, mix.inputs["B"])

    # gain = (D / D_max ** c) ** k
    beaming = inp.outputs["Beaming"]
    exposure = b.math("POWER", inp.outputs["Peak Doppler"], inp.outputs["Exposure Compensation"], x=-700, y=-250)
    gain = b.math("POWER", b.math("DIVIDE", doppler, exposure, x=-500, y=-150), beaming, x=-300, y=-150)
    tinted = b.vmath("MULTIPLY", inp.outputs["Color"], mix.outputs["Result"], x=150, y=100)
    b.link(b.vmath("SCALE", tinted, x=400, y=0, scale=gain), out.inputs["Color"])
    return group


def ensure_speed_properties():
    """F15["rapidity"] drives the shaders; F15["beta"] (driven from it by animate_speed.py) is for reading."""
    rig = bpy.data.objects[RIG]
    for name in ("rapidity", "beta"):
        if name not in rig:
            rig[name] = 0.0
    rig.id_properties_ui("rapidity").update(min=0.0, max=MAX_RAPIDITY, precision=3,
                                            description="Rapidity phi: beta = tanh(phi), gamma = cosh(phi)")
    rig.id_properties_ui("beta").update(min=0.0, max=1.0, precision=6,
                                        description="Speed as a fraction of the speed of light")
    return rig


# World nodes whose hand-tuned input values (the look controls) survive a rebuild.
TUNABLE_NODES = ("SkyRotation", "DopplerShift")


def saved_inputs(world):
    """Unlinked input values of the tunable world nodes, by node and input name.

    build_world recreates the world's nodes, so their hand-tuned values are
    read first and put back afterwards.
    """
    values = {}
    if world is None or world.node_tree is None:
        return values
    for name in TUNABLE_NODES:
        node = world.node_tree.nodes.get(name)
        if node is None:
            continue
        for socket in node.inputs:
            if not socket.is_linked and hasattr(socket, "default_value"):
                value = socket.default_value
                values[name, socket.name] = tuple(value) if hasattr(value, "__len__") else value
    return values


def restore_inputs(tree, values):
    for (name, socket_name), value in values.items():
        node = tree.nodes.get(name)
        if node is not None and socket_name in node.inputs:
            node.inputs[socket_name].default_value = value


def build_world(aberration, doppler_shift, rig, tweaks):
    world = bpy.context.scene.world
    world.use_nodes = True
    tree = world.node_tree
    image = bpy.data.images.load(STARMAP, check_existing=True)
    tree.nodes.clear()

    b = Builder(tree)
    coord = b.node("ShaderNodeTexCoord", -1200, 0)
    ab = b.node("ShaderNodeGroup", -1000, 0, node_tree=aberration, name="Aberration", label="Aberration")
    # Orients the star map relative to the flight path (art direction): what
    # lies straight ahead and behind decides how the squeezed sky looks.
    rotate = b.node("ShaderNodeVectorRotate", -780, 150, rotation_type="EULER_XYZ",
                    name="SkyRotation", label="Sky Rotation")
    env = b.node("ShaderNodeTexEnvironment", -550, 100, image=image, name="Starmap", label="Starmap")
    shift = b.node("ShaderNodeGroup", -250, 0, node_tree=doppler_shift, name="DopplerShift", label="Doppler Shift")
    bg = b.node("ShaderNodeBackground", 0, 0)
    bg.inputs["Strength"].default_value = MILKY_WAY_STRENGTH
    output = b.node("ShaderNodeOutputWorld", 200, 0)
    restore_inputs(tree, tweaks)

    # In a world shader, Generated coordinates are the view direction.
    b.link(coord.outputs["Generated"], ab.inputs["View"])
    b.link(ab.outputs["Vector"], rotate.inputs["Vector"])
    b.link(rotate.outputs["Vector"], env.inputs["Vector"])
    b.link(env.outputs["Color"], shift.inputs["Color"])
    b.link(ab.outputs["Doppler"], shift.inputs["Doppler"])
    b.link(ab.outputs["Peak Doppler"], shift.inputs["Peak Doppler"])
    b.link(shift.outputs["Color"], bg.inputs["Color"])
    b.link(bg.outputs["Background"], output.inputs["Surface"])

    speed = ab.inputs["Rapidity"]
    speed.driver_remove("default_value")
    fcurve = speed.driver_add("default_value")
    driver = fcurve.driver
    driver.type = "AVERAGE"
    var = driver.variables.new()
    var.name = "phi"
    var.type = "SINGLE_PROP"
    var.targets[0].id_type = "OBJECT"
    var.targets[0].id = rig
    var.targets[0].data_path = '["rapidity"]'


def reset_group_users(group):
    """Set unlinked inputs of group nodes using `group` outside the world to its defaults.

    The bodies' materials drive the look controls from the world; this keeps
    their other inputs (such as the reference temperature) at the defaults,
    also in files saved by earlier versions of these scripts, which reset them.
    """
    defaults = {item.name: item.default_value for item in group.interface.items_tree
                if item.item_type == "SOCKET" and item.in_out == "INPUT" and hasattr(item, "default_value")}
    for mat in bpy.data.materials:
        if not mat.use_nodes:
            continue
        for node in mat.node_tree.nodes:
            if node.bl_idname == "ShaderNodeGroup" and node.node_tree == group:
                for socket in node.inputs:
                    if not socket.is_linked and socket.name in defaults:
                        socket.default_value = defaults[socket.name]


if __name__ == "__main__":
    # `-- --reset` drops hand-tuned look controls and uses the defaults above.
    reset = "--reset" in sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else False
    tweaks = {} if reset else saved_inputs(bpy.context.scene.world)
    rig = ensure_speed_properties()
    doppler_shift = build_doppler_shift()
    build_world(build_aberration(), doppler_shift, rig, tweaks)
    reset_group_users(doppler_shift)
    bpy.ops.wm.save_mainfile()
