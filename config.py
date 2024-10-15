import json, os


class AddonSettings:
    def __init__(self, filepath):
        self.filepath = filepath
        self.SETTINGS = {}
        self.DEFAULT_SETTINGS = {
            "has_synchronized_meshpoint_color": False,
            "is_first_installation": True,
            "current_version": "",
        }

    def init(self):
        try:
            os.makedirs(os.path.dirname(self.filepath), exist_ok=True)
            if not os.path.exists(self.filepath):
                self.reset_settings()
        except Exception as e:
            raise Exception(f"AddonSettings.init() could not create settings file: {e}")

    def load_settings(self):
        try:
            with open(self.filepath, "r") as f:
                self.SETTINGS = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            self.reset_settings()
            self.load_settings()

        return self.SETTINGS

    def reset_settings(self):
        self.SETTINGS = self.DEFAULT_SETTINGS.copy()
        self.save_settings()

    def save_settings(self):
        with open(self.filepath, "w") as f:
            json.dump(self.SETTINGS, f, indent=4)
