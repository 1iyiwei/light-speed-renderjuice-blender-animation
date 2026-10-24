# Progress

Work-in-progress milestones shared in the [WIP Discord post](https://discord.com/channels/1547269486057627728/1563423274296152095/1563423274296152095).
Each entry names the git tag of the commit that produced its images, so any of them can be re-rendered.

## wip-1: first scene (2026-10-24)

Commit `9b019a7` (tag `wip-1`).

![F-15 against the star map, seen from the chase camera](progress/wip1_f15_still.jpg)

* Replaced the Kitbash cargo plane with a CC0 F-15A Eagle.
* Chase camera riding along with the plane; NASA SVS star map as the background.

## wip-2: relativistic sky (2026-10-24)

Commit `ba97255` (tag `wip-2`).

![Chase camera at beta = 0, 0.5, 0.9, 0.99, 0.999, and a camera aimed along the flight path at 0.999](progress/wip2_starbow_beta_sweep.jpg)

* World shader for aberration, Doppler color shift and beaming, driven by `F15["beta"]`.
* Bright stars drawn as 108k catalog points (HYG) over a Milky-Way-only map, so the sky ahead collapses into a sparkling starbow instead of a blurry glow.
* Chase camera at beta = 0, 0.5, 0.9 (top row), 0.99, 0.999, then a camera aimed along the flight path at 0.999.
