# Progress

Work-in-progress milestones shared in the [WIP Discord post](https://discord.com/channels/1547269486057627728/1563423274296152095/1563423274296152095).
Each entry names the git tag of the commit that produced its images, so any of them can be re-rendered.

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

<!--
physically correct but visually counter-intuitive - the stars cluster towards where the vehicle is moving to giving the impression that it is moving backward (2026-10-24)
-->

<a href="https://youtu.be/5vq9ntRFD-o">
<img src="https://img.youtube.com/vi/5vq9ntRFD-o/mqdefault.jpg" width=320>
</a>

## wip-3: direction cues to counter the counter-intuitive warping effect: earth and moon for anchoring, and asteroids for vection (2026-10-24)

<a href="https://youtu.be/JlnyL4PsOVI">
<img src="https://img.youtube.com/vi/JlnyL4PsOVI/mqdefault.jpg" width=320>
</a>

## wip-4: slowing down after reaching peak speed but the directional flip looks unnatural

https://youtu.be/gJxubWsJA_c

## wip-5: retro thrusters for slowing down, pointing 25° out, 8° up for visibility from the current camera angle.

https://youtu.be/wzp1PKvSnt0

## wip-6: rockets angled 12° outward and 8° up with a viewport that won't cut off the afterburner

https://youtu.be/iBoEott07nU

## wip-7: (Tesla-inspired) rainbow projection for fun artistic flavor and speed visualization

https://youtu.be/zq631Oqnygw

## wip-8: adding clocks and the RenderJuice logo

https://youtu.be/WfO4vC5za3Y

## wip-9: adding some RenderJuice cans (one big and many small)

https://youtu.be/O6ucVJOKp78