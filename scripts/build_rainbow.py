"""Add the rainbow light stripes that sweep over the F-15 in light_speed.blend.

Run headless from the project root, after animate_speed.py (saves the .blend
in place):

    blender -b light_speed.blend --python scripts/build_rainbow.py

An artistic layer, inspired by Tesla's Rainbow Road, that stays out of the
physics' way: bands of light on the plane's own skin (in the pilot's frame,
so no relativistic effects apply) sweep from nose to tail.

* Each band is a little spectrum, violet on its nose side to red on its
  tail side: a nod to the Doppler shift outside (blue ahead, red behind), and
  the whole rainbow shows from any angle, including the chase camera, which
  mostly sees the back of the plane.
* The bands scroll back at a speed proportional to the rapidity (zero at
  rest, growing through the burn, back to zero at Jupiter), capped at
  MAX_SPEED so they never strobe at 30 fps. Their offset is baked into
  F15["rainbow_offset"] from the rapidity curve.
* Brightness follows beta: invisible at rest, full near light speed.

The overlay is a shader group (RainbowOverlay) added on top of each opaque
F-15 material, in the Airframe's coordinates so the bands run continuously
across all the parts. Safe to re-run: the group is rebuilt, the materials are
wired once, and the offset is re-baked (re-run after animate_speed.py).
"""

import os
import sys

import bpy

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build_sky_shader import AIRFRAME, RIG, Builder, Interface, new_group  # noqa: E402

# Along the plane's length (Airframe +Y, nose at -9.7 m, tail at +9.7 m).
NOSE_NM, TAIL_NM = 400.0, 700.0  # each band's spectrum, violet to red
BAND_SPACING = 5.0  # meters between bands
BAND_WIDTH = 0.6  # fraction of the spacing that is lit
MAX_SPEED = 30.0  # m/s at peak rapidity: 6 bands per second at most
STRENGTH = 2.0  # emission at full brightness


def bake_offset(rig, scene):
    """F15["rainbow_offset"] (m): integral of MAX_SPEED * rapidity / peak rapidity."""
    phi = next(fc for fc in rig.animation_data.action.fcurves if fc.data_path == '["rapidity"]')
    frames = range(scene.frame_start, scene.frame_end + 1)
    peak = max(phi.evaluate(f) for f in frames) or 1.0
    action = rig.animation_data.action
    for fc in [fc for fc in action.fcurves if fc.data_path == '["rainbow_offset"]']:
        action.fcurves.remove(fc)
    rig["rainbow_offset"] = 0.0
    rig.id_properties_ui("rainbow_offset").update(description="Rainbow stripe scroll (m), baked from rapidity")
    offset = 0.0
    for f in frames:
        if f > scene.frame_start:
            offset += MAX_SPEED * 0.5 * (phi.evaluate(f - 1) + phi.evaluate(f)) / peak / scene.render.fps
        rig["rainbow_offset"] = offset
        rig.keyframe_insert('["rainbow_offset"]', frame=f)
    fc = next(fc for fc in action.fcurves if fc.data_path == '["rainbow_offset"]')
    for key in fc.keyframe_points:
        key.interpolation = "LINEAR"


def add_driver(socket, expression, variables):
    socket.driver_remove("default_value")
    driver = socket.driver_add("default_value").driver
    driver.type = "SCRIPTED"
    for name, target, data_path in variables:
        var = driver.variables.new()
        var.name = name
        var.targets[0].id = target
        var.targets[0].data_path = data_path
    driver.expression = expression
    assert driver.is_simple_expression, expression


def build_group(rig, airframe):
    group = new_group("RainbowOverlay")
    face = Interface(group)
    face.new_socket("Shader", in_out="INPUT", socket_type="NodeSocketShader")
    face.new_socket("Shader", in_out="OUTPUT", socket_type="NodeSocketShader")
    face.done()
    b = Builder(group)
    inp = b.node("NodeGroupInput", -1400, 0)
    out = b.node("NodeGroupOutput", 600, 0)

    coord = b.node("ShaderNodeTexCoord", -1400, 300, object=airframe)
    y = b.node("ShaderNodeSeparateXYZ", -1200, 300)
    b.link(coord.outputs["Object"], y.inputs["Vector"])
    y = y.outputs["Y"]

    offset = b.node("ShaderNodeValue", -1400, -200, name="Offset", label="Offset (m)")
    add_driver(offset.outputs[0], "v", [("v", rig, '["rainbow_offset"]')])
    level = b.node("ShaderNodeValue", -1400, -350, name="Brightness", label="Brightness")
    add_driver(level.outputs[0], "v", [("v", rig, '["beta"]')])

    # Bands moving toward the tail: s runs 0 -> 1 across a band, nose side to
    # tail side (outside a band it leaves [0, 1]).
    phase = b.math("FRACT", b.math("DIVIDE", b.math("SUBTRACT", y, offset.outputs[0], x=-1000, y=200), BAND_SPACING, x=-850, y=200), x=-700, y=200)
    across = b.math("DIVIDE", b.math("SUBTRACT", phase, 0.5 - 0.5 * BAND_WIDTH, x=-550, y=200), BAND_WIDTH, x=-400, y=200)
    inside = b.math("MINIMUM", b.math("MAXIMUM", across, 0.0, x=-250, y=200), 1.0, x=-100, y=200)
    # Soft hump, zero at both edges.
    mask = b.math("POWER", b.math("SINE", b.math("MULTIPLY", inside, 3.14159265, x=50, y=200), x=200, y=200), 0.7, x=350, y=200)

    # Spectrum across each band, violet on the nose side to red on the tail side.
    remap = b.node("ShaderNodeMapRange", -1000, 450, clamp=True)
    b.link(inside, remap.inputs["Value"])
    for socket, value in (("From Min", 0.0), ("From Max", 1.0), ("To Min", NOSE_NM), ("To Max", TAIL_NM)):
        remap.inputs[socket].default_value = value
    color = b.node("ShaderNodeWavelength", -800, 450)
    b.link(remap.outputs["Result"], color.inputs["Wavelength"])

    emit = b.node("ShaderNodeEmission", 200, -100)
    b.link(color.outputs["Color"], emit.inputs["Color"])
    b.link(b.math("MULTIPLY", b.math("MULTIPLY", mask, level.outputs[0], x=350, y=0), STRENGTH, x=450, y=-50), emit.inputs["Strength"])
    add = b.node("ShaderNodeAddShader", 450, 0)
    b.link(inp.outputs["Shader"], add.inputs[0])
    b.link(emit.outputs["Emission"], add.inputs[1])
    b.link(add.outputs["Shader"], out.inputs["Shader"])
    return group


def wire_materials(airframe, group):
    """Put the overlay between each opaque F-15 material's surface shader and its output (once)."""
    mats = {m for o in airframe.children_recursive if o.type == "MESH" and not o.name.startswith(("Afterburner", "Retro"))
            for m in o.data.materials if m}
    wired = []
    for mat in sorted(mats, key=lambda m: m.name):
        # Skip the canopy glass and lights: blended, see-through surfaces.
        if not mat.use_nodes or mat.surface_render_method == "BLENDED":
            continue
        tree = mat.node_tree
        output = next(n for n in tree.nodes if n.bl_idname == "ShaderNodeOutputMaterial" and n.is_active_output)
        overlay = tree.nodes.get("RainbowOverlay")
        if overlay is None:
            overlay = tree.nodes.new("ShaderNodeGroup")
            overlay.name = overlay.label = "RainbowOverlay"
            overlay.location = (output.location.x, output.location.y - 200)
        overlay.node_tree = group
        # The material's own surface shader: what feeds the overlay, or else the output.
        feed = overlay.inputs[0].links or [l for l in output.inputs["Surface"].links if l.from_node != overlay]
        shader = feed[0].from_socket if feed else next(n for n in tree.nodes if n.bl_idname == "ShaderNodeBsdfPrincipled").outputs[0]
        tree.links.new(shader, overlay.inputs[0])
        tree.links.new(overlay.outputs[0], output.inputs["Surface"])
        wired.append(mat.name)
    print(f"Rainbow overlay on {len(wired)} materials: {', '.join(wired)}")


if __name__ == "__main__":
    scene = bpy.context.scene
    rig = bpy.data.objects[RIG]
    airframe = bpy.data.objects[AIRFRAME]
    bake_offset(rig, scene)
    wire_materials(airframe, build_group(rig, airframe))
    bpy.ops.wm.save_mainfile()
