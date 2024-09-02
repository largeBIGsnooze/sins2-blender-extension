bl_info = {
    "name": "Sins II Utility",
    "description": "Extension for exporting meshes whilst leveraging official tooling",
    "author": "Tyloth, Cyno Studios",
    "version": (0, 2, 0),
    "blender": (4, 1, 0),
    "location": "3D View",
    "category": "Import-Export",
}

import bpy


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
