# [⁠RenderJuice "Speed" Blender animation (5-30 sec)](https://www.renderjuice.com/contests/speed)

## Title
Chasing the speed of light

## Idea
A vehicle moving faster and faster until it gets very close to the speed of light, with cool shape and background effects (relativity).
The blender scene itself can be simple - just a vehicle (spaceship or plane) moving in a straight line, with background texture(s) (potentially multiple layers for parallax effects). The majority of the effects will come from procedural animation via shaders.

## Progress

WIP milestones, with contact sheets and the git tag of each, are logged in [docs/progress.md](docs/progress.md).

## Scene setup

Fetch the assets first (the F-15 needs a manual Sketchfab download; the script says how):

```bash
scripts/fetch_assets.sh
```

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

```bash
blender -b light_speed.blend --python scripts/animate_speed.py
```

```bash
blender -b light_speed.blend --python scripts/build_afterburner.py
```

```bash
blender -b light_speed.blend --python scripts/build_earth_moon.py
```

```bash
blender -b light_speed.blend --python scripts/build_asteroids.py
```

Re-run `build_star_points.py` after changing the camera's lens or the render resolution: it sizes the stars in pixels.
Re-run `animate_speed.py` after editing the rapidity curve (it bakes the distance flown) and then `build_asteroids.py` (it times the rocks from that distance); re-run `build_earth_moon.py` and `build_asteroids.py` after moving the sun (they light the surfaces).
`animate_speed.py -- --reset` replaces hand-edited rapidity and thrust curves with the defaults.

* `setup_scene.py`: removes leftover assets, groups the F-15 under the `F15` empty, adds the `ChaseCam` camera (parented to `F15`, i.e. riding along with the plane) and a sun, and uses the star map as the world background.
* `build_sky_shader.py`: builds the relativistic world shader (aberration, Doppler color shift, beaming), seen from the plane's frame.
  Speed is the custom property `beta` (fraction of c) on the `F15` empty; keyframe it to animate.
  Look controls are on the world's `Doppler Shift` node (`Beaming` exponent, `Exposure Compensation`, `Color Shift`) and `Sky Rotation` node (which part of the sky lies ahead); re-running the script keeps their values.
  The background is the Milky Way map without its bright stars.
* `build_star_points.py`: draws the ~108k catalog stars (to magnitude 10) as points with Geometry Nodes (`Stars` object, `RelativisticStars` node group), with the same aberration, Doppler and beaming, so ahead of the plane they pile up into a sparkling cluster instead of blurring into a glow.
  It reads `beta` and the look controls through drivers, so stars and background always agree, and adds a compositor bloom (`StarBloom`) so brighter stars look bigger.
* `build_afterburner.py`: afterburner flames on both nozzles (transparent cones with an additive emission shader: blue-white core cooling to orange, shock diamonds, flickering noise flowing down the plume) plus orange lights on the tail.
  `F15["thrust"]` (default 1) scales their brightness and length; keyframe it for an ignition.
  They are the "pushing forward" cue: aberration contracts the sky toward the direction of travel, which on its own reads as flying backward.
* `animate_speed.py`: sets 11 s at 30 fps: a 1 s hold at rest while the afterburners light (`F15["thrust"]` ramps 0 to 1), then 10 s of constant thrust, keyframing `F15["rapidity"]` linearly; `beta = tanh(rapidity)` is driven from it, reaching 0.9 three seconds into the burn and 0.9999 at the end.
  Edit the rapidity curve in the Graph Editor to change the pacing; re-running keeps it.
  It also bakes `F15["distance_km"]`, the distance flown in the stars' frame (the animation clock is the pilot's proper time, so it grows as c sinh(rapidity)).
* `build_earth_moon.py`: real-scale Earth (with an atmosphere shell) and Moon, at rest in the stars' frame, so they stream backward past the plane: it skims over the Atlantic toward Africa and leaves the Earth behind within half a second, and passes the Moon about 28,000 km away about 2.2 s into the burn (beta ~ 0.79).
  Each vertex gets the same aberration as the stars and is drawn on a shell 300-850 m from the camera, ordered by true distance; surfaces are sunlit in the stars' frame, then Doppler-shifted and beamed like the sky.
* `build_asteroids.py`: 700 rocks between the Earth and the Moon, timed to pass steadily over the first ~3 s of the burn, 1,500-40,000 km from the flight path, so they stream outward from the direction of travel (the forward-motion cue the stars can't give), then bend forward toward the starbow as beta climbs.
  The density is artistic license (that space is nearly empty); the motion is real scale, through the same transform as the Earth and Moon.

Render a quick preview video (half resolution, 16 samples; does not modify the `.blend`) to `previews/preview.mp4`:

```bash
blender -b light_speed.blend --python scripts/render_preview.py
```

Assets live under `assets/` (git-ignored) and are linked from there, not packed into the `.blend`:
`f-15a-eagle-usaf-76-0020-duxford/`, `milkyway_2020_8k.exr`, `hygdata_v41.csv`, `world.200412.3x5400x2700.jpg`, `lroc_color_poles_4k.tif` (`starmap_2020_8k.exr` is the older combined map, now unused).

## Credits

* F-15A Eagle model by mgg8 on [Sketchfab](https://sketchfab.com/3d-models/f-15a-eagle-usaf-76-0020-duxford-524f9394057e46ec8424d4a356f794b7), CC0 (credit optional).
* Milky Way background: NASA/Goddard Space Flight Center Scientific Visualization Studio, [Deep Star Maps 2020](https://svs.gsfc.nasa.gov/4851/); Gaia DR2: ESA/Gaia/DPAC.
* Earth: NASA Earth Observatory, [Blue Marble Next Generation](https://visibleearth.nasa.gov/images/74218) (December 2004), Reto Stöckli.
* Moon: NASA's Scientific Visualization Studio, [CGI Moon Kit](https://svs.gsfc.nasa.gov/4720/), Ernie Wright, from Lunar Reconnaissance Orbiter data.
* Star catalog: [HYG Database](https://github.com/astronexus/HYG-Database) v4.1 by David Nash (astronexus), [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/).
