"""Build the relativistic sky shader in light_speed.blend.

Run headless from the project root (saves the .blend in place):

    blender -b light_speed.blend --python scripts/build_sky_shader.py

The camera rides along with the plane, so everything relativistic happens
in the world shader: we see the star map as it appears to an observer moving
at speed beta (fraction of c) along a direction.

* Aberration: a ray leaving the camera at angle t' to the motion direction
  came from the star-frame angle t, where
      cos t = (cos t' - beta) / (1 - beta cos t'),
  which crowds the sky toward the direction of travel.
* Doppler factor: D = 1 / (gamma (1 - beta cos t')), > 1 ahead (blue), < 1
  behind and to the side (red); looking sideways it is 1 / gamma.
* Color shift: a blackbody at temperature T is seen as one at D T, so the
  pixel color is tinted by Blackbody(D T_ref) / Blackbody(T_ref).
* Beaming: intensity scales by D ** k (k = 3 for specific intensity, 4 for
  total power).
* Exposure compensation (artistic, not physics): divide by the peak Doppler
  factor D_max ** (k c), where D_max = gamma (1 + beta) is straight ahead and
  c in [0, 1]. With c = 1 the forward point keeps its rest brightness and the
  rest of the sky dims, like a camera auto-exposing for the bright spot.

Speed is the custom property "beta" on the F15 empty; the shader reads it via
a driver, so keyframe F15["beta"] to animate. Safe to re-run: the node groups
and world nodes are rebuilt from scratch.
"""

import bpy

RIG = "F15"
# The Milky Way without its bright stars; those are drawn as points by
# build_star_points.py.
STARMAP = "//assets/milkyway_2020_8k.exr"
# The Milky Way map is brighter than the background of the combined NASA star
# map; this brings it back to that level.
MILKY_WAY_STRENGTH = 0.6
# The plane faces -Y and flies along it.
MOTION = (0.0, -1.0, 0.0)
MAX_BETA = 0.9999


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
    old = bpy.data.node_groups.get(name)
    if old:
        bpy.data.node_groups.remove(old)
    return bpy.data.node_groups.new(name, tree_type)


def build_aberration():
    """View direction in the moving frame -> direction in the star frame."""
    group = new_group("RelativisticAberration")
    face = group.interface
    face.new_socket("View", in_out="INPUT", socket_type="NodeSocketVector")
    beta = face.new_socket("Beta", in_out="INPUT", socket_type="NodeSocketFloat")
    beta.min_value, beta.max_value = 0.0, MAX_BETA
    motion = face.new_socket("Direction", in_out="INPUT", socket_type="NodeSocketVector")
    motion.default_value = MOTION
    face.new_socket("Vector", in_out="OUTPUT", socket_type="NodeSocketVector")
    face.new_socket("Doppler", in_out="OUTPUT", socket_type="NodeSocketFloat")
    face.new_socket("Peak Doppler", in_out="OUTPUT", socket_type="NodeSocketFloat")

    b = Builder(group)
    inp = b.node("NodeGroupInput", -1200, 0)
    out = b.node("NodeGroupOutput", 1000, 0)
    beta = inp.outputs["Beta"]

    v = b.vmath("NORMALIZE", inp.outputs["View"], x=-1000, y=200)
    n = b.vmath("NORMALIZE", inp.outputs["Direction"], x=-1000, y=-100)
    cos_obs = b.vmath("DOT_PRODUCT", v, n, x=-800, y=100)

    # cos t = (cos t' - beta) / (1 - beta cos t')
    num = b.math("SUBTRACT", cos_obs, beta, x=-600, y=300)
    den = b.math("SUBTRACT", 1.0, b.math("MULTIPLY", beta, cos_obs, x=-600, y=150), x=-450, y=150)
    cos_star = b.math("DIVIDE", num, den, x=-300, y=250)
    sin_star = b.math("SQRT", b.math("MAXIMUM", b.math("SUBTRACT", 1.0, b.math("POWER", cos_star, 2.0, x=-150, y=400), x=0, y=400), 0.0, x=150, y=400), x=300, y=400)

    # Keep the azimuth around the motion axis: split v into along-axis and
    # perpendicular parts, then rebuild with the star-frame angle.
    along = b.vmath("SCALE", n, x=-600, y=-150, scale=cos_obs)
    perp = b.vmath("NORMALIZE", b.vmath("SUBTRACT", v, along, x=-400, y=-150), x=-200, y=-150)
    star_dir = b.vmath(
        "ADD",
        b.vmath("SCALE", n, x=500, y=200, scale=cos_star),
        b.vmath("SCALE", perp, x=500, y=0, scale=sin_star),
        x=700,
        y=100,
    )
    b.link(star_dir, out.inputs["Vector"])

    # D = 1 / (gamma (1 - beta cos t')), gamma = 1 / sqrt(1 - beta^2)
    gamma = b.math("DIVIDE", 1.0, b.math("SQRT", b.math("SUBTRACT", 1.0, b.math("POWER", beta, 2.0, x=-800, y=-450), x=-600, y=-450), x=-400, y=-450), x=-200, y=-450)
    drop = b.math("SUBTRACT", 1.0, b.math("MULTIPLY", beta, cos_obs, x=-400, y=-600), x=-200, y=-600)
    b.link(b.math("DIVIDE", 1.0, b.math("MULTIPLY", gamma, drop, x=0, y=-600), x=150, y=-500), out.inputs["Doppler"])
    peak = b.math("MULTIPLY", gamma, b.math("ADD", 1.0, beta, x=-200, y=-750), x=0, y=-700)
    b.link(peak, out.inputs["Peak Doppler"])
    return group


def build_doppler_shift():
    """Tint and brighten a color by the Doppler factor."""
    group = new_group("RelativisticDopplerShift")
    face = group.interface
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


def ensure_beta_property():
    rig = bpy.data.objects[RIG]
    if "beta" not in rig:
        rig["beta"] = 0.0
    ui = rig.id_properties_ui("beta")
    ui.update(min=0.0, max=MAX_BETA, soft_min=0.0, soft_max=MAX_BETA, precision=4,
              description="Speed as a fraction of the speed of light")
    return rig


def saved_inputs(tree, names):
    """Unlinked input values of the named nodes, to survive a rebuild."""
    values = {}
    for name in names:
        node = tree.nodes.get(name)
        if node is None:
            continue
        for socket in node.inputs:
            if not socket.is_linked and hasattr(socket, "default_value"):
                value = socket.default_value
                values[name, socket.identifier] = tuple(value) if hasattr(value, "__len__") else value
    return values


def restore_inputs(tree, values):
    for (name, identifier), value in values.items():
        node = tree.nodes.get(name)
        socket = node and next((s for s in node.inputs if s.identifier == identifier), None)
        if socket is not None:
            socket.default_value = value


def build_world(aberration, doppler_shift, rig):
    world = bpy.context.scene.world
    world.use_nodes = True
    tree = world.node_tree
    image = bpy.data.images.load(STARMAP, check_existing=True)
    tweaks = saved_inputs(tree, ("SkyRotation", "DopplerShift"))
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

    beta = ab.inputs["Beta"]
    beta.driver_remove("default_value")
    fcurve = beta.driver_add("default_value")
    driver = fcurve.driver
    driver.type = "AVERAGE"
    var = driver.variables.new()
    var.name = "beta"
    var.type = "SINGLE_PROP"
    var.targets[0].id_type = "OBJECT"
    var.targets[0].id = rig
    var.targets[0].data_path = '["beta"]'


if __name__ == "__main__":
    rig = ensure_beta_property()
    build_world(build_aberration(), build_doppler_shift(), rig)
    bpy.ops.wm.save_mainfile()
