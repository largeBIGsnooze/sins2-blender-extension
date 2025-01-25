from mathutils import Vector
from ....constants import (
    GAME_MATRIX,
    MESHPOINT_MATRIX,
    MESHPOINTING_RULES,
    MESHBUILDER_EXE,
    REBELLION_MESHBUILDER_EXE,
    TEXCONV_EXE,
)
from .filesystem import normalize, rename
from .mesh import MeshMaterial
import bpy, os, json, re, subprocess


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


def frozen(mesh):
    if mesh.type == "MESH":
        if (
            not all(vec == 1 for vec in mesh.scale)
            or not all(vec == 0 for vec in mesh.rotation_euler)
            or not all(vec == 0 for vec in mesh.location)
        ):
            return False

    return True


def apply_meshpoint_transforms(mesh):
    transforms = []
    if len(mesh.children) >= 1:
        for empty in mesh.children:
            if empty is None and not empty.type == "EMPTY":
                continue
            transforms.append(empty.matrix_world.copy())
            empty.matrix_local = empty.matrix_basis @ MESHPOINT_MATRIX
    return transforms


def apply_transforms(mesh):
    if not frozen(mesh):
        bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)


def get_materials(mesh):
    materials = []
    if mesh.type == "MESH":
        for material in mesh.data.materials:
            if material is not None:
                materials.append(material.name.lower())
        if len(materials) == 0:
            return mesh.name
    return materials


def get_avaliable_sorted_materials(mesh):
    materials = get_materials(mesh)
    unused_mats = get_unused_materials(mesh, materials)
    return sorted(
        material for material in set(materials) if material not in unused_mats
    )


def create_and_move_mesh_materials(file_path, mesh):
    materials = get_materials(mesh)
    unused_mats = get_unused_materials(mesh, materials)
    # create new ones
    for material in (material for material in materials if material not in unused_mats):
        # skip unused material
        material_name = f"{material}.mesh_material"
        mesh_materials_dir = normalize(file_path, "../mesh_materials")
        mesh_material = os.path.join(mesh_materials_dir, material_name)
        if os.path.exists(mesh_material):
            continue
        with open(os.path.join(file_path, material_name), "w") as f:
            mesh_material = MeshMaterial(
                clr=f"{material}_clr",
                nrm=f"{material}_nrm",
                msk=f"{material}_msk",
                orm=f"{material}_orm",
            ).json()
            f.write(json.dumps(mesh_material, indent=4))
            f.close()
        dest = mesh_materials_dir if os.path.exists(mesh_materials_dir) else file_path
        rename(path=file_path, dest=dest, filename=material_name)


def restore_mesh_transforms(transforms, meshes):
    for i, mesh in enumerate(meshes):
        mt, mpt = transforms[i]
        mesh.matrix_world = mt
        restore_meshpoint_transforms(children=mesh.children, original=mpt)


def restore_meshpoint_transforms(children, original):
    if children and len(children) >= 1:
        for i, empty in enumerate(children):
            empty.matrix_local = original[i]


def get_original_transforms(mesh):
    original_transform = mesh.matrix_world.copy()
    mesh.matrix_world = GAME_MATRIX @ mesh.matrix_world
    original_meshpoint_transforms = apply_meshpoint_transforms(mesh=mesh)
    return original_transform, original_meshpoint_transforms


def join_meshes(meshes):
    bpy.ops.object.select_all(action="DESELECT")
    for mesh in sorted(meshes, key=lambda mesh: mesh.name.lower()):
        mesh.select_set(True)
    if len(meshes) > 1:
        bpy.ops.object.join()
    return bpy.context.view_layer.objects.active


def purge_orphans():
    bpy.ops.outliner.orphans_purge()


def make_meshpoint_rules(mesh):
    invalid_meshpoints = []

    for meshpoint in mesh.children:
        name = meshpoint.name
        is_matched = False

        for key, regex in MESHPOINTING_RULES.items():
            if re.match(regex, name):
                is_matched = True
                break

        if not is_matched:
            invalid_meshpoints.append(name)

    return invalid_meshpoints


def convert_rebellion_mesh(file_path, dest_path, mode):
    subprocess.run([REBELLION_MESHBUILDER_EXE, "mesh", file_path, dest_path, mode])
    with open(dest_path, "r+") as f:
        lines = f.readlines()

        # temp solution to a bug ironclad needs to fix:
        # - meshbuilder doesn't recognize the archive line in sins 1 meshes
        if len(lines) > 1 and lines[1].startswith("SinsArchiveVersion"):
            lines.pop(1)
        f.seek(0)
        f.truncate()
        f.writelines(lines)


def run_meshbuilder(file_path, dest_path):
    try:
        args = [
            MESHBUILDER_EXE,
            f"--input_path={file_path}",
            f"--output_folder_path={dest_path}",
            "--mesh_output_format=binary",
        ]
        with subprocess.Popen(
            args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
        ) as f:
            for line in f.stdout:
                text = line.strip()

                if re.search(r"Unexpected\smesh\spoint\sname", text):
                    meshpoint = re.sub(
                        r"Unexpected\smesh\spoint\sname\s\:\s\'(.*)\'", r"\1", text
                    )
                    return "mesh_point", meshpoint
                elif re.search(r"Attribute\snot\sfound\s\:\sTEXCOORD_\d", text):
                    raise NotImplementedError("The mesh is missing UV Coordinates.")
                elif re.search(r"No\smeshes\sfound\.", text):
                    raise NotImplementedError(text)
                print(text)
        return None, None
    except subprocess.CalledProcessError as e:
        if not str(e.stderr).strip().endswith("not found"):
            return None, e.stderr


def run_texconv(texture, temp_dir):
    subprocess.run(
        [TEXCONV_EXE, "-m", "1", "-y", "-f", "BC7_UNORM", "-r", texture, "-o", temp_dir]
    )
