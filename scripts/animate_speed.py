"""Animate the trip in light_speed.blend: Earth to Jupiter, accelerate, coast, brake.

Run headless from the project root, after build_afterburner.py (saves the
.blend in place):

    blender -b light_speed.blend --python scripts/animate_speed.py

Thrust is the one animated control; everything else follows from it:

* F15["thrust"] (>= 0) sets the afterburners' size and the acceleration.
  It grows during each burn, so a bigger flame goes with faster acceleration
  (and gives the eye a speed cue the contracting sky doesn't).
* F15["burn_direction"] is +1 while accelerating (the afterburners burn) and
  -1 while braking (the forward-facing retro-rockets burn instead; see
  build_afterburner.py). The plane keeps its heading throughout.

Rapidity phi (beta = tanh phi) is baked from them: the animation clock is the
pilot's proper time tau, and under thrust d(phi)/d(tau) = rate * thrust *
burn_direction. The rate is solved for so that the trip covers TRIP_KM: the
plane leaves the Earth, collapses the sky ahead to a point at peak gamma
(several hundred), unwinds it while braking, and comes to rest STANDOFF_KM
short of Jupiter (placed by build_earth_moon.py from the baked distance).
F15["distance_km"], the distance flown in the stars' frame, grows as
c sinh(phi) per unit proper time, and F15["earth_time_s"], the time on Earth's
(the stars' frame) clocks, as cosh(phi): about 35 minutes for the pilot's 25
seconds. F15["beta"] is driven from the rapidity for
reading only.

Safe to re-run: hand-edited thrust and burn_direction curves are kept
(re-run after editing them to re-bake). Pass `-- --reset` to replace them with
the defaults below.
"""

import math
import os
import sys

import bpy

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build_sky_shader import AIRFRAME, MAX_RAPIDITY, RIG  # noqa: E402

FPS = 30
C_KM_S = 299792.458
AU_KM = 1.496e8
# Jupiter at its closest to Earth, if the planets lined up along the flight path.
JUPITER_KM = 4.2 * AU_KM
# Where the plane stops, short of Jupiter's center (radius 69,911 km): close
# enough for Jupiter to fill a good part of the frame, with room above it.
STANDOFF_KM = 500000.0
TRIP_KM = JUPITER_KM - STANDOFF_KM

# Timeline (seconds).
HOLD_S = 1.0  # at rest while the afterburners light
IGNITION_S = 0.6  # thrust ramps up over the end of the hold
BURN_S = 10.0  # accelerating
CUT_S = 0.2  # thrust cut at the end of a burn
COAST_S = 1.0  # engines off, switching from afterburners to retro-rockets
BRAKE_S = BURN_S
ARRIVE_S = 4.0  # at rest at Jupiter, with room for the end card
# Thrust at the start and end of each burn (braking mirrors accelerating).
THRUST_LOW, THRUST_HIGH = 0.6, 1.4

SUBSTEPS = 16


def frame(seconds):
    return 1 + round(seconds * FPS)


def matches(fc, data_path, index):
    return fc.data_path == data_path and (index is None or fc.array_index == index)


def has_curve(obj, data_path, index=None):
    anim = obj.animation_data
    return bool(anim and anim.action and any(matches(fc, data_path, index) for fc in anim.action.fcurves))


def get_curve(obj, data_path, index=0):
    return next(fc for fc in obj.animation_data.action.fcurves if matches(fc, data_path, index))


def remove_curve(obj, data_path, index=None):
    while has_curve(obj, data_path, index):
        action = obj.animation_data.action
        action.fcurves.remove(next(fc for fc in action.fcurves if matches(fc, data_path, index)))


def set_keys(obj, prop, keys, interpolation):
    for f, value in keys:
        obj[prop] = value
        obj.keyframe_insert(f'["{prop}"]', frame=f)
    for key in get_curve(obj, f'["{prop}"]').keyframe_points:
        key.interpolation = interpolation


def timeline():
    burn_end = HOLD_S + BURN_S
    brake_start = burn_end + COAST_S
    brake_end = brake_start + BRAKE_S
    return burn_end, brake_start, brake_end, brake_end + IGNITION_S + ARRIVE_S


def key_controls(rig, airframe, scene, reset):
    burn_end, brake_start, brake_end, end = timeline()
    scene.render.fps = FPS
    scene.frame_start = 1
    scene.frame_end = frame(end)

    for name, desc in (("thrust", "Afterburner size and acceleration (>= 0)"),
                       ("burn_direction", "+1 accelerating, -1 braking")):
        if name not in rig:
            rig[name] = 0.0
        rig.id_properties_ui(name).update(description=desc)
    if reset:
        remove_curve(rig, '["thrust"]')
        remove_curve(rig, '["burn_direction"]')
    # The plane no longer flips to brake (an earlier version did).
    remove_curve(airframe, "rotation_euler", 2)
    airframe.rotation_euler = (0.0, 0.0, 0.0)

    if not has_curve(rig, '["thrust"]'):
        # Linear keys, braking the mirror image of accelerating, so the
        # braking burn takes off exactly the rapidity the first one built up.
        set_keys(rig, "thrust", (
            (frame(0), 0.0), (frame(HOLD_S - IGNITION_S), 0.0), (frame(HOLD_S), THRUST_LOW),
            (frame(burn_end), THRUST_HIGH), (frame(burn_end + CUT_S), 0.0),
            (frame(brake_start - CUT_S), 0.0), (frame(brake_start), THRUST_HIGH),
            (frame(brake_end), THRUST_LOW), (frame(brake_end + IGNITION_S), 0.0),
        ), "LINEAR")
    if not has_curve(rig, '["burn_direction"]'):
        set_keys(rig, "burn_direction", ((frame(0), 1.0), (frame(burn_end + COAST_S / 2), -1.0)), "CONSTANT")


def integrate(rig, scene, rate):
    """Per-frame rapidity, distance (km) and Earth time (s) for a rapidity rate (1/s per unit thrust)."""
    thrust = get_curve(rig, '["thrust"]')
    direction = get_curve(rig, '["burn_direction"]')
    step = 1.0 / (FPS * SUBSTEPS)
    phi, distance, earth = [0.0], [0.0], [0.0]
    for f in range(scene.frame_start + 1, scene.frame_end + 1):
        p, d, e = phi[-1], distance[-1], earth[-1]
        for i in range(SUBSTEPS):
            t = f - 1 + (i + 0.5) / SUBSTEPS
            change = rate * thrust.evaluate(t) * direction.evaluate(t) * step
            # Midpoint rule: distance and time at the rapidity half a step in.
            mid = max(p + 0.5 * change, 0.0)
            d += C_KM_S * math.sinh(mid) * step
            e += math.cosh(mid) * step
            p = max(p + change, 0.0)
        phi.append(p)
        distance.append(d)
        earth.append(e)
    return phi, distance, earth


def solve_rate(rig, scene):
    """Rapidity rate for which the whole trip covers TRIP_KM (distance grows with rate)."""
    lo, hi = 0.01, 3.0
    for _ in range(50):
        mid = 0.5 * (lo + hi)
        if integrate(rig, scene, mid)[1][-1] > TRIP_KM:
            hi = mid
        else:
            lo = mid
    return 0.5 * (lo + hi)


def bake(rig, scene, rate):
    phi, distance, earth = integrate(rig, scene, rate)
    for prop, values, desc in (
            ("rapidity", phi, "Rapidity phi, baked from thrust: beta = tanh(phi), gamma = cosh(phi)"),
            ("distance_km", distance, "Distance flown in the stars' frame (km), baked from rapidity"),
            ("earth_time_s", earth, "Time on Earth's clocks (s), baked from rapidity")):
        remove_curve(rig, f'["{prop}"]')
        rig[prop] = 0.0
        rig.id_properties_ui(prop).update(min=0.0, description=desc)
        set_keys(rig, prop, list(zip(range(scene.frame_start, scene.frame_end + 1), values)), "LINEAR")
    peak = max(phi)
    assert peak < MAX_RAPIDITY, peak
    print(f"Rapidity rate {rate:.4f}/s per unit thrust; peak gamma {math.cosh(peak):.0f} "
          f"(beta = 1 - {1 - math.tanh(peak):.1e}); final rapidity {phi[-1]:.2e}; "
          f"distance {distance[-1]:,.0f} km ({distance[-1] / AU_KM:.2f} AU) in {(scene.frame_end - 1) / FPS:.1f} s "
          f"(Earth clocks: {earth[-1] / 60:.1f} min)")


def drive_beta(rig):
    remove_curve(rig, '["beta"]')
    rig.driver_remove('["beta"]')
    driver = rig.driver_add('["beta"]').driver
    driver.type = "SCRIPTED"
    var = driver.variables.new()
    var.name = "phi"
    var.targets[0].id = rig
    var.targets[0].data_path = '["rapidity"]'
    # tanh(phi), written with exp so it runs without Python auto-run.
    driver.expression = "1 - 2 / (exp(2 * phi) + 1)"
    assert driver.is_simple_expression


if __name__ == "__main__":
    reset = "--reset" in sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else False
    scene = bpy.context.scene
    rig = bpy.data.objects[RIG]
    key_controls(rig, bpy.data.objects[AIRFRAME], scene, reset)
    bake(rig, scene, solve_rate(rig, scene))
    drive_beta(rig)
    bpy.ops.wm.save_mainfile()
