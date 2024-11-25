import bpy, json


def meshpoint_name(self, context):
    if self.meshpoint_name != context.scene.mesh_properties.meshpoint_type:
        context.scene.mesh_properties.meshpoint_type = "custom"


def meshpoint_type(self, context):
    if context.scene.mesh_properties.meshpoint_type != "custom":
        context.scene.mesh_properties.meshpoint_name = (
            context.scene.mesh_properties.meshpoint_type
        )


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

    meshpoint_name: bpy.props.StringProperty(
        name="", default="REPLACE_ME", maxlen=100, update=meshpoint_name
    )

    duplicate_meshpoint_toggle: bpy.props.BoolProperty(
        name="Duplicate meshpoints", default=False
    )

    toggle_teamcolor: bpy.props.BoolProperty(name="Enable Team Color", default=True)

    meshpoint_type: bpy.props.EnumProperty(
        items=[
            ("", "Meshpoint Types", ""),
            ("custom", "--custom--", ""),
            ("ability", "ability", ""),
            ("bomb", "bomb", ""),
            ("exhaust", "exhaust", ""),
            ("hangar", "hangar", ""),
            ("turret_muzzle", "turret_muzzle", ""),
            ("ship_build", "ship_build", ""),
            ("extractor", "extractor", ""),
        ],
        name="",
        default="custom",
        update=meshpoint_type,
    )

    icon_zoom: bpy.props.FloatProperty(
        name="Icon Zoom",
        description="Controls the size of the icon in the image",
        default=3.45,
        min=0.01,
        max=10.0,
        step=0.01,
    )

    hdri_path: bpy.props.StringProperty(
        name="HDRi Path",
        description="Path to the HDRi file",
        default="",
    )

    starfield_mix: bpy.props.FloatProperty(
        name="Starfield Mix",
        description="Controls the mix of starfield and environment",
        default=0.5,
    )

    ambient_strength: bpy.props.FloatProperty(
        name="Ambient Strength",
        description="Controls the strength of the ambient light",
        default=0.7,
    )

    background_strength: bpy.props.FloatProperty(
        name="Background Strength",
        description="Controls the strength of the background light",
        default=1.0,
    )

    hdri_strength: bpy.props.FloatProperty(
        name="HDRi Strength",
        description="Controls the strength of the HDRi background",
        default=15.0,
        min=0.0,
        soft_max=20.0,
    )

    camera_distance: bpy.props.FloatProperty(
        name="Camera Distance",
        description="Controls how far the camera is from the subject",
        default=100.0,
        min=0.1,
        soft_max=1000.0,
    )

    focal_length: bpy.props.FloatProperty(
        name="Focal Length",
        description="Camera focal length in millimeters",
        default=24.0,
        min=1.0,
        soft_max=200.0,
    )

    light_distance: bpy.props.FloatProperty(
        name="Light Distance",
        description="Controls the distance of the lights from the subject",
        default=100.0,
        min=0.1,
        soft_max=1000.0,
    )


def register():
    bpy.utils.register_class(Properties)
    bpy.types.Scene.mesh_properties = bpy.props.PointerProperty(type=Properties)


def unregister():
    del bpy.types.Scene.mesh_properties
    bpy.utils.unregister_class(Properties)