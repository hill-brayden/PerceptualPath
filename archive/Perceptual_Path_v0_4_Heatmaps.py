bl_info = {
    "name": "Perceptual Path",
    "author": "Brayden Hill",
    "version": (0, 4, 0),
    "blender": (4, 0, 0),
    "location": "View3D > Sidebar > Perceptual Path",
    "description": "Human perception point-cloud analysis for architectural space",
    "category": "3D View",
}

import bpy
import math
import heapq

from mathutils import Vector


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

    elif mode == 'REVEAL':
        attribute.attribute_name = "first_seen"
        low.position = 0.0
        high.position = 1.0
        low.color = (0.02, 0.55, 1.0, 1.0)
        high.color = (1.0, 0.12, 0.02, 1.0)

        middle = ramp.color_ramp.elements.new(0.5)
        middle.color = (0.55, 0.08, 0.85, 1.0)

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

    for i in range(len(points)):
        count_attr.data[i].value = counts[i]
        persistence_attr.data[i].value = persistence_values[i]
        first_seen_attr.data[i].value = first_seen_values[i]
        last_seen_attr.data[i].value = last_seen_values[i]

    cloud_obj = bpy.data.objects.new(name, mesh)
    context.collection.objects.link(cloud_obj)

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

    mesh_to_points = nodes.new("GeometryNodeMeshToPoints")
    mesh_to_points.mode = 'VERTICES'
    mesh_to_points.inputs["Radius"].default_value = point_size

    set_material = nodes.new("GeometryNodeSetMaterial")
    set_material.name = "PP_Set_Material"
    set_material.label = "Analysis Material"

    analysis_material = configure_analysis_material(
        context.scene.pp_display_mode
    )

    set_material.inputs["Material"].default_value = analysis_material

    links.new(
        input_node.outputs["Geometry"],
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

        if obj.type != 'MESH':
            continue

        # Ignore our generated data
        if obj.name.startswith("Perception_"):
            continue

        if obj.name.startswith("PP_"):
            continue

        # Ignore very flat objects such as floors
        # Walls should usually be taller than this.
        if obj.dimensions.z < 1.0:
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

        min_x -= clearance
        max_x += clearance

        min_y -= clearance
        max_y += clearance

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

    blocked = set()

    for gx in range(width + 1):

        wx = world_min_x + gx * grid_size

        for gy in range(height + 1):

            wy = world_min_y + gy * grid_size

            for (
                min_x,
                max_x,
                min_y,
                max_y
            ) in obstacle_boxes:

                if (
                    min_x <= wx <= max_x
                    and
                    min_y <= wy <= max_y
                ):

                    blocked.add(
                        (gx, gy)
                    )

                    break

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

        layout.label(
            text="Use Material Preview for colors",
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

            hits = cast_fov(
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

            for hit in hits:

                key = point_to_voxel(
                    hit,
                    scene.pp_voxel_size
                )

                if key not in seen_this_step:

                    seen_this_step[key] = {
                        "position_sum": hit.copy(),
                        "ray_count": 1
                    }

                else:

                    seen_this_step[key]["position_sum"] += hit
                    seen_this_step[key]["ray_count"] += 1

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
                        "last_seen": step_number
                    }

                else:

                    memory[key]["position_sum"] += step_position
                    memory[key]["count"] += 1
                    memory[key]["last_seen"] = step_number

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
    """Switch the existing cloud between plain, persistence, and reveal."""

    configure_analysis_material(
        context.scene.pp_display_mode
    )

    cloud = bpy.data.objects.get(
        "PP_Experience_Cloud"
    )

    if cloud is None:
        return

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