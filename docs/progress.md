# Progress

Work-in-progress milestones shared in the [WIP Discord post](https://discord.com/channels/1547269486057627728/1563423274296152095/1563423274296152095).
Each entry names the commit (and, for the first ones, the git tag) that produced its images or video, so any of them can be re-rendered.

## wip-1: first scene (2026-10-24)

Commit `9b019a7` (tag `wip-1`).

![F-15 against the star map, seen from the chase camera](progress/wip1_f15_still.jpg)

* Replaced the Kitbash cargo plane with a CC0 F-15A Eagle.
* Chase camera riding along with the plane; NASA SVS star map as the background.

## wip-1b: texture-only relativistic sky (2026-10-24)

Commit `9b019a7` (tag `wip-1`; same commit, rendered with the sky shader it already contains).

![Texture-only sky: chase camera at beta = 0, 0.5, 0.9, 0.99, 0.999, and a camera aimed along the flight path at 0.999](progress/wip1b_texture_sky_beta_sweep.jpg)

* First world shader: aberration, Doppler color shift and beaming applied to the NASA star map as a texture.
* Two problems, both fixed in wip-2:
  * The Doppler factor used the wrong one of its two equivalent-looking forms (correct only straight ahead and behind), so the sky stayed bright to the sides instead of fading.
  * Stars squeezed ahead of the plane were averaged by texture filtering into a dim glow (the "dark hole" at 0.999), and stars behind were blown up into blobs. Real stars stay points, which led to drawing them from a catalog.

## wip-2: relativistic sky (2026-10-24)

Commit `ba97255` (tag `wip-2`).

![Chase camera at beta = 0, 0.5, 0.9, 0.99, 0.999, and a camera aimed along the flight path at 0.999](progress/wip2_starbow_beta_sweep.jpg)

* World shader for aberration, Doppler color shift and beaming, driven by `F15["beta"]`.
* Bright stars drawn as 108k catalog points (HYG) over a Milky-Way-only map, so the sky ahead collapses into a sparkling starbow instead of a blurry glow.
* Chase camera at beta = 0, 0.5, 0.9 (top row), 0.99, 0.999, then a camera aimed along the flight path at 0.999.

Video (rendered from commit `1839df7`, the first animated speed ramp):

<!--
physically correct but visually counter-intuitive - the stars cluster towards where the vehicle is moving to giving the impression that it is moving backward (2026-10-24)
-->

<a href="https://youtu.be/5vq9ntRFD-o">
<img src="https://img.youtube.com/vi/5vq9ntRFD-o/mqdefault.jpg" width=320>
</a>

## wip-3: direction cues (2026-10-24)

Commit `57a6dfe`.

Cues to counter the counter-intuitive warping effect: Earth and Moon for anchoring, and asteroids for vection.

<a href="https://youtu.be/JlnyL4PsOVI">
<img src="https://img.youtube.com/vi/JlnyL4PsOVI/mqdefault.jpg" width=320>
</a>

## wip-4: slowing down after peak speed (2026-10-24)

Not committed on its own (between `57a6dfe` and `311d08b`).

Slowing down after reaching peak speed, but the directional flip looks unnatural.

<a href="https://youtu.be/gJxubWsJA_c">
<img src="https://img.youtube.com/vi/gJxubWsJA_c/mqdefault.jpg" width=320>
</a>

## wip-5: retro thrusters (2026-10-24)

Commit `311d08b`.

Retro thrusters for slowing down, pointing 25° out and 8° up for visibility from the current camera angle.

<a href="https://youtu.be/wzp1PKvSnt0">
<img src="https://img.youtube.com/vi/wzp1PKvSnt0/mqdefault.jpg" width=320>
</a>

## wip-6: retro thrusters at 12°, reframed camera (2026-10-24)

Commit `fd37428`.

Rockets angled 12° outward and 8° up, with a viewport that won't cut off the afterburner.

<a href="https://youtu.be/iBoEott07nU">
<img src="https://img.youtube.com/vi/iBoEott07nU/mqdefault.jpg" width=320>
</a>

## wip-7: rainbow projection (2026-10-25)

Not committed on its own (included in `041a9ac`).

(Tesla-inspired) rainbow projection for a fun artistic flavor and speed visualization.

<a href="https://youtu.be/zq631Oqnygw">
<img src="https://img.youtube.com/vi/zq631Oqnygw/mqdefault.jpg" width=320>
</a>

## wip-8: clocks and the RenderJuice logo (2026-10-25)

Commit `041a9ac`.

Adding the on-screen clocks (pilot and Earth time), the end card, and the RenderJuice logo.

<a href="https://youtu.be/WfO4vC5za3Y">
<img src="https://img.youtube.com/vi/WfO4vC5za3Y/mqdefault.jpg" width=320>
</a>

## wip-9: RenderJuice cans (2026-10-25)

Commit `591f7a6`.

Adding some RenderJuice cans (one big and many small) to the asteroid field.

<a href="https://youtu.be/O6ucVJOKp78">
<img src="https://img.youtube.com/vi/O6ucVJOKp78/mqdefault.jpg" width=320>
</a>

## final: rendered in EEVEE with background music (2026-10-25)

After `591f7a6`, plus the fix for the big can's z-fighting, the resumable full-resolution render, and `scripts/add_music.sh`.

1920x1080, 30 fps, 26.6 s, 64 samples; the music's drop lands at 11.0 s, at top speed.

<a href="https://youtu.be/4M4FqIFfBvA">
<img src="https://img.youtube.com/vi/4M4FqIFfBvA/mqdefault.jpg" width=320>
</a>
