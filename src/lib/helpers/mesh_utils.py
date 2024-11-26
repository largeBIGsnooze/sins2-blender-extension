from mathutils import Vector, Matrix

# Define matrix here instead of importing from ui
GAME_MATRIX = Matrix(((-1, 0, 0, 0), (0, 0, 1, 0), (0, 1, 0, 0), (0, 0, 0, 1)))

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

        # We can add more helper functions from ui.py here
