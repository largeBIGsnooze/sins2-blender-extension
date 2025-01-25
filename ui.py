import bpy, json, os, math, subprocess, re, shutil, time, bmesh, sys
from struct import unpack, pack
from bpy_extras.io_utils import ExportHelper, ImportHelper
from mathutils import Vector, Matrix
from .src.lib.helpers.mesh import MeshMaterial
from . import bl_info, TEMP_TEXTURES_PATH
from .src.lib.github_downloader import Github
from .src.lib.binary_reader import BinaryReader
from .src.lib.helpers.cryptography import generate_hash_from_directory
from .config import AddonSettings
from .src.lib.helpers.mesh_utils import (
    get_bounding_box,
    get_unused_materials,
    get_avaliable_sorted_materials,
    get_materials,
    apply_transforms,
    get_original_transforms,
    create_and_move_mesh_materials,
    restore_mesh_transforms,
    join_meshes,
    purge_orphans,
    make_meshpoint_rules,
    run_meshbuilder,
    run_texconv,
    convert_rebellion_mesh,
)
from .src.lib.helpers.filesystem import normalize, basename
from .src.lib.render_manager import RenderManager
from .src.lib.image_processor import IconProcessor
from .constants import (
    CWD_PATH,
    ADDON_SETTINGS_FILE,
    GAME_MATRIX,
    MESHBUILDER_EXE,
    MESHPOINT_COLOR,
    MESHPOINT_MATRIX,
    MESHPOINTING_RULES,
    TEMP_DIR,
    TEXCONV_EXE,
    REBELLION_PATH,
)

github = Github(TEMP_DIR)

def is_debugging():
    return sys.gettrace() is not None

# check for updates when extension activates
if not is_debugging():
    try:
        latest_version = github.fetch_latest_commit()
    except:
        latest_version = None
else:
    latest_version = None

settings = AddonSettings(ADDON_SETTINGS_FILE)
settings.init()

SETTINGS = settings.load_settings()

if "is_first_installation" in SETTINGS:
    SETTINGS["current_version"] = latest_version
    del SETTINGS["is_first_installation"]
    settings.save_settings()

has_update = False if is_debugging() else SETTINGS["current_version"] != latest_version


class SINSII_Main_Panel:

    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Sins II Extension"


class SINSII_PT_Panel(SINSII_Main_Panel, bpy.types.Panel):
    bl_label = "Import/Export"
    bl_order = 1

    def draw(self, context):
        row = self.layout.row(align=True)
        row.operator("sinsii.export_mesh", icon="EXPORT", text="Export mesh")
        row.separator(factor=0.5)
        row.operator("sinsii.import_mesh", icon="IMPORT", text="Import mesh")
        col = self.layout.column(align=True)
        # col.separator(factor=1.0)
        # col.operator("sinsii.debug")
        box = col.box()
        if context.scene.mesh_properties.toggle_teamcolor:
            box.label(text="Primary, Secondary, Emissive")
            row = box.row()
            row.prop(context.scene.mesh_properties, "team_color_1")
            row.prop(context.scene.mesh_properties, "team_color_2")
            row.prop(context.scene.mesh_properties, "team_color_3")
        else:
            box.label(text="Emissive")
            box.prop(context.scene.mesh_properties, "team_color_3")

        if SETTINGS["has_synchronized_meshpoint_color"] == False:
            col = col.column()
            col.separator(factor=1.0)
            col.operator("sinsii.sync_color", text="Synchronize Meshpoint Color")
        else:
            for theme in bpy.context.preferences.themes:
                if tuple(theme.view_3d.empty) != MESHPOINT_COLOR:
                    SETTINGS["has_synchronized_meshpoint_color"] = False
                    settings.save_settings()
                    break

        box.prop(context.scene.mesh_properties, "toggle_teamcolor")


class SINSII_PT_Render_Panel(SINSII_Main_Panel, bpy.types.Panel):
    bl_label = "Renders"
    bl_idname = "SINSII_PT_render_settings"
    bl_options = {"DEFAULT_CLOSED"}
    bl_order = 5

    def draw(self, context):
        layout = self.layout
        props = context.scene.mesh_properties

        # Render Buttons
        box = layout.box()
        box.label(text="Render", icon="RENDER_STILL")
        row = box.row()
        selected_mesh = get_selected_mesh()
        if (
            selected_mesh
            and selected_mesh.type == "MESH"
            and selected_mesh.data.vertices
        ):
            row.operator("sinsii.render_perspective", text="Render Scene")
            row.operator("sinsii.render_top_down", text="Render Icon")
        else:
            row.label(text="No valid mesh selected!", icon="ERROR")

        # Template Selection
        box = layout.box()
        box.label(text="Camera Templates", icon="CAMERA_DATA")
        # Check if we have any cameras set up
        if len(props.cameras) == 0:
            row = box.row()
            row.operator(
                "sinsii.load_default_template",
                icon="FILE_TICK",
                text="Load Default Template",
            )
        else:
            row = box.row()
            row.prop(props, "camera_template", text="")

        # HDRI Settings
        box = layout.box()
        box.label(text="HDRI Settings", icon="WORLD")
        row = box.row(align=True)
        row.prop(props, "hdri_path", text="")
        row.operator("sinsii.pick_hdri", icon="FILE_FOLDER", text="")

        # Icon Settings
        box = layout.box()
        box.label(text="Icon Settings", icon="IMAGE_DATA")
        box.prop(props, "icon_zoom", text="Icon Zoom")

        # Template Management
        if props.camera_template == "CUSTOM":
            row = box.row()
            row.operator(
                "sinsii.save_camera_template", icon="FILE_TICK", text="Save As Template"
            )
        elif props.camera_template not in ["DEFAULT", "CUSTOM"]:
            row = box.row()
            row.operator(
                "sinsii.remove_camera_template", icon="X", text="Remove Template"
            )

        # Camera Settings
        box = layout.box()
        row = box.row()
        row.prop(
            props,
            "show_camera_settings",
            icon="TRIA_DOWN" if props.show_camera_settings else "TRIA_RIGHT",
            icon_only=True,
        )
        row.label(text="Camera Settings", icon="SCENE")

        if props.show_camera_settings:
            # Header row with scene numbers and remove buttons
            row = box.row()
            row.label(text="")  # Empty cell for property names
            for i, _ in enumerate(props.cameras):
                col = row.column()
                sub_row = col.row(align=True)
                sub_row.label(text=f"Camera {i+1}")
                if (
                    len(props.cameras) > 1
                ):  # Only show remove button if we have more than one camera
                    op = sub_row.operator(
                        "sinsii.remove_render_scene", text="", icon="X"
                    )
                    op.camera_index = i

            # Settings rows
            def add_setting_row(label, prop_name):
                row = box.row()
                row.label(text=label)
                for camera in props.cameras:
                    col = row.column()
                    if isinstance(getattr(camera, prop_name), bool):
                        # Center boolean toggles
                        split = col.split(factor=0.5)
                        split.alignment = "CENTER"
                        split.prop(camera, prop_name, text="")
                    else:
                        col.prop(camera, prop_name, text="")

            add_setting_row("Name", "filename_suffix")
            add_setting_row("Type", "type")
            add_setting_row("Clip End", "clip_end")
            add_setting_row("F Length", "focal_length")
            add_setting_row("Samples", "samples")
            add_setting_row("Res X", "resolution_x")
            add_setting_row("Res Y", "resolution_y")
            add_setting_row("Distance", "distance")
            add_setting_row("H Angle", "horizontal_angle")
            add_setting_row("V Angle", "vertical_angle")
            add_setting_row("Tilt", "tilt")
            add_setting_row("Transparent", "transparent")
            add_setting_row("HDRI Str", "hdri_strength")
            add_setting_row("X Offset", "offset_x")
            add_setting_row("Y Offset", "offset_y")
            add_setting_row("Z Offset", "offset_z")
            add_setting_row("Lighting", "lighting_enabled")
            add_setting_row("Light Dis", "lighting_distance")
            add_setting_row("Light Size", "light_size_multiplier")
            add_setting_row("Key Light", "key_light_energy")
            add_setting_row("Fill Light", "fill_light_energy")
            add_setting_row("Back Light", "back_light_energy")
            add_setting_row("Sun", "sun_enabled")
            add_setting_row("Sun Energy", "sun_energy")
            add_setting_row("Sun H", "sun_angle_h")
            add_setting_row("Sun V", "sun_angle_v")

        # Scene Management
        row = box.row()
        row.operator("sinsii.add_render_scene", icon="ADD", text="Add Camera")


class SINSII_OT_Load_Default_Template(bpy.types.Operator):
    bl_idname = "sinsii.load_default_template"
    bl_label = "Load Default Template"
    bl_description = "Load the default camera configuration template"

    def execute(self, context):
        props = context.scene.mesh_properties
        props.camera_template = "DEFAULT"  # This will trigger the update function
        return {"FINISHED"}


class SINSII_OT_Add_Render_Scene(bpy.types.Operator):
    bl_idname = "sinsii.add_render_scene"
    bl_label = "Add Render Scene"
    bl_description = "Add a new render scene configuration"

    def execute(self, context):
        props = context.scene.mesh_properties
        new_camera = props.cameras.add()

        # Set default camera name
        new_camera.filename_suffix = f"view_{len(props.cameras)}"

        # Copy settings from last camera if it exists
        if len(props.cameras) > 1:
            last_camera = props.cameras[-2]
            for prop in new_camera.bl_rna.properties:
                if (
                    not prop.is_readonly and prop.identifier != "filename_suffix"
                ):  # Don't copy the name
                    setattr(
                        new_camera,
                        prop.identifier,
                        getattr(last_camera, prop.identifier),
                    )
        return {"FINISHED"}


class SINSII_OT_Remove_Render_Scene(bpy.types.Operator):
    bl_idname = "sinsii.remove_render_scene"
    bl_label = "Remove Render Scene"
    bl_description = "Remove this render scene configuration"

    camera_index: bpy.props.IntProperty()

    def execute(self, context):
        props = context.scene.mesh_properties
        if len(props.cameras) > 1:  # Keep at least one camera
            props.cameras.remove(self.camera_index)
        return {"FINISHED"}


class SINSII_OT_Render_Top_Down(bpy.types.Operator, ExportHelper):
    bl_label = "Render Top Down Icon"
    bl_description = "Creates a top-down orthographic render of the selected object in full white with a transparent background"
    bl_idname = "sinsii.render_top_down"

    filename_ext = ".png"
    filter_glob: bpy.props.StringProperty(default="*.png", options={"HIDDEN"})

    @classmethod
    def poll(cls, context):
        return context.mode == "OBJECT" and get_selected_mesh() is not None

    def invoke(self, context, event):
        mesh = get_selected_mesh()
        if mesh:
            self.filepath = f"{mesh.name}_main_view_icon.png"
        return super().invoke(context, event)

    def execute(self, context):
        try:
            mesh = get_selected_mesh()
            if not mesh:
                self.report({"ERROR"}, "No mesh selected!")
                return {"CANCELLED"}

            render_manager = RenderManager(context, mesh, self.filepath)

            # Setup everything for icon rendering
            render_manager.setup_icon_render_settings()
            render_manager.setup_transparent_world()
            render_manager.setup_icon_materials()
            render_manager.setup_top_down_camera(
                context.scene.mesh_properties.icon_zoom
            )

            # Render and get the unique path
            unique_filepath = render_manager.render(self.filepath)

            # Post-process using the unique filepath
            processor = IconProcessor()
            if processor.process_icon(unique_filepath):
                self.report({"INFO"}, f"Icon render saved to: {unique_filepath}")
            else:
                self.report(
                    {"WARNING"},
                    f"Render saved but post-processing failed: {unique_filepath}",
                )

        except Exception as e:
            self.report({"ERROR"}, f"Render failed: {str(e)}")
            return {"CANCELLED"}

        finally:
            if "render_manager" in locals():
                render_manager.cleanup()
                render_manager.cleanup_icon_materials()

        return {"FINISHED"}


class SINSII_OT_Render_Perspective(bpy.types.Operator, ExportHelper):
    bl_label = "Render Perspective View"
    bl_description = "Creates perspective renders of the model with original materials"
    bl_idname = "sinsii.render_perspective"

    filename_ext = ""
    use_filter_folder = True
    directory: bpy.props.StringProperty(
        name="Output Directory",
        description="Directory to save renders",
        subtype="DIR_PATH",
    )

    def execute(self, context):
        try:
            mesh = get_selected_mesh()
            if not mesh:
                self.report({"ERROR"}, "No mesh selected!")
                return {"CANCELLED"}

            render_manager = RenderManager(context, mesh, self.directory)
            render_manager.render_all_scenes(self.directory)

            self.report({"INFO"}, f"All scenes rendered successfully")

        except Exception as e:
            self.report({"ERROR"}, f"Render failed: {str(e)}")
            return {"CANCELLED"}

        finally:
            if "render_manager" in locals():
                render_manager.cleanup()

        return {"FINISHED"}


class SINSII_OT_Pick_HDRI(bpy.types.Operator, ImportHelper):
    bl_idname = "sinsii.pick_hdri"
    bl_label = "Select HDRI"

    filename_ext = ".hdr;.exr"
    filter_glob: bpy.props.StringProperty(
        default="*.hdr;*.exr",
        options={"HIDDEN"},
    )

    def execute(self, context):
        context.scene.mesh_properties.hdri_path = self.filepath
        return {"FINISHED"}


class SINSII_OT_Save_Camera_Template(bpy.types.Operator):
    bl_idname = "sinsii.save_camera_template"
    bl_label = "Save Camera Template"
    bl_description = "Save current camera configuration as a template"

    template_name: bpy.props.StringProperty(
        name="Template Name",
        description="Name for the new template",
        default="My Template",
    )

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "template_name")

    def execute(self, context):
        from .src.lib.template_manager import TemplateManager

        template_manager = TemplateManager()

        # Save all current cameras to template
        template_manager.save_template(
            self.template_name, context.scene.mesh_properties
        )

        # Force update of template enum
        context.scene.mesh_properties.property_unset("camera_template")

        self.report({"INFO"}, f"Saved template: {self.template_name}")
        return {"FINISHED"}


class SINSII_OT_Remove_Camera_Template(bpy.types.Operator):
    bl_idname = "sinsii.remove_camera_template"
    bl_label = "Remove Camera Template"
    bl_description = "Remove selected camera template"

    def execute(self, context):
        from .src.lib.template_manager import TemplateManager

        template_manager = TemplateManager()

        props = context.scene.mesh_properties
        if props.camera_template not in ["DEFAULT", "CUSTOM"]:
            template_manager.remove_template(props.camera_template)
            props.camera_template = "DEFAULT"

        return {"FINISHED"}


class SINSII_PT_Mesh_Panel(SINSII_Main_Panel, bpy.types.Panel):
    bl_label = "Mesh"
    bl_options = {"DEFAULT_CLOSED"}
    bl_order = 3

    def draw(self, context):
        col = self.layout.column(align=True)
        mesh = get_selected_mesh()
        if not mesh or mesh.type != "MESH":
            col.label(text="Select a mesh...")
        else:
            col.label(text=f"Selected: {mesh.name}")
            col.operator("sinsii.spawn_shield", icon="MESH_CIRCLE")
            col.operator(
                "sinsii.create_buffs", icon="EMPTY_SINGLE_ARROW", text="Generate Buffs"
            )
            col.separator(factor=0.5)
            col.operator("sinsii.export_spatial", icon="META_BALL")


class SINSII_OT_Format_Meshpoints(bpy.types.Operator):
    bl_idname = "sinsii.format_meshpoints"
    bl_label = "Format"

    @classmethod
    def poll(cls, context):
        mesh = get_selected_mesh()
        return mesh and mesh.type == "EMPTY"

    def execute(self, context):
        meshpoints = get_selected_meshes(type="EMPTY")
        mesh_props = context.scene.mesh_properties

        def meshpoint_format(name, idx):
            return (
                f"{name}.0-{i}"
                if mesh_props.duplicate_meshpoint_toggle
                else f"{name}.{i}"
            )

        for _ in range(2):
            for i, meshpoint in enumerate(meshpoints):
                name = (
                    mesh_props.meshpoint_name
                    if mesh_props.meshpoint_type == "custom"
                    else mesh_props.meshpoint_type
                )
                meshpoint.name = re.sub(r"\.\d{3}", "", meshpoint_format(name, i))
        return {"FINISHED"}


class SINSII_PT_Mesh_Point_Panel(SINSII_Main_Panel, bpy.types.Panel):
    bl_label = "Meshpoints"
    bl_options = {"DEFAULT_CLOSED"}
    bl_order = 4

    def draw(self, context):
        col = self.layout.column(align=True)
        col.label(text="Name")
        row = col.row()
        row.prop(context.scene.mesh_properties, "meshpoint_name")
        row.prop(context.scene.mesh_properties, "meshpoint_type")
        col.separator(factor=1.0)
        row = col.row()
        row.operator("sinsii.spawn_meshpoint", icon="EMPTY_AXIS")
        row.operator("sinsii.format_meshpoints")
        col.separator(factor=1.0)
        col.prop(context.scene.mesh_properties, "duplicate_meshpoint_toggle")
        col.separator(factor=1.0)
        col.label(text=f"Selected meshpoints: {len(get_selected_meshes(type='EMPTY'))}")


class SINSII_PT_Meshpoint_Turret(SINSII_Main_Panel, bpy.types.Panel):
    bl_label = "Turret"
    bl_parent_id = "SINSII_PT_Meshpoint_Documentation"
    bl_options = {"DEFAULT_CLOSED"}
    bl_order = 7

    def draw(self, context):
        box = self.layout.box()
        box.label(text="Turret", icon="EMPTY_AXIS")
        col = box.column(align=True)
        col.label(text="Mount attachment point")
        box = col.box()
        box.label(text="child.<mount_name>")
        col.label(text="Barrel muzzle")
        box = col.box()
        box.label(text="turret_muzzle.[0-9]")


class SINSII_PT_Meshpoint_Miscellaneous(SINSII_Main_Panel, bpy.types.Panel):
    bl_label = "Miscellaneous"
    bl_parent_id = "SINSII_PT_Meshpoint_Documentation"
    bl_options = {"DEFAULT_CLOSED"}
    bl_order = 8

    def draw(self, context):
        box = self.layout.box()
        box.label(text="Miscellaneous", icon="EMPTY_AXIS")
        col = box.column(align=True)
        col.label(text="Ship building effects")
        box = col.box()
        box.label(text="ship_build")
        col.label(text="Asteroid resource extractor attachment point")
        box = col.box()
        box.label(text="extractor")


class SINSII_PT_Meshpoint(SINSII_Main_Panel, bpy.types.Panel):
    bl_label = "General"
    bl_parent_id = "SINSII_PT_Meshpoint_Documentation"
    bl_options = {"DEFAULT_CLOSED"}
    bl_order = 6

    def draw(self, context):
        col = self.layout.column(align=True).box()
        col.label(text="General", icon="EMPTY_AXIS")
        col.label(text="Orientation")
        col.operator(
            "wm.url_open", text="See meshpoint orientation here", icon="URL"
        ).url = "https://i.imgur.com/VluXLbg.png"
        col.label(
            text="Align your mesh towards wherever the Monkey Primitive points to"
        )
        col.label(text="Note")
        col.label(
            text="If you add a dash (-) delimiter before a number the engine will ignore everything after it"
        )
        col.label(
            text="- Ex: ability.0-1, ability.0-2, they will be perceived as ability.0"
        )
        col.label(
            text="Additionally, when doing meshpoints you'll have to parent it to the host mesh"
        )
        col.label(text="Types", icon="EMPTY_DATA")
        col.label(text="Buffs")
        box = col.box()
        box.label(text="aura, center, above")
        col.label(text="Ability")
        box = col.box()
        box.label(text="ability.[0-9]")
        col.label(text="Weapon")
        box = col.box()
        box.label(text="child.<turret_name>_[0-9]")
        box.label(text="weapon.<weapon_name>")
        box.label(text="bomb")
        col.label(text="Exhaust")
        box = col.box()
        box.label(text="exhaust.[0-9]")
        col.label(text="Hangar")
        box = col.box()
        box.label(text="hangar.[0-9]")


class SINSII_PT_Meshpoint_Documentation(SINSII_Main_Panel, bpy.types.Panel):
    bl_label = "Meshpoints"
    bl_parent_id = "SINSII_PT_Documentation_Panel"
    bl_options = {"DEFAULT_CLOSED"}
    bl_order = 6

    def draw(self, context):
        col = self.layout.column(align=True)
        col.label(
            text="Here you will find all your need to know about meshpointing your ship"
        )


def flip_normals(mesh):
    try:
        bpy.context.view_layer.objects.active = mesh
        bpy.ops.object.editmode_toggle()
        bpy.ops.mesh.select_all(action="SELECT")
        bpy.ops.mesh.flip_normals()
        bpy.ops.object.editmode_toggle()
    except:
        pass


class SINSII_OT_Sync_Empty_Color(bpy.types.Operator):
    bl_label = "Synchronize Meshpoint Color"
    bl_description = "Changes Blender Empty color to a cyan-like blue"
    bl_idname = "sinsii.sync_color"

    def execute(self, context):
        for theme in bpy.context.preferences.themes:
            theme.view_3d.empty = MESHPOINT_COLOR
        SETTINGS["has_synchronized_meshpoint_color"] = True
        settings.save_settings()
        return {"FINISHED"}


class SINSII_PT_Documentation_Panel(SINSII_Main_Panel, bpy.types.Panel):
    bl_label = "Help" if not has_update else "Help - ℹ Update Available ℹ"
    bl_options = {"DEFAULT_CLOSED"}
    bl_order = 5

    def draw(self, context):
        col = self.layout.column(align=True)
        col.label(
            text=f"Version: {'.'.join(map(str, bl_info['version']))} {'- up to date' if not has_update else '- new version avaliable.'}"
        )
        col.separator(factor=1.0)
        col.operator(
            "sinsii.updates",
            icon="URL",
            text="Check for updates" if not has_update else "Update now",
        )


class SINSII_OT_Generate_Buffs(bpy.types.Operator):
    bl_idname = "sinsii.create_buffs"
    bl_label = "Generate Buffs"

    @classmethod
    def poll(cls, context):
        return context.mode == "OBJECT"

    def execute(self, context):
        has_center, has_above, has_aura = False, False, False
        mesh = get_selected_mesh()
        apply_transforms(mesh)

        if mesh:
            radius = get_bounding_box(mesh)[0]

            for empty in (e for e in mesh.children if e.type == "EMPTY"):
                if "center" in empty.name:
                    has_center = True
                if "above" in empty.name:
                    has_above = True
                if "aura" in empty.name:
                    has_aura = True

            if mesh.type == "MESH":
                if not has_center:
                    create_empty(mesh, radius, "center", (0, 0, 0), "PLAIN_AXES")
                if not has_above:
                    create_empty(mesh, radius, "above", (0, 0, radius), "PLAIN_AXES")
                if not has_aura:
                    create_empty(mesh, radius, "aura", (0, 0, -radius), "PLAIN_AXES")
        else:
            self.report({"WARNING"}, "Select the mesh before generating buffs")

        return {"FINISHED"}


class SINSII_OT_Export_Spatial_Information(bpy.types.Operator, ExportHelper):
    bl_idname = "sinsii.export_spatial"
    bl_label = "Export spatials"

    filename_ext = ".unit"
    filter_glob: bpy.props.StringProperty(default="*.unit", options={"HIDDEN"})

    @classmethod
    def poll(cls, context):
        return context.mode == "OBJECT"

    def execute(self, context):
        mesh = get_selected_mesh()

        if not mesh or not mesh.type == "MESH":
            self.report({"WARNING"}, "You need to select a mesh before exporting")
            return {"CANCELLED"}

        radius, extents, center = get_bounding_box(mesh=mesh)

        try:
            with open(self.filepath, "r+") as f:
                unit_contents = json.load(f)
                if "spatial" in unit_contents:
                    unit_contents["spatial"] = {
                        "radius": radius,
                        "box": {"center": tuple((center)), "extents": tuple((extents))},
                        "collision_rank": 1,
                    }
                    f.seek(0)
                    f.write(json.dumps(unit_contents, indent=4))
                    f.truncate()
                else:
                    self.report(
                        {"ERROR"}, "Cannot locate spatial object, try creating it"
                    )
                    return {"CANCELLED"}
        except Exception as e:
            self.report({"ERROR"}, f"Spatial export failed: {e}")
            return {"CANCELLED"}

        return {"FINISHED"}


class SINSII_OT_Spawn_Meshpoint(bpy.types.Operator):
    bl_idname = "sinsii.spawn_meshpoint"
    bl_label = "Spawn meshpoint"
    bl_description = "Spawns an empty on the selected face/vertex"

    def execute(self, context):
        if not bpy.context.mode == "EDIT_MESH":
            self.report({"WARNING"}, "Make sure you are in edit mode")
            return {"CANCELLED"}
        mesh = get_selected_mesh()
        if not mesh:
            self.report({"WARNING"}, "Please select a mesh first")
            return {"CANCELLED"}
        bpy.ops.object.editmode_toggle()
        apply_transforms(mesh)
        bpy.ops.object.editmode_toggle()

        radius = get_bounding_box(mesh)[0]
        bpy.ops.view3d.snap_cursor_to_selected()
        bpy.ops.object.editmode_toggle()
        create_empty(
            mesh=mesh,
            radius=radius / 2,
            name=context.scene.mesh_properties.meshpoint_name,
            empty_type="ARROWS",
            location=bpy.context.scene.cursor.location,
        )
        bpy.ops.view3d.snap_cursor_to_center()

        return {"FINISHED"}


def get_file_list(directory):
    files = []
    for dirpath, dirname, filenames in os.walk(directory):
        if ".git" in dirpath:
            continue
        for name in dirname:
            if ".git" in name or "__pycache__" in name:
                continue
            files.append(os.path.relpath(os.path.join(dirpath, name), directory))
        for name in filenames:
            if "pyc" in name:
                continue
            files.append(os.path.relpath(os.path.join(dirpath, name), directory))
    return files


class SINSII_OT_Debug(bpy.types.Operator):
    bl_idname = "sinsii.debug"
    bl_label = "Debug"

    def execute(self, context):
        return {"FINISHED"}


class SINSII_OT_Check_For_Updates(bpy.types.Operator):
    bl_idname = "sinsii.updates"
    bl_label = "Check for updates"

    @classmethod
    def poll(cls, context):
        return not is_debugging()

    def execute(self, context):
        temp_path = github.temp
        github.fetch_latest_archive()

        current_files = set(get_file_list(CWD_PATH))
        temp_files = set(get_file_list(temp_path))

        for file in current_files.difference(temp_files):
            file_path = os.path.join(CWD_PATH, file)
            if os.path.isdir(file_path):
                shutil.rmtree(file_path)
            else:
                os.remove(file_path)

        curr_hash = generate_hash_from_directory(
            directory=CWD_PATH, file_list=get_file_list(CWD_PATH)
        )

        repo_hash = generate_hash_from_directory(
            directory=temp_path, file_list=get_file_list(temp_path)
        )

        if curr_hash == repo_hash:
            shutil.rmtree(temp_path)
            self.report({"INFO"}, "No updates found.")
        else:
            os.makedirs(os.path.join(CWD_PATH, "src"), exist_ok=True)
            for file in os.listdir(temp_path):
                if os.path.isdir(os.path.join(temp_path, file)):
                    shutil.copytree(
                        os.path.join(temp_path, file),
                        os.path.join(CWD_PATH, "src"),
                        dirs_exist_ok=True,
                    )
                else:
                    shutil.copy(os.path.join(temp_path, file), CWD_PATH)
            shutil.rmtree(temp_path)

            SETTINGS["current_version"] = latest_version
            settings.save_settings()

            self.report(
                {"INFO"},
                "Extension updated successfully, restart blender for it to take effect.",
            )
        return {"FINISHED"}


def create_empty(mesh, radius, name, location, empty_type):
    bpy.ops.object.empty_add(type=empty_type)
    empty = bpy.context.object
    empty.empty_display_size = radius * 0.05
    empty.name = name
    empty.location = location
    empty.parent = mesh
    empty.rotation_euler = (math.radians(90), 0, 0)


def get_active_material():
    mesh = get_selected_mesh()
    if mesh and mesh.active_material:
        return mesh.active_material


def get_selected_meshes(type="MESH"):
    selected_meshes = []
    for mesh in bpy.context.selected_objects:
        if mesh.type == type:
            selected_meshes.append(mesh)
    return selected_meshes


def get_selected_mesh():
    selected_objects = bpy.context.selected_objects
    if len(selected_objects) > 0:
        return selected_objects[0]


def clear_leftovers(export_dir, mesh_name):
    for leftover in os.listdir(export_dir):
        if any(e for e in [".mesh_material", ".bin", ".gltf"] if leftover.endswith(e)):
            try:
                os.remove(os.path.join(export_dir, leftover))
            except:
                raise Exception(f"Could not remove: {leftover}")


class SINSII_OT_Spawn_Shield_Mesh(bpy.types.Operator):
    bl_idname = "sinsii.spawn_shield"
    bl_label = "Spawn shield mesh"
    bl_options = {"REGISTER"}

    @classmethod
    def poll(cls, context):
        return context.mode == "OBJECT"

    def execute(self, context):
        mesh = get_selected_mesh()

        if mesh:
            radius = get_bounding_box(mesh)[0]

            bpy.ops.mesh.primitive_uv_sphere_add(
                segments=32, radius=radius, align="WORLD", location=mesh.location
            )
            bpy.ops.object.shade_smooth()

            shield = bpy.context.active_object
            shield.name = f"{mesh.name}_shield"
            new_mat = bpy.data.materials.new(name=f"{mesh.name}_shield")
            shield.data.materials.append(new_mat)
            shield.select_set(False)

        # purge_orphans()

        return {"FINISHED"}


# delete and force blender to recalculate edge connections to fix CTD on bad polygons
def sanitize_degenerate_polygons(obj, faces):
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="DESELECT")

    bm_edit = bmesh.from_edit_mesh(obj.data)
    bm_edit.faces.ensure_lookup_table()

    for i in faces:
        bm_edit.faces[i].select = True

    bpy.ops.mesh.separate(type="SELECTED")
    bpy.ops.object.mode_set(mode="OBJECT")

    degenerate_obj = next(
        (
            _obj
            for _obj in bpy.data.objects
            if _obj.type == "MESH" and _obj.name.startswith(f"{obj.name}.001")
        ),
        None,
    )
    bpy.data.objects.remove(degenerate_obj, do_unlink=True)


def load_mesh_data(self, mesh_data, mesh_name, mesh, mesh_materials_path):
    primitives = mesh_data["primitives"]
    materials = mesh_data["materials"]
    meshpoints = mesh_data["meshpoints"]

    vert_arr, normal_arr, uv_coords = [], [], {x: [] for x in ["uv0", "uv1"]}

    for i, vertex in enumerate(mesh_data["vertices"]):
        p = tuple(
            GAME_MATRIX @ Vector([vertex["p"][0], vertex["p"][1], -vertex["p"][2]])
        )
        vert_arr.append(p)

        n = tuple(
            GAME_MATRIX @ Vector([-vertex["n"][0], -vertex["n"][1], vertex["n"][2]])
        )
        normal_arr.append(n)

        uv0 = [vertex["uv0"][0], 1 - vertex["uv0"][1]]
        uv_coords["uv0"].append(uv0)

        if vertex["uv1"]:
            uv1 = [vertex["uv1"][0], 1 - vertex["uv1"][1]]
            uv_coords["uv1"].append(uv1)
        else:
            # failsafe
            uv_coords["uv1"].append([0, 0])

    for i in range(2):
        mesh.uv_layers.new(name=f"uv{i}")

    indices = mesh_data["indices"]
    loops = [indices[i : i + 3] for i in range(0, len(indices), 3)]

    mesh.from_pydata(vert_arr, [], loops)
    mesh.update()

    obj = bpy.data.objects.new(name=mesh_name, object_data=mesh)
    scene = bpy.context.scene
    scene.collection.objects.link(obj)
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)

    bm = bmesh.new()
    bm.from_mesh(mesh)

    degenerate_faces = []
    for face in bm.faces:
        if face.calc_area() <= 1e-99:
            degenerate_faces.append(face.index)
            continue
        for loop in face.loops:
            loop[bm.loops.layers.uv["uv0"]].uv = uv_coords["uv0"][loop.vert.index]
            if uv_coords["uv1"]:
                loop[bm.loops.layers.uv["uv1"]].uv = uv_coords["uv1"][loop.vert.index]

    bm.to_mesh(mesh)
    bm.free()

    textures_path = normalize(self.filepath, "../../textures")
    for material in materials:
        if not os.path.exists(mesh_materials_path):
            new_mat = bpy.data.materials.new(name=material)
        elif mesh_materials_path == REBELLION_PATH:
            new_mat = create_rebellion_shader_nodes(
                material, mesh_materials_path, textures_path
            )
        else:
            new_mat = create_shader_nodes(material, mesh_materials_path, textures_path)
        mesh.materials.append(new_mat)

    for primitive in primitives:
        mat_idx = primitive["material_index"]
        start = primitive["vertex_index_start"]
        count = primitive["vertex_index_count"]
        end = start + count
        for i in range(start // 3, end // 3):
            mesh.polygons[i].material_index = mat_idx

    mesh.update()
    mesh.polygons.foreach_set("use_smooth", [True] * len(mesh.polygons))
    mesh.normals_split_custom_set_from_vertices(normal_arr)

    radius = get_bounding_box(obj)[0]

    name_indices = {}
    for i, meshpoint in enumerate(meshpoints):
        name = meshpoint["name"]
        pos = meshpoint["position"]
        rot = meshpoint["rotation"]

        bpy.ops.object.empty_add(type="ARROWS")

        empty = bpy.context.object
        empty.empty_display_size = radius * 0.05
        if name in name_indices:
            name_indices[name] += 1
            empty.name = f"{name}-{name_indices[name]}"
        else:
            name_indices[name] = 0
            empty.name = name
        empty.location = GAME_MATRIX @ Vector((pos[0], pos[1], -pos[2]))
        empty.parent = obj
        empty.rotation_euler = (
            Matrix(
                (
                    (rot[0], rot[3], rot[6]),
                    (rot[2], rot[5], -rot[8]),
                    (-rot[1], rot[4], rot[7]),
                )
            ).to_4x4()
        ).to_euler()

    if len(degenerate_faces) > 0:
        sanitize_degenerate_polygons(obj, degenerate_faces)

    flip_normals(obj)

    # purge_orphans()

    return obj, radius


def is_rebellion_mesh(file_path):
    with open(file_path, "tr") as txt_file:
        try:
            if txt_file.readable() and "TXT" in txt_file.readline():
                convert_rebellion_mesh(file_path, file_path, "bin")
        except:
            pass

    with open(file_path, "rb") as f:
        header = f.read(4).decode("utf-8")
        if header.startswith("BIN"):
            if                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                              not "Sins of a Solar Empire Rebellion".lower() in normalize(os.path.dirname(file_path), "../").lower():
                raise                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                 NotImplementedError("Non-vanilla meshes are not supported")

            return True

    return False


def import_mesh(self, file_path):
    mesh_name = file_path.rsplit("\\", 1)[1].split(".mesh")[0]
    mesh = bpy.data.meshes.new(name=mesh_name)
    print("Loading: ", mesh_name)
    try:

        #  _____ _____ _   _  _____     _____
        # /  ___|_   _| \ | |/  ___|   / __  \
        # \ `--.  | | |  \| |\ `--.    `' / /'
        #  `--. \ | | | . ` | `--. \     / /
        # /\__/ /_| |_| |\  |/\__/ /   ./ /___
        # \____/ \___/\_| \_/\____/    \_____/

        # handle sins 1 meshes
        if not is_rebellion_mesh(file_path):
            mesh_materials_path = normalize(file_path, "../../mesh_materials")
            reader = BinaryReader.initialize_from(mesh_file=file_path)
        else:
            os.makedirs(REBELLION_PATH, exist_ok=True)

            mesh_materials_path = REBELLION_PATH
            dest = os.path.join(REBELLION_PATH, f"{basename(file_path)}.sins1_mesh")

            shutil.copy(file_path, dest)
            convert_rebellion_mesh(file_path, dest, "txt")

            malformed_meshpoints = []

            while True:
                kind, meshbuilder_err = run_meshbuilder(
                    file_path=dest, dest_path=REBELLION_PATH
                )
                if not meshbuilder_err:
                    os.remove(dest)
                    break

                if meshbuilder_err:
                    if kind == "mesh_point":
                        with open(dest, "r+") as f:
                            lines = f.readlines()
                            for i, line in enumerate(lines):
                                if re.search(rf'.*"{meshbuilder_err}"', line):
                                    print(
                                        f"invalid mesh point: '{meshbuilder_err}', renaming..."
                                    )
                                    lines[i] = line.replace(
                                        meshbuilder_err,
                                        f"Flair-{meshbuilder_err}-remove_flair_prefix",
                                    )
                                    malformed_meshpoints.append(meshbuilder_err)
                                    break
                            f.seek(0)
                            f.truncate()
                            f.writelines(lines)

                        convert_rebellion_mesh(dest, dest, "txt")
                    else:
                        raise ValueError(meshbuilder_err)

            reader = BinaryReader.initialize_from(
                mesh_file=os.path.join(REBELLION_PATH, f"{basename(file_path)}.mesh")
            )

            if malformed_meshpoints:
                self.report(
                    {"WARNING"},
                    f"Found malformed meshpoint names: {[meshpoint for meshpoint in malformed_meshpoints]}",
                )

        if bpy.context.space_data.shading.type != "MATERIAL":
            bpy.context.space_data.shading.type = "MATERIAL"
            bpy.context.space_data.shading.use_compositor = "ALWAYS"

        if (4, 2, 0) <= bpy.app.version:
            create_composite_nodes()

    except Exception as e:
        self.report({"ERROR"}, f"Mesh import failed: {e}")
        return {"CANCELLED"}

    return load_mesh_data(self, reader.mesh_data, mesh_name, mesh, mesh_materials_path)


class SINSII_OT_Import_Mesh(bpy.types.Operator, ImportHelper):
    bl_idname = "sinsii.import_mesh"
    bl_label = "Import mesh"
    bl_description = "You might encounter normal issues on certain models"
    bl_options = {"REGISTER"}

    filename_ext = ".mesh"
    filter_glob: bpy.props.StringProperty(default="*.mesh", options={"HIDDEN"})

    files: bpy.props.CollectionProperty(type=bpy.types.PropertyGroup)

    @classmethod
    def poll(cls, context):
        return context.mode == "OBJECT"

    def execute(self, context):
        os.makedirs(TEMP_TEXTURES_PATH, exist_ok=True)
        radius_arr = []
        offset = 0

        try:
            for i, file in enumerate(self.files):
                mesh, radius = import_mesh(
                    self, os.path.join(os.path.dirname(self.filepath), file.name)
                )
                radius_arr.append(radius)
                if i > 0:
                    offset += radius_arr[i - 1] + radius_arr[i]

                mesh.location = (offset, 0, 0)
            self.report(
                {"INFO"}, f"Imported meshes: {[file.name for file in self.files]}"
            )
        except:
            pass

        return {"FINISHED"}


def sanitize_gltf_document(file_path):
    with open(f"{file_path}.gltf", "r+") as f:
        gltf_document = json.load(f)
        try:
            for material in gltf_document["materials"]:
                del material["doubleSided"]
        except:
            pass
        f.seek(0)
        f.write(json.dumps(gltf_document))
        f.truncate()


def sanitize_mesh_name(mesh_name):
    if "-" in mesh_name:
        mesh_name = mesh_name.replace("-", "_")
    elif " " in mesh_name:
        mesh_name = mesh_name.replace(" ", "_")
    return mesh_name


def export_gltf_document(file_path):
    bpy.ops.export_scene.gltf(
        filepath=file_path,
        export_format="GLTF_SEPARATE",
        export_yup=False,
        use_selection=True,
        export_apply=False,
        export_image_format="NONE",
    )
    sanitize_gltf_document(file_path)


def export_mesh(self, mesh_name, export_dir):
    now = time.time()

    original_transforms_arr = []

    if not get_selected_meshes():
        self.report({"WARNING"}, f"You need to select a mesh before exporting")
        return

    mesh = get_selected_mesh()

    invalid_meshpoints = make_meshpoint_rules(mesh)
    if invalid_meshpoints:
        self.report(
            {"ERROR"},
            f'Invalid meshpoints: [ {", ".join(meshpoint for meshpoint in invalid_meshpoints)} ]',
        )
        return

    materials = get_materials(mesh)
    if type(materials) is str:
        self.report(
            {"ERROR"},
            'Cannot export "{0}" without any materials'.format(materials),
        )
        return

    if not mesh_name:
        self.report({"ERROR"}, "Invalid mesh name")
        return

    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.separate(type="MATERIAL")
    bpy.ops.object.mode_set(mode="OBJECT")
    meshes = get_selected_meshes()

    for mesh in meshes:
        apply_transforms(mesh)
        original_transform, original_meshpoint_transforms = get_original_transforms(
            mesh
        )
        original_transforms_arr.append(
            (original_transform, original_meshpoint_transforms)
        )
        for meshpoint in mesh.children:
            meshpoint.select_set(True)

    mesh_name = sanitize_mesh_name(mesh_name)

    full_mesh_path = os.path.join(export_dir, mesh_name)

    export_gltf_document(full_mesh_path)
    restore_mesh_transforms(original_transforms_arr, meshes)

    _, meshbuilder_err = run_meshbuilder(
        file_path=f"{full_mesh_path}.gltf", dest_path=export_dir
    )

    mesh = join_meshes(meshes)

    if meshbuilder_err:
        clear_leftovers(export_dir, mesh_name)
    else:
        print(meshbuilder_err)

    reader = BinaryReader.initialize_from(
        mesh_file=os.path.join(export_dir, f"{mesh_name}.mesh")
    )
    sanitize_mesh_binary(reader, export_dir, mesh_name, mesh)
    post_export_operations(export_dir, mesh_name, mesh)

    self.report(
        {"INFO"},
        "Mesh exported successfully to: {} - Finished in: {:.2f}s".format(
            f"{self.filepath}.mesh", time.time() - now
        ),
    )


def sanitize_mesh_binary(reader, export_dir, mesh_name, mesh):
    curr_offset = reader.meshpoint_offset_start
    new_buffer = bytearray(reader.buffer)
    for meshpoint in mesh.children:
        if meshpoint.hide_get():
            continue
        name_length_offset = curr_offset
        name_length = reader.u32_at_offset(name_length_offset)

        new_name = re.sub("\\b\-\d+\\b", "", meshpoint.name).encode("utf-8")

        start = 4 + name_length_offset
        end = start + len(new_name)

        new_buffer[start:end] = pack(f"{len(new_name)}s", new_name)
        curr_offset += 4 + name_length + 50

    curr_mat_offset = reader.materials_offset_start
    buffer_end = len(new_buffer)

    material_bytes = bytearray(new_buffer[:curr_mat_offset])

    # consume prefixes
    for material in get_avaliable_sorted_materials(mesh):
        mat_length_offset = curr_mat_offset
        old_name_length = reader.u32_at_offset(mat_length_offset)

        material_name = material.encode("utf-8")

        material_bytes.extend(pack("I", len(material_name)))
        material_bytes.extend(material_name)

        curr_mat_offset += 4 + old_name_length
    material_bytes.extend(new_buffer[curr_mat_offset:buffer_end])

    new_buffer = material_bytes

    with open(os.path.join(export_dir, f"{mesh_name}.mesh"), "wb") as f:
        f.write(new_buffer)


def post_export_operations(export_dir, mesh_name, mesh):
    clear_leftovers(export_dir, mesh_name)
    create_and_move_mesh_materials(export_dir, mesh)


class SINSII_OT_Export_Mesh(bpy.types.Operator, ExportHelper):
    bl_idname = "sinsii.export_mesh"
    bl_label = "Export mesh"
    bl_options = {"REGISTER"}

    filename_ext = ""

    filter_glob: bpy.props.StringProperty(default="*.mesh", options={"HIDDEN"})

    def invoke(self, context, event):
        try:
            self.filepath = get_selected_mesh().name
        except:
            pass
        return super().invoke(context, event)

    @classmethod
    def poll(cls, context):
        return context.mode == "OBJECT"

    def execute(self, context):
        __ = self.filepath.rsplit("\\", 1)
        EXPORT_DIR = __[0]
        MESH_NAME = __[1].lower().strip()

        try:
            export_mesh(self, MESH_NAME, EXPORT_DIR)
        except Exception as e:
            self.report({"ERROR"}, f"Could not export the model: {e}")
            return {"CANCELLED"}

        # purge_orphans()

        return {"FINISHED"}


def set_node_position(node, x, y):
    node.location = (x * 100, y * -100)


def add_color_ramp_driver(node_id, node, name, data_path):
    is_emissive = 2 if name == "Emissive" else 1
    for i, driver in enumerate(
        node_id.driver_add(
            f'nodes["{node.name}"].color_ramp.elements[{is_emissive}].color'
        )
    ):
        add_driver(node_id, node, name, f"{data_path}[{i}]", driver.driver)


def add_driver(node_id, node, name, data_path, driver):
    driver = driver
    driver.type = "SUM"
    var = driver.variables.new()
    var.name = name
    var.targets[0].id_type = "SCENE"
    var.targets[0].id = bpy.context.scene
    var.targets[0].data_path = data_path


def load_texture(node, texture):
    try:
        # convert to usable formats for blender
        tex_file = os.path.basename(texture)
        tmp_texture_path = os.path.join(TEMP_TEXTURES_PATH, tex_file)

        if not os.path.exists(tmp_texture_path):
            run_texconv(texture, TEMP_TEXTURES_PATH)
        if not bpy.data.images.get(tex_file):
            node.image = bpy.data.images.load(tmp_texture_path)
        node.image = bpy.data.images[tex_file]
    except:
        node.image = bpy.data.images.load(os.path.join(CWD_PATH, "texture_error.png"))

    if node.image and node.label != "_clr":
        node.image.colorspace_settings.name = "Non-Color"


def load_mesh_material(name, filepath, textures_path):
    mesh_material = os.path.join(filepath, f"{name}.mesh_material")
    # If no mesh_material file exists, look for textures in game directory
    if not os.path.exists(mesh_material):
        if os.path.exists(textures_path):
            texture_base = os.path.join(textures_path, name)
            return [
                (
                    f"{texture_base}_{tex_map}.dds"
                    if os.path.exists(f"{texture_base}_{tex_map}.dds")
                    else ""
                )
                for tex_map in ["clr", "orm", "msk", "nrm"]
            ]
        return ["", "", "", ""]

    contents = json.load(open(mesh_material, "r"))
    return [
        (
            os.path.join(
                textures_path,
                re.sub(r"(.*?)(\.dds)?$", r"\1", contents.get(key)) + ".dds",
            )
            if contents.get(key)
            else " "
        )
        for key in [
            "base_color_texture",
            "occlusion_roughness_metallic_texture",
            "mask_texture",
            "normal_texture",
        ]
    ]


def create_composite_nodes():
    bpy.context.scene.use_nodes = True
    node_tree = bpy.context.scene.node_tree
    scene = bpy.data.scenes["Scene"]

    if not "Glare" in scene.node_tree.nodes:
        bloom_node = node_tree.nodes.new(type="CompositorNodeGlare")
        bloom_node.glare_type = "BLOOM"
        bloom_node.threshold = 75
        bloom_node.quality = "HIGH"

        composite_node = scene.node_tree.nodes["Composite"]
        render_layers = scene.node_tree.nodes["Render Layers"]

        node_tree.links.new(bloom_node.outputs["Image"], composite_node.inputs["Image"])
        node_tree.links.new(render_layers.outputs["Image"], bloom_node.inputs["Image"])


def create_rebellion_shader_nodes(material_name, mesh_materials_path, textures_path):

    textures = load_mesh_material(material_name, mesh_materials_path, textures_path)

    material = bpy.data.materials.new(name=material_name)
    material.use_nodes = True
    node_id = material.node_tree
    nodes = material.node_tree.nodes

    principled_node = next(node for node in nodes if node.type == "BSDF_PRINCIPLED")
    set_node_position(principled_node, 0, 0)

    _clr = nodes.new(type="ShaderNodeTexImage")
    set_node_position(_clr, -16, 0)
    _clr.label = "_clr"
    load_texture(_clr, textures[0])
    _clr.image.alpha_mode = "NONE"

    links = material.node_tree.links
    links.new(_clr.outputs["Color"], principled_node.inputs["Base Color"])

    return material


def create_shader_nodes(material_name, mesh_materials_path, textures_path):

    textures = load_mesh_material(material_name, mesh_materials_path, textures_path)

    material = bpy.data.materials.new(name=material_name)
    material.use_nodes = True
    node_id = material.node_tree
    nodes = material.node_tree.nodes

    principled_node = next(node for node in nodes if node.type == "BSDF_PRINCIPLED")
    set_node_position(principled_node, 0, 0)

    _clr = nodes.new(type="ShaderNodeTexImage")
    set_node_position(_clr, -16, 0)
    _clr.label = "_clr"
    load_texture(_clr, textures[0])

    _orm = nodes.new(type="ShaderNodeTexImage")
    set_node_position(_orm, -16, 2)
    _orm.label = "_orm"
    load_texture(_orm, textures[1])

    _msk = nodes.new(type="ShaderNodeTexImage")
    set_node_position(_msk, -16, 4)
    _msk.label = "_msk"
    load_texture(_msk, textures[2])

    _nrm = nodes.new(type="ShaderNodeTexImage")
    set_node_position(_nrm, -16, 6)
    _nrm.label = "_nrm"
    load_texture(_nrm, textures[3])

    mapping_node = nodes.new(type="ShaderNodeMapping")
    set_node_position(mapping_node, -19, 0)

    tex_coord_node = nodes.new(type="ShaderNodeTexCoord")
    set_node_position(tex_coord_node, -21, 0)

    mix_node_1 = nodes.new(type="ShaderNodeMix")
    set_node_position(mix_node_1, -4, -2)
    mix_node_1.data_type = "RGBA"
    mix_node_1.blend_type = "MIX"

    mix_node_2 = nodes.new(type="ShaderNodeMix")
    set_node_position(mix_node_2, -8, -2)
    mix_node_2.data_type = "RGBA"
    mix_node_2.blend_type = "VALUE"

    mix_node_team_color = nodes.new(type="ShaderNodeMix")
    set_node_position(mix_node_team_color, -6, -5)
    mix_node_team_color.data_type = "RGBA"
    mix_node_team_color.blend_type = "MIX"
    add_driver(
        node_id,
        mix_node_team_color,
        "Toggle Team Color",
        "mesh_properties.toggle_teamcolor",
        node_id.driver_add(
            f'nodes["{mix_node_team_color.name}"].inputs[0].default_value'
        ).driver,
    )

    clamp_node = nodes.new(type="ShaderNodeClamp")
    clamp_node.inputs[1].default_value = 0.135
    clamp_node.inputs[2].default_value = 0.350
    clamp_node.clamp_type = "RANGE"
    set_node_position(clamp_node, -10, 1)

    separate_color_node = nodes.new(type="ShaderNodeSeparateColor")
    set_node_position(separate_color_node, -13, 2)
    separate_color_node_2 = nodes.new(type="ShaderNodeSeparateColor")
    set_node_position(separate_color_node_2, -13, 4)

    color_ramp = nodes.new(type="ShaderNodeValToRGB")
    set_node_position(color_ramp, -7, 3)
    color_ramp.color_ramp.interpolation = "EASE"
    color_ramp.color_ramp.elements[0].position = 0.445
    color_ramp.color_ramp.elements[1].position = 0.560

    color_ramp_2 = nodes.new(type="ShaderNodeValToRGB")
    set_node_position(color_ramp_2, -7, 5)
    color_ramp_2.color_ramp.elements[0].color = (0, 0, 0, 1)
    add_color_ramp_driver(
        node_id, color_ramp_2, "Team Color - 1", "mesh_properties.team_color_1"
    )

    color_ramp_3 = nodes.new(type="ShaderNodeValToRGB")
    set_node_position(color_ramp_3, -7, 7)
    color_ramp_3.color_ramp.elements[0].color = (0, 0, 0, 1)
    add_color_ramp_driver(
        node_id, color_ramp_3, "Team Color - 2", "mesh_properties.team_color_2"
    )

    color_ramp_4 = nodes.new(type="ShaderNodeValToRGB")
    set_node_position(color_ramp_4, -7, 9)
    color_ramp_4.color_ramp.elements[0].color = (0, 0, 0, 1)
    color_ramp_4.color_ramp.elements.new(position=0.5)
    color_ramp_4.color_ramp.elements[1].color = (0, 0, 0, 1)
    add_color_ramp_driver(
        node_id, color_ramp_4, "Emissive", "mesh_properties.team_color_3"
    )

    separate_color_node_3 = nodes.new(type="ShaderNodeSeparateColor")
    set_node_position(separate_color_node_3, -13, 6)

    multiply_node = nodes.new(type="ShaderNodeMath")
    multiply_node.operation = "MULTIPLY"
    multiply_node.inputs[1].default_value = 1
    set_node_position(multiply_node, -10, 12)

    multiply_node_2 = nodes.new(type="ShaderNodeMath")
    multiply_node_2.operation = "MULTIPLY"
    set_node_position(multiply_node_2, -4, 13)
    multiply_node_2.inputs[1].default_value = 2.0

    multiply_node_3 = nodes.new(type="ShaderNodeMath")
    multiply_node_3.operation = "MULTIPLY"
    set_node_position(multiply_node_3, -4, 11)
    multiply_node_3.inputs[1].default_value = 2.0

    subtract_node = nodes.new(type="ShaderNodeMath")
    subtract_node.operation = "SUBTRACT"
    set_node_position(subtract_node, -2, 11)
    subtract_node.inputs[1].default_value = 1.0

    subtract_node_2 = nodes.new(type="ShaderNodeMath")
    subtract_node_2.operation = "SUBTRACT"
    set_node_position(subtract_node_2, -2, 13)
    subtract_node_2.inputs[1].default_value = 1.0

    combine_xyz_node = nodes.new(type="ShaderNodeCombineXYZ")
    set_node_position(combine_xyz_node, 0, 12)

    dot_product_node = nodes.new(type="ShaderNodeVectorMath")
    set_node_position(dot_product_node, 2, 12)
    dot_product_node.operation = "DOT_PRODUCT"

    color_invert_node = nodes.new(type="ShaderNodeInvert")
    set_node_position(color_invert_node, 4, 12)

    normal_y_invert_node = nodes.new(type="ShaderNodeInvert")
    set_node_position(normal_y_invert_node, 2, 10)

    clamp_node_2 = nodes.new(type="ShaderNodeClamp")
    clamp_node_2.inputs[1].default_value = 0
    clamp_node_2.inputs[2].default_value = 1
    set_node_position(clamp_node_2, 6, 12)

    square_root_node = nodes.new(type="ShaderNodeMath")
    square_root_node.operation = "SQRT"
    set_node_position(square_root_node, 8, 12)

    combine_xyz_node_2 = nodes.new(type="ShaderNodeCombineXYZ")
    set_node_position(combine_xyz_node_2, 10, 10)

    normal_map_node = nodes.new(type="ShaderNodeNormalMap")
    set_node_position(normal_map_node, 12, 10)

    principled_node.inputs["Emission Strength"].default_value = 100

    links = material.node_tree.links
    links.new(_clr.outputs["Color"], mix_node_team_color.inputs["A"])
    links.new(
        mix_node_team_color.outputs["Result"], principled_node.inputs["Base Color"]
    )
    links.new(multiply_node.outputs["Value"], normal_y_invert_node.inputs["Color"])
    links.new(normal_y_invert_node.outputs["Color"], combine_xyz_node_2.inputs["Y"])
    links.new(mix_node_1.outputs["Result"], mix_node_team_color.inputs["B"])
    links.new(mix_node_2.outputs["Result"], mix_node_1.inputs["B"])
    links.new(_clr.outputs["Color"], mix_node_2.inputs["B"])
    links.new(multiply_node.outputs["Value"], multiply_node_3.inputs["Value"])
    links.new(subtract_node.outputs["Value"], combine_xyz_node.inputs["X"])
    links.new(subtract_node_2.outputs["Value"], combine_xyz_node.inputs["Y"])
    links.new(_orm.outputs["Color"], separate_color_node.inputs["Color"])
    links.new(separate_color_node.outputs["Green"], clamp_node.inputs["Value"])
    links.new(multiply_node_3.outputs["Value"], subtract_node.inputs["Value"])
    links.new(combine_xyz_node.outputs["Vector"], dot_product_node.inputs[0])
    links.new(combine_xyz_node.outputs["Vector"], dot_product_node.inputs[1])
    links.new(dot_product_node.outputs["Value"], color_invert_node.inputs["Color"])
    links.new(multiply_node_2.outputs["Value"], subtract_node_2.inputs["Value"])
    links.new(square_root_node.outputs["Value"], combine_xyz_node_2.inputs["Z"])
    links.new(combine_xyz_node_2.outputs["Vector"], normal_map_node.inputs["Color"])
    links.new(normal_map_node.outputs["Normal"], principled_node.inputs["Normal"])
    links.new(separate_color_node_3.outputs["Red"], combine_xyz_node_2.inputs["X"])
    links.new(clamp_node.outputs["Result"], principled_node.inputs["Roughness"])
    links.new(separate_color_node_3.outputs["Green"], multiply_node_2.inputs["Value"])
    links.new(color_invert_node.outputs["Color"], clamp_node_2.inputs["Value"])
    links.new(clamp_node_2.outputs["Result"], square_root_node.inputs["Value"])
    links.new(separate_color_node.outputs["Blue"], color_ramp.inputs["Fac"])
    links.new(color_ramp.outputs["Color"], principled_node.inputs["Metallic"])
    links.new(color_ramp_2.outputs["Color"], mix_node_2.inputs["A"])
    links.new(separate_color_node_3.outputs["Green"], multiply_node.inputs["Value"])
    links.new(color_ramp_3.outputs["Color"], mix_node_1.inputs["A"])
    links.new(color_ramp_4.outputs["Color"], principled_node.inputs[26])
    links.new(_nrm.outputs["Color"], separate_color_node_3.inputs["Color"])
    links.new(_msk.outputs["Color"], separate_color_node_2.inputs["Color"])
    links.new(separate_color_node_2.outputs["Red"], color_ramp_2.inputs["Fac"])
    links.new(separate_color_node_2.outputs["Green"], color_ramp_3.inputs["Fac"])
    links.new(separate_color_node_2.outputs["Blue"], color_ramp_4.inputs["Fac"])
    links.new(tex_coord_node.outputs["UV"], mapping_node.inputs["Vector"])
    links.new(mapping_node.outputs["Vector"], _clr.inputs["Vector"])
    links.new(mapping_node.outputs["Vector"], _nrm.inputs["Vector"])
    links.new(mapping_node.outputs["Vector"], _msk.inputs["Vector"])
    links.new(mapping_node.outputs["Vector"], _orm.inputs["Vector"])
    links.new(_clr.outputs["Alpha"], principled_node.inputs["Alpha"])
    links.new(separate_color_node_2.outputs["Blue"], color_ramp_4.inputs["Fac"])
    links.new(color_ramp_4.outputs["Color"], principled_node.inputs["Emission Color"])

    return material


classes = (
    SINSII_OT_Import_Mesh,
    SINSII_OT_Export_Mesh,
    SINSII_OT_Generate_Buffs,
    SINSII_OT_Check_For_Updates,
    SINSII_OT_Debug,
    SINSII_OT_Sync_Empty_Color,
    SINSII_OT_Spawn_Meshpoint,
    SINSII_OT_Spawn_Shield_Mesh,
    SINSII_OT_Export_Spatial_Information,
    SINSII_PT_Panel,
    SINSII_OT_Pick_HDRI,
    SINSII_OT_Render_Perspective,
    SINSII_OT_Render_Top_Down,
    SINSII_OT_Add_Render_Scene,
    SINSII_OT_Remove_Render_Scene,
    SINSII_OT_Save_Camera_Template,
    SINSII_OT_Remove_Camera_Template,
    SINSII_OT_Load_Default_Template,
    SINSII_PT_Render_Panel,
    SINSII_OT_Format_Meshpoints,
    SINSII_PT_Mesh_Point_Panel,
    SINSII_PT_Mesh_Panel,
    SINSII_PT_Documentation_Panel,
    SINSII_PT_Meshpoint_Documentation,
    SINSII_PT_Meshpoint_Miscellaneous,
    SINSII_PT_Meshpoint_Turret,
    SINSII_PT_Meshpoint,
)


def register():
    for Class in classes:
        bpy.utils.register_class(Class)


def unregister():
    for Class in classes:
        bpy.utils.unregister_class(Class)
