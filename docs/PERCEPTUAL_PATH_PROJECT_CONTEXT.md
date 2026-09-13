# Perceptual Path — Project Context / Handoff Notes
**Last updated:** 2026-09-12  
**Primary environment:** Blender 5.2.x + Python add-on  
**Current working build:** `Perceptual_Path_v0_5_2_Analysis_FIXED.py`

---

## 1. Project Summary

**Perceptual Path** is a Blender add-on being developed for an architecture studio workflow. The goal is to simulate a human-like agent moving through architectural geometry, record what the agent can actually see within a human field of view, convert that visibility data into a 3D point cloud, and derive useful architectural analysis from the accumulated perception.

The tool is **not intended to declare architecture objectively “good” or “bad.”** Instead, it is meant to produce measurable evidence that can support qualitative design judgments and Assignment 2 evaluation criteria.

The central conceptual chain is:

```text
ARCHITECTURAL GEOMETRY
        ↓
START + END CONDITIONS
        ↓
AGENT NAVIGATION
        ↓
HUMAN FIELD OF VIEW
        ↓
3D RAYCASTING
        ↓
VISIBLE-SURFACE POINT CLOUD
        ↓
PERCEPTION MEMORY
        ↓
PERSISTENCE / REVEAL
        ↓
ARCHITECTURAL METRICS
        ↓
COMPARISON / EVALUATION
```

---

## 2. Studio / Assignment Context

This add-on is being developed alongside **Assignment 2: Proto-Architectural Spaces**.

The assignment develops multiple spatial iterations from a **shared geometric system**, organized around three programmatic categories:

- Gathering
- Workspace / Office
- Lobby / Entrance

The studio wants multiple iterations to be generated, analyzed, evaluated, and selected.

The add-on is intended to become one evaluation instrument within that process.

The most useful kinds of design questions are expected to include:

- When does a destination or space become visible?
- How much of the architecture remains visually persistent during a journey?
- Does the space reveal itself all at once or gradually?
- Is the experience visually open, enclosed, compressed, or released?
- Does the geometry create strong visual anchors?
- Does a workspace remain visually exposed to circulation?
- Does a gathering space act as a persistent destination?
- Does a lobby provide immediate orientation or delayed reveal?
- How do multiple generated variants differ under equivalent start/end conditions?

The long-term workflow is:

```text
shared geometric system
        ↓
variation A / B / C / ...
        ↓
Perceptual Path analysis
        ↓
metrics + point cloud graphics
        ↓
criteria-based comparison
        ↓
selection / iteration
```

---

## 3. Core Concept

The point cloud is **not a normal scan of the building**.

It is a record of what an occupant was capable of seeing while navigating through the architecture.

A ray is cast from the virtual eye. Only the **first geometry intersection** is recorded.

Therefore:

```text
EYE ───────────────→ WALL ─────────→ HIDDEN GEOMETRY
                     ●
```

Only the `●` point is recorded.

This means:

- geometry behind walls is occluded;
- visible surfaces are recorded;
- hidden surfaces remain absent;
- the cloud is a visualization of **perception**, not total geometry.

This distinction is central to explaining the project.

---

## 4. Development History / Milestones

### v0.1 — Stationary Human POV Scanner
Implemented:

- `Agent_Eye`
- `Agent_Target`
- human-like field of view
- horizontal FOV
- vertical FOV
- ray density controls
- Blender raycasting
- first-hit geometry capture
- visible point-cloud generation
- Geometry Nodes point display

Initial test settings were roughly:

```text
Horizontal FOV: 110°
Vertical FOV:    70°
Horizontal Rays: 90
Vertical Rays:   50
```

A stationary scan successfully produced points on visible floors/walls and respected occlusion.

### v0.2 — Start / End + A* Pathfinding
Implemented:

- `PP_Start`
- `PP_End`
- route generation
- 2D / 2.5D navigation grid
- wall obstacle detection
- agent clearance
- A* search
- visible Blender curve `PP_Path`

Current pathfinding logic:

1. Sample the XY plan into a grid.
2. Treat tall mesh objects as obstacles.
3. Expand obstacle bounding boxes by agent clearance.
4. Convert Start and End into grid positions.
5. Run A*.
6. Convert the resulting nodes back to world coordinates.
7. Build a Blender curve.

Important current limitation:

- obstacle checking is based on **XY bounding boxes**, not exact mesh collision;
- rotated walls can generate oversized collision boxes;
- navigation is currently plan-based rather than full 3D;
- stairs/ramps/multilevel navigation are not implemented yet.

### v0.3 — Run Experience / Accumulated Perception Cloud
Implemented:

- sample positions along `PP_Path`;
- raise the viewer to human eye height;
- face the viewer toward the next path node;
- raycast human FOV at each sampled viewpoint;
- accumulate all visible geometry;
- create `PP_Experience_Cloud`.

Conceptually:

```text
START
  ↓
viewpoint 0 → scan
  ↓
viewpoint 1 → scan
  ↓
viewpoint 2 → scan
  ↓
...
  ↓
END

all visible hits
        ↓
PP_Experience_Cloud
```

Current gaze behavior:

```text
gaze direction = direction of travel
```

Future versions may allow head/gaze exploration separate from body/path direction.

### v0.3 / v0.4 — Perception Memory
Raw overlapping ray hits were replaced with spatial memory cells.

A hit is quantized using a voxel-like memory key:

```python
(
    round(point.x / voxel_size),
    round(point.y / voxel_size),
    round(point.z / voxel_size)
)
```

Nearby observations therefore become the same spatial region.

Each memory cell stores:

```text
position_sum
count
first_seen
last_seen
```

The final point position is the average of the observations stored in that cell.

This dramatically reduces noisy duplicate points and creates useful analysis data.

---

## 5. Important Persistence Correction

Persistence should **not** count every ray independently.

Example of the bad interpretation:

```text
one viewpoint
5 rays hit one memory cell
→ count = 5
```

That would incorrectly make ray density affect architectural persistence.

The current working logic instead groups all hits from one viewpoint into memory cells first.

Each cell can be counted only **once per sampled viewpoint**.

Therefore:

```text
persistence =
number of sampled viewpoints where region was visible
/
total sampled viewpoints
```

Examples:

```text
0.10 = region visible from 10% of viewpoints
0.50 = region visible from 50% of viewpoints
0.90 = region visible from 90% of viewpoints
```

This interpretation is much more defensible academically.

---

## 6. Current Point Attributes

`PP_Experience_Cloud` contains named per-point attributes:

### `observation_count`
Integer number of sampled viewpoints from which the memory cell was visible.

### `persistence`
Normalized 0–1 value:

```text
observation_count / total sampled viewpoints
```

Interpretation:

> How repeatedly / continuously did this spatial region remain visually accessible during the journey?

### `first_seen`
Normalized 0–1 position in the journey where the region first entered perception.

```text
0.0 = discovered near START
1.0 = discovered near END
```

Interpretation:

> When did this region first become visible?

### `last_seen`
Normalized 0–1 position of the final sampled viewpoint from which the region was visible.

Potential future use:

- disappearance;
- separation;
- visual memory;
- continuity;
- duration.

---

## 7. Display Modes

The add-on currently supports:

### Plain
Neutral point-cloud visualization.

### Persistence
Heatmap driven by `persistence`.

Approximate meaning:

```text
BLUE ───────── YELLOW ───────── RED
brief                             persistent
```

Interpretation:

> How frequently did this spatial region remain visible?

### Reveal
Heatmap driven by `first_seen`.

Approximate meaning:

```text
BLUE / CYAN ─── PURPLE ─── RED
seen early                    seen late
```

Interpretation:

> At what stage in the journey did this spatial region first become visible?

Material Preview is needed to clearly see the heatmap colors.

A dark architectural context material currently makes the analysis cloud much easier to read.

---

## 8. Current UI Controls

The Perceptual Path Blender sidebar currently contains or is intended to contain:

### AGENT
- Create Agent

### ROUTE
- Create Start
- Create End
- Grid Size
- Agent Clearance
- Generate Path
- Eye Height
- Sample Every
- Memory Cell Size
- Run Experience

### DISPLAY
- Plain
- Persistence
- Reveal
- legend / explanation

### PLAYBACK
- Frames Per Step
- Create Playback
- Spacebar playback

### ANALYSIS SUMMARY
- Route Length
- Viewpoints
- Visible Regions
- Mean Persistence
- Max Persistence
- Early Reveal
- Mid Reveal
- Late Reveal

### VISION
- Horizontal FOV
- Vertical FOV
- Horizontal Rays
- Vertical Rays
- Max Distance
- Point Size
- Scan POV

---

## 9. Playback System

Current playback build:

`Perceptual_Path_v0_5_Playback_FIXED.py`

The analysis build is based on that working playback version.

Playback works by using the already-computed `first_seen` point attribute.

A Geometry Nodes chain reads:

```text
first_seen
```

and compares it against an animated:

```text
PP_Playback_Progress
```

value ranging from:

```text
0.0 → 1.0
```

If:

```text
first_seen > playback_progress
```

that point is considered “future” information and is deleted from the displayed cloud.

As playback progresses, more points appear.

This means playback does **not need to rerun raycasts every frame**.

The agent's `Agent_Eye` and `Agent_Target` positions are keyframed along the route.

Workflow:

```text
Generate Path
→ Run Experience
→ Create Playback
→ press Spacebar
```

Playback currently visualizes:

- agent movement;
- progressive spatial reveal;
- accumulated perception.

---

## 10. Analysis Summary — Current Metrics

Latest build:

`Perceptual_Path_v0_5_2_Analysis_FIXED.py`

The Analysis Summary currently calculates:

### Route Length
Total polyline length of `PP_Path`.

Interpretation:

> How far did the occupant travel?

Useful for comparing efficiency / indirectness.

### Viewpoints
Number of sampled eye positions used during the experience.

Interpretation:

> Methodological sample size.

Example explanation:

> “The route was analyzed from 21 sampled human-eye positions.”

### Visible Regions
Number of unique memory cells discovered.

Interpretation:

> How many distinct spatial regions became visually accessible?

This is a rough quantity and should not yet be treated as a standalone quality score.

### Mean Persistence

```text
mean of all memory-cell persistence values
```

Interpretation:

> On average, how continuously did observed architectural regions remain present through the route?

### Max Persistence
Highest persistence value found in the experience.

Interpretation:

> The strongest visual anchor / most continuously visible spatial region.

### Reveal Distribution

The normalized journey is divided into thirds:

```text
0.00–0.333 = Early
0.333–0.666 = Mid
0.666–1.00 = Late
```

Every region is categorized by `first_seen`.

The add-on reports:

```text
Early Reveal %
Mid Reveal %
Late Reveal %
```

Example:

```text
Early Reveal: 52%
Mid Reveal:   29%
Late Reveal:  19%
```

Interpretation:

> Most of the ultimately visible architecture was disclosed early.

Another geometry might produce:

```text
Early Reveal: 18%
Mid Reveal:   32%
Late Reveal:  50%
```

Interpretation:

> The geometry creates a much more delayed / sequential reveal.

These are **behavior descriptors**, not “good/bad” scores.

---

## 11. Architectural Meaning of Current Metrics

### Persistence
Can suggest:

- visual anchor;
- spatial continuity;
- persistent destination;
- landmark condition;
- dominant edge/wall;
- sustained visual relationship.

### Reveal
Can suggest:

- threshold;
- concealment;
- discovery;
- sequence;
- anticipation;
- wayfinding;
- delayed spatial disclosure.

### Path Length
Can suggest:

- efficiency;
- indirect exploration;
- journey complexity.

### Visible Regions
Can suggest:

- amount of perceptual information;
- visual access;
- uniqueness of spatial discovery.

These metrics should support qualitative architectural descriptors rather than replace them.

---

## 12. Intended Assignment 2 Use by Program Type

### Lobby / Entrance
Potential questions:

- Is reception visible immediately?
- When does the destination become legible?
- Does the entry sequence reveal too much immediately?
- Is there a visual anchor?
- Is orientation obvious or delayed?
- Does the lobby sequence create approach → entry → orientation → handoff?

Useful metrics:

- destination reveal;
- persistence;
- visual depth;
- route length;
- openness;
- late vs. early reveal.

### Workspace / Office
Potential questions:

- How exposed are workstations to circulation?
- How visually separated are private work areas?
- Can occupants retain visual connection to gathering/support spaces?
- Is the workspace layered or fully open?
- Which surfaces remain dominant visual anchors?

Useful metrics:

- visual exposure;
- persistence;
- visual continuity;
- enclosure;
- occlusion;
- distance to shared space.

### Gathering
Potential questions:

- Does the gathering space remain visible during approach?
- Is it a continuous anchor or a hidden destination?
- Does the room reveal suddenly or gradually?
- Are people / activity zones visually connected?
- Is gathering centralized, fragmented, layered, open, or enclosed?

Useful metrics:

- persistence;
- reveal;
- visual depth;
- openness;
- continuity;
- compression/release.

---

## 13. Planned Near-Term Development

### NEXT: v0.6 — Section Analysis

Goal:

> Use the existing 3D perception dataset to create clean section-based architectural graphics.

Important principle:

**Section should not require a new simulation.**

The agent navigates and perceives in 3D.

Plan, section, and 3D are simply different ways of viewing the same experience dataset.

Planned functionality:

```text
Create Section Plane
Section Thickness
Show Section Cloud
Plan View
Section View
3D View
Agent POV
```

Possible logic:

- create `PP_Section`;
- define a plane + slice thickness;
- calculate distance of each cloud point to the plane;
- show only points within the slice;
- optionally clip model context too.

Expected result:

```text
FULL 3D CLOUD
     ↓
SECTION SLICE
     ↓
architectural sectional perception diagram
```

This is especially important because the studio is interested in sectional / vertical relationships.

---

## 14. Planned Metrics After Section

The next useful experiential metrics are expected to be:

### Visual Depth
Distance from the eye to ray-hit surfaces.

Possible outputs:

- average depth;
- maximum depth;
- forward visual depth;
- visual-depth graph over journey.

Interpretation:

- intimacy;
- openness;
- long visual axes;
- spatial expansion.

### Enclosure
Likely derived from distribution of nearby FOV ray-hit distances.

Interpretation:

- compressed;
- enclosed;
- intimate;
- open.

### Openness
Potentially:

- proportion of rays traveling beyond a chosen distance;
- percentage of long-distance visibility;
- visual field without nearby obstruction.

### Compression / Release
Derived from changes in visual depth / enclosure across sampled viewpoints.

Expected graph:

```text
visual depth
high                  ______
                    /
             ______/
            /
low _______/
    START            END
```

Interpretation:

> compressed sequence opening into spatial release.

This is one of the strongest future Assignment 2 metrics.

---

## 15. Longer-Term Comparison System

Once the metrics are stable, the add-on should support analyzing multiple variants under equivalent conditions.

Example:

```text
                VAR A   VAR B   VAR C

Route Length     18m     24m     20m
Persistence      72%     48%     61%
Late Reveal      21%     57%     36%
Visual Depth     9.2m   14.8m   11.1m
Enclosure        high    low     medium
```

This would allow Assignment 2 iterations to be evaluated comparatively.

Important:

The add-on should **not** say:

```text
VARIANT B = objectively best
```

Instead, a designer / studio criterion can say something like:

```text
For a lobby:
high orientation + early reveal = preferred

For a dramatic gathering sequence:
late reveal + strong compression/release = preferred
```

The criteria determine desirability.

The software measures behavior.

---

## 16. Long-Term Generative Goal

Only after analysis/comparison is stable:

```text
PARAMETRIC GEOMETRY
        ↓
GENERATE VARIANTS
        ↓
RUN PERCEPTUAL PATH
        ↓
CALCULATE METRICS
        ↓
APPLY DESIGN CRITERIA
        ↓
RANK / SELECT
        ↓
MUTATE / ITERATE
```

Possible geometry parameters:

- terrace height;
- opening width;
- void size;
- partition density;
- ceiling height;
- wall angle;
- porosity;
- rotation;
- circulation width;
- sectional offset.

Potential development stages:

### Manual parameter sliders
Designer adjusts geometry and reruns analysis.

### Batch generation
Generate 10–20 controlled variants.

### Comparative evaluation
Analyze all variants with identical conditions.

### Evolutionary generation
Keep best-performing variants according to user-defined criteria, mutate parameters, generate new variants.

This is a future objective, not the immediate priority.

---

## 17. Current Known Limitations

### Navigation
- plan-based / 2.5D only;
- not true 3D walkability;
- no stairs/ramps yet;
- obstacle collision uses XY bounding boxes;
- rotated geometry can be over-blocked.

### Agent
- gaze follows direction of travel;
- no independent head movement;
- no behavioral exploration / curiosity;
- no alternate route personalities;
- no multi-agent simulation.

### Vision
- current rays use an angular grid;
- no eye-tracking probability model;
- no focal/peripheral acuity distinction;
- no material transparency logic;
- no mirror/reflection handling.

### Point Cloud
- memory-cell size influences spatial grouping;
- point density depends on FOV ray density;
- the metric should always be interpreted in context of settings;
- black architectural context currently improves display manually.

### Metrics
- persistence and reveal are useful and fairly interpretable;
- visible-region count is still crude;
- visual depth/enclosure/compression-release are not yet implemented;
- no score weighting system yet.

### Presentation
- legend currently lives in sidebar;
- no graphic/export legend object yet;
- no automated board export;
- section output not yet implemented.

---

## 18. Recommended Development Order

Do not jump directly into automated geometry generation.

Recommended order:

```text
CURRENT
✓ POV scanner
✓ point cloud
✓ pathfinding
✓ experience accumulation
✓ perception memory
✓ persistence
✓ reveal
✓ playback
✓ analysis summary

NEXT
→ section analysis / section plane
→ plan / section / 3D view presets
→ visual depth
→ enclosure
→ compression / release
→ iteration comparison

LATER
→ parametric geometry generation
→ automated variant batches
→ criterion weighting
→ ranking
→ mutation / evolutionary loop
```

---

## 19. Coding / Architecture Notes for a Copilot Agent

### Keep these object names stable

```text
Agent_Eye
Agent_Target
PP_Start
PP_End
PP_Path
Perception_Cloud
PP_Experience_Cloud
PP_Analysis_Material
```

### Important Geometry Nodes names

```text
Point_Display
PP_Set_Material
PP_Playback_Progress
PP_First_Seen
PP_Delete_Future
PP_Mesh_To_Points
```

Future code should reuse these names where possible so UI/update callbacks do not break.

### Important Scene properties

Current properties include:

```text
pp_horizontal_fov
pp_vertical_fov
pp_horizontal_rays
pp_vertical_rays
pp_max_distance
pp_point_size

pp_grid_size
pp_clearance

pp_eye_height
pp_sample_every
pp_voxel_size

pp_display_mode

pp_frames_per_step
```

Current Analysis Summary data is stored as custom scene dictionary values:

```text
scene["pp_route_length"]
scene["pp_viewpoint_count"]
scene["pp_region_count"]
scene["pp_mean_persistence"]
scene["pp_max_persistence"]
scene["pp_early_reveal"]
scene["pp_mid_reveal"]
scene["pp_late_reveal"]
```

### Core functions / responsibilities

Expected function responsibilities include:

```text
get_or_create_empty()
    object helper

delete_object_by_name()
    cleanup helper

cast_fov()
    human FOV raycasting

create_cloud_object()
    simple stationary scan point display

point_to_voxel()
    memory-cell quantization

configure_analysis_material()
    Plain / Persistence / Reveal material setup

create_memory_cloud()
    builds analytical experience cloud + attributes + Geometry Nodes

world_bbox_xy()
    obstacle bounding-box projection

get_obstacles()
    identifies route obstacles

build_navigation_grid()
    creates A* grid

heuristic()
    A* heuristic

astar()
    route search

create_path_curve()
    Blender path object

calculate_path_length()
    route metric
```

Operators currently include:

```text
PP_OT_create_start
PP_OT_create_end
PP_OT_create_agent
PP_OT_scan_pov
PP_OT_generate_path
PP_OT_run_experience
PP_OT_create_playback
```

UI:

```text
PP_PT_main_panel
```

---

## 20. Testing Workflow

When changing the add-on, preserve the following test workflow:

```text
1. Create / open simple maze geometry
2. Make sure floor is near Z = 0
3. Place PP_Start
4. Place PP_End
5. Generate Path
6. Verify path avoids walls
7. Run Experience
8. Verify PP_Experience_Cloud exists
9. Switch to Material Preview
10. Test Persistence
11. Test Reveal
12. Create Playback
13. Press Spacebar
14. Verify Agent_Eye moves
15. Verify point cloud progressively appears
16. Check Analysis Summary
```

Useful test settings:

```text
Horizontal FOV:   110°
Vertical FOV:      70°
Horizontal Rays:   40
Vertical Rays:     25
Eye Height:       1.65 m
Sample Every:        2–3
Memory Cell Size: 0.12–0.21 m
Point Size:       0.04–0.06
Frames Per Step:     6
```

---

## 21. Basic Professor / Crit Explanation

Short explanation:

> Perceptual Path uses a virtual human eye moving along a generated route. At each sampled position, rays are cast through a human-like field of view. Only the first visible geometry intersection is recorded. Those hits are accumulated into a point cloud representing what the occupant could actually perceive. The cloud stores when each region was first seen and how many viewpoints it remained visible from, which allows the same geometry to be visualized in terms of persistence and spatial reveal.

If asked how persistence works:

> A spatial region is counted only once per sampled viewpoint. Persistence is the percentage of sampled viewpoints from which that region remained visible.

If asked how Reveal works:

> Reveal records where along the normalized start-to-end journey each region first entered the visual field.

If asked what Blender provides:

> Blender provides geometry, raycasting, animation, Geometry Nodes, materials, and the Python API. The add-on defines the architectural perception logic, agent navigation, memory, metrics, and visualization.

If asked whether the tool makes design decisions:

> The tool analyzes spatial behavior. The designer still decides which behaviors are desirable according to the design criteria.

---

## 22. Design Philosophy

Do not turn this project into:

```text
AI magically designs architecture.
```

The stronger project is:

```text
Architecture is generated through a controlled system.
A simulated occupant experiences it.
Perception becomes data.
Data becomes evidence.
Evidence informs evaluation.
Evaluation guides iteration.
```

This is the conceptual identity of Perceptual Path.

---

## 23. Immediate Next Task

**Build v0.6 — Section Analysis.**

Recommended minimum feature set:

```text
[ Create Section Plane ]

Section Thickness: 0.30 m

[ Show Section Cloud ]

View:
[ Plan ] [ Section ] [ 3D ]
```

Section should filter the existing `PP_Experience_Cloud`, not rerun the simulation.

After section output is stable, implement:

```text
Visual Depth
Enclosure
Compression / Release
```

Then build multi-variant comparison.

---

## 24. Current Project Status in One Sentence

**Perceptual Path is currently a functioning Blender prototype that can navigate an agent between user-defined points, simulate human-field-of-view visibility along the route, accumulate visible geometry into a 3D perception-memory point cloud, visualize persistence and reveal, animate the perceptual journey, and report basic route/perception statistics; the next major milestone is architectural section analysis.**
