import tempfile, os
from mathutils import Matrix, Vector

TEMP_DIR = tempfile.gettempdir()
MESHPOINT_COLOR = (0.18039216101169586, 0.7686275243759155, 1.0)

GAME_MATRIX = Matrix(((-1, 0, 0, 0), (0, 0, 1, 0), (0, 1, 0, 0), (0, 0, 0, 1)))
MESHPOINT_MATRIX = Matrix(((-1, 0, 0, 0), (0, 1, 0, 0), (0, 0, -1, 0), (0, 0, 0, 1)))

ADDON_SETTINGS_FILE = os.path.join(
    os.environ["LOCALAPPDATA"], "sins2", "sins2-blender-extension", "settings.json"
)

TEMP_TEXTURES_PATH = os.path.join(TEMP_DIR, "sins2-blender-extension.tmp.textures.dir")

CWD_PATH = os.path.dirname(os.path.abspath(__file__))
MESHBUILDER_EXE = os.path.join(
    CWD_PATH, "src", "lib", "tools", "meshbuilder", "meshbuilder.exe"
)
REBELLION_PATH = os.path.join(TEMP_TEXTURES_PATH, "rebellion")
REBELLION_MESHBUILDER_EXE = os.path.join(
    CWD_PATH, "src", "lib", "tools", "sins1_meshbuilder", "sins1_meshbuilder.exe"
)
TEXCONV_EXE = os.path.join(CWD_PATH, "src", "lib", "tools", "texconv", "texconv.exe")