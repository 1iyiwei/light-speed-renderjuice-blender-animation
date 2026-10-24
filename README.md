# [⁠RenderJuice "Speed" Blender animation (5-30 sec)](https://www.renderjuice.com/contests/speed)

## Title
Light speed

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
Run them headless from the project root, in this order; each script saves the `.blend` in place and is safe to re-run:

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
blender -b light_speed.blend --python scripts/build_afterburner.py
```

```bash
blender -b light_speed.blend --python scripts/animate_speed.py
```

```bash
blender -b light_speed.blend --python scripts/build_earth_moon.py
```

```bash
blender -b light_speed.blend --python scripts/build_asteroids.py
```

What to re-run after a change:

* Camera lens or render resolution: `build_star_points.py` (it sizes the stars in pixels).
* Thrust or burn direction curves (hand-edited in the Graph Editor): `animate_speed.py` (it re-bakes rapidity and distance), then `build_earth_moon.py` (Jupiter sits where the trip ends) and `build_asteroids.py` (rocks are timed from the distance).
* Sun direction: `build_earth_moon.py` and `build_asteroids.py` (they light the surfaces).
* `animate_speed.py -- --reset` replaces hand-edited curves with the defaults; `build_sky_shader.py -- --reset` does the same for the look controls.

The physics, script by script:

* `setup_scene.py`: removes leftover assets, puts the F-15 under `F15` > `Airframe` (so the plane can be turned independently of the rig, which keeps facing the direction of travel), adds the `ChaseCam` camera (on `F15`, i.e. riding along with the plane, looking level along the flight path) and a sun behind it.
* `build_sky_shader.py`: the relativistic world shader (aberration, Doppler color shift, beaming), seen from the plane's frame.
  Speed comes from `F15["rapidity"]` (phi: beta = tanh phi, gamma = cosh phi); the math is written in rapidity, in half-angle form, so it stays exact at gamma in the hundreds, where 1 - beta is below single-precision resolution.
  Look controls are on the world's `Doppler Shift` node (`Beaming` exponent, `Exposure Compensation`, `Color Shift`) and `Sky Rotation` node (which part of the sky lies ahead); re-running keeps their values.
  The background is the Milky Way map without its bright stars.
* `build_star_points.py`: the ~108k catalog stars (to magnitude 10) as points with Geometry Nodes (`Stars` object, `RelativisticStars` node group), with the same aberration, Doppler and beaming, so ahead of the plane they pile up into a sparkling cluster and, at peak speed, a single point.
  They are drawn additively, so piled-up stars add their light instead of hiding the sky; a compositor bloom (`StarBloom`) makes brighter stars look bigger.
  Speed and look controls come in through drivers, so stars and background always agree.
* `build_afterburner.py`: afterburner flames on both nozzles (transparent cones with an additive emission shader: blue-white core cooling to orange, shock diamonds, flickering noise flowing down the plume) plus orange lights, and two forward-facing retro-rockets on the sides of the nose for braking, canted 25 degrees outward like thrust reversers so they show from the chase camera as a V.
  `F15["thrust"]` scales their brightness and length; `F15["burn_direction"]` picks which pair burns (+1 afterburners, -1 retro-rockets).
  The afterburners are the "pushing forward" cue: aberration contracts the sky toward the direction of travel, which on its own reads as flying backward.
* `animate_speed.py`: the trip, Earth to Jupiter (4.2 AU) in 24.6 s at 30 fps, driven by thrust alone: a 1 s hold while the afterburners light, a 10 s burn with thrust (and flame) growing from 0.6 to 1.4, a 1 s coast with the engines off, a mirrored 10 s braking burn on the retro-rockets, and 2 s at rest at Jupiter.
  It bakes `F15["rapidity"]` (d phi / d tau = rate x thrust x `F15["burn_direction"]`, the animation clock being the pilot's proper time) and `F15["distance_km"]` (the distance flown in the stars' frame, growing as c sinh phi), solving for the rate that makes the trip end at Jupiter: peak gamma is about 700, so the sky ahead collapses to a point, then unwinds while braking.
  `F15["beta"]` is driven from the rapidity, for reading only.
* `build_earth_moon.py`: real-scale Earth (with an atmosphere shell), Moon and Jupiter, at rest in the stars' frame.
  The plane skims over the Atlantic toward Africa and leaves the Earth behind, passes the Moon about 28,000 km away at about 3 s, and stops 450,000 km in front of Jupiter (Great Red Spot facing it).
  Each vertex gets the same aberration as the stars and is drawn on a shell 300-850 m from the camera, ordered by true distance; surfaces are sunlit in the stars' frame, then Doppler-shifted and beamed like the sky.
* `build_asteroids.py`: 700 rocks between the Earth and the Moon, timed to pass steadily over the first ~3 s of the burn, 1,500-40,000 km from the flight path, so they stream outward from the direction of travel (the forward-motion cue the stars can't give), then bend forward toward the starbow as the speed climbs.
  The density is artistic license (that space is nearly empty); the motion is real scale, through the same transform as the Earth and Moon.

Render a quick preview video (half resolution, 16 samples; does not modify the `.blend`) to `previews/preview.mp4`:

```bash
blender -b light_speed.blend --python scripts/render_preview.py
```

Assets live under `assets/` (git-ignored) and are linked from there, not packed into the `.blend`:
`f-15a-eagle-usaf-76-0020-duxford/`, `milkyway_2020_8k.exr`, `hygdata_v41.csv`, `world.200412.3x5400x2700.jpg`, `lroc_color_poles_4k.tif`, `PIA07782.jpg` (`starmap_2020_8k.exr` is the older combined map, now unused).

## Credits

* F-15A Eagle model by mgg8 on [Sketchfab](https://sketchfab.com/3d-models/f-15a-eagle-usaf-76-0020-duxford-524f9394057e46ec8424d4a356f794b7), CC0 (credit optional).
* Milky Way background: NASA/Goddard Space Flight Center Scientific Visualization Studio, [Deep Star Maps 2020](https://svs.gsfc.nasa.gov/4851/); Gaia DR2: ESA/Gaia/DPAC.
* Earth: NASA Earth Observatory, [Blue Marble Next Generation](https://visibleearth.nasa.gov/images/74218) (December 2004), Reto Stöckli.
* Moon: NASA's Scientific Visualization Studio, [CGI Moon Kit](https://svs.gsfc.nasa.gov/4720/), Ernie Wright, from Lunar Reconnaissance Orbiter data.
* Jupiter: NASA/JPL/Space Science Institute, Cassini global map [PIA07782](https://photojournal.jpl.nasa.gov/catalog/PIA07782).
* Star catalog: [HYG Database](https://github.com/astronexus/HYG-Database) v4.1 by David Nash (astronexus), [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/).
