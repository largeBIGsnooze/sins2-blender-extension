class Vertex:
    def __init__(self, pos, normals, tangents, uv0, uv1):
        self.pos = pos
        self.normals = normals
        self.tangents = tangents
        self.uv0 = uv0
        self.uv1 = uv1


class Primitive:
    def __init__(self, mat_idx, start, end):
        self.mat_idx = mat_idx
        self.start = start
        self.end = end


class Meshpoint:
    def __init__(self, name, pos, rot, bone_idx):
        self.name = name
        self.pos = pos
        self.rot = rot
        self.bone_idx = bone_idx


class ShieldEffect:
    def __init__(self, mesh_name):
        self.mesh_name = mesh_name

    def json(self):
        return {
            "primary": {
                "mesh": self.mesh_name,
                "impact_texture_animation": "trader_normal_shield_impact",
                "color": "ffffffff",
                "max_radius": 67.937225,
                "duration": 2.0,
                "fps": 32.0,
                "min_radius": 33.937225,
            }
        }


class MeshMaterial:
    def __init__(
        self,
        clr=None,
        nrm=None,
        msk=None,
        orm=None,
    ):
        self.clr = clr
        self.nrm = nrm
        self.msk = msk
        self.orm = orm

    def json(self):
        return {
            key: value
            for key, value in {
                "base_color_texture": self.clr or "",
                "normal_texture": self.nrm or "",
                "mask_texture": self.msk or "",
                "occlusion_roughness_metallic_texture": self.orm or "",
                "emissive_hue_strength": 1,
                "base_color_factor": list((1, 1, 1, 1)),
                "roughness_factor": 1,
                "metallic_factor": 1,
            }.items()
            if value
        }
