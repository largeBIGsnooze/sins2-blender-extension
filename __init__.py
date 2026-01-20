bl_info = {
    "name": "Sins II Extension",
    "description": "Extension for importing and exporting Sins of a Solar Empire 2 meshes whilst leveraging official tooling",
    "author": "Tyloth, Cyno Studios",
    "version": (1, 4, 1),
    "blender": (4, 1, 0),
    "location": "3D View",
    "category": "Import-Export",
}

import bpy, os


def register():
    from .src import properties
    from . import ui

    ui.register()
    properties.register()


def unregister():
    from .src import properties
    from . import ui

    ui.unregister()
    properties.unregister()


if __name__ == "__main__":
    register()
