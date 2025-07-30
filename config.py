import json, os


class AddonSettings:
    def __init__(self, filepath):
        self.filepath = filepath
        self.settings = {}
        self.meshpoint_rules = {
            "ability": "^ability(\\.\\d*(\\-\\d+)?)?$",
            "child": "^child\\.(\\w*)\\.?(\\d+)?(\\-\\d+)?$",
            "weapon": "^weapon\\.\\w+(\\.\\d+|\\.\\w+)?(\\-\\d+)?$",
            "hangar": "^hangar(\\.\\d*(\\-\\d+)?)?$",
            "bomb": "^bomb(\\.\\d+(\\-\\d+)?)?$",
            "exhaust": "^exhaust(\\.\\d*(\\-\\d+)?)?$",
            "aura": "^aura$",
            "center": "^center$",
            "above": "^above$",
            "turret_muzzle": "^turret_muzzle(\\.\\d+)?(\\-\\d+)?$",
            "flair": "^flair(\\.\\w+)(\\.?\\d+)?(\\-\\d+)?$",
            "ship_build": "^ship_build$",
            "extractor": "^extractor$",
        }
        self.default_settings = {
            "has_synchronized_meshpoint_color": False,
            "is_first_installation": True,
            "current_version": "",
            "meshpoint_rules": self.meshpoint_rules,
        }

    def init(self):
        try:
            os.makedirs(os.path.dirname(self.filepath), exist_ok=True)
            if not os.path.exists(self.filepath):
                self.reset()
        except Exception as e:
            raise Exception(f"AddonSettings.init() could not create settings file: {e}")

    def load(self, required_props=["meshpoint_rules"]):
        try:
            with open(self.filepath, "r") as f:
                self.settings = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            self.reset()
            self.load()

        for p in required_props:
            if p not in self.settings:
                self.settings.setdefault(p, self.default_settings[p])

        self.save()
        return self.settings

    def reset(self):
        self.settings = self.default_settings.copy()
        self.save()

    def save(self):
        with open(self.filepath, "w") as f:
            json.dump(self.settings, f, indent=4)
