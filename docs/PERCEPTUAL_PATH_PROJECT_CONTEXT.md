# Perceptual Path — Updated Project Context

**Updated:** 2026-09-13  
**Current user-facing milestone:** Perceptual Path V1.5  
**Next target:** V1.6 analytical expansion

## 1. Project Overview
Perceptual Path is a Blender add-on for architectural perception analysis.

It began as a simple stationary human-POV raycaster and now can:

- place Start and End points;
- generate an A* route through architecture;
- move a human-height virtual viewer along that route;
- cast rays through a human field of view;
- record only first-hit visible surfaces;
- accumulate those hits into a 3D point-cloud memory;
- calculate Persistence;
- calculate Reveal;
- visualize heatmaps;
- animate the journey;
- progressively reveal the point cloud during playback;
- show an Agent POV camera in the current working project;
- report basic route/perception metrics.

The long-term workflow is:

`Generate Space → Simulate Occupant → Measure Perception → Compare → Evaluate → Iterate`

The software measures behavior. The designer decides whether that behavior is desirable.

## 2. Assignment 2 Relevance
The add-on supports Assignment 2: Proto-Architectural Spaces, where multiple iterations are developed from a shared geometric system and compared across Gathering, Workspace/Office, and Lobby/Entrance conditions.

Examples:

### Lobby
- When does reception/destination become visible?
- Is orientation immediate or delayed?
- Is circulation direct or exploratory?
- Does a visual anchor persist?

### Workspace
- How visually exposed are work areas?
- What remains visually connected?
- How deep is the visual field?
- Which surfaces remain dominant?

### Gathering
- Is gathering continuously visible?
- Is it concealed and later revealed?
- Does the approach compress then release?
- Is circulation direct or sequential?

## 3. Core Perception Logic
At each sampled eye position:

`Agent Eye → Human FOV → Raycast → First Geometry Hit → Save XYZ`

Only the first hit is recorded. Geometry behind an occluding wall is not.

Therefore the point cloud represents **perception**, not total building geometry.

## 4. Navigation
Objects:
- `PP_Start`
- `PP_End`
- `PP_Path`

Current route logic:
1. project obstacles into XY;
2. expand obstacle bounds using Agent Clearance;
3. discretize into a grid;
4. run A*;
5. convert nodes back to world coordinates;
6. create a Blender curve.

Current navigation is best described as **2.5D**:
- route solved primarily in plan;
- perception remains fully 3D.

Known limitations:
- no true stairs/ramps/multilevel navigation yet;
- rotated walls can be over-blocked due to bounding boxes;
- gaze mostly follows direction of travel;
- not yet true autonomous exploration.

## 5. Human Vision
Key objects:
- `Agent_Eye`
- `Agent_Target`

Typical settings:
- Horizontal FOV: 110°
- Vertical FOV: 70°
- Horizontal Rays: 40–120
- Vertical Rays: 25–80

The regular ray grid was useful for debugging but is now visually limiting.

## 6. Perception Memory
Raw ray hits are grouped into 3D spatial memory cells using a voxel-like key based on `pp_voxel_size`.

Typical memory cell size:
- 0.12–0.21 m

Current memory data includes:
- `position_sum`
- `count`
- `first_seen`
- `last_seen`

## 7. Persistence
Persistence answers:

**How often did this region remain visible during the journey?**

Definition:

`persistence = sampled viewpoints where region was visible / total sampled viewpoints`

Multiple rays from the same viewpoint hitting one cell count only once.

Interpretation can include:
- visual anchor;
- continuity;
- persistent destination;
- dominant edge;
- sustained spatial relationship.

## 8. Reveal
Reveal answers:

**When did this region first enter perception?**

`first_seen` is normalized from:
- 0.0 = beginning of journey
- 1.0 = end of journey

Reveal can describe:
- threshold;
- anticipation;
- discovery;
- orientation;
- delayed disclosure.

Current summary divides Reveal into:
- Early
- Mid
- Late

## 9. Current Display Modes
Current:
- Plain
- Persistence
- Reveal

Persistence:
`Blue → Yellow → Red`
`brief → persistent`

Reveal:
`Blue/Cyan → Purple → Red`
`early → late`

Black architectural materials have proven much easier to read than white context.

## 10. Playback
Playback uses the existing `first_seen` attribute.

A Geometry Nodes value named `PP_Playback_Progress` animates from 0 → 1.

Conceptual logic:

```text
if first_seen > playback_progress:
    hide point
else:
    show point
```

This means playback does not rerun raycasts every frame.

Current limitation:
- point reveal is relatively binary rather than smoothly fading.

## 11. Agent POV
Agent POV has been successfully set up in Blender and is considered functional enough for now.

This allows:
- Plan
- 3D perception cloud
- Agent POV

POV is not the immediate development priority.

## 12. Current Analysis Summary
Current working metrics include:
- Route Length
- Viewpoints
- Visible Regions
- Mean Persistence
- Max Persistence
- Early Reveal
- Mid Reveal
- Late Reveal

A recent test produced roughly:
- Route Length: 18.56 m
- Viewpoints: 15
- Visible Regions: 14,604
- Mean Persistence: 19%
- Max Persistence: 66.7%
- Early Reveal: 62.7%
- Mid Reveal: 12.1%
- Late Reveal: 24.9%

These describe behavior, not quality.

## 13. Simplified Metric Vocabulary
Two proposed metrics are intentionally postponed.

### Visibility Duration — postponed
This describes first-to-last sighting span, but Persistence currently communicates the more useful idea: how often a region was actually visible.

### Enclosure — postponed
Enclosure is related to the distribution of ray-hit distances. Visual Depth is the clearer first metric.

## 14. Preferred V1.6 Metrics
Keep the next analytical set focused:

1. Persistence — **What stays with me?**
2. Reveal — **When do I discover it?**
3. Visual Depth — **How far can I see?**
4. Reveal Rate — **Where does a lot of new space suddenly appear?**
5. Path Directness / Turns — **How does circulation choreograph the experience?**

## 15. V1.6A — Visual Depth
Visual Depth is the next recommended implementation.

Definition:

`distance from Agent_Eye to the first visible ray-hit surface`

Interpretation:
- compressed;
- intimate;
- expansive;
- long visual axis;
- spatial release.

Visual Depth is not the same as Enclosure. A long narrow corridor can have high forward visual depth while remaining laterally enclosed.

Recommended implementation:
- preserve the stable `cast_fov()`;
- add `cast_fov_detailed(...)`;
- return `location` and `distance`;
- use detailed raycasts in `Run Experience`;
- extend memory with depth data;
- write point attributes such as `mean_depth`, `min_depth`, `max_depth`;
- add a `Visual Depth` display mode;
- add Mean / Max Visual Depth to the summary.

Potential heatmap:
`Red/Orange = near`
`Yellow = medium`
`Cyan/Blue = far`

Keep the raw distance in meters. Do not normalize away the true analysis value.

## 16. Reveal Rate
Reveal Rate should count newly discovered memory cells at each sampled viewpoint.

Example:

```text
Step 1: +320
Step 2: +74
Step 3: +32
Step 4: +19
Step 5: +611  <- major reveal
```

This can identify threshold / reveal events.

It is primarily a route-level metric, not a point-cloud heatmap.

## 17. Path Directness / Turns
Planned route metrics:
- route length;
- direct Start→End distance;
- directness ratio;
- turn count;
- average turn angle;
- total angular change.

Possible directness definition:

`straight-line distance / actual route length`

These values describe circulation behavior, not quality.

## 18. Planned Sampling Modes
Do not switch analysis to pure uncontrolled randomness.

Preferred future modes:
- **Analysis Grid** — deterministic and repeatable
- **Jittered** — stratified jitter inside grid cells
- **Presentation** — denser, smaller, jittered points for graphics

The user specifically wants presentation clouds closer to previous studio graphics.

Analytical metrics and presentation density should remain separable.

## 19. Planned Smooth Playback
Current reveal:
`hidden → visible`

Planned:
`hidden → tiny/faint → medium → full`

Possible fade:

`fade = (playback_progress - first_seen) / fade_duration`

Clamp to 0–1 and use it to drive point radius and/or brightness.

## 20. Planned Live Persistence
Desired animation:

`Blue → Cyan → Yellow → Orange/Red`

as the agent repeatedly sees a region.

Current memory is insufficient for exact temporal replay because it only stores:
- count
- first_seen
- last_seen

Future memory needs something like:

`seen_steps = [1, 2, 4, 7]`

This allows true live persistence rather than using only final values.

## 21. Section Analysis
Section remains a major goal after the V1.6 analytical/graphic work.

Principle:
**Do not rerun a separate section simulation.**

The point cloud is already 3D. Section should simply filter the existing dataset.

Planned tools:
- Create Section Plane
- Section Thickness
- Show Section Cloud
- Plan View
- Section View
- 3D View

## 22. Longer-Term Comparison
Eventually compare multiple Assignment 2 variants under equivalent settings.

Example:

```text
                A       B       C
Route Length    18m     24m     20m
Persistence     72%     48%     61%
Late Reveal     21%     57%     36%
Visual Depth    9.2m   14.8m   11.1m
Directness      .82     .55     .68
```

The designer then applies program-specific criteria.

## 23. VS Code / Codex Workflow
Recommended repo:

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

The latest Blender-tested known-good add-on should become:

`addon/perceptual_path.py`

Use Git for version history.

Baseline:
```bash
git init
git add .
git commit -m "Baseline working Perceptual Path V1.5"
```

Feature branch:
```bash
git switch -c feature/visual-depth
```

Review:
```bash
git diff
```

Rollback:
```bash
git restore addon/perceptual_path.py
```

Commit after Blender validation:
```bash
git add .
git commit -m "Add visual depth analysis"
```

## 24. ChatGPT + Codex Division of Work
Use ChatGPT for:
- architectural reasoning;
- metric definitions;
- Assignment 2 relevance;
- screenshots/videos;
- development planning;
- conceptual debugging.

Use Codex in VS Code for:
- reading the live codebase;
- implementing approved plans;
- syntax checks;
- diff review;
- surgical edits.

Ideal flow:

`User + ChatGPT decide WHAT/WHY → context files preserve decisions → Codex implements HOW → Git diff → Blender test → User + ChatGPT evaluate`

Codex should not silently redefine the methodology.

## 25. Stable Names
Important object names:
- `Agent_Eye`
- `Agent_Target`
- `PP_Start`
- `PP_End`
- `PP_Path`
- `Perception_Cloud`
- `PP_Experience_Cloud`
- `PP_Analysis_Material`

Important Geometry Nodes names:
- `Point_Display`
- `PP_Set_Material`
- `PP_Playback_Progress`
- `PP_First_Seen`
- `PP_Delete_Future`
- `PP_Mesh_To_Points`

Important Scene properties include:
- `pp_horizontal_fov`
- `pp_vertical_fov`
- `pp_horizontal_rays`
- `pp_vertical_rays`
- `pp_max_distance`
- `pp_point_size`
- `pp_grid_size`
- `pp_clearance`
- `pp_eye_height`
- `pp_sample_every`
- `pp_voxel_size`
- `pp_display_mode`
- `pp_frames_per_step`

Current summary data includes:
- `pp_route_length`
- `pp_viewpoint_count`
- `pp_region_count`
- `pp_mean_persistence`
- `pp_max_persistence`
- `pp_early_reveal`
- `pp_mid_reveal`
- `pp_late_reveal`

## 26. Immediate Roadmap

### V1.6A
- Visual Depth
- Visual Depth heatmap
- Mean Visual Depth
- Max Visual Depth

### V1.6B
- Reveal Rate
- Path Directness
- Turn Count / angular change

### V1.6C
- Analysis Grid
- Jittered
- Presentation sampling

### V1.6D
- Smooth playback fade/growth

### V1.7
- temporal `seen_steps`
- live persistence color evolution

### V1.8
- Section Plane
- Section Thickness
- Plan / Section / 3D presets

### V2.0
- multi-variant comparison
- Assignment 2 evaluation logic
- eventual generative iteration

## 27. Professor / Crit Explanation
Short explanation:

> Perceptual Path simulates a human-height viewer moving through architectural geometry. At sampled positions along the route, rays are cast through a human-like field of view, and only the first visible geometry intersection is recorded. Those observations are grouped into a spatial point-cloud memory. The system can then visualize which regions remained visually persistent, when regions were first revealed, and increasingly other spatial measures such as visual depth and circulation behavior.

If asked whether the software decides what is good:

> No. It measures spatial behavior. The studio criteria determine whether that behavior is desirable for a lobby, workspace, gathering space, or another condition.

## 28. Current Project Identity
Perceptual Path is:

**A Blender-based architectural perception instrument that converts a simulated occupant journey into spatial evidence for analysis, visualization, comparison, and eventually design iteration.**

The point cloud is the evidence layer, not the final goal.
