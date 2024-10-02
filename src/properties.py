import bpy, json
from ..ui import get_selected_mesh


class Properties(bpy.types.PropertyGroup):
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


def register():
    bpy.utils.register_class(Properties)
    bpy.types.Scene.mesh_properties = bpy.props.PointerProperty(type=Properties)


def unregister():
    del bpy.types.Scene.mesh_properties
    bpy.utils.unregister_class(Properties)
