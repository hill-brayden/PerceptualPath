# AGENTS.md — Perceptual Path

## Release status — 2026-09-14

The user saved the current working implementation as `addon/perceptual_pathv1.6.py` (internal version 1.6.1). Treat that file as canonical; older `addon/perceptual_path.py` references below are historical. V1.6A Visual Depth is implemented. Preserve this saved source and the existing feature protections. See `README.md` and `docs/RELEASE_v1.6.1.md` for current behavior and packaging. Later roadmap features still require an explicit request.

## Purpose
Perceptual Path is a Blender Python add-on for architectural perception analysis. It simulates a human-like agent moving through architecture, records only geometry actually visible within a human field of view, converts that visibility into a 3D point-cloud memory, and derives architectural analysis from the journey.

Read `PERCEPTUAL_PATH_PROJECT_CONTEXT.md` before making major changes.

Canonical implementation should live at:

`addon/perceptual_path.py`

## Critical Rules

1. Preserve working features unless explicitly asked to change them:
   - Create Agent
   - Create Start / End
   - A* path generation
   - POV raycasting
   - perception-memory point cloud
   - Persistence display
   - Reveal display
   - playback
   - Agent POV if present
   - analysis summary

2. Make surgical edits:
   - explain the plan first;
   - identify exact functions/classes to touch;
   - avoid broad refactors during feature work;
   - run a syntax check afterward;
   - summarize the diff.

3. Preserve stable names unless explicitly approved:
   - `Agent_Eye`
   - `Agent_Target`
   - `PP_Start`
   - `PP_End`
   - `PP_Path`
   - `Perception_Cloud`
   - `PP_Experience_Cloud`
   - `PP_Analysis_Material`
   - `Point_Display`
   - `PP_Set_Material`
   - `PP_Playback_Progress`
   - `PP_First_Seen`
   - `PP_Delete_Future`
   - `PP_Mesh_To_Points`

4. `bpy` is provided by Blender at runtime. Do not remove or replace Blender API imports just because the local VS Code interpreter reports them unresolved.

5. Do not silently redefine metrics.

### Persistence
Percentage of sampled viewpoints from which a spatial memory cell was visible.

`persistence = viewpoints where visible / total sampled viewpoints`

A memory cell counts at most once per viewpoint.

### Reveal
Normalized journey position where a spatial memory cell was first seen.

`0.0 = near START`
`1.0 = near END`

### Visual Depth — next feature
Distance from `Agent_Eye` to the first visible ray-hit surface. It answers: **How far could the occupant see?**

### Reveal Rate — planned
How many previously unseen memory cells appear at each sampled viewpoint.

### Path Directness / Turns — planned
Describes circulation behavior, not architectural quality.

6. Do not implement these unless explicitly requested:
   - Visibility Duration
   - Enclosure Index

They are intentionally postponed to keep the analysis vocabulary clear.

7. Analysis is not evaluation. Never convert metrics directly into “good” or “bad.” A late reveal may be desirable for gathering but undesirable for a lobby.

## Current Priority — V1.6A
Implement Visual Depth while preserving all current behavior.

Preferred approach:
- keep the stable `cast_fov()` for simple scans;
- add a new helper such as `cast_fov_detailed(...)`;
- return records containing `location` and `distance`;
- use detailed raycasts in `Run Experience`;
- extend memory cells with depth data;
- write `mean_depth`, `min_depth`, and `max_depth` attributes;
- add a `Visual Depth` display mode;
- add Mean / Max Visual Depth to the analysis summary.

Do not break Persistence or Reveal.

## Display Roadmap
Current:
- Plain
- Persistence
- Reveal

Near-term:
- Plain
- Persistence
- Reveal
- Visual Depth
- Observation Count (optional/debug)

Future:
- Live Persistence
- Section display

## Point Sampling Roadmap
Do not replace analytical sampling with uncontrolled randomness.

Preferred modes:
- **Analysis Grid** — deterministic, repeatable
- **Jittered** — stratified jitter within grid cells
- **Presentation** — denser, smaller, jittered points for graphics

Analytical values and presentation density should remain separable.

## Playback Roadmap
Current playback progressively reveals points by `first_seen`.

Planned:
- smooth reveal: hidden → small/faint → full;
- live persistence coloring: blue → cyan → yellow → red as a region is repeatedly seen.

True live persistence requires temporal memory such as:

`seen_steps = [1, 2, 4, 7]`

Do not fake this from only final `count`, `first_seen`, and `last_seen`.

## Testing Workflow
After every significant change:

1. Open known test geometry.
2. Verify `PP_Start` and `PP_End`.
3. Generate Path.
4. Verify `PP_Path` avoids walls.
5. Run Experience.
6. Confirm `PP_Experience_Cloud` exists.
7. Switch to Material Preview.
8. Test Persistence.
9. Test Reveal.
10. Create Playback.
11. Press Spacebar.
12. Verify `Agent_Eye` movement.
13. Verify cloud reveal.
14. Verify Analysis Summary.
15. Verify Agent POV if present.

Do not commit a feature if a protected feature regresses.

## Git Workflow
Use Git instead of multiplying “final_fixed_v2” files.

Typical flow:

```bash
git switch -c feature/visual-depth
git diff
```

Rollback:

```bash
git restore addon/perceptual_path.py
```

Commit after Blender testing:

```bash
git add .
git commit -m "Add visual depth analysis"
```

## Repository Layout
```text
PerceptualPath/
├── AGENTS.md
├── PERCEPTUAL_PATH_PROJECT_CONTEXT.md
├── README.md
├── addon/
│   └── perceptual_path.py
└── archive/
    └── old_versions/
```

Treat `addon/perceptual_path.py` as canonical. Do not treat archived prototypes as current.

## Coding Style
- prefer readable Blender/Python code;
- use descriptive names;
- keep analysis logic separated from UI where practical;
- avoid premature modularization;
- avoid external dependencies unless necessary;
- prefer Blender-native APIs, Geometry Nodes, named attributes, and Python standard library.

## Project Philosophy
Perceptual Path should follow:

`Architecture → Simulated Occupant → Perception → Data → Evidence → Evaluation → Iteration`

Do not turn this into “AI decides which architecture is best.”
