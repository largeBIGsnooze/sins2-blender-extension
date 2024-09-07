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
