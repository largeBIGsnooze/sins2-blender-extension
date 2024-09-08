import bpy, json, os, math, subprocess, re, shutil, time
from struct import unpack, pack
from bpy_extras.io_utils import ExportHelper, ImportHelper
from mathutils import Vector, Matrix
from .src.lib.helpers.material import MeshMaterial
from . import bl_info
import bmesh, tempfile
from .src.lib.github_downloader import Github_Downloader
from .src.lib.binary_reader import BinaryReader
from .src.lib.helpers.cryptography import generate_hash_from_directory

CWD_PATH = os.path.dirname(os.path.abspath(__file__))
MESHBUILDER_EXE = os.path.join(
    CWD_PATH, "src", "lib", "tools", "meshbuilder", "meshbuilder.exe"
)

GAME_MATRIX = Matrix(((-1, 0, 0, 0), (0, 0, 1, 0), (0, 1, 0, 0), (0, 0, 0, 1)))
MESHPOINT_MATRIX = Matrix(((-1, 0, 0, 0), (0, 1, 0, 0), (0, 0, -1, 0), (0, 0, 0, 1)))


class SINSII_Main_Panel:

    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Sins II Utility"


class SINSII_PT_Panel(SINSII_Main_Panel, bpy.types.Panel):
    bl_label = "Export"
    bl_order = 1

    def draw(self, context):
        col = self.layout.column(align=True)
        col.label(text="Spawn a Monkey Mesh if you're unsure of sins 2 orientation")
        col.separator(factor=0.5)
        col.operator("sinsii.export_mesh", icon="MESH_CUBE", text="Export mesh")
        # col.separator(factor=1.5)
        # col.operator("sinsii.debug")
        col.separator(factor=1.5)
        box = col.box()
        box.label(text="Ensure the orientation is red")
        box.prop(context.scene.mesh_properties, "check_normals_orientation")
        box.operator("sinsii.flip_normals")
        col.separator(factor=1.5)
        col.prop(context.scene.mesh_properties, "enable_experimental_features")
        if context.scene.mesh_properties.enable_experimental_features == True:
            col.separator(factor=1.5)
            col.operator("sinsii.import_mesh", icon="LOOP_FORWARDS", text="Import mesh")


class SINSII_PT_Mesh_Panel(SINSII_Main_Panel, bpy.types.Panel):
    bl_label = "Mesh"
    bl_options = {"DEFAULT_CLOSED"}
    bl_order = 3

    def draw(self, context):
        col = self.layout.column(align=True)
        col.operator("sinsii.spawn_shield", icon="MESH_CIRCLE")
        col.separator(factor=1.5)
        col.operator("sinsii.export_spatial", icon="META_BALL")


class SINSII_PT_Mesh_Point_Panel(SINSII_Main_Panel, bpy.types.Panel):
    bl_label = "Meshpoints"
    bl_options = {"DEFAULT_CLOSED"}
    bl_order = 4

    def draw(self, context):
        col = self.layout.column(align=True)
        mesh = get_selected_mesh()
        if not mesh or mesh is None:
            col.label(text="Select a mesh...")
        else:
            col.label(text=f"Selected: {mesh.name}")
            col.operator(
                "sinsii.create_buffs", icon="EMPTY_SINGLE_ARROW", text="Generate Buffs"
            )
            col.separator(factor=1.5)
            col.operator("sinsii.spawn_meshpoint", icon="EMPTY_AXIS")


class SINSII_PT_Meshpoint_Documentation(SINSII_Main_Panel, bpy.types.Panel):
    bl_label = "Meshpoints"
    bl_parent_id = "SINSII_PT_Documentation_Panel"
    bl_options = {"DEFAULT_CLOSED"}
    bl_order = 6

    def draw(self, context):
        col = self.layout.column(align=True).box()
        col.label(text="Meshpoints", icon="EMPTY_AXIS")
        col.label(text="Orientation")
        col.operator(
            "wm.url_open", text="See meshpoint orientation here", icon="URL"
        ).url = "https://i.imgur.com/VluXLbg.png"
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
        box.label(text="weapon.torpedo-[0-9]")
        box.label(text="weapon.[0-9]")
        box.label(text="bomb")
        col.label(text="Exhaust")
        box = col.box()
        box.label(text="exhaust.[0-9]")
        col.label(text="Hangar")
        box = col.box()
        box.label(text="hangar.[0-9]")


class SINSII_OT_Flip_Normals(bpy.types.Operator):
    bl_label = "Flip"
    bl_idname = "sinsii.flip_normals"

    def execute(self, context):
        mesh = get_selected_mesh()
        try:
            bpy.context.view_layer.objects.active = mesh
            bpy.ops.object.editmode_toggle()
            bpy.ops.mesh.select_all(action="SELECT")
            bpy.ops.mesh.flip_normals()
            bpy.ops.object.editmode_toggle()
        except:
            pass
        return {"FINISHED"}


class SINSII_PT_Documentation_Panel(SINSII_Main_Panel, bpy.types.Panel):
    bl_label = "Help"
    bl_options = {"DEFAULT_CLOSED"}
    bl_order = 5

    def draw(self, context):
        col = self.layout.column(align=True)
        col.label(text=f"Version: {','.join(map(str, bl_info['version']))}")
        col.separator(factor=1.0)
        col.operator("sinsii.updates", icon="URL")


class SINSII_OT_Generate_Buffs(bpy.types.Operator):
    bl_idname = "sinsii.create_buffs"
    bl_label = "Generate Buffs"

    def execute(self, context):
        has_center, has_above, has_aura = False, False, False
        mesh = get_selected_mesh()

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
                    create_empty(
                        mesh, radius, "above", (0, 0, radius * 0.25), "PLAIN_AXES"
                    )
                if not has_aura:
                    create_empty(
                        mesh, radius, "aura", (0, 0, -radius * 0.25), "PLAIN_AXES"
                    )
        else:
            self.report({"WARNING"}, "Select the mesh before generating buffs")

        return {"FINISHED"}


class SINSII_OT_Export_Spatial_Information(bpy.types.Operator, ExportHelper):
    bl_idname = "sinsii.export_spatial"
    bl_label = "Export spatials"

    filename_ext = ".unit"
    filter_glob: bpy.props.StringProperty(default="*.unit", options={"HIDDEN"})

    def execute(self, context):
        mesh = get_selected_mesh()

        if not bpy.context.mode == "OBJECT":
            self.report({"WARNING"}, "Please enter into Object Mode before exporting")
            return {"CANCELLED"}
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

    def execute(self, context):
        if not bpy.context.mode == "EDIT_MESH":
            self.report({"WARNING"}, "Make sure you are in edit mode")
            return {"CANCELLED"}
        mesh = get_selected_mesh()
        radius = get_bounding_box(mesh)[0]
        bpy.ops.view3d.snap_cursor_to_selected()
        bpy.ops.object.editmode_toggle()
        create_empty(
            mesh=mesh,
            radius=radius / 2,
            name="child.empty.0",
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

    def execute(self, context):

        temp_dir = tempfile.gettempdir()

        gh = Github_Downloader.initialize(temp_dir)
        temp_path = gh.temp

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

            self.report(
                {"INFO"},
                "Extension updated successfully, restart blender for it take effect.",
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


def get_bounding_box(mesh):

    def calculate_center(l):
        return (max(l) + min(l)) / 2 if l else 0

    if mesh:
        mesh_box = [GAME_MATRIX @ Vector(axis) for axis in mesh.bound_box]

        bounds = [
            coord for vector in mesh_box for coord in (vector.x, vector.y, vector.z)
        ]

        bounds_x = bounds[::3]
        bounds_y = bounds[1::3]
        bounds_z = bounds[2::3]

        center_x = calculate_center(bounds_x)
        center_y = calculate_center(bounds_y)
        center_z = calculate_center(bounds_z)

        center = [center_x, center_y, -center_z]

        extents = [
            ((max(bounds_x) - min(bounds_x)) / 2),
            ((max(bounds_y) - min(bounds_y)) / 2),
            ((max(bounds_z) - min(bounds_z)) / 2),
        ]

        bounding_sphere_radius = max(
            (p - Vector([center_x, center_y, center_z])).length for p in mesh_box
        )

        return bounding_sphere_radius, extents, center


def get_active_material():
    mesh = get_selected_mesh()
    if mesh and mesh.active_material:
        return mesh.active_material


def get_selected_meshes():
    selected_meshes = []
    for mesh in bpy.context.selected_objects:
        selected_meshes.append(mesh)
    return selected_meshes


def get_selected_mesh():
    selected_objects = bpy.context.selected_objects
    if len(selected_objects) > 0:
        return selected_objects[0]


def run_meshbuilder(file_path, dest_path, dest_format):
    subprocess.run(
        [
            MESHBUILDER_EXE,
            f"--input_path={file_path}",
            f"--output_folder_path={dest_path}",
            f"--mesh_output_format={dest_format}",
        ],
    )


def get_materials(mesh):
    materials = []
    if mesh.type == "MESH" and len(mesh.data.materials) != 0:
        for material in mesh.data.materials:
            if material is not None:
                materials.append(material.name)
    if len(materials) == 0:
        return mesh.name
    else:
        return materials


def move_textures(path):
    for texture in os.listdir(path):
        if not ".png" in texture:
            continue
        dest = (
            normalize(path, "../textures")
            if os.path.exists(normalize(path, "../textures"))
            else path
        )
        rename(path=path, dest=dest, filename=texture)


def create_and_move_mesh_materials(file_path, mesh):
    materials = get_materials(mesh)
    unused_mats = get_unused_materials(mesh, materials)
    # create new ones
    for material in (material for material in materials if material not in unused_mats):
        # skip unused material
        material_name = f"{material}.mesh_material"
        with open(os.path.join(file_path, material_name), "w") as f:
            mesh_material = MeshMaterial(
                clr=f"{material}_clr",
                nrm=f"{material}_nrm",
                msk=f"{material}_msk",
                orm=f"{material}_orm",
            ).json()
            f.write(json.dumps(mesh_material, indent=4))
            f.close()
        dest = (
            normalize(file_path, "../mesh_materials")
            if os.path.exists(normalize(file_path, "../mesh_materials"))
            else file_path
        )
        rename(path=file_path, dest=dest, filename=material_name)


def apply_meshpoint_transforms(mesh):
    transforms = []
    if len(mesh.children) >= 1:
        for empty in mesh.children:
            if empty is None and not empty.type == "EMPTY":
                continue
            transforms.append(empty.matrix_world.copy())
            empty.matrix_local = empty.matrix_basis @ MESHPOINT_MATRIX
    return transforms


def restore_meshpoint_transforms(children, original):
    if children and len(children) >= 1:
        for i, empty in enumerate(children):
            empty.matrix_local = original[i]


def clear_leftovers(export_dir, mesh_name):
    for leftover in os.listdir(export_dir):
        if any(e for e in [".mesh_material", ".bin", ".gltf"] if leftover.endswith(e)):
            try:
                os.remove(os.path.join(export_dir, leftover))
            except:
                raise Exception(f"Could not remove: {leftover}")


def normalize(file_path, args):
    return os.path.normpath(os.path.join(file_path, args))


def rename(path, dest, filename):
    os.replace(os.path.join(path, filename), os.path.join(dest, filename))


def purge_orphans():
    bpy.ops.outliner.orphans_purge()


class SINSII_OT_Spawn_Shield_Mesh(bpy.types.Operator):
    bl_idname = "sinsii.spawn_shield"
    bl_label = "Spawn shield mesh"
    bl_options = {"REGISTER"}

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

        purge_orphans()

        return {"FINISHED"}


def get_unused_materials(mesh, materials):
    unused_mats = []
    for i, mat in enumerate(materials):
        tris = []
        for tri in mesh.data.polygons:
            if tri.material_index == i:
                tris.append(tri.material_index)
        if len(tris) == 0:
            unused_mats.append(mat)
    return unused_mats


def import_mesh(mesh_data, mesh_name, mesh):
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
            GAME_MATRIX @ Vector([vertex["n"][0], vertex["n"][1], -vertex["n"][2]])
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

    for face in bm.faces:
        for loop in face.loops:
            loop[bm.loops.layers.uv["uv0"]].uv = uv_coords["uv0"][loop.vert.index]
            if uv_coords["uv1"]:
                loop[bm.loops.layers.uv["uv1"]].uv = uv_coords["uv1"][loop.vert.index]

    bm.to_mesh(mesh)
    bm.free()

    for material in materials:
        new_mat = bpy.data.materials.new(name=material)
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
    # mesh.normals_split_custom_set_from_vertices(normal_arr)

    radius = get_bounding_box(obj)[0]

    for meshpoint in meshpoints:
        name = meshpoint["name"]
        pos = meshpoint["position"]
        rot = meshpoint["rotation"]

        bpy.ops.object.empty_add(type="ARROWS")
        empty = bpy.context.object
        empty.empty_display_size = radius * 0.05
        empty.name = name
        empty.location = GAME_MATRIX @ Vector((pos[0], pos[1], -pos[2]))
        empty.parent = obj
        empty.rotation_euler = (
            GAME_MATRIX.transposed()
            @ Matrix(
                (
                    (rot[0], rot[1], rot[2]),
                    (rot[3], rot[4], rot[5]),
                    (rot[6], rot[7], rot[8]),
                )
            ).to_4x4()
            @ MESHPOINT_MATRIX
        ).to_euler()

    purge_orphans()


class SINSII_OT_Import_Mesh(bpy.types.Operator, ImportHelper):
    bl_idname = "sinsii.import_mesh"
    bl_label = "Import mesh"
    bl_description = "You might encounter normal issues on certain models"
    bl_options = {"REGISTER"}

    filename_ext = ".mesh"

    filter_glob: bpy.props.StringProperty(default="*.mesh", options={"HIDDEN"})

    def execute(self, context):
        mesh_name = self.filepath.rsplit("\\", 1)[1].split(".mesh")[0]
        mesh = bpy.data.meshes.new(name=mesh_name)
        try:

            #  _____ _____ _   _  _____     _____
            # /  ___|_   _| \ | |/  ___|   / __  \
            # \ `--.  | | |  \| |\ `--.    `' / /'
            #  `--. \ | | | . ` | `--. \     / /
            # /\__/ /_| |_| |\  |/\__/ /   ./ /___
            # \____/ \___/\_| \_/\____/    \_____/

            buffer = BinaryReader.open(self.filepath)
            reader = BinaryReader.initialize_from(buffer)
        except Exception as e:
            self.report({"ERROR"}, f"Mesh import failed.: {e}")
            return {"CANCELLED"}

        import_mesh(reader.mesh_data, mesh_name, mesh)

        self.report({"INFO"}, f"Imported: {self.filepath}")
        return {"FINISHED"}


def export_mesh(self, mesh, mesh_name, export_dir):
    if not mesh or not mesh.type == "MESH":
        self.report({"WARNING"}, "You need to select a mesh before exporting")
        return
    if not bpy.context.mode == "OBJECT":
        self.report({"WARNING"}, "Please enter into Object Mode before exporting")
        return
    if (
        not all(vec == 1 for vec in mesh.scale)
        or not all(vec == 0 for vec in mesh.rotation_euler)
        or not all(vec == 0 for vec in mesh.location)
    ):
        self.report({"ERROR"}, "Freeze the model before exporting!")
        return

    materials = get_materials(mesh)
    if type(materials) is str:
        self.report(
            {"ERROR"},
            'Cannot export "{0}" without any materials'.format(materials),
        )
        return

    now = time.time()

    if mesh.children and len(mesh.children) >= 1:
        for child in mesh.children:
            child.select_set(True)

    original_transform = mesh.matrix_world.copy()

    mesh.matrix_world = GAME_MATRIX @ mesh.matrix_world

    original_meshpoint_transforms = apply_meshpoint_transforms(mesh=mesh)

    if "-" in mesh_name:
        mesh_name = mesh_name.replace("-", "_")

    bpy.ops.export_scene.gltf(
        filepath=os.path.join(export_dir, mesh_name),
        use_selection=self.export_selected,
        export_format="GLTF_SEPARATE",
        export_yup=False,
    )

    mesh.matrix_world = original_transform

    run_meshbuilder(
        file_path=os.path.join(export_dir, f"{mesh_name}.gltf"),
        dest_path=export_dir,
        dest_format="binary",
    )

    buffer = BinaryReader.open(os.path.join(export_dir, f"{mesh_name}.mesh"))
    reader = BinaryReader.initialize_from(buffer)

    curr_offset = reader.meshpoint_offset_start
    new_buffer = bytearray(buffer)
    for meshpoint in mesh.children:
        name_length_offset = curr_offset
        name_length = reader.u32_at_offset(name_length_offset)

        start = 4 + name_length_offset
        end = start + name_length
        new_name = re.sub("\\b\-\d+\\b", "", meshpoint.name).encode("utf-8")
        new_buffer[start:end] = pack(f"{len(meshpoint.name)}s", new_name)
        curr_offset += 4 + name_length + 50

    curr_mat_offset = reader.materials_offset_start
    buffer_end = len(new_buffer)

    material_bytes = bytearray(new_buffer[:curr_mat_offset])

    # consume prefixes
    materials = get_materials(mesh)
    unused_mats = get_unused_materials(mesh, materials)

    for material in sorted(
        material for material in materials if material not in unused_mats
    ):
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

    restore_meshpoint_transforms(
        children=mesh.children, original=original_meshpoint_transforms
    )

    self.report(
        {"INFO"},
        "Mesh exported successfully to: {}, \n Finished in: {:.6f}s".format(
            self.filepath, time.time() - now
        ),
    )


def clear_files(export_dir, mesh_name, mesh):
    clear_leftovers(export_dir, mesh_name)
    create_and_move_mesh_materials(export_dir, mesh)
    move_textures(export_dir)


class SINSII_OT_Export_Mesh(bpy.types.Operator, ExportHelper):
    bl_idname = "sinsii.export_mesh"
    bl_label = "Export mesh"
    bl_options = {"REGISTER"}

    filename_ext = ""

    filter_glob: bpy.props.StringProperty(default="*.mesh", options={"HIDDEN"})

    export_selected: bpy.props.BoolProperty(
        name="Export selected", default=True, options={"HIDDEN"}
    )

    def execute(self, context):
        __ = self.filepath.rsplit("\\", 1)
        EXPORT_DIR = __[0]
        MESH_NAME = __[1].lower()

        mesh = get_selected_mesh()
        try:
            export_mesh(self, mesh, MESH_NAME, EXPORT_DIR)
            clear_files(EXPORT_DIR, MESH_NAME, mesh)
        except Exception as e:
            clear_files(EXPORT_DIR, MESH_NAME, mesh)
            self.report({"ERROR"}, f"Could not export the model: {e}")
            return {"CANCELLED"}

        purge_orphans()

        return {"FINISHED"}


classes = (
    SINSII_OT_Import_Mesh,
    SINSII_OT_Export_Mesh,
    SINSII_OT_Generate_Buffs,
    SINSII_OT_Check_For_Updates,
    SINSII_OT_Debug,
    SINSII_OT_Flip_Normals,
    SINSII_OT_Spawn_Meshpoint,
    SINSII_OT_Spawn_Shield_Mesh,
    SINSII_OT_Export_Spatial_Information,
    SINSII_PT_Panel,
    SINSII_PT_Mesh_Point_Panel,
    SINSII_PT_Mesh_Panel,
    SINSII_PT_Documentation_Panel,
    SINSII_PT_Meshpoint_Documentation,
)


def register():
    for Class in classes:
        bpy.utils.register_class(Class)


def unregister():
    for Class in classes:
        bpy.utils.unregister_class(Class)
