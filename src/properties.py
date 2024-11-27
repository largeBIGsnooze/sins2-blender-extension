import bpy, json
from typing import List, Dict, Any

DEFAULT_TEMPLATE = {
    "global_settings": {
        "icon_zoom": 3.45,
        "hdri_path": "C:/Users/Noah/Downloads/rogland_clear_night_4k.exr",
    },
    "cameras": [
        {
            "filename_suffix": "tooltip_picture",
            "type": 'PERSP',
            "clip_end": 100000,
            "focal_length": 50,
            "samples": 32,
            "resolution_x": 918,
            "resolution_y": 432,
            "distance": 4,
            "horizontal_angle": -45,
            "vertical_angle": 45,
            "extra_zoom": 1.0,
            "tilt": -3,
            "transparent": "TRANSPARENT",
            "hdri_strength": 5.0,
            "offset_x": 0,
            "offset_y": 0,
            "offset_z": 0,
        },
        {
            "filename_suffix": "hud_picture",
            "type": 'PERSP',
            "clip_end": 100000,
            "focal_length": 50,
            "samples": 32,
            "resolution_x": 530,
            "resolution_y": 170,
            "distance": 4,
            "horizontal_angle": 60,
            "vertical_angle": 20,
            "extra_zoom": 1.0,
            "tilt": -3,
            "transparent": "SOLID",
            "hdri_strength": 4.0,
            "offset_x": 0,
            "offset_y": 0,
            "offset_z": 0,
        }
    ]
}

def meshpoint_name(self, context):
    if self.meshpoint_name != context.scene.mesh_properties.meshpoint_type:
        context.scene.mesh_properties.meshpoint_type = "custom"


def meshpoint_type(self, context):
    if context.scene.mesh_properties.meshpoint_type != "custom":
        context.scene.mesh_properties.meshpoint_name = (
            context.scene.mesh_properties.meshpoint_type
        )

class CameraProperties(bpy.types.PropertyGroup):
    filename_suffix: bpy.props.StringProperty(
        name="Filename Suffix",
        description="Filename suffix for the rendered image",
        default="New View",
    )
    
    type: bpy.props.EnumProperty(
        items=[("PERSP", "Perspective", ""), ("ORTHO", "Orthographic", "")],
        name="Camera Type",
        default="PERSP",
    )
    
    clip_end: bpy.props.FloatProperty(
        name="Camera Clip End",
        description="Clip end of the camera",
        default=100000,
        min=0.1,
    )
    
    focal_length: bpy.props.FloatProperty(
        name="F Length/Scale",
        description="Focal length for perspective cameras, or orthographic scale for ortho cameras",
        default=50,
        min=0.1,
    )

    samples: bpy.props.IntProperty(
        name="Samples",
        description="Render samples",
        default=32,
        min=1,
    )

    resolution_x: bpy.props.IntProperty(
        name="Res X",
        description="Resolution X",
        default=1920,
        min=1,
    )

    resolution_y: bpy.props.IntProperty(
        name="Res Y",
        description="Resolution Y",
        default=1080,
        min=1,
    )

    distance: bpy.props.FloatProperty(
        name="Distance",
        description="Distance from the model center",
        default=10.0,
        min=0.1,
    )
    
    horizontal_angle: bpy.props.FloatProperty(
        name="H Angle",
        description="Camera horizontal angle away from the center",
        default=45.0
    )
    
    vertical_angle: bpy.props.FloatProperty(
        name="V Angle",
        description="Camera vertical angle away from the center",
        default=30.0
    )

    extra_zoom: bpy.props.FloatProperty(
        name="Extra Zoom",
        description="Additional zoom factor",
        default=1.0,
        min=0.1,
    )

    tilt: bpy.props.FloatProperty(
        name="Tilt",
        description="Camera tilt in degrees",
        default=0,
    )

    transparent: bpy.props.EnumProperty(
        name="Background",
        description="Background type for rendering",
        items=[
            ("TRANSPARENT", "Transparent", "Render with transparent background"),
            ("SOLID", "Solid", "Render with solid background")
        ],
        default="TRANSPARENT"
    )

    hdri_strength: bpy.props.FloatProperty(
        name="HDRi Str",
        description="Strength of the HDRi",
        default=1.0,
        min=0.0,
    )

    offset_x: bpy.props.FloatProperty(
        name="X Offset",
        description="Camera X offset",
        default=0.0,
    )
    
    offset_y: bpy.props.FloatProperty(
        name="Y Offset",
        description="Camera Y offset",
        default=0.0,
    )
    
    offset_z: bpy.props.FloatProperty(
        name="Z Offset",
        description="Camera Z offset",
        default=0.0,
    )

class CameraTemplate(bpy.types.PropertyGroup):
    name: bpy.props.StringProperty(
        name="Template Name",
        description="Name of the camera template",
        default="New Template"
    )
    
    settings: bpy.props.CollectionProperty(type=CameraProperties)

    def save_current_cameras(self, context):
        """Save current camera settings to this template"""
        self.settings.clear()
        for camera in context.scene.mesh_properties.cameras:
            new_cam = self.settings.add()
            # Copy all properties
            for prop in camera.bl_rna.properties:
                if not prop.is_readonly:
                    setattr(new_cam, prop.identifier, getattr(camera, prop.identifier))

class Properties(bpy.types.PropertyGroup):
    show_camera_settings: bpy.props.BoolProperty(
        name="Show Camera Settings",
        description="Show or hide camera settings",
        default=False
    )
    
    def get_template_items(self, context):
        items = [
            ('DEFAULT', "Default", "Default camera configuration"),
            ('CUSTOM', "Custom", "Custom camera configuration"),
        ]
        
        # Add saved templates
        from .lib.template_manager import TemplateManager
        template_manager = TemplateManager()
        templates = template_manager.load_templates()
        for name in templates.keys():
            items.append((name, name, f"Load {name} template"))
            
        return items
        
    def load_camera_template(self, context):
        props = context.scene.mesh_properties
        
        if self.camera_template == 'DEFAULT':
            # Load default template
            props.icon_zoom = DEFAULT_TEMPLATE["global_settings"]["icon_zoom"]
            props.hdri_path = DEFAULT_TEMPLATE["global_settings"]["hdri_path"]
            
            props.cameras.clear()
            for camera_settings in DEFAULT_TEMPLATE["cameras"]:
                camera = props.cameras.add()
                for prop, value in camera_settings.items():
                    if hasattr(camera, prop):
                        setattr(camera, prop, value)
        
        elif self.camera_template == 'CUSTOM':
            # Keep current settings
            pass
        else:
            # Load from template manager
            from .lib.template_manager import TemplateManager
            template_manager = TemplateManager()
            template_manager.load_template(self.camera_template, props)
    
    camera_template: bpy.props.EnumProperty(
        name="Camera Template",
        description="Select a camera configuration template",
        items=get_template_items,
        default=0,  # Using integer index instead of string when items is a function
        update=load_camera_template
    )
    
    cameras: bpy.props.CollectionProperty(type=CameraProperties)

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

    hdri_strength: bpy.props.FloatProperty(
        name="HDRi Strength",
        description="Strength of the HDRi",
        default=1.0,
        min=0.0,
    )

def register():
    bpy.utils.register_class(CameraProperties)
    bpy.utils.register_class(CameraTemplate)
    bpy.utils.register_class(Properties)
    bpy.types.Scene.mesh_properties = bpy.props.PointerProperty(type=Properties)
    
    # Register the handler
    bpy.app.handlers.load_post.append(initialize_default_cameras)

@bpy.app.handlers.load_post.append
def initialize_default_cameras(dummy=None):
    """Initialize default camera settings"""
    try:
        if hasattr(bpy.context, "scene"):
            scene = bpy.context.scene
            if hasattr(scene, "mesh_properties"):
                if not scene.mesh_properties.cameras:
                    bpy.ops.sinsii.load_default_template()
    except Exception:
        # Scene or properties not yet available
        pass
    return None


def unregister():
    # Remove the handler first
    if initialize_default_cameras in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(initialize_default_cameras)
        
    # Then unregister classes
    del bpy.types.Scene.mesh_properties
    bpy.utils.unregister_class(Properties)
    bpy.utils.unregister_class(CameraProperties)