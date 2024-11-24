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

    icon_size: bpy.props.EnumProperty(
        name="Icon Size",
        items=[
            ('200', '200x200', 'Recommended icon size'),
            ('256', '256x256', 'Small icon size'),
            ('512', '512x512', 'Medium icon size'),
            ('1024', '1024x1024', 'Large icon size')
        ],
        default='200'
    )
    icon_zoom: bpy.props.FloatProperty(
        name="Camera Zoom",
        default=3.0,
        min=1.0,
        max=5.0,
        step=0.1
    )
    icon_border_thickness: bpy.props.IntProperty(
        name="Border Thickness",
        default=2,
        min=1,
        max=5
    )
    icon_height_threshold: bpy.props.FloatProperty(
        name="Detail Threshold",
        default=0.01,
        min=0.001,
        max=1.0,
        step=0.001
    )
    icon_rotation: bpy.props.FloatProperty(
        name="Rotation",
        default=90.0,
        min=-360.0,
        max=360.0,
        step=1.0
    )
    icon_kernel_size: bpy.props.IntProperty(
        name="Kernel Size",
        default=5,
        min=1,
        max=15
    )
    icon_border_hardness: bpy.props.FloatProperty(
        name="Border Hardness",
        default=1.0,
        min=0.0,
        max=10.0
    )


def register():
    bpy.utils.register_class(Properties)
    bpy.types.Scene.mesh_properties = bpy.props.PointerProperty(type=Properties)


def unregister():
    del bpy.types.Scene.mesh_properties
    bpy.utils.unregister_class(Properties)
