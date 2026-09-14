# Perceptual Path 1.6.1 — Visual Depth

This release adds first-hit visual depth measurements to the architectural perception workflow, alongside Persistence and Reveal.

- Per-cell mean, minimum, and maximum depth attributes in meters.
- Visual Depth heatmap with an adjustable Depth Color Max and matching legend.
- Full Analysis Summary, including Mean/Max Visual Depth.
- Persistence colors normalized within each run; absolute persistence remains in the analysis data and summary.
- Navigation obstacle footprints sampled from evaluated mesh geometry using BVHs, with clearance applied on the navigation grid.
- Start/End creation, agent creation, Scan POV, route generation, experience memory, legends, and progressive playback.

Install the attached `perceptual_path-1.6.1.zip` through Blender's add-on installer. Run Experience again to populate the new attributes in older projects.

The source is `addon/perceptual_pathv1.6.py`; its internal version is `(1, 6, 1)`. The installable ZIP uses the stable package name `perceptual_path` and contains that exact saved source.

Navigation remains planar. Grid resolution affects obstacle detection. Visual Depth is based only on successful first hits, and the depth summary describes the entire journey.

The installable ZIP passed automated Blender 4.1.0 and 5.2.1 LTS checks covering registration, a synthetic navigation route, raycasting, memory attributes, display modes, legends, adjustable depth colors, Analysis Summary, and playback. These checks complement the user's testing of the saved working script; they do not cover every architectural model.
