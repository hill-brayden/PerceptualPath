bl_info = {
    "name": "Perceptual Path",
    "author": "Brayden Hill",
    "version": (1, 6, 1),
    "blender": (4, 0, 0),
    "location": "View3D > Sidebar > Perceptual Path",
    "description": "Human perception point-cloud analysis for architectural space",
    "category": "3D View",
}

import bpy
import math
import heapq

from mathutils import Vector
from mathutils.bvhtree import BVHTree


# =======================================================
# GENERAL HELPERS
# =======================================================

def get_or_create_empty(name, location=(0, 0, 0)):

    obj = bpy.data.objects.get(name)

    if obj is None:

        obj = bpy.data.objects.new(name, None)

        obj.empty_display_type = 'PLAIN_AXES'
        obj.empty_display_size = 0.4

        obj.location = location

        bpy.context.collection.objects.link(obj)

    return obj


def delete_object_by_name(name):

    obj = bpy.data.objects.get(name)

    if obj:
        bpy.data.objects.remove(
            obj,
            do_unlink=True
        )


# =======================================================
# START / END / AGENT
# =======================================================

class PP_OT_create_start(bpy.types.Operator):

    bl_idname = "pp.create_start"
    bl_label = "Create Start"

    def execute(self, context):

        obj = get_or_create_empty(
            "PP_Start",
            context.scene.cursor.location
        )

        bpy.context.view_layer.objects.active = obj

        obj.select_set(True)

        return {'FINISHED'}


class PP_OT_create_end(bpy.types.Operator):

    bl_idname = "pp.create_end"
    bl_label = "Create End"

    def execute(self, context):

        obj = get_or_create_empty(
            "PP_End",
            context.scene.cursor.location
        )

        bpy.context.view_layer.objects.active = obj

        obj.select_set(True)

        return {'FINISHED'}


class PP_OT_create_agent(bpy.types.Operator):

    bl_idname = "pp.create_agent"
    bl_label = "Create Agent"

    def execute(self, context):

        cursor = context.scene.cursor.location.copy()

        eye = get_or_create_empty(
            "Agent_Eye",
            cursor + Vector((0, 0, 1.65))
        )

        target = get_or_create_empty(
            "Agent_Target",
            cursor + Vector((2, 0, 1.65))
        )

        eye.empty_display_size = 0.25
        target.empty_display_size = 0.25

        return {'FINISHED'}


# =======================================================
# POV SCANNER
# =======================================================

def clear_old_cloud():

    delete_object_by_name("Perception_Cloud")


def cast_fov(
    context,
    eye,
    target,
    horizontal_fov,
    vertical_fov,
    horizontal_rays,
    vertical_rays,
    max_distance
):

    forward_vector = target - eye

    if forward_vector.length == 0:
        return []

    forward = forward_vector.normalized()

    world_up = Vector((0, 0, 1))

    if abs(forward.dot(world_up)) > 0.99:
        world_up = Vector((0, 1, 0))

    right = forward.cross(world_up).normalized()
    up = right.cross(forward).normalized()

    depsgraph = context.evaluated_depsgraph_get()

    hit_points = []

    horizontal_half = math.radians(
        horizontal_fov / 2.0
    )

    vertical_half = math.radians(
        vertical_fov / 2.0
    )

    for y in range(vertical_rays):

        v = y / max(
            vertical_rays - 1,
            1
        )

        vertical_angle = (
            -vertical_half
            + (2 * vertical_half * v)
        )

        for x in range(horizontal_rays):

            u = x / max(
                horizontal_rays - 1,
                1
            )

            horizontal_angle = (
                -horizontal_half
                + (2 * horizontal_half * u)
            )

            direction = (
                forward
                + right * math.tan(horizontal_angle)
                + up * math.tan(vertical_angle)
            ).normalized()

            hit, location, normal, face_index, obj, matrix = (
                context.scene.ray_cast(
                    depsgraph,
                    eye,
                    direction,
                    distance=max_distance
                )
            )

            if hit:
                hit_points.append(
                    location.copy()
                )

    return hit_points


def cast_fov_detailed(
    context,
    eye,
    target,
    horizontal_fov,
    vertical_fov,
    horizontal_rays,
    vertical_rays,
    max_distance
):
    """Return first-hit locations and eye-to-hit distances in world units."""

    hit_points = cast_fov(
        context,
        eye,
        target,
        horizontal_fov,
        vertical_fov,
        horizontal_rays,
        vertical_rays,
        max_distance
    )

    records = []

    for location in hit_points:
        records.append({
            "location": location.copy(),
            "distance": (location - eye).length
        })

    return records


def create_cloud_object(
    context,
    points,
    name,
    point_size
):

    delete_object_by_name(name)

    mesh = bpy.data.meshes.new(
        name + "_Mesh"
    )

    mesh.from_pydata(
        points,
        [],
        []
    )

    mesh.update()

    cloud_obj = bpy.data.objects.new(
        name,
        mesh
    )

    context.collection.objects.link(
        cloud_obj
    )

    modifier = cloud_obj.modifiers.new(
        name="Point_Display",
        type='NODES'
    )

    node_group = bpy.data.node_groups.new(
        name + "_Point_Display",
        'GeometryNodeTree'
    )

    modifier.node_group = node_group

    node_group.interface.new_socket(
        name="Geometry",
        in_out='INPUT',
        socket_type='NodeSocketGeometry'
    )

    node_group.interface.new_socket(
        name="Geometry",
        in_out='OUTPUT',
        socket_type='NodeSocketGeometry'
    )

    nodes = node_group.nodes
    links = node_group.links

    input_node = nodes.new(
        "NodeGroupInput"
    )

    output_node = nodes.new(
        "NodeGroupOutput"
    )

    mesh_to_points = nodes.new(
        "GeometryNodeMeshToPoints"
    )

    mesh_to_points.mode = 'VERTICES'

    mesh_to_points.inputs[
        "Radius"
    ].default_value = point_size

    links.new(
        input_node.outputs["Geometry"],
        mesh_to_points.inputs["Mesh"]
    )

    links.new(
        mesh_to_points.outputs["Points"],
        output_node.inputs["Geometry"]
    )

    return cloud_obj


# =======================================================
# PERCEPTION MEMORY + ANALYSIS DISPLAY
# =======================================================

def point_to_voxel(point, voxel_size):
    """Convert a world-space hit position into a spatial memory cell."""
    return (
        round(point.x / voxel_size),
        round(point.y / voxel_size),
        round(point.z / voxel_size)
    )


def calculate_path_length(points):
    """Return total polyline length through the sampled navigation path."""
    total = 0.0

    for i in range(len(points) - 1):
        total += (
            points[i + 1]
            - points[i]
        ).length

    return total


def configure_analysis_material(mode):
    """Create/update the material used to visualize analysis attributes."""

    material_name = "PP_Analysis_Material"
    material = bpy.data.materials.get(material_name)

    if material is None:
        material = bpy.data.materials.new(material_name)

    material.use_nodes = True

    nodes = material.node_tree.nodes
    links = material.node_tree.links
    nodes.clear()

    attribute = nodes.new("ShaderNodeAttribute")
    attribute.name = "PP_Attribute"
    attribute.label = "Perception Attribute"
    attribute.attribute_type = 'GEOMETRY'

    ramp = nodes.new("ShaderNodeValToRGB")
    ramp.name = "PP_ColorRamp"

    emission = nodes.new("ShaderNodeEmission")
    emission.name = "PP_Emission"
    emission.inputs["Strength"].default_value = 1.35

    output = nodes.new("ShaderNodeOutputMaterial")

    links.new(attribute.outputs["Fac"], ramp.inputs["Fac"])
    links.new(ramp.outputs["Color"], emission.inputs["Color"])
    links.new(emission.outputs["Emission"], output.inputs["Surface"])

    low = ramp.color_ramp.elements[0]
    high = ramp.color_ramp.elements[1]

    if mode == 'PLAIN':
        attribute.attribute_name = "persistence"
        low.position = 0.0
        high.position = 1.0
        low.color = (0.78, 0.78, 0.78, 1.0)
        high.color = (0.78, 0.78, 0.78, 1.0)

    elif mode == 'PERSISTENCE':
        # The real analytical value remains stored in "persistence".
        # This relative attribute stretches the current run's strongest
        # persistence to 1.0 so the heatmap remains visually legible.
        attribute.attribute_name = "relative_persistence"

        low.position = 0.0
        high.position = 1.0

        low.color = (0.02, 0.12, 0.95, 1.0)
        high.color = (1.0, 0.05, 0.01, 1.0)

        cyan = ramp.color_ramp.elements.new(0.30)
        cyan.color = (0.02, 0.75, 1.0, 1.0)

        yellow = ramp.color_ramp.elements.new(0.60)
        yellow.color = (1.0, 0.78, 0.02, 1.0)

    elif mode == 'REVEAL':
        attribute.attribute_name = "first_seen"
        low.position = 0.0
        high.position = 1.0
        low.color = (0.02, 0.55, 1.0, 1.0)
        high.color = (1.0, 0.12, 0.02, 1.0)

        middle = ramp.color_ramp.elements.new(0.5)
        middle.color = (0.55, 0.08, 0.85, 1.0)

    elif mode == 'VISUAL_DEPTH':
        attribute.attribute_name = "mean_depth"

        # User-controlled display range in meters.
        # Stored depth attributes remain unchanged.
        normalize = nodes.new("ShaderNodeMath")
        normalize.name = "PP_Depth_Normalize"
        depth_display_max = max(
            getattr(bpy.context.scene, "pp_depth_display_max", 20.0),
            0.1
        )

        normalize.label = (
            f"Visual Depth: 0–{depth_display_max:.1f} m"
        )
        normalize.operation = 'DIVIDE'
        normalize.inputs[1].default_value = depth_display_max

        links.remove(ramp.inputs["Fac"].links[0])

        links.new(
            attribute.outputs["Fac"],
            normalize.inputs[0]
        )

        links.new(
            normalize.outputs[0],
            ramp.inputs["Fac"]
        )

        low.position = 0.0
        low.color = (1.0, 0.12, 0.02, 1.0)

        high.position = 1.0
        high.color = (0.02, 0.12, 0.95, 1.0)

        middle = ramp.color_ramp.elements.new(0.5)
        middle.color = (1.0, 0.85, 0.02, 1.0)

        far = ramp.color_ramp.elements.new(0.75)
        far.color = (0.02, 0.85, 1.0, 1.0)
    else:
        attribute.attribute_name = "persistence"
        low.position = 0.0
        high.position = 1.0
        low.color = (0.02, 0.12, 0.95, 1.0)
        high.color = (1.0, 0.05, 0.01, 1.0)

        middle = ramp.color_ramp.elements.new(0.5)
        middle.color = (1.0, 0.72, 0.02, 1.0)

    return material


def create_memory_cloud(
    context,
    memory,
    name,
    point_size,
    total_steps
):
    """Build the experience point cloud and store analysis attributes."""

    delete_object_by_name(name)

    if not memory:
        return None

    points = []
    counts = []
    persistence_values = []
    relative_persistence_values = []
    first_seen_values = []
    last_seen_values = []

    for data in memory.values():

        average_position = (
            data["position_sum"]
            / data["count"]
        )

        points.append(average_position)
        counts.append(data["count"])

        persistence = (
            data["count"]
            / max(total_steps, 1)
        )

        persistence_values.append(
            min(max(persistence, 0.0), 1.0)
        )

        first_seen = (
            data["first_seen"]
            / max(total_steps - 1, 1)
        )

        last_seen = (
            data["last_seen"]
            / max(total_steps - 1, 1)
        )

        first_seen_values.append(
            min(max(first_seen, 0.0), 1.0)
        )

        last_seen_values.append(
            min(max(last_seen, 0.0), 1.0)
        )

    # Absolute persistence remains the analytical metric.
    # Relative persistence is only a display normalization so
    # long paths do not collapse the entire heatmap into blue.
    strongest_persistence = max(
        persistence_values,
        default=0.0
    )

    if strongest_persistence > 0.0:
        relative_persistence_values = [
            min(max(value / strongest_persistence, 0.0), 1.0)
            for value in persistence_values
        ]
    else:
        relative_persistence_values = [
            0.0 for _ in persistence_values
        ]

    mesh = bpy.data.meshes.new(name + "_Mesh")
    mesh.from_pydata(points, [], [])
    mesh.update()

    count_attr = mesh.attributes.new(
        name="observation_count",
        type='INT',
        domain='POINT'
    )

    persistence_attr = mesh.attributes.new(
        name="persistence",
        type='FLOAT',
        domain='POINT'
    )

    relative_persistence_attr = mesh.attributes.new(
        name="relative_persistence",
        type='FLOAT',
        domain='POINT'
    )

    first_seen_attr = mesh.attributes.new(
        name="first_seen",
        type='FLOAT',
        domain='POINT'
    )

    last_seen_attr = mesh.attributes.new(
        name="last_seen",
        type='FLOAT',
        domain='POINT'
    )

    # Adding attributes can invalidate earlier references in Blender 4.x.
    count_attr = mesh.attributes["observation_count"]
    persistence_attr = mesh.attributes["persistence"]
    relative_persistence_attr = mesh.attributes["relative_persistence"]
    first_seen_attr = mesh.attributes["first_seen"]
    last_seen_attr = mesh.attributes["last_seen"]

    for i in range(len(points)):
        count_attr.data[i].value = counts[i]
        persistence_attr.data[i].value = persistence_values[i]
        relative_persistence_attr.data[i].value = (
            relative_persistence_values[i]
        )
        first_seen_attr.data[i].value = first_seen_values[i]
        last_seen_attr.data[i].value = last_seen_values[i]
    units = context.scene.unit_settings
    meters_per_unit = (
        1.0 if units.system == 'NONE'
        else units.scale_length
    )

    mean_depth_attr = mesh.attributes.new(
        name="mean_depth",
        type='FLOAT',
        domain='POINT'
    )

    min_depth_attr = mesh.attributes.new(
        name="min_depth",
        type='FLOAT',
        domain='POINT'
    )

    max_depth_attr = mesh.attributes.new(
        name="max_depth",
        type='FLOAT',
        domain='POINT'
    )

    mean_depth_attr = mesh.attributes["mean_depth"]
    min_depth_attr = mesh.attributes["min_depth"]
    max_depth_attr = mesh.attributes["max_depth"]

    for i, data in enumerate(memory.values()):

        mean_depth_attr.data[i].value = (
            data["depth_sum"] / data["depth_count"]
        ) * meters_per_unit

        min_depth_attr.data[i].value = (
            data["min_depth"] * meters_per_unit
        )

        max_depth_attr.data[i].value = (
            data["max_depth"] * meters_per_unit
        )
    cloud_obj = bpy.data.objects.new(name, mesh)
    context.collection.objects.link(cloud_obj)
    total_depth_sum = sum(
        data["depth_sum"] for data in memory.values()
    )

    total_depth_count = sum(
        data["depth_count"] for data in memory.values()
    )

    cloud_obj["pp_mean_visual_depth"] = (
        total_depth_sum / total_depth_count
    ) * meters_per_unit

    cloud_obj["pp_max_visual_depth"] = max(
        data["max_depth"] for data in memory.values()
    ) * meters_per_unit

    modifier = cloud_obj.modifiers.new(
        name="Point_Display",
        type='NODES'
    )

    node_group = bpy.data.node_groups.new(
        name + "_Point_Display",
        'GeometryNodeTree'
    )

    modifier.node_group = node_group

    node_group.interface.new_socket(
        name="Geometry",
        in_out='INPUT',
        socket_type='NodeSocketGeometry'
    )

    node_group.interface.new_socket(
        name="Geometry",
        in_out='OUTPUT',
        socket_type='NodeSocketGeometry'
    )

    nodes = node_group.nodes
    links = node_group.links

    input_node = nodes.new("NodeGroupInput")
    output_node = nodes.new("NodeGroupOutput")

    # Read each point's first-seen time.
    first_seen_node = nodes.new(
        "GeometryNodeInputNamedAttribute"
    )
    first_seen_node.name = "PP_First_Seen"
    first_seen_node.data_type = 'FLOAT'
    first_seen_node.inputs["Name"].default_value = "first_seen"

    # Animated 0.0 -> 1.0 value controlling how much of the
    # experience cloud has been revealed.
    progress_node = nodes.new("ShaderNodeValue")
    progress_node.name = "PP_Playback_Progress"
    progress_node.label = "Playback Progress"
    progress_node.outputs["Value"].default_value = 1.0

    # Delete points whose first_seen value is later than
    # the current playback progress.
    compare = nodes.new("FunctionNodeCompare")
    compare.name = "PP_Future_Compare"
    compare.data_type = 'FLOAT'
    compare.operation = 'GREATER_THAN'

    delete_geometry = nodes.new(
        "GeometryNodeDeleteGeometry"
    )
    delete_geometry.name = "PP_Delete_Future"
    delete_geometry.domain = 'POINT'

    mesh_to_points = nodes.new(
        "GeometryNodeMeshToPoints"
    )
    mesh_to_points.name = "PP_Mesh_To_Points"
    mesh_to_points.mode = 'VERTICES'
    mesh_to_points.inputs["Radius"].default_value = point_size

    set_material = nodes.new(
        "GeometryNodeSetMaterial"
    )
    set_material.name = "PP_Set_Material"
    set_material.label = "Analysis Material"

    analysis_material = configure_analysis_material(
        context.scene.pp_display_mode
    )

    set_material.inputs["Material"].default_value = (
        analysis_material
    )

    links.new(
        first_seen_node.outputs["Attribute"],
        compare.inputs["A"]
    )

    links.new(
        progress_node.outputs["Value"],
        compare.inputs["B"]
    )

    links.new(
        input_node.outputs["Geometry"],
        delete_geometry.inputs["Geometry"]
    )

    links.new(
        compare.outputs["Result"],
        delete_geometry.inputs["Selection"]
    )

    links.new(
        delete_geometry.outputs["Geometry"],
        mesh_to_points.inputs["Mesh"]
    )

    links.new(
        mesh_to_points.outputs["Points"],
        set_material.inputs["Geometry"]
    )

    links.new(
        set_material.outputs["Geometry"],
        output_node.inputs["Geometry"]
    )

    return cloud_obj


class PP_OT_scan_pov(bpy.types.Operator):

    bl_idname = "pp.scan_pov"
    bl_label = "Scan POV"

    def execute(self, context):

        scene = context.scene

        eye_obj = bpy.data.objects.get("Agent_Eye")
        target_obj = bpy.data.objects.get("Agent_Target")

        if eye_obj is None or target_obj is None:

            self.report(
                {'ERROR'},
                "Create Agent_Eye and Agent_Target first"
            )

            return {'CANCELLED'}

        eye = eye_obj.matrix_world.translation
        target = target_obj.matrix_world.translation

        forward_vector = target - eye

        if forward_vector.length == 0:

            self.report(
                {'ERROR'},
                "Agent_Target cannot occupy the same position as Agent_Eye"
            )

            return {'CANCELLED'}

        forward = forward_vector.normalized()

        world_up = Vector((0, 0, 1))

        if abs(forward.dot(world_up)) > 0.99:
            world_up = Vector((0, 1, 0))

        right = forward.cross(world_up).normalized()

        up = right.cross(forward).normalized()

        depsgraph = context.evaluated_depsgraph_get()

        hit_points = []

        horizontal_half = math.radians(
            scene.pp_horizontal_fov / 2.0
        )

        vertical_half = math.radians(
            scene.pp_vertical_fov / 2.0
        )

        horizontal_rays = scene.pp_horizontal_rays
        vertical_rays = scene.pp_vertical_rays

        for y in range(vertical_rays):

            v = y / max(
                vertical_rays - 1,
                1
            )

            vertical_angle = (
                -vertical_half
                + (2 * vertical_half * v)
            )

            for x in range(horizontal_rays):

                u = x / max(
                    horizontal_rays - 1,
                    1
                )

                horizontal_angle = (
                    -horizontal_half
                    + (2 * horizontal_half * u)
                )

                direction = (
                    forward
                    + right * math.tan(horizontal_angle)
                    + up * math.tan(vertical_angle)
                ).normalized()

                hit, location, normal, face_index, obj, matrix = (
                    scene.ray_cast(
                        depsgraph,
                        eye,
                        direction,
                        distance=scene.pp_max_distance
                    )
                )

                if hit:
                    hit_points.append(
                        location.copy()
                    )

        clear_old_cloud()

        mesh = bpy.data.meshes.new(
            "Perception_Cloud_Mesh"
        )

        mesh.from_pydata(
            hit_points,
            [],
            []
        )

        mesh.update()

        cloud_obj = bpy.data.objects.new(
            "Perception_Cloud",
            mesh
        )

        context.collection.objects.link(
            cloud_obj
        )

        modifier = cloud_obj.modifiers.new(
            name="Point_Display",
            type='NODES'
        )

        node_group = bpy.data.node_groups.new(
            "Perception_Point_Display",
            'GeometryNodeTree'
        )

        modifier.node_group = node_group

        node_group.interface.new_socket(
            name="Geometry",
            in_out='INPUT',
            socket_type='NodeSocketGeometry'
        )

        node_group.interface.new_socket(
            name="Geometry",
            in_out='OUTPUT',
            socket_type='NodeSocketGeometry'
        )

        nodes = node_group.nodes
        links = node_group.links

        input_node = nodes.new(
            "NodeGroupInput"
        )

        output_node = nodes.new(
            "NodeGroupOutput"
        )

        mesh_to_points = nodes.new(
            "GeometryNodeMeshToPoints"
        )

        mesh_to_points.mode = 'VERTICES'

        mesh_to_points.inputs[
            "Radius"
        ].default_value = scene.pp_point_size

        links.new(
            input_node.outputs["Geometry"],
            mesh_to_points.inputs["Mesh"]
        )

        links.new(
            mesh_to_points.outputs["Points"],
            output_node.inputs["Geometry"]
        )

        self.report(
            {'INFO'},
            f"Generated {len(hit_points)} perception points"
        )

        return {'FINISHED'}


# =======================================================
# PATHFINDING
# =======================================================

def build_obstacle_bvh(obj, depsgraph):

    evaluated = obj.evaluated_get(
        depsgraph
    )

    mesh = evaluated.to_mesh()

    if mesh is None:
        return None

    vertices = [
        evaluated.matrix_world @ vertex.co
        for vertex in mesh.vertices
    ]

    polygons = [
        tuple(poly.vertices)
        for poly in mesh.polygons
    ]

    if not vertices or not polygons:

        evaluated.to_mesh_clear()

        return None

    bvh = BVHTree.FromPolygons(
        vertices,
        polygons,
        all_triangles=False
    )

    evaluated.to_mesh_clear()

    return bvh

def world_bbox_xy(obj):

    corners = [
        obj.matrix_world @ Vector(corner)
        for corner in obj.bound_box
    ]

    min_x = min(p.x for p in corners)
    max_x = max(p.x for p in corners)

    min_y = min(p.y for p in corners)
    max_y = max(p.y for p in corners)

    return (
        min_x,
        max_x,
        min_y,
        max_y
    )


def get_obstacles(scene):

    obstacles = []

    for obj in scene.objects:

        if obj.hide_get():
            continue

        if obj.hide_viewport:
            continue

        if obj.type not in {
            'MESH',
            'CURVE'
        }:
            continue

        # Ignore our generated data
        if obj.name.startswith("Perception_"):
            continue

        if obj.name.startswith("PP_"):
            continue

        # Ignore very flat objects such as floors
        # Walls should usually be taller than this.
        if obj.dimensions.z < 0.3:
            continue

        obstacles.append(obj)

    return obstacles


def build_navigation_grid(
    start,
    end,
    obstacles,
    grid_size,
    clearance
):

    xs = [start.x, end.x]
    ys = [start.y, end.y]

    obstacle_boxes = []

    for obj in obstacles:

        min_x, max_x, min_y, max_y = (
            world_bbox_xy(obj)
        )

        obstacle_boxes.append(
            (
                min_x,
                max_x,
                min_y,
                max_y
            )
        )

        xs.extend(
            [min_x, max_x]
        )

        ys.extend(
            [min_y, max_y]
        )

    padding = 2.0

    world_min_x = min(xs) - padding
    world_max_x = max(xs) + padding

    world_min_y = min(ys) - padding
    world_max_y = max(ys) + padding

    width = math.ceil(
        (world_max_x - world_min_x)
        / grid_size
    )

    height = math.ceil(
        (world_max_y - world_min_y)
        / grid_size
    )

    # -----------------------------------------
    # BUILD ACTUAL GEOMETRY BVHs
    # -----------------------------------------

    depsgraph = bpy.context.evaluated_depsgraph_get()

    obstacle_bvhs = []

    for obj in obstacles:

        bvh = build_obstacle_bvh(
            obj,
            depsgraph
        )

        if bvh is not None:

            obstacle_bvhs.append(
                bvh
            )


    # -----------------------------------------
    # SAMPLE ACTUAL OBSTACLE FOOTPRINTS
    # -----------------------------------------

    blocked = set()

    ray_direction = Vector(
        (
            0,
            0,
            -1
        )
    )

    # Start well above the architecture.
    # We only care whether obstacle geometry
    # exists at this XY grid position.
    ray_start_z = 1000.0

    ray_distance = 2000.0


    for gx in range(width + 1):

        wx = (
            world_min_x
            + gx * grid_size
        )

        for gy in range(height + 1):

            wy = (
                world_min_y
                + gy * grid_size
            )

            ray_origin = Vector(
                (
                    wx,
                    wy,
                    ray_start_z
                )
            )

            for bvh in obstacle_bvhs:

                location, normal, index, distance = (
                    bvh.ray_cast(
                        ray_origin,
                        ray_direction,
                        ray_distance
                    )
                )

                if location is not None:

                    blocked.add(
                        (
                            gx,
                            gy
                        )
                    )

                    break

    # -----------------------------------------
    # EXPAND BLOCKED CELLS BY AGENT CLEARANCE
    # -----------------------------------------

    if clearance > 0.0:

        clearance_cells = math.ceil(
            clearance
            / grid_size
        )

        expanded_blocked = set(
            blocked
        )

        for gx, gy in blocked:

            for dx in range(
                -clearance_cells,
                clearance_cells + 1
            ):

                for dy in range(
                    -clearance_cells,
                    clearance_cells + 1
                ):

                    neighbor = (
                        gx + dx,
                        gy + dy
                    )

                    nx, ny = neighbor

                    if (
                        0 <= nx <= width
                        and
                        0 <= ny <= height
                        and math.hypot(dx, dy) * grid_size
                        <= clearance + 1e-9
                    ):

                        expanded_blocked.add(
                            neighbor
                        )

        blocked = expanded_blocked

    def world_to_grid(pos):

        gx = round(
            (pos.x - world_min_x)
            / grid_size
        )

        gy = round(
            (pos.y - world_min_y)
            / grid_size
        )

        return (
            gx,
            gy
        )

    def grid_to_world(node):

        gx, gy = node

        return Vector(
            (
                world_min_x
                + gx * grid_size,

                world_min_y
                + gy * grid_size,

                start.z
            )
        )

    return (
        width,
        height,
        blocked,
        world_to_grid,
        grid_to_world
    )


def heuristic(a, b):

    return math.sqrt(
        (a[0] - b[0]) ** 2
        +
        (a[1] - b[1]) ** 2
    )


def astar(
    start,
    goal,
    width,
    height,
    blocked
):

    open_heap = []

    heapq.heappush(
        open_heap,
        (0, start)
    )

    came_from = {}

    g_score = {
        start: 0
    }

    directions = [

        (1, 0),
        (-1, 0),

        (0, 1),
        (0, -1),

        (1, 1),
        (1, -1),

        (-1, 1),
        (-1, -1),
    ]

    while open_heap:

        _, current = heapq.heappop(
            open_heap
        )

        if current == goal:

            path = [current]

            while current in came_from:

                current = came_from[current]

                path.append(
                    current
                )

            path.reverse()

            return path

        for dx, dy in directions:

            neighbor = (
                current[0] + dx,
                current[1] + dy
            )

            nx, ny = neighbor

            if (
                nx < 0
                or
                ny < 0
                or
                nx > width
                or
                ny > height
            ):
                continue

            if neighbor in blocked:
                continue

            move_cost = (
                1.414
                if dx != 0 and dy != 0
                else 1.0
            )

            tentative = (
                g_score[current]
                + move_cost
            )

            if tentative < g_score.get(
                neighbor,
                float("inf")
            ):

                came_from[
                    neighbor
                ] = current

                g_score[
                    neighbor
                ] = tentative

                priority = (
                    tentative
                    + heuristic(
                        neighbor,
                        goal
                    )
                )

                heapq.heappush(
                    open_heap,
                    (
                        priority,
                        neighbor
                    )
                )

    return None


def create_path_curve(points):

    delete_object_by_name("PP_Path")

    curve_data = bpy.data.curves.new(
        "PP_Path_Curve",
        type='CURVE'
    )

    curve_data.dimensions = '3D'

    curve_data.bevel_depth = 0.04
    curve_data.bevel_resolution = 3

    spline = curve_data.splines.new(
        'POLY'
    )

    spline.points.add(
        len(points) - 1
    )

    for i, point in enumerate(points):

        spline.points[i].co = (
            point.x,
            point.y,
            point.z + 0.05,
            1
        )

    path_obj = bpy.data.objects.new(
        "PP_Path",
        curve_data
    )

    bpy.context.collection.objects.link(
        path_obj
    )

    return path_obj


class PP_OT_generate_path(bpy.types.Operator):

    bl_idname = "pp.generate_path"
    bl_label = "Generate Path"

    def execute(self, context):

        scene = context.scene

        start_obj = bpy.data.objects.get(
            "PP_Start"
        )

        end_obj = bpy.data.objects.get(
            "PP_End"
        )

        if start_obj is None or end_obj is None:

            self.report(
                {'ERROR'},
                "Create Start and End first"
            )

            return {'CANCELLED'}

        start = start_obj.matrix_world.translation
        end = end_obj.matrix_world.translation

        obstacles = get_obstacles(
            scene
        )

        (
            width,
            height,
            blocked,
            world_to_grid,
            grid_to_world
        ) = build_navigation_grid(

            start,
            end,
            obstacles,

            scene.pp_grid_size,
            scene.pp_clearance
        )

        start_node = world_to_grid(
            start
        )

        end_node = world_to_grid(
            end
        )

        # Start and end must always remain usable.
        blocked.discard(
            start_node
        )

        blocked.discard(
            end_node
        )

        node_path = astar(
            start_node,
            end_node,
            width,
            height,
            blocked
        )

        if node_path is None:

            self.report(
                {'ERROR'},
                "No path found"
            )

            return {'CANCELLED'}

        world_path = [
            grid_to_world(node)
            for node in node_path
        ]

        world_path[0] = start.copy()
        world_path[-1] = end.copy()

        create_path_curve(
            world_path
        )

        self.report(
            {'INFO'},
            f"Path generated with {len(world_path)} nodes"
        )

        return {'FINISHED'}


# =======================================================
# UI PANEL
# =======================================================

class PP_PT_main_panel(bpy.types.Panel):

    bl_label = "Perceptual Path"
    bl_idname = "PP_PT_main_panel"

    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Perceptual Path"

    def draw(self, context):

        layout = self.layout
        scene = context.scene

        # -----------------------
        # AGENT
        # -----------------------

        layout.label(text="AGENT")

        layout.operator(
            "pp.create_agent",
            icon='OUTLINER_OB_EMPTY'
        )

        layout.separator()

        # -----------------------
        # ROUTE
        # -----------------------

        layout.label(text="ROUTE")

        row = layout.row()

        row.operator("pp.create_start")
        row.operator("pp.create_end")

        layout.prop(
            scene,
            "pp_grid_size",
            text="Grid Size"
        )

        layout.prop(
            scene,
            "pp_clearance",
            text="Agent Clearance"
        )

        layout.operator(
            "pp.generate_path",
            icon='CURVE_PATH'
        )

        layout.prop(
            scene,
            "pp_eye_height",
            text="Eye Height"
        )

        layout.prop(
            scene,
            "pp_sample_every",
            text="Sample Every"
        )

        layout.prop(
            scene,
            "pp_voxel_size",
            text="Memory Cell Size"
        )

        layout.operator(
            "pp.run_experience",
            icon='PLAY'
        )

        layout.separator()

        # -----------------------
        # DISPLAY
        # -----------------------

        layout.label(text="DISPLAY")

        layout.prop(
            scene,
            "pp_display_mode",
            text=""
        )

        legend = layout.box()
        legend.label(text="LEGEND")

        if scene.pp_display_mode == 'PERSISTENCE':

            legend.label(
                text="Blue = Low persistence"
            )

            legend.label(
                text="Yellow = Moderate"
            )

            legend.label(
                text="Red = Highest in this run"
            )

            legend.separator()

            legend.label(
                text="Color = relative persistence"
            )

            legend.label(
                text="Summary % = absolute persistence"
            )

        elif scene.pp_display_mode == 'REVEAL':

            legend.label(
                text="Blue = Seen early"
            )

            legend.label(
                text="Purple = Mid journey"
            )

            legend.label(
                text="Red = Seen late"
            )

            legend.separator()

            legend.label(
                text="Metric:"
            )

            legend.label(
                text="When a region first entered"
            )

            legend.label(
                text="the agent's visual field"
            )

        elif scene.pp_display_mode == 'VISUAL_DEPTH':

            cloud = bpy.data.objects.get("PP_Experience_Cloud")

            if (
                cloud is None
                or cloud.type != 'MESH'
                or cloud.data.attributes.get("mean_depth") is None
            ):
                legend.label(text="Gray = Depth data unavailable")
                legend.label(text="Run Experience to calculate")

            else:
                depth_max = scene.pp_depth_display_max
                legend.label(text="Red/Orange = near")
                legend.label(
                    text=f"Yellow = {depth_max * 0.50:.1f} m"
                )
                legend.label(
                    text=f"Cyan = {depth_max * 0.75:.1f} m"
                )
                legend.label(
                    text=f"Blue = {depth_max:.1f} m or more"
                )

            legend.separator()
            legend.label(text="Metric:")
            legend.label(text="Mean first-hit distance")
            legend.label(text="for each visible region, in meters")

            layout.prop(
                scene,
                "pp_depth_display_max",
                text="Depth Color Max"
            )

        else:

            legend.label(
                text="Neutral perception cloud"
            )

        layout.label(
            text="Use Material Preview for colors",
            icon='INFO'
        )
        if scene.pp_display_mode == 'VISUAL_DEPTH':
            cloud = bpy.data.objects.get("PP_Experience_Cloud")

            if (
                cloud is None
                or cloud.type != 'MESH'
                or cloud.data.attributes.get("mean_depth") is None
            ):
                layout.label(
                    text="Run Experience to generate depth data",
                    icon='INFO'
                )
            else:
                layout.label(
                    text=(
                        f"Depth colors: 0–"
                        f"{scene.pp_depth_display_max:.1f} m"
                    ),
                    icon='INFO'
                )

        layout.separator()

        # -----------------------
        # PLAYBACK
        # -----------------------

        layout.label(text="PLAYBACK")

        layout.prop(
            scene,
            "pp_frames_per_step",
            text="Frames Per Step"
        )

        layout.operator(
            "pp.create_playback",
            icon='ANIM'
        )

        layout.label(
            text="Press Spacebar to play",
            icon='PLAY'
        )

        layout.separator()

        # -----------------------
        # ANALYSIS SUMMARY
        # -----------------------

        layout.label(
            text="ANALYSIS SUMMARY"
        )

        summary = layout.box()

        route_length = scene.get(
            "pp_route_length",
            None
        )

        if route_length is None:

            summary.label(
                text="Run Experience to calculate",
                icon='INFO'
            )

        else:

            viewpoints = scene.get(
                "pp_viewpoint_count",
                0
            )

            regions = scene.get(
                "pp_region_count",
                0
            )

            mean_persistence = scene.get(
                "pp_mean_persistence",
                0.0
            )

            max_persistence = scene.get(
                "pp_max_persistence",
                0.0
            )

            early_reveal = scene.get(
                "pp_early_reveal",
                0.0
            )

            mid_reveal = scene.get(
                "pp_mid_reveal",
                0.0
            )

            late_reveal = scene.get(
                "pp_late_reveal",
                0.0
            )

            summary.label(
                text=f"Route Length: {route_length:.2f} m"
            )

            summary.label(
                text=f"Viewpoints: {viewpoints}"
            )

            summary.label(
                text=f"Visible Regions: {regions}"
            )

            summary.separator()

            summary.label(
                text=(
                    f"Mean Persistence: "
                    f"{mean_persistence * 100:.1f}%"
                )
            )

            summary.label(
                text=(
                    f"Max Persistence: "
                    f"{max_persistence * 100:.1f}%"
                )
            )

            summary.separator()

            summary.label(
                text=(
                    f"Early Reveal: "
                    f"{early_reveal * 100:.1f}%"
                )
            )

            summary.label(
                text=(
                    f"Mid Reveal: "
                    f"{mid_reveal * 100:.1f}%"
                )
            )

            summary.label(
                text=(
                    f"Late Reveal: "
                    f"{late_reveal * 100:.1f}%"
                )
            )

        summary.separator()

        cloud = bpy.data.objects.get("PP_Experience_Cloud")

        if (
            cloud is not None
            and cloud.type == 'MESH'
            and cloud.data.attributes.get("mean_depth") is not None
            and "pp_mean_visual_depth" in cloud
            and "pp_max_visual_depth" in cloud
        ):
            mean_depth = cloud["pp_mean_visual_depth"]
            max_depth = cloud["pp_max_visual_depth"]

            summary.label(
                text=f"Mean Visual Depth: {mean_depth:.2f} m"
            )

            summary.label(
                text=f"Max Visual Depth: {max_depth:.2f} m"
            )

            units = scene.unit_settings
            meters_per_unit = (
                1.0 if units.system == 'NONE'
                else units.scale_length
            )
            ray_limit_m = (
                scene.pp_max_distance * meters_per_unit
            )

            if (
                ray_limit_m > 0.0
                and max_depth >= ray_limit_m * 0.98
            ):
                summary.label(
                    text="Max depth reaches ray limit",
                    icon='ERROR'
                )

        else:
            summary.label(
                text="Run Experience to calculate Visual Depth",
                icon='INFO'
            )

        layout.separator()

        # -----------------------
        # VISION
        # -----------------------

        layout.label(text="VISION")

        layout.prop(
            scene,
            "pp_horizontal_fov",
            text="Horizontal FOV"
        )

        layout.prop(
            scene,
            "pp_vertical_fov",
            text="Vertical FOV"
        )

        layout.prop(
            scene,
            "pp_horizontal_rays",
            text="Horizontal Rays"
        )

        layout.prop(
            scene,
            "pp_vertical_rays",
            text="Vertical Rays"
        )

        layout.prop(
            scene,
            "pp_max_distance",
            text="Max Distance"
        )

        layout.prop(
            scene,
            "pp_point_size",
            text="Point Size"
        )

        layout.operator(
            "pp.scan_pov",
            icon='HIDE_OFF'
        )

class PP_OT_run_experience(bpy.types.Operator):

    bl_idname = "pp.run_experience"
    bl_label = "Run Experience"
    bl_description = (
        "Move the virtual viewer along the generated path "
        "and accumulate visible geometry with perception memory"
    )

    def execute(self, context):

        scene = context.scene

        path_obj = bpy.data.objects.get(
            "PP_Path"
        )

        if path_obj is None:

            self.report(
                {'ERROR'},
                "Generate a path first"
            )

            return {'CANCELLED'}

        if path_obj.type != 'CURVE':

            self.report(
                {'ERROR'},
                "PP_Path is not a curve"
            )

            return {'CANCELLED'}

        if not path_obj.data.splines:

            self.report(
                {'ERROR'},
                "PP_Path has no spline data"
            )

            return {'CANCELLED'}

        spline = path_obj.data.splines[0]
        path_points = []

        for p in spline.points:

            local = Vector(
                (
                    p.co.x,
                    p.co.y,
                    p.co.z
                )
            )

            world = path_obj.matrix_world @ local
            path_points.append(world)

        if len(path_points) < 2:

            self.report(
                {'ERROR'},
                "Path needs at least two points"
            )

            return {'CANCELLED'}

        memory = {}

        eye_height = scene.pp_eye_height
        sample_every = max(
            1,
            scene.pp_sample_every
        )

        sampled_indices = list(
            range(
                0,
                len(path_points),
                sample_every
            )
        )

        # Always include the final position.
        if sampled_indices[-1] != len(path_points) - 1:
            sampled_indices.append(
                len(path_points) - 1
            )

        for step_number, index in enumerate(
            sampled_indices
        ):

            current = path_points[index]

            next_index = min(
                index + 1,
                len(path_points) - 1
            )

            if next_index == index:
                next_index = max(
                    index - 1,
                    0
                )

            next_point = path_points[next_index]

            eye = current + Vector(
                (0, 0, eye_height)
            )

            target = next_point + Vector(
                (0, 0, eye_height)
            )

            hits = cast_fov_detailed(
                context,
                eye,
                target,
                scene.pp_horizontal_fov,
                scene.pp_vertical_fov,
                scene.pp_horizontal_rays,
                scene.pp_vertical_rays,
                scene.pp_max_distance
            )

            # Group rays from this viewpoint by memory cell first.
            # A cell is counted once per sampled viewpoint, not once per ray.
            seen_this_step = {}

            for record in hits:

                hit = record["location"]
                distance = record["distance"]

                key = point_to_voxel(
                    hit,
                    scene.pp_voxel_size
                )

                if key not in seen_this_step:

                    seen_this_step[key] = {
                        "position_sum": hit.copy(),
                        "ray_count": 1,
                        "depth_sum": distance,
                        "min_depth": distance,
                        "max_depth": distance
                    }

                else:

                    step_data = seen_this_step[key]

                    step_data["position_sum"] += hit
                    step_data["ray_count"] += 1
                    step_data["depth_sum"] += distance

                    step_data["min_depth"] = min(
                        step_data["min_depth"],
                        distance
                    )

                    step_data["max_depth"] = max(
                        step_data["max_depth"],
                        distance
                    )

            for key, step_data in seen_this_step.items():

                step_position = (
                    step_data["position_sum"]
                    / step_data["ray_count"]
                )

                if key not in memory:

                    memory[key] = {
                        "position_sum": step_position.copy(),
                        "count": 1,
                        "first_seen": step_number,
                        "last_seen": step_number,
                        "depth_sum": step_data["depth_sum"],
                        "depth_count": step_data["ray_count"],
                        "min_depth": step_data["min_depth"],
                        "max_depth": step_data["max_depth"]
                    }

                else:

                    memory[key]["position_sum"] += step_position
                    memory[key]["count"] += 1
                    memory[key]["last_seen"] = step_number

                    memory[key]["depth_sum"] += step_data["depth_sum"]
                    memory[key]["depth_count"] += step_data["ray_count"]

                    memory[key]["min_depth"] = min(
                        memory[key]["min_depth"],
                        step_data["min_depth"]
                    )

                    memory[key]["max_depth"] = max(
                        memory[key]["max_depth"],
                        step_data["max_depth"]
                    )

        if len(memory) == 0:

            self.report(
                {'ERROR'},
                "Experience produced no visible points"
            )

            return {'CANCELLED'}

        create_memory_cloud(
            context,
            memory,
            "PP_Experience_Cloud",
            scene.pp_point_size,
            len(sampled_indices)
        )

        # ===================================================
        # ANALYSIS SUMMARY
        # ===================================================

        total_steps = max(
            len(sampled_indices),
            1
        )

        route_length = calculate_path_length(
            path_points
        )

        persistence_values = [
            data["count"] / total_steps
            for data in memory.values()
        ]

        mean_persistence = (
            sum(persistence_values)
            / len(persistence_values)
            if persistence_values
            else 0.0
        )

        max_persistence = (
            max(persistence_values)
            if persistence_values
            else 0.0
        )

        early_count = 0
        mid_count = 0
        late_count = 0

        for data in memory.values():

            reveal_position = (
                data["first_seen"]
                / max(total_steps - 1, 1)
            )

            if reveal_position < 0.333:
                early_count += 1

            elif reveal_position < 0.666:
                mid_count += 1

            else:
                late_count += 1

        region_count = len(memory)

        if region_count > 0:

            early_reveal = (
                early_count / region_count
            )

            mid_reveal = (
                mid_count / region_count
            )

            late_reveal = (
                late_count / region_count
            )

        else:

            early_reveal = 0.0
            mid_reveal = 0.0
            late_reveal = 0.0

        # Store the summary on the Blender scene so the
        # UI can display it without rerunning the simulation.
        scene["pp_route_length"] = route_length
        scene["pp_viewpoint_count"] = len(
            sampled_indices
        )
        scene["pp_region_count"] = region_count
        scene["pp_mean_persistence"] = (
            mean_persistence
        )
        scene["pp_max_persistence"] = (
            max_persistence
        )
        scene["pp_early_reveal"] = (
            early_reveal
        )
        scene["pp_mid_reveal"] = (
            mid_reveal
        )
        scene["pp_late_reveal"] = (
            late_reveal
        )

        self.report(
            {'INFO'},
            (
                f"Experience complete: "
                f"{len(sampled_indices)} viewpoints, "
                f"{len(memory)} perception cells"
            )
        )

        return {'FINISHED'}

def update_display_mode(self, context):
    """Update analysis colors, using plain display if depth data is missing."""

    cloud = bpy.data.objects.get(
        "PP_Experience_Cloud"
    )

    if cloud is None:
        return

    mode = context.scene.pp_display_mode

    if mode == 'VISUAL_DEPTH':
        if (
            cloud.type != 'MESH'
            or cloud.data.attributes.get("mean_depth") is None
        ):
            mode = 'PLAIN'

    configure_analysis_material(mode)

    modifier = cloud.modifiers.get(
        "Point_Display"
    )

    if modifier is None or modifier.node_group is None:
        return

    set_material = modifier.node_group.nodes.get(
        "PP_Set_Material"
    )

    if set_material is None:
        return

    set_material.inputs["Material"].default_value = (
        bpy.data.materials.get("PP_Analysis_Material")
    )


class PP_OT_create_playback(bpy.types.Operator):

    bl_idname = "pp.create_playback"
    bl_label = "Create Playback"

    bl_description = (
        "Animate the agent along the path and progressively "
        "reveal the perception cloud"
    )

    def execute(self, context):

        scene = context.scene

        path_obj = bpy.data.objects.get("PP_Path")

        if path_obj is None:
            self.report(
                {'ERROR'},
                "Generate a path first"
            )
            return {'CANCELLED'}

        if path_obj.type != 'CURVE' or not path_obj.data.splines:
            self.report(
                {'ERROR'},
                "PP_Path is not a valid curve"
            )
            return {'CANCELLED'}

        spline = path_obj.data.splines[0]

        path_points = []

        for p in spline.points:

            local = Vector(
                (
                    p.co.x,
                    p.co.y,
                    p.co.z
                )
            )

            world = (
                path_obj.matrix_world
                @ local
            )

            path_points.append(world)

        if len(path_points) < 2:
            self.report(
                {'ERROR'},
                "Path needs at least two points"
            )
            return {'CANCELLED'}

        sample_every = max(
            1,
            scene.pp_sample_every
        )

        sampled_indices = list(
            range(
                0,
                len(path_points),
                sample_every
            )
        )

        if sampled_indices[-1] != len(path_points) - 1:
            sampled_indices.append(
                len(path_points) - 1
            )

        eye = get_or_create_empty(
            "Agent_Eye"
        )

        target = get_or_create_empty(
            "Agent_Target"
        )

        eye.empty_display_type = 'SPHERE'
        eye.empty_display_size = 0.20

        target.empty_display_type = 'PLAIN_AXES'
        target.empty_display_size = 0.15

        eye.animation_data_clear()
        target.animation_data_clear()

        cloud = bpy.data.objects.get(
            "PP_Experience_Cloud"
        )

        if cloud is None:
            self.report(
                {'ERROR'},
                "Run Experience first"
            )
            return {'CANCELLED'}

        modifier = cloud.modifiers.get(
            "Point_Display"
        )

        if modifier is None or modifier.node_group is None:
            self.report(
                {'ERROR'},
                "Experience cloud has no playback node tree"
            )
            return {'CANCELLED'}

        node_group = modifier.node_group

        progress_node = node_group.nodes.get(
            "PP_Playback_Progress"
        )

        if progress_node is None:
            self.report(
                {'ERROR'},
                "Run Experience again using this v0.5 build"
            )
            return {'CANCELLED'}

        # Clear old node-tree animation only.
        node_group.animation_data_clear()

        progress_socket = progress_node.outputs["Value"]

        start_frame = 1
        frames_per_step = max(
            1,
            scene.pp_frames_per_step
        )

        total_steps = len(sampled_indices)

        end_frame = (
            start_frame
            + (total_steps - 1) * frames_per_step
        )

        scene.frame_start = start_frame
        scene.frame_end = end_frame

        for step_number, index in enumerate(
            sampled_indices
        ):

            frame = (
                start_frame
                + step_number * frames_per_step
            )

            current = path_points[index]

            next_index = min(
                index + 1,
                len(path_points) - 1
            )

            if next_index == index:
                next_index = max(
                    index - 1,
                    0
                )

            next_point = path_points[next_index]

            eye.location = (
                current
                + Vector(
                    (
                        0,
                        0,
                        scene.pp_eye_height
                    )
                )
            )

            target.location = (
                next_point
                + Vector(
                    (
                        0,
                        0,
                        scene.pp_eye_height
                    )
                )
            )

            eye.keyframe_insert(
                data_path="location",
                frame=frame
            )

            target.keyframe_insert(
                data_path="location",
                frame=frame
            )

            progress = (
                step_number
                / max(total_steps - 1, 1)
            )

            progress_socket.default_value = progress

            progress_socket.keyframe_insert(
                data_path="default_value",
                frame=frame
            )

        # Start with nothing revealed except cells first seen
        # at the beginning of the route.
        scene.frame_set(start_frame)

        self.report(
            {'INFO'},
            (
                f"Playback created: "
                f"frames {start_frame}–{end_frame}"
            )
        )

        return {'FINISHED'}


# =======================================================
# REGISTER
# =======================================================

classes = (

    PP_OT_create_start,
    PP_OT_create_end,
    PP_OT_create_agent,

    PP_OT_scan_pov,
    PP_OT_generate_path,
    PP_OT_run_experience,
    PP_OT_create_playback,

    PP_PT_main_panel,
)


def register():

    for cls in classes:
        bpy.utils.register_class(cls)

    bpy.types.Scene.pp_display_mode = (
        bpy.props.EnumProperty(
            name="Display Mode",
            items=[
                (
                    'PLAIN',
                    "Plain",
                    "Neutral perception point cloud"
                ),
                (
                    'PERSISTENCE',
                    "Persistence",
                    "Color by fraction of sampled viewpoints from which each cell was visible"
                ),
                (
                    'REVEAL',
                    "Reveal",
                    "Color by when each cell first became visible along the journey"
                ),
                (
                    'VISUAL_DEPTH',
                    "Visual Depth",
                    "Mean first-hit distance: red/orange at 0 m, yellow at 10 m, blue at 20 m and beyond"
                ),
            ],
            default='PERSISTENCE',
            update=update_display_mode
        )
    )

    bpy.types.Scene.pp_eye_height = (
        bpy.props.FloatProperty(
            name="Eye Height",
            default=1.65,
            min=0.5,
            max=3.0
        )
    )

    bpy.types.Scene.pp_sample_every = (
        bpy.props.IntProperty(
            name="Sample Every",
            default=3,
            min=1,
            max=20
        )
    )

    bpy.types.Scene.pp_voxel_size = (
        bpy.props.FloatProperty(
            name="Memory Cell Size",
            default=0.12,
            min=0.02,
            max=1.0
        )
    )

    bpy.types.Scene.pp_horizontal_fov = (
        bpy.props.FloatProperty(
            default=110.0,
            min=10.0,
            max=180.0
        )
    )

    bpy.types.Scene.pp_frames_per_step = (
        bpy.props.IntProperty(
            name="Frames Per Step",
            default=6,
            min=1,
            max=60
        )
    )

    bpy.types.Scene.pp_depth_display_max = (
        bpy.props.FloatProperty(
            name="Depth Color Max",
            description=(
                "Distance mapped to the far/blue end of the "
                "Visual Depth heatmap"
            ),
            default=20.0,
            min=1.0,
            max=500.0,
            update=update_display_mode
        )
    )

    bpy.types.Scene.pp_vertical_fov = (
        bpy.props.FloatProperty(
            default=70.0,
            min=10.0,
            max=180.0
        )
    )

    bpy.types.Scene.pp_horizontal_rays = (
        bpy.props.IntProperty(
            default=90,
            min=5,
            max=500
        )
    )

    bpy.types.Scene.pp_vertical_rays = (
        bpy.props.IntProperty(
            default=50,
            min=5,
            max=500
        )
    )

    bpy.types.Scene.pp_max_distance = (
        bpy.props.FloatProperty(
            default=50.0,
            min=0.1
        )
    )

    bpy.types.Scene.pp_point_size = (
        bpy.props.FloatProperty(
            default=0.035,
            min=0.001,
            max=1.0
        )
    )

    bpy.types.Scene.pp_grid_size = (
        bpy.props.FloatProperty(
            name="Grid Size",
            default=0.4,
            min=0.1,
            max=5.0
        )
    )

    bpy.types.Scene.pp_clearance = (
        bpy.props.FloatProperty(
            name="Agent Clearance",
            default=0.35,
            min=0.0,
            max=5.0
        )
    )


def unregister():

    del bpy.types.Scene.pp_display_mode
    del bpy.types.Scene.pp_eye_height
    del bpy.types.Scene.pp_sample_every
    del bpy.types.Scene.pp_voxel_size

    del bpy.types.Scene.pp_frames_per_step
    del bpy.types.Scene.pp_depth_display_max

    del bpy.types.Scene.pp_horizontal_fov
    del bpy.types.Scene.pp_vertical_fov

    del bpy.types.Scene.pp_horizontal_rays
    del bpy.types.Scene.pp_vertical_rays

    del bpy.types.Scene.pp_max_distance
    del bpy.types.Scene.pp_point_size

    del bpy.types.Scene.pp_grid_size
    del bpy.types.Scene.pp_clearance

    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)

if __name__ == "__main__":

    register()
