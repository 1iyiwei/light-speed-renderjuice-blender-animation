# [⁠RenderJuice "Speed" Blender animation (5-30 sec)](https://www.renderjuice.com/contests/speed)

## Title
Close to the speed of light

## Idea
A vehicle moving faster and faster until it gets very close to the speed of light, with cool shape and background effects (relativity).
The blender scene itself can be simple - just a vehicle (spaceship or plane) moving in a straight line, with background texture(s) (potentially multiple layers for parallax effects). The majority of the effects will come from procedural animation via shaders.

## Scene setup

`light_speed.blend` is built and cleaned up by the scripts in `scripts/`, which are the source of truth (the `.blend` is binary and does not diff well in git).
Run them headless from the project root; each script saves the `.blend` in place and is safe to re-run:

```bash
blender -b light_speed.blend --python scripts/setup_scene.py
```

```bash
blender -b light_speed.blend --python scripts/build_sky_shader.py
```

```bash
blender -b light_speed.blend --python scripts/build_star_points.py
```

* `setup_scene.py`: removes leftover assets, groups the F-15 under the `F15` empty, adds the `ChaseCam` camera (parented to `F15`, i.e. riding along with the plane) and a sun, and uses the star map as the world background.
* `build_sky_shader.py`: builds the relativistic world shader (aberration, Doppler color shift, beaming), seen from the plane's frame.
  Speed is the custom property `beta` (fraction of c) on the `F15` empty; keyframe it to animate.
  Look controls are on the world's `Doppler Shift` node (`Beaming` exponent, `Exposure Compensation`, `Color Shift`) and `Sky Rotation` node (which part of the sky lies ahead); re-running the script keeps their values.
  The background is the Milky Way map without its bright stars.
* `build_star_points.py`: draws the ~108k catalog stars (to magnitude 10) as points with Geometry Nodes (`Stars` object, `RelativisticStars` node group), with the same aberration, Doppler and beaming, so ahead of the plane they pile up into a sparkling cluster instead of blurring into a glow.
  It reads `beta` and the look controls through drivers, so stars and background always agree, and adds a compositor bloom (`StarBloom`) so brighter stars look bigger.

Assets live under `assets/` (git-ignored) and are linked from there, not packed into the `.blend`:
`f-15a-eagle-usaf-76-0020-duxford/`, `milkyway_2020_8k.exr`, `hygdata_v41.csv` (`starmap_2020_8k.exr` is the older combined map, now unused).

## Credits

* F-15A Eagle model by mgg8 on [Sketchfab](https://sketchfab.com/3d-models/f-15a-eagle-usaf-76-0020-duxford-524f9394057e46ec8424d4a356f794b7), CC0 (credit optional).
* Milky Way background: NASA/Goddard Space Flight Center Scientific Visualization Studio, [Deep Star Maps 2020](https://svs.gsfc.nasa.gov/4851/); Gaia DR2: ESA/Gaia/DPAC.
* Star catalog: [HYG Database](https://github.com/astronexus/HYG-Database) v4.1 by David Nash (astronexus), [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/).
