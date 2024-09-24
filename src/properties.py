import bpy, json
from ..ui import get_selected_mesh


def toggle_normal_orientation(self, context):
    for area in bpy.context.screen.areas:
        if not area.type == "VIEW_3D":
            continue
        for space in area.spaces:
            if not space.type == "VIEW_3D":
                continue
            space.overlay.show_face_orientation = (
                not space.overlay.show_face_orientation
            )
            break


def reset_team_colors(self, context):
    if context.scene.mesh_properties.enable_experimental_features == False:
        context.scene.mesh_properties.team_color_1 = (1, 1, 1, 1)
        context.scene.mesh_properties.team_color_2 = (1, 1, 1, 1)
        context.scene.mesh_properties.team_color_3 = (1, 1, 1, 1)


class Properties(bpy.types.PropertyGroup):
    check_normals_orientation: bpy.props.BoolProperty(
        name="Toggle normal orientation",
        default=False,
        update=toggle_normal_orientation,
    )

    team_color_1: bpy.props.FloatVectorProperty(
        name="",
        subtype="COLOR",
        min=0,
        max=1,
        size=4,
        default=(1, 1, 1, 1),
    )
    team_color_2: bpy.props.FloatVectorProperty(
        name="",
        subtype="COLOR",
        min=0,
        max=1,
        size=4,
        default=(1, 1, 1, 1),
    )
    team_color_3: bpy.props.FloatVectorProperty(
        name="", subtype="COLOR", min=0, max=1, size=4, default=(1, 1, 1, 1)
    )

    enable_experimental_features: bpy.props.BoolProperty(
        name="Experimental features", default=False, update=reset_team_colors
    )


def register():
    bpy.utils.register_class(Properties)
    bpy.types.Scene.mesh_properties = bpy.props.PointerProperty(type=Properties)


def unregister():
    del bpy.types.Scene.mesh_properties
    bpy.utils.unregister_class(Properties)
