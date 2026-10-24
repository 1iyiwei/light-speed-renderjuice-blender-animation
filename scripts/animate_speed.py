"""Animate the plane's speed in light_speed.blend.

Run headless from the project root, after build_sky_shader.py (saves the .blend
in place):

    blender -b light_speed.blend --python scripts/animate_speed.py

Speed is keyframed as rapidity phi rather than beta: beta = tanh(phi). Rapidity
adds up linearly under constant thrust (proper acceleration), so a straight
line in phi is what the pilot feels as steady acceleration: beta creeps toward
1 but never reaches it. F15["beta"], which the shaders read, is driven by
F15["rapidity"], so edit the rapidity curve in the Graph Editor to change the
pacing.

F15["distance_km"] is baked from the rapidity curve: how far the plane has
flown in the stars' frame, for objects at real scale (Earth, Moon). The
animation clock is the pilot's proper time tau, so d(distance)/d(tau) =
c sinh(phi). Re-run this script after editing the rapidity curve.

The shot opens with HOLD_S at rest while the afterburners light
(F15["thrust"] ramps 0 -> 1), so the Earth below can register before the
plane leaves it; then constant thrust takes over.

Safe to re-run: existing rapidity and thrust curves are kept, so hand edits
survive. Pass `-- --reset` to replace them with the defaults above.
"""

import math
import os
import sys

import bpy

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build_sky_shader import MAX_BETA, RIG  # noqa: E402

FPS = 30
HOLD_S = 1.0
DURATION_S = HOLD_S + 10.0
# Reach MAX_BETA on the last frame.
FINAL_RAPIDITY = math.atanh(MAX_BETA)
C_KM_S = 299792.458


def set_frame_range(scene):
    scene.render.fps = FPS
    scene.frame_start = 1
    scene.frame_end = round(FPS * DURATION_S)


def has_curve(obj, data_path):
    anim = obj.animation_data
    return bool(anim and anim.action and any(fc.data_path == data_path for fc in anim.action.fcurves))


def remove_curve(obj, data_path):
    if has_curve(obj, data_path):
        action = obj.animation_data.action
        action.fcurves.remove(next(fc for fc in action.fcurves if fc.data_path == data_path))


def set_keys(obj, prop, keys, interpolation):
    for frame, value in keys:
        obj[prop] = value
        obj.keyframe_insert(f'["{prop}"]', frame=frame)
    for fc in obj.animation_data.action.fcurves:
        if fc.data_path == f'["{prop}"]':
            for key in fc.keyframe_points:
                key.interpolation = interpolation


def key_rapidity(obj, scene, reset):
    if "rapidity" not in obj:
        obj["rapidity"] = 0.0
    obj.id_properties_ui("rapidity").update(
        min=0.0, soft_max=FINAL_RAPIDITY, precision=3,
        description="Rapidity phi; beta = tanh(phi). Linear in phi = constant thrust")
    if reset:
        remove_curve(obj, '["rapidity"]')
    if has_curve(obj, '["rapidity"]'):
        return
    ignition = scene.frame_start + round(HOLD_S * FPS)
    set_keys(obj, "rapidity", ((scene.frame_start, 0.0), (ignition, 0.0), (scene.frame_end, FINAL_RAPIDITY)), "LINEAR")


def key_thrust(obj, scene, reset):
    """Afterburners light during the hold, at full thrust when acceleration starts."""
    if reset:
        remove_curve(obj, '["thrust"]')
    if "thrust" not in obj or has_curve(obj, '["thrust"]'):
        return
    ignition = scene.frame_start + round(HOLD_S * FPS)
    set_keys(obj, "thrust", ((scene.frame_start, 0.0), (ignition - round(0.6 * FPS), 0.0), (ignition, 1.0)), "BEZIER")


def drive_beta(obj):
    if has_curve(obj, '["beta"]'):
        obj.keyframe_delete('["beta"]')
    obj.driver_remove('["beta"]')
    driver = obj.driver_add('["beta"]').driver
    driver.type = "SCRIPTED"
    var = driver.variables.new()
    var.name = "phi"
    var.targets[0].id = obj
    var.targets[0].data_path = '["rapidity"]'
    # tanh(phi), written with exp so it runs without Python auto-run.
    driver.expression = f"min(1 - 2 / (exp(2 * phi) + 1), {MAX_BETA})"
    assert driver.is_simple_expression


def rapidity_curve(obj):
    return next(fc for fc in obj.animation_data.action.fcurves if fc.data_path == '["rapidity"]')


def bake_distance(obj, scene, substeps=16):
    """Keyframe the distance flown (km) on every frame, integrating c sinh(phi)."""
    if has_curve(obj, '["distance_km"]'):
        obj.animation_data.action.fcurves.remove(
            next(fc for fc in obj.animation_data.action.fcurves if fc.data_path == '["distance_km"]'))
    obj["distance_km"] = 0.0
    obj.id_properties_ui("distance_km").update(
        min=0.0, description="Distance flown in the stars' frame (km), baked from rapidity")
    phi = rapidity_curve(obj)
    fps = scene.render.fps
    distance = 0.0
    for frame in range(scene.frame_start, scene.frame_end + 1):
        if frame > scene.frame_start:
            # Midpoint rule over the previous frame.
            for i in range(substeps):
                f = frame - 1 + (i + 0.5) / substeps
                distance += C_KM_S * math.sinh(phi.evaluate(f)) / (fps * substeps)
        obj["distance_km"] = distance
        obj.keyframe_insert('["distance_km"]', frame=frame)
    for fc in obj.animation_data.action.fcurves:
        if fc.data_path == '["distance_km"]':
            for key in fc.keyframe_points:
                key.interpolation = "LINEAR"


if __name__ == "__main__":
    reset = "--reset" in sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else False
    scene = bpy.context.scene
    rig = bpy.data.objects[RIG]
    set_frame_range(scene)
    key_rapidity(rig, scene, reset)
    key_thrust(rig, scene, reset)
    drive_beta(rig)
    bake_distance(rig, scene)
    bpy.ops.wm.save_mainfile()
