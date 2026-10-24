# [⁠RenderJuice "Speed" Blender animation (5-30 sec)](https://www.renderjuice.com/contests/speed)

Close to the speed of light

Idea: a vehicle moving faster and faster until it gets very close to the speed of light, with cool shape and background effects (relativity).
The blender scene itself can be simple - just a vehicle (spaceship or plane) moving in a straight line, with background texture(s) (potentially multiple layers for parallax effects). The majority of the effects will come from procedural animation via shaders.

## Scene setup

`light_speed.blend` is built and cleaned up by the scripts in `scripts/`, which are the source of truth (the `.blend` is binary and does not diff well in git).
Run them headless from the project root; each script saves the `.blend` in place and is safe to re-run:

```bash
blender -b light_speed.blend --python scripts/setup_scene.py
```

* `setup_scene.py`: removes leftover assets, groups the F-15 under the `F15` empty, adds the `ChaseCam` camera (parented to `F15`, i.e. riding along with the plane) and a sun, and uses the star map as the world background.
* `build_sky_shader.py`: builds the relativistic world shader (aberration, Doppler color shift, beaming), seen from the plane's frame.
  Speed is the custom property `beta` (fraction of c) on the `F15` empty; keyframe it to animate.
  Look controls are on the world's `Doppler Shift` node (`Beaming` exponent, `Exposure Compensation`, `Color Shift`) and `Sky Rotation` node (which part of the sky lies ahead); re-running the script keeps their values.

Assets live under `assets/` (git-ignored); the star map is linked from there, not packed into the `.blend`.
