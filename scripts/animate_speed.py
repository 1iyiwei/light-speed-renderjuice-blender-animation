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

Safe to re-run: an existing rapidity curve is kept, so hand edits survive.
"""

import math
import os
import sys

import bpy

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build_sky_shader import MAX_BETA, RIG  # noqa: E402

FPS = 30
DURATION_S = 10.0
# Reach MAX_BETA on the last frame.
FINAL_RAPIDITY = math.atanh(MAX_BETA)


def set_frame_range(scene):
    scene.render.fps = FPS
    scene.frame_start = 1
    scene.frame_end = round(FPS * DURATION_S)


def has_curve(obj, data_path):
    anim = obj.animation_data
    return bool(anim and anim.action and any(fc.data_path == data_path for fc in anim.action.fcurves))


def key_rapidity(obj, scene):
    if "rapidity" not in obj:
        obj["rapidity"] = 0.0
    obj.id_properties_ui("rapidity").update(
        min=0.0, soft_max=FINAL_RAPIDITY, precision=3,
        description="Rapidity phi; beta = tanh(phi). Linear in phi = constant thrust")
    if has_curve(obj, '["rapidity"]'):
        return
    for frame, value in ((scene.frame_start, 0.0), (scene.frame_end, FINAL_RAPIDITY)):
        obj["rapidity"] = value
        obj.keyframe_insert('["rapidity"]', frame=frame)
    for fc in obj.animation_data.action.fcurves:
        if fc.data_path == '["rapidity"]':
            for key in fc.keyframe_points:
                key.interpolation = "LINEAR"


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


if __name__ == "__main__":
    scene = bpy.context.scene
    rig = bpy.data.objects[RIG]
    set_frame_range(scene)
    key_rapidity(rig, scene)
    drive_beta(rig)
    bpy.ops.wm.save_mainfile()
