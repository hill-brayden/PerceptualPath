# Perceptual Path

A Blender add-on for architectural perception analysis.

Perceptual Path samples a human-height viewer along a navigation route, records first-hit visible surfaces, and builds a point-cloud memory of the journey. The measurements support design interpretation; they do not rate architecture as good or bad.

## Current release

**1.6.1 — Visual Depth**

The working source is [`addon/perceptual_pathv1.6.py`](addon/perceptual_pathv1.6.py). The version inside `bl_info` determines the release version. Files in `archive/` are historical references.

## Installation

1. Download the `perceptual_path-1.6.1.zip` release attachment. Keep it zipped.
2. In Blender, open **Edit > Preferences > Add-ons** and use **Install from Disk** (or **Install** in older versions).
3. Select the ZIP and enable **Perceptual Path**. Disable an older copy first if it registers the same controls.
4. Open the 3D Viewport sidebar with **N**, then select **Perceptual Path**.

The release ZIP contains a Python package named `perceptual_path`. GitHub's automatically generated source archive is a repository download, not the installation package.

## Basic workflow

1. Open architectural mesh geometry. For the existing navigation and route-length conventions, use one world unit per meter.
2. Create the agent and place **Start** and **End** with the 3D cursor.
3. Set Grid Size and Agent Clearance, then **Generate Path**. Inspect the resulting route.
4. Set Eye Height, sampling, and vision settings, then **Run Experience**.
5. Use **Material Preview** and select Plain, Persistence, Reveal, or Visual Depth.
6. Read the legend and Analysis Summary.
7. Use **Create Playback**, then play the timeline to move the agent and reveal the cloud.

Existing Agent POV cameras can follow `Agent_Eye` and `Agent_Target`; this release does not create a camera rig automatically.

## Measurements and colors

| Measurement | Meaning |
| --- | --- |
| Persistence | Fraction of sampled viewpoints from which a memory cell was visible. A cell counts once per viewpoint. |
| Reveal | Normalized journey position where a cell was first seen. |
| Visual Depth | Distance from a sampled eye position to the first ray-hit surface. Missed rays do not contribute a distance. |

Persistence **colors** are normalized to the strongest persistence in the current run. Summary percentages retain the absolute values. Visual Depth attributes and summary values remain in meters; **Depth Color Max** changes only the color scale. Depth means weight each successful ray hit equally.

The Analysis Summary includes Route Length, Viewpoints, Visible Regions, Mean/Max Persistence, Early/Mid/Late Reveal, and Mean/Max Visual Depth. Summary values describe the complete run, including during playback.

## Scope and limitations

- Navigation is primarily planar; stairs and multilevel routes are not supported.
- Obstacle footprints are sampled from evaluated mesh geometry using BVHs. Grid resolution and agent clearance affect the route.
- Gaze follows the path, with the existing endpoint behavior retained.
- Regenerate the experience after changing geometry or sampling settings. Older clouds may lack newer display attributes.
- The later roadmap includes Reveal Rate, circulation metrics, presentation sampling, smoother playback, temporal persistence, sections, and variant comparison.

## Development and release packaging

Run `python tools/build_release.py` with Python 3 to create a ZIP and SHA-256 checksum under `dist/`. The builder copies the saved source byte for byte into `perceptual_path/__init__.py` and checks Python syntax without importing Blender.

Use a Git commit as a new recovery checkpoint and a version tag such as `v1.6.1` to identify a release. Keep existing history; Auto Save and local file recovery are separate from Git commits.

See [`docs/RELEASE_v1.6.1.md`](docs/RELEASE_v1.6.1.md) for release notes and [`docs/PERCEPTUAL_PATH_PROJECT_CONTEXT.md`](docs/PERCEPTUAL_PATH_PROJECT_CONTEXT.md) for project context.
