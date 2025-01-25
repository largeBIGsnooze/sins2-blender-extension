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

DUPLICATION_POSTFIX = r"(\-\d+)?"
MESHPOINTING_RULES = {
    "ability": rf"^ability(\.\d*{DUPLICATION_POSTFIX})?$",
    "child": rf"^child\.(\w*)\.?(\d+)?{DUPLICATION_POSTFIX}$",
    "weapon": rf"^weapon\.\w+(\.\d+|\.\w+)?{DUPLICATION_POSTFIX}$",
    "hangar": rf"^hangar(\.\d*{DUPLICATION_POSTFIX})?$",
    "bomb": rf"^bomb(\.\d+{DUPLICATION_POSTFIX})?$",
    "exhaust": rf"^exhaust(\.\d*{DUPLICATION_POSTFIX})?$",
    "aura": r"^aura$",
    "center": r"^center$",
    "above": r"^above$",
    "turret_muzzle": rf"^turret_muzzle(\.\d+)?{DUPLICATION_POSTFIX}$",
    "flair": rf"^flair(\.\w+)(\.?\d+)?{DUPLICATION_POSTFIX}$",
    "ship_build": r"^ship_build$",
    "extractor": r"^extractor$",
    # ---------------------------- from 2022  ---------------------------- #
    # - `exhaust` // ship exhaust effects                                  #
    # - `bomb` // planet bombing points                                    #
    # - `above` // for effects above                                       #
    # - `aura` // aura effects                                             #
    # - `center` // effects from center                                    #
    # - `extractor` // asteroid resource extractor attachment point        #
    # - `hangar` // strikecraft hangar position                            #
    # - `ship_build` // ship build effects                                 #
    # - `atmosphere_entry` // atmosphere entry effects                     # <-- no references?
    # - `build` // build effects                                           # <-- only sins 1 meshes reference this?
    # - `flair` // flair effects                                             #
    # - `ability` // ability effects                                       #
    # - `weapon`                                                           #
    # - `child`                                                            #
    # - `turret_muzzle`                                                    #
}
