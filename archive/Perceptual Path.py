bl_info = {
    "name": "Perceptual Path",
    "author": "Brayden Hill",
    "version": (0, 1, 0),
    "blender": (4, 0, 0),
    "location": "View3D > Sidebar > Perceptual Path",
    "description": "Human perception point-cloud analysis for architectural space",
    "category": "3D View",
}

import bpy
import math
from mathutils import Vector


# -------------------------------------------------------
# HELPERS
# -------------------------------------------------------

def get_or_create_empty(name, location=(0, 0, 0)):
    obj = bpy.data.objects.get(name)

    if obj is None:
        obj = bpy.data.objects.new(name, None)
        obj.empty_display_type = 'PLAIN_AXES'
        obj.empty_display_size = 0.4
        obj.location = location
        bpy.context.collection.objects.link(obj)

    return obj


def clear_old_cloud():
    old = bpy.data.objects.get("Perception_Cloud")

    if old:
        bpy.data.objects.remove(old, do_unlink=True)


# -------------------------------------------------------
# CREATE START
# -------------------------------------------------------

class PP_OT_create_start(bpy.types.Operator):
    bl_idname = "pp.create_start"
    bl_label = "Create Start"
    bl_description = "Create the agent start point"

    def execute(self, context):

        obj = get_or_create_empty(
            "PP_Start",
            context.scene.cursor.location
        )

        bpy.context.view_layer.objects.active = obj
        obj.select_set(True)

        return {'FINISHED'}


# -------------------------------------------------------
# CREATE END
# -------------------------------------------------------

class PP_OT_create_end(bpy.types.Operator):
    bl_idname = "pp.create_end"
    bl_label = "Create End"
    bl_description = "Create the agent destination"

    def execute(self, context):

        obj = get_or_create_empty(
            "PP_End",
            context.scene.cursor.location
        )

        bpy.context.view_layer.objects.active = obj
        obj.select_set(True)

        return {'FINISHED'}


# -------------------------------------------------------
# CREATE AGENT
# -------------------------------------------------------

class PP_OT_create_agent(bpy.types.Operator):
    bl_idname = "pp.create_agent"
    bl_label = "Create Agent"
    bl_description = "Create Agent_Eye and Agent_Target"

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


# -------------------------------------------------------
# POV SCANNER
# -------------------------------------------------------

class PP_OT_scan_pov(bpy.types.Operator):
    bl_idname = "pp.scan_pov"
    bl_label = "Scan POV"
    bl_description = "Generate perception cloud from the human field of view"

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
                "Agent_Target cannot be at the same location as Agent_Eye"
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

        horizontal_half = math.radians(scene.pp_horizontal_fov / 2.0)
        vertical_half = math.radians(scene.pp_vertical_fov / 2.0)

        horizontal_rays = scene.pp_horizontal_rays
        vertical_rays = scene.pp_vertical_rays

        for y in range(vertical_rays):

            v = y / max(vertical_rays - 1, 1)

            vertical_angle = (
                -vertical_half +
                (2 * vertical_half * v)
            )

            for x in range(horizontal_rays):

                u = x / max(horizontal_rays - 1, 1)

                horizontal_angle = (
                    -horizontal_half +
                    (2 * horizontal_half * u)
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
                    hit_points.append(location.copy())

        clear_old_cloud()

        mesh = bpy.data.meshes.new("Perception_Cloud_Mesh")
        mesh.from_pydata(hit_points, [], [])
        mesh.update()

        cloud_obj = bpy.data.objects.new(
            "Perception_Cloud",
            mesh
        )

        context.collection.objects.link(cloud_obj)

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

        input_node = nodes.new("NodeGroupInput")
        output_node = nodes.new("NodeGroupOutput")
        mesh_to_points = nodes.new("GeometryNodeMeshToPoints")

        mesh_to_points.mode = 'VERTICES'
        mesh_to_points.inputs["Radius"].default_value = scene.pp_point_size

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


# -------------------------------------------------------
# SIDEBAR PANEL
# -------------------------------------------------------

class PP_PT_main_panel(bpy.types.Panel):
    bl_label = "Perceptual Path"
    bl_idname = "PP_PT_main_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Perceptual Path"

    def draw(self, context):

        layout = self.layout
        scene = context.scene

        layout.label(text="AGENT")

        layout.operator(
            "pp.create_agent",
            icon='OUTLINER_OB_EMPTY'
        )

        layout.separator()

        layout.label(text="ROUTE")

        row = layout.row()
        row.operator("pp.create_start")
        row.operator("pp.create_end")

        layout.separator()

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

        layout.separator()

        layout.operator(
            "pp.scan_pov",
            icon='HIDE_OFF'
        )


# -------------------------------------------------------
# REGISTER
# -------------------------------------------------------

classes = (
    PP_OT_create_start,
    PP_OT_create_end,
    PP_OT_create_agent,
    PP_OT_scan_pov,
    PP_PT_main_panel,
)


def register():

    for cls in classes:
        bpy.utils.register_class(cls)

    bpy.types.Scene.pp_horizontal_fov = bpy.props.FloatProperty(
        name="Horizontal FOV",
        default=110.0,
        min=10.0,
        max=180.0
    )

    bpy.types.Scene.pp_vertical_fov = bpy.props.FloatProperty(
        name="Vertical FOV",
        default=70.0,
        min=10.0,
        max=180.0
    )

    bpy.types.Scene.pp_horizontal_rays = bpy.props.IntProperty(
        name="Horizontal Rays",
        default=90,
        min=5,
        max=500
    )

    bpy.types.Scene.pp_vertical_rays = bpy.props.IntProperty(
        name="Vertical Rays",
        default=50,
        min=5,
        max=500
    )

    bpy.types.Scene.pp_max_distance = bpy.props.FloatProperty(
        name="Max Distance",
        default=50.0,
        min=0.1
    )

    bpy.types.Scene.pp_point_size = bpy.props.FloatProperty(
        name="Point Size",
        default=0.035,
        min=0.001,
        max=1.0
    )


def unregister():

    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)

    del bpy.types.Scene.pp_horizontal_fov
    del bpy.types.Scene.pp_vertical_fov
    del bpy.types.Scene.pp_horizontal_rays
    del bpy.types.Scene.pp_vertical_rays
    del bpy.types.Scene.pp_max_distance
    del bpy.types.Scene.pp_point_size


if __name__ == "__main__":
    register()