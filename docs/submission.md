# Submission notes

Notes for entering the [RenderJuice "Speed" contest](https://www.renderjuice.com/contests/speed#rules): which awards fit, and the text for the entry.

## Key rules

* **Format:** a 5-30 s MP4 (or public video link) posted in Discord `#contest-submissions`, with a short description and one Blender work-in-progress image. A `.blend` is not required, but admins may ask for project files before confirming an award.
* **Deadline:** October 31, 2026, 23:59 UTC. Community Choice voting closes November 3, 23:59 UTC.
* **One award per animation:** admins give each entry at most one Major or Specialty award. Community Choice is separate and can be won on top.
* **Major awards** are scored out of 100: Idea 30 (clear, creative, memorable), Animation 25 (clear, intentional, well-timed movement), Visuals 25 (camera, lighting, color, overall look), Use of Speed 20. Length does not affect the score.
* **Specialty awards** are judged first on their category requirements, then on idea, quality and use of Speed.

Since an entry can win at most one Major or Specialty award, "more ways to win" means more chances at one award, not several. The priority is a strong Major entry; the specialty categories are fallbacks, and the description should make the best-fitting one easy for the judges to see.

## Categories

| Award | Fit | Notes |
|---|---|---|
| Major (1st-3rd) | Strong | Idea: the speed theme taken to its physical limit, with a clear arc (launch, collapse to a point, unwind, arrival). Use of Speed is the whole piece. The biggest gap is making the idea readable to viewers who don't know relativity (see the on-screen clocks below). |
| Best Procedural & Programmatic Animation | Strong, our main specialty | Eligibility needs Geometry Nodes, the bpy API or code to be a substantial part, with the workflow described. Everything here is built by Python scripts and Geometry Nodes (see the workflow text below). |
| Best Simulation & FX | Weak | Eligibility needs Blender physics or simulation (particles, fluids, smoke, cloth, rigid bodies, hair) to be substantial. The stars, rocks, Earth, Moon and Jupiter are moved by formulas evaluated per frame, not simulated, and the flames are shaders. That is procedural animation, not simulation, so we should not claim this category. Adding a token simulation (say, a Geometry Nodes simulation zone for exhaust sparks) would not change that it is a minor part, and could only win instead of, not on top of, the procedural award. |
| Best Motion Design | Possible, with work | Eligibility needs animated typography, shapes or graphic elements. On-screen clocks would add exactly that, and help the Major score more (see below). |
| Funniest Animation | No | It needs the piece to be built around a joke. A light closing line can add charm, but it would not make this a comedy entry. |
| Best RenderJuice Promo | Cheap hedge | RenderJuice, its logo or its service has to be part of the idea. A logo decal on the plane is easy; tying it into the idea (an end card, see below) makes it count for more. |
| Community Choice | Everyone is entered | Decided by 🔥 reactions on the Discord entry post. A memorable thumbnail (the starbow, or the Jupiter arrival) and the WIP thread help. |

### Additions

1. **On-screen clocks (the biggest win, done in `build_hud.py`).** A small, clean readout ticking in a corner: the pilot's clock, an Earth clock, gamma and the distance flown. From launch to rest at Jupiter the pilot's clock reaches 0:22.6 while the Earth clock reaches 35:00 (minutes), close to the 34.9 minutes light itself needs for those 628 million km; gamma peaks at about 700. That one contrast explains the whole piece to non-physicists (Idea, Use of Speed) and is animated typography (Motion Design). The text is Geometry Nodes driven by the baked animation (`F15["rapidity"]`, `F15["distance_km"]`, `F15["earth_time_s"]`), which also strengthens the procedural workflow story.
2. **RenderJuice logo (done).** The can from the logo pack shared on the contest Discord is on both tail fins, and the wordmark fades in on the end card. It costs little and does not hurt the other categories.
3. **Closing line (done).** The end card after the arrival reads "628 million km to Jupiter / 23 seconds for the pilot, 35 minutes on Earth", the clocks' payoff.

## Entry text (draft)

**Title:** From Earth to Jupiter in 25 Seconds

**Short description:**

> An F-15 accelerates from Earth to within a millionth of the speed of light and brakes to a stop at Jupiter, 628 million km away, in 23 seconds of the pilot's own time (Earth's clocks see 35 minutes). On-screen clocks show both. Everything you see follows special relativity: the sky crowds toward the direction of travel and collapses into a single point of light at peak speed, colors shift blue ahead and red behind, and the Moon and asteroids stream past at real scale. Built entirely with Python scripts and Geometry Nodes in Blender.

**Workflow (for the Procedural & Programmatic award):**

> The scene is generated by a pipeline of Python scripts (bpy) that build and re-build the .blend from scratch, so every look is reproducible from code. The physics is written in rapidity, which keeps it exact at gamma ~ 700.
>
> * Relativistic sky: a world shader (node groups built by script) applies aberration, Doppler color shift and relativistic beaming to NASA's Milky Way map.
> * Stars: 108,000 stars from the HYG catalog, placed by Geometry Nodes and moved with the same aberration and Doppler formulas, so they pile up into a sparkling point instead of a blur.
> * Earth, Moon, Jupiter and 700 asteroids: real-scale meshes whose vertices are transformed by Geometry Nodes every frame, so they stream past and distort as the relativistic plane sees them.
> * Motion: a single keyframed thrust curve; a script integrates it into speed and distance (solving for the thrust that ends the trip exactly at Jupiter) and bakes them.
> * Effects: procedural afterburner and retro-rocket shaders, and rainbow light bands whose speed follows the plane's.
>
> Rendered in EEVEE. Assets: CC0 F-15 model (Sketchfab, mgg8), NASA SVS Deep Star Maps, Blue Marble, CGI Moon Kit and Cassini Jupiter map, HYG star catalog (CC BY-SA 4.0).

**WIP image:** one of the contact sheets in [progress.md](progress.md), or a screenshot of the Geometry Nodes star field in Blender, which also shows the procedural workflow.

## Credits

See the Credits section of the [README](../README.md); the HYG catalog's CC BY-SA 4.0 license asks for its credit line wherever the work is shown.
