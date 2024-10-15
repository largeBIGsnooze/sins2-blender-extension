bl_info = {
    "name": "Sins II Extension",
    "description": "Extension for importing and exporting Sins of a Solar Empire 2 meshes whilst leveraging official tooling",
    "author": "Tyloth, Cyno Studios",
    "version": (0, 8, 7),
    "blender": (4, 1, 0),
    "location": "3D View",
    "category": "Import-Export",
}

import bpy, os, tempfile

TEMP_TEXTURES_PATH = os.path.join(
    tempfile.gettempdir(), "sins2-blender-extension.tmp.textures.dir"
)


# clear cached textures
def clear_temp_textures():
    os.makedirs(TEMP_TEXTURES_PATH, exist_ok=True)
    for texture in os.listdir(TEMP_TEXTURES_PATH):
        os.remove(os.path.join(TEMP_TEXTURES_PATH, texture))


def register():
    from .src import properties
    from . import ui

    ui.register()
    properties.register()
    clear_temp_textures()


def unregister():
    from .src import properties
    from . import ui

    ui.unregister()
    properties.unregister()
    clear_temp_textures()


if __name__ == "__main__":
    register()
