from struct import pack, unpack
import json, os, shutil, re
from .helpers.mesh import Meshpoint, Primitive, Vertex
from .helpers.mesh_utils import run_meshbuilder, convert_rebellion_mesh
from .helpers.filesystem import basename, normalize
from ...constants import TEMP_TEXTURES_PATH


class BinaryReader:
    def __init__(self):
        self.offset = 0
        self.buffer = None
        self.mesh_data = {
            x: []
            for x in ["vertices", "indices", "primitives", "materials", "meshpoints"]
        }

        self.materials_offset_start = None
        self.meshpoint_offset_start = None

    def meshpoint(self):
        name_length = self.integer()
        name = self.string(name_length)
        pos = self.vector3f()
        rot = self.matrix3()
        bone_idx = self.short()
        return Meshpoint(name, pos, rot, bone_idx)

    def primitive(self):
        mat_idx = self.short()
        start = self.integer()
        end = self.integer()
        return Primitive(mat_idx, start, end)

    def vertex(self):
        pos = self.vector3f()
        normals = self.vector3f()
        tangents = self.vector4f()
        uv0 = tuple((self.float()[0], self.float()[0]))
        has_uv1 = self.boolean()
        if has_uv1:
            uv1 = tuple((self.float()[0], self.float()[0]))
        else:
            uv1 = None
        return Vertex(pos, normals, tangents, uv0, uv1)

    def bounding_box(self, result=[None, None]):
        result[0] = self.vector3f()
        result[1] = self.vector3f()
        return result

    def bounding_sphere(self, result=[None, None]):
        result[0] = self.vector3f()
        result[1] = self.float()[0]
        return result

    def parse_vertices(self):
        vertex_count = self.integer()
        self.skip(4)
        for i in range(vertex_count):
            v = self.vertex()
            self.mesh_data["vertices"].append(
                {
                    "p": v.pos,
                    "n": v.normals,
                    "t": v.tangents,
                    "uv0": v.uv0,
                    "uv1": v.uv1 if v.uv1 else None,
                }
            )

    def parse_indices(self):
        indices_count = self.integer()
        self.skip(4)
        for i in range(indices_count):
            self.mesh_data["indices"].append(self.integer())

    def parse_primitives(self):
        primitive_count = self.integer()
        self.skip(4)
        for i in range(primitive_count):
            p = self.primitive()
            self.mesh_data["primitives"].append(
                {
                    "material_index": p.mat_idx,
                    "vertex_index_start": p.start,
                    "vertex_index_count": p.end,
                }
            )

    def parse_meshpoints(self):
        meshpoint_count = self.integer()
        self.skip(4)
        self.meshpoint_offset_start = self.offset
        for i in range(meshpoint_count):
            p = self.meshpoint()
            self.mesh_data["meshpoints"].append(
                {
                    "name": p.name,
                    "position": p.pos,
                    "rotation": p.rot,
                    "bone_index": p.bone_idx,
                }
            )

    def parse_bones(self):
        bones = self.integer()
        self.skip(4)

    def parse_materials(self):
        material_count = self.integer()
        self.skip(4)
        self.materials_offset_start = self.offset
        for i in range(material_count):
            name_length = self.integer()
            name = self.string(name_length)
            self.mesh_data["materials"].append(name)

    @staticmethod
    def initialize_from(mesh_file):
        reader = BinaryReader()

        with open(mesh_file, "rb") as f:
            buffer = f.read()

        reader.buffer = buffer
        reader.string(4)  # header
        reader.boolean()  # is_skinned
        reader.bounding_box()
        reader.bounding_sphere()
        reader.skip(8)  # padding
        reader.parse_vertices()
        reader.parse_indices()
        reader.parse_primitives()
        reader.parse_meshpoints()
        reader.parse_bones()
        reader.parse_materials()
        return reader

    def skip(self, amount):
        self.offset += amount

    def matrix3(self):
        return [
            vec
            for row in [
                self.vector3f(),
                self.vector3f(),
                self.vector3f(),
            ]
            for vec in row
        ]

    def short(self):
        result = unpack("h", self.buffer[self.offset : self.offset + 2])[0]
        self.offset += 2
        return result

    def boolean(self):
        result = unpack("?", self.buffer[self.offset : self.offset + 1])[0]
        self.offset += 1
        if result == True:
            return 1
        else:
            return 0

    def string(self, length):
        result = unpack(f"{length}s", self.buffer[self.offset : self.offset + length])[
            0
        ].decode("utf-8")
        self.offset += length
        return result

    def vector3f(self):
        return [self.float()[0] for i in range(3)]

    def vector4f(self):
        return [self.float()[0] for i in range(4)]

    def u32_at_offset(self, offset):
        return unpack("I", self.buffer[offset : offset + 4])[0]

    def integer(self):
        integer = unpack("I", self.buffer[self.offset : self.offset + 4])[0]
        self.offset += 4
        return integer

    def float(self):
        float = unpack("f", self.buffer[self.offset : self.offset + 4])
        self.offset += 4
        return float
