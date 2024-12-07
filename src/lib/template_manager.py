import json, os


class TemplateManager:
    def __init__(self):
        self.templates_file = os.path.join(
            os.environ["LOCALAPPDATA"],
            "sins2",
            "sins2-blender-extension",
            "camera_templates.json",
        )

    def save_template(self, name, props):
        """Save a camera template with multiple cameras"""
        templates = self.load_templates()

        # Save global settings
        template = {
            "global_settings": {
                "icon_zoom": props.icon_zoom,
                "hdri_path": props.hdri_path,
                "hdri_strength": props.hdri_strength,
            },
            "cameras": [],
        }

        # Save camera settings
        for camera in props.cameras:
            camera_settings = {}
            for prop in camera.bl_rna.properties:
                if not prop.is_readonly:
                    camera_settings[prop.identifier] = getattr(camera, prop.identifier)
            template["cameras"].append(camera_settings)

        templates[name] = template

        # Ensure directory exists
        os.makedirs(os.path.dirname(self.templates_file), exist_ok=True)

        # Save to file
        with open(self.templates_file, "w") as f:
            json.dump(templates, f, indent=4)

    def load_template(self, name, props):
        """Load a template into properties"""
        templates = self.load_templates()
        if name not in templates:
            return False

        template = templates[name]

        # Load global settings
        for prop, value in template["global_settings"].items():
            if hasattr(props, prop):
                setattr(props, prop, value)

        # Load camera settings
        props.cameras.clear()
        for camera_settings in template["cameras"]:
            new_camera = props.cameras.add()
            for prop_name, value in camera_settings.items():
                if hasattr(new_camera, prop_name):
                    setattr(new_camera, prop_name, value)

        return True

    def load_templates(self):
        """Load all saved templates"""
        if not os.path.exists(self.templates_file):
            return {}

        try:
            with open(self.templates_file, "r") as f:
                return json.load(f)
        except json.JSONDecodeError:
            return {}

    def get_template_enum_items(self):
        """Get templates formatted for EnumProperty"""
        items = [
            ("DEFAULT", "Default", "Default camera configuration"),
            ("CUSTOM", "Custom", "Custom camera configuration"),
        ]

        templates = self.load_templates()
        for name in templates.keys():
            items.append((name, name, f"Load {name} template"))

        return items

    def remove_template(self, name):
        """Remove a template from storage"""
        templates = self.load_templates()
        if name in templates:
            del templates[name]
            with open(self.templates_file, "w") as f:
                json.dump(templates, f, indent=4)
