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


class Properties(bpy.types.PropertyGroup):
    check_normals_orientation: bpy.props.BoolProperty(
        name="Toggle normal orientation",
        default=False,
        update=toggle_normal_orientation,
    )

    enable_experimental_features: bpy.props.BoolProperty(
        name="Experimental features", default=False
    )


def register():
    bpy.utils.register_class(Properties)
    bpy.types.Scene.mesh_properties = bpy.props.PointerProperty(type=Properties)


def unregister():
    del bpy.types.Scene.mesh_properties
    bpy.utils.unregister_class(Properties)
