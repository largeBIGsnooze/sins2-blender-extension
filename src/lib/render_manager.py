import bpy
import os
import math
from mathutils import Vector, Euler
from .helpers.mesh_utils import get_bounding_box, GAME_MATRIX


class RenderManager:
    def __init__(self, context, mesh, filepath):
        self.context = context
        self.mesh = mesh
        self.filepath = filepath
        self.cam_obj = None
        self.cam_data = None

        # Store original settings
        self.original_settings = {
            "camera": context.scene.camera,
            "engine": context.scene.render.engine,
            "exposure": context.scene.view_settings.exposure,
            "world": self._save_world_lighting(),
        }

        # Store cycles samples only if using cycles
        if context.scene.render.engine == "CYCLES":
            self.original_settings["samples"] = context.scene.cycles.samples

    def _save_world_lighting(self):
        """Save the current world lighting settings"""
        if self.context.scene.world:
            return self.context.scene.world.copy()
        return None

    def _restore_world_lighting(self, saved_world):
        """Restore previously saved world lighting settings"""
        if saved_world:
            self.context.scene.world = saved_world

    def _store_original_settings(self):
        """Store all original render settings"""
        return {
            "camera": self.context.scene.camera,
            "engine": self.context.scene.render.engine,
            "samples": self.context.scene.cycles.samples,
            "exposure": self.context.scene.view_settings.exposure,
            "world": self._save_world_lighting(),
        }

    def setup_camera(self, camera_settings):
        """Setup camera with given settings"""
        bounding_sphere_radius, _, center = get_bounding_box(self.mesh)
        if not bounding_sphere_radius or bounding_sphere_radius <= 0:
            raise ValueError("Invalid bounding sphere radius")

        print("\n=== Camera Setup ===")
        print(f"Filename Suffix: {camera_settings.filename_suffix}")
        print(f"Bounding Sphere Radius: {bounding_sphere_radius}")
        print(f"Model Center: {center}")

        # Create camera with proper name
        camera_name = (
            camera_settings.filename_suffix
            if camera_settings.filename_suffix
            else "Unnamed Camera"
        )
        self.cam_data = bpy.data.cameras.new(name=f"Render_Camera_{camera_name}")
        self.cam_obj = bpy.data.objects.new(
            f"Render_Camera_{camera_name}", self.cam_data
        )
        self.context.scene.collection.objects.link(self.cam_obj)

        # Set camera as active
        self.context.scene.camera = self.cam_obj

        # Calculate camera position using spherical coordinates
        distance = camera_settings.distance * bounding_sphere_radius
        h_angle = math.radians(camera_settings.horizontal_angle)
        v_angle = math.radians(camera_settings.vertical_angle)

        print("\n=== Camera Settings ===")
        print(f"Distance: {distance} (base: {camera_settings.distance})")
        print(f"Horizontal Angle: {math.degrees(h_angle)}°")
        print(f"Vertical Angle: {math.degrees(v_angle)}°")
        print(f"Tilt: {camera_settings.tilt}°")

        # Convert spherical to Cartesian coordinates
        # Vertical angle: 0° = horizontal, 90° = up, -90° = down
        # Horizontal angle: 0° = front (-Y), 90° = left (-X), -90° = right (+X)
        horizontal_distance = distance * math.cos(
            v_angle
        )  # Distance projected onto XY plane
        x = -horizontal_distance * math.sin(
            h_angle
        )  # X = -horizontal_distance * sin(h)
        y = -horizontal_distance * math.cos(
            h_angle
        )  # Y = -horizontal_distance * cos(h)
        z = distance * math.sin(v_angle)  # Z = distance * sin(v)

        print("\n=== Pre-Transform Position ===")
        print(f"Initial Position: ({x}, {y}, {z})")

        # Set camera position with offsets
        final_pos = Vector(
            (
                center[0] + x + camera_settings.offset_x,
                center[1] + y + camera_settings.offset_y,
                center[2] + z + camera_settings.offset_z,
            )
        )
        self.cam_obj.location = final_pos

        print("\n=== Final Camera Setup ===")
        print(f"Final Position: {final_pos}")
        print(
            f"Offsets: ({camera_settings.offset_x}, {camera_settings.offset_y}, {camera_settings.offset_z})"
        )

        # Point camera at model center
        direction = Vector(center) - self.cam_obj.location
        rot_quat = direction.to_track_quat("-Z", "Y")
        self.cam_obj.rotation_euler = rot_quat.to_euler()

        # Apply tilt rotation around local X axis
        tilt_rad = math.radians(camera_settings.tilt)
        local_rotation = Euler((tilt_rad, 0, 0), "XYZ")

        # Convert to quaternions for proper local rotation
        rot_quat = self.cam_obj.rotation_euler.to_quaternion()
        tilt_quat = local_rotation.to_quaternion()
        final_rot = rot_quat @ tilt_quat

        # Apply final rotation
        self.cam_obj.rotation_euler = final_rot.to_euler()

        print(
            f"Final Rotation: {[math.degrees(a) for a in self.cam_obj.rotation_euler]}"
        )

        # Set camera settings
        self.cam_data.type = camera_settings.type
        if camera_settings.type == "ORTHO":
            self.cam_data.ortho_scale = camera_settings.focal_length
        else:
            self.cam_data.lens = camera_settings.focal_length
        self.cam_data.clip_end = camera_settings.clip_end

        print("\n=== Camera Properties ===")
        print(f"Type: {camera_settings.type}")
        print(f"Focal Length: {camera_settings.focal_length}mm")
        print(f"Clip End: {camera_settings.clip_end}")
        print("==================\n")

    def setup_render_settings(self, render_settings):
        """Setup render settings"""
        self.context.scene.render.engine = "CYCLES"

        # Set cycles settings for better lighting
        if hasattr(self.context.scene, "cycles"):
            cycles = self.context.scene.cycles
            cycles.samples = render_settings.samples
            cycles.use_adaptive_sampling = True
            cycles.adaptive_threshold = 0.01
            cycles.use_denoising = True
            cycles.denoiser = "OPTIX"  # Use OptiX denoiser if available

        self.context.scene.render.resolution_x = render_settings.resolution_x
        self.context.scene.render.resolution_y = render_settings.resolution_y
        self.context.scene.render.film_transparent = (
            render_settings.transparent == "TRANSPARENT"
        )

    def setup_hdri(self, hdri_settings, camera_settings):
        """Setup HDRI world lighting with camera ray control"""
        if hdri_settings.hdri_path:
            self.context.scene.world.use_nodes = True
            nodes = self.context.scene.world.node_tree.nodes
            links = self.context.scene.world.node_tree.links

            nodes.clear()

            # Create nodes
            output = nodes.new("ShaderNodeOutputWorld")
            mix_shader = nodes.new("ShaderNodeMixShader")
            light_path = nodes.new("ShaderNodeLightPath")
            background_1 = nodes.new("ShaderNodeBackground")  # Controlled strength
            background_2 = nodes.new("ShaderNodeBackground")  # Full strength
            env_tex = nodes.new("ShaderNodeTexEnvironment")
            mapping = nodes.new("ShaderNodeMapping")
            tex_coord = nodes.new("ShaderNodeTexCoord")

            # Load HDRI image
            env_tex.image = bpy.data.images.load(hdri_settings.hdri_path)

            # Set strengths
            background_1.inputs["Strength"].default_value = (
                camera_settings.hdri_strength
            )
            background_2.inputs["Strength"].default_value = 1.0

            # Connect nodes
            links.new(tex_coord.outputs["Generated"], mapping.inputs[0])
            links.new(mapping.outputs[0], env_tex.inputs[0])
            links.new(env_tex.outputs["Color"], background_1.inputs["Color"])
            links.new(env_tex.outputs["Color"], background_2.inputs["Color"])
            links.new(light_path.outputs["Is Camera Ray"], mix_shader.inputs[0])
            links.new(background_1.outputs["Background"], mix_shader.inputs[1])
            links.new(background_2.outputs["Background"], mix_shader.inputs[2])
            links.new(mix_shader.outputs[0], output.inputs["Surface"])

            # Position nodes
            output.location = (300, 0)
            mix_shader.location = (100, 0)
            light_path.location = (-100, 200)
            background_1.location = (-100, 0)
            background_2.location = (-100, -200)
            env_tex.location = (-300, 0)
            mapping.location = (-500, 0)
            tex_coord.location = (-700, 0)

    def setup_icon_render_settings(self):
        """Setup specific render settings for icon rendering"""
        print("\n=== Setting up Icon Render Settings ===")
        render = self.context.scene.render
        view = self.context.scene.view_settings

        print(f"Original Engine: {render.engine}")
        render.engine = "CYCLES"
        print(f"Setting Engine to: {render.engine}")

        # Basic render settings
        render.resolution_x = 200
        render.resolution_y = 200
        render.film_transparent = True
        render.filter_size = 1.5
        print(f"Resolution: {render.resolution_x}x{render.resolution_y}")
        print(f"Transparent: {render.film_transparent}")

        # Set cycles settings
        if hasattr(self.context.scene, "cycles"):
            self.context.scene.cycles.samples = 64
            print(f"Cycles Samples: {self.context.scene.cycles.samples}")

        # Image settings
        render.image_settings.file_format = "PNG"
        render.image_settings.color_mode = "RGBA"
        render.image_settings.color_depth = "8"

        # View transform settings
        view.view_transform = "Standard"
        view.look = "None"
        view.exposure = 0
        view.gamma = 1.0

    def setup_transparent_world(self):
        """Setup transparent world background"""
        self.context.scene.world.use_nodes = True
        nodes = self.context.scene.world.node_tree.nodes
        links = self.context.scene.world.node_tree.links

        # Clear all nodes first
        nodes.clear()

        # Create and link transparent background
        output = nodes.new("ShaderNodeOutputWorld")
        background = nodes.new("ShaderNodeBackground")
        background.inputs["Color"].default_value = (0, 0, 0, 0)
        background.inputs["Strength"].default_value = 0

        links.new(background.outputs["Background"], output.inputs["Surface"])

    def setup_icon_materials(self):
        """Setup white emission materials for icon rendering"""
        self.original_materials = {}

        for obj in self.context.scene.objects:
            if obj.type == "MESH":
                # Store original material
                self.original_materials[obj] = obj.active_material

                # Create icon material
                icon_mat = bpy.data.materials.new(name="Icon_Material")
                icon_mat.use_nodes = True
                nodes = icon_mat.node_tree.nodes
                links = icon_mat.node_tree.links

                nodes.clear()

                # Create nodes
                output = nodes.new("ShaderNodeOutputMaterial")
                emission = nodes.new("ShaderNodeEmission")
                transparent = nodes.new("ShaderNodeBsdfTransparent")
                mix_shader = nodes.new("ShaderNodeMixShader")
                geometry = nodes.new(
                    "ShaderNodeNewGeometry"
                )  # Add geometry node for backface detection

                # Position nodes
                output.location = (300, 0)
                mix_shader.location = (100, 0)
                emission.location = (-100, -100)
                transparent.location = (-100, 100)
                geometry.location = (-300, 0)

                # Setup emission
                emission.inputs[0].default_value = (1.0, 1.0, 1.0, 1.0)
                emission.inputs[1].default_value = 1.0

                # Connect nodes - use backfacing for mix factor
                links.new(geometry.outputs["Backfacing"], mix_shader.inputs[0])
                links.new(transparent.outputs[0], mix_shader.inputs[1])
                links.new(emission.outputs[0], mix_shader.inputs[2])
                links.new(mix_shader.outputs[0], output.inputs[0])

                obj.active_material = icon_mat

    def cleanup_icon_materials(self):
        """Restore original materials after icon rendering"""
        if hasattr(self, "original_materials"):
            for obj, material in self.original_materials.items():
                obj.active_material = material

            # Clean up temporary icon materials
            for material in bpy.data.materials:
                if material.name.startswith("Icon_Material"):
                    bpy.data.materials.remove(material, do_unlink=True)

    def setup_top_down_camera(self, zoom_factor):
        """Setup orthographic top-down camera"""
        bounding_sphere_radius, _, center = get_bounding_box(self.mesh)
        if not bounding_sphere_radius or bounding_sphere_radius <= 0:
            raise ValueError("Invalid bounding sphere radius")

        self.cam_data = bpy.data.cameras.new(name="Top_Down_Camera")
        self.cam_data.type = "ORTHO"

        self.cam_obj = bpy.data.objects.new("Top_Down_Camera", self.cam_data)
        self.context.scene.collection.objects.link(self.cam_obj)

        # Position camera above mesh center
        self.cam_obj.location = (
            center[0],
            center[1],
            center[2] + bounding_sphere_radius * 2,
        )

        # Rotate camera to look down (-90 degrees around X)
        self.cam_obj.rotation_euler = (0, 0, math.radians(-90))

        # Set orthographic scale based on bounding sphere and zoom
        self.cam_data.ortho_scale = bounding_sphere_radius * zoom_factor

        # Set as active camera
        self.context.scene.camera = self.cam_obj

    def setup_three_point_lighting(self, camera_settings):
        """Setup 3-point lighting for perspective renders"""
        print("\n=== Setting up 3-Point Lighting ===")
        bounding_sphere_radius, _, center = get_bounding_box(self.mesh)
        if not bounding_sphere_radius or bounding_sphere_radius <= 0:
            raise ValueError("Invalid bounding sphere radius")

        # Scale the distance based on both the radius and lighting_distance setting
        base_distance = bounding_sphere_radius * 2  # Base distance is 2x the radius
        distance = (
            base_distance * camera_settings.lighting_distance
        )  # Apply the multiplier
        center_vec = Vector(center)
        print(f"Bounding Sphere Radius: {bounding_sphere_radius}")
        print(f"Base Light Distance: {base_distance}")
        print(f"Final Light Distance: {distance}")
        print(f"Lighting Distance Multiplier: {camera_settings.lighting_distance}")
        print(f"Center: {center_vec}")

        # Store original lights to restore later
        self.original_lights = []
        for obj in self.context.scene.objects:
            if obj.type == "LIGHT":
                self.original_lights.append(obj)
        print(f"Stored {len(self.original_lights)} original lights")

        # Create and log each light setup
        def create_light(name, energy):
            print(f"\nCreating {name}:")
            light = bpy.data.lights.new(name=name, type="AREA")
            light.energy = energy
            light.size = bounding_sphere_radius * camera_settings.light_size_multiplier
            light.use_shadow = True
            light.cycles.cast_shadow = True
            light.spread = 90
            obj = bpy.data.objects.new(name, light)
            self.context.scene.collection.objects.link(obj)
            return obj, light

        key_obj, key_light = create_light("Key_Light", camera_settings.key_light_energy)
        fill_obj, fill_light = create_light(
            "Fill_Light", camera_settings.fill_light_energy
        )
        back_obj, back_light = create_light(
            "Back_Light", camera_settings.back_light_energy
        )

        # Position lights relative to camera using camera's world matrix
        cam_matrix = self.cam_obj.matrix_world
        cam_direction = cam_matrix.to_quaternion() @ Vector((0.0, 0.0, -1.0))
        cam_right = cam_matrix.to_quaternion() @ Vector((1.0, 0.0, 0.0))
        cam_up = cam_matrix.to_quaternion() @ Vector((0.0, 1.0, 0.0))

        print("\nCalculating light positions:")
        print(f"Camera Direction: {cam_direction}")
        print(f"Camera Right: {cam_right}")
        print(f"Camera Up: {cam_up}")

        # Position and log each light
        def position_light(obj, direction, name):
            pos = center_vec + direction.normalized() * distance
            obj.location = pos
            print(f"\n{name} Position:")
            print(f"Direction: {direction.normalized()}")
            print(f"Final Position: {pos}")
            return pos

        key_pos = position_light(key_obj, cam_right + cam_up, "Key Light")
        fill_pos = position_light(fill_obj, -cam_right + cam_up * 0.5, "Fill Light")
        back_pos = position_light(back_obj, -cam_direction + cam_up, "Back Light")

        # Make lights face the center
        print("\nAiming lights at center:")
        for light in [key_obj, fill_obj, back_obj]:
            direction = center_vec - light.location
            rot_quat = direction.to_track_quat("-Z", "Y")
            # Apply camera's rotation influence
            final_rot = self.cam_obj.rotation_euler.to_quaternion() @ rot_quat
            light.rotation_euler = final_rot.to_euler()
            print(
                f"{light.name} Rotation: {[math.degrees(a) for a in light.rotation_euler]}"
            )

        # Add sun if enabled
        if camera_settings.sun_enabled == "ENABLED":
            print("\nCreating Sun Light:")
            sun_light = bpy.data.lights.new(name="Sun_Light", type="SUN")
            sun_light.energy = camera_settings.sun_energy
            sun_obj = bpy.data.objects.new("Sun_Light", sun_light)
            self.context.scene.collection.objects.link(sun_obj)

            # Calculate sun position using spherical coordinates
            h_angle = math.radians(camera_settings.sun_angle_h)
            v_angle = math.radians(camera_settings.sun_angle_v)

            # Convert angles to direction vector
            direction = Vector(
                (
                    -math.sin(h_angle) * math.cos(v_angle),
                    -math.cos(h_angle) * math.cos(v_angle),
                    math.sin(v_angle),
                )
            )

            # Position sun far from scene center
            sun_distance = distance * 10  # Place sun further than other lights
            sun_obj.location = center_vec + direction * sun_distance

            # Point sun at center
            sun_direction = center_vec - sun_obj.location
            rot_quat = sun_direction.to_track_quat("-Z", "Y")
            sun_obj.rotation_euler = rot_quat.to_euler()

            print(f"Sun Energy: {sun_light.energy}")
            print(f"Sun Position: {sun_obj.location}")
            print(f"Sun Rotation: {[math.degrees(a) for a in sun_obj.rotation_euler]}")

        print("\n3-Point Lighting Setup Complete!")

    def get_unique_filepath(self, base_path):
        """Get a unique filepath by adding a number suffix if needed"""
        directory = os.path.dirname(base_path)
        filename = os.path.basename(base_path)
        name, ext = os.path.splitext(filename)

        counter = 1
        final_path = base_path

        while os.path.exists(final_path):
            final_path = os.path.join(directory, f"{name}_{counter}{ext}")
            counter += 1

        return final_path

    def render(self, base_path):
        """Render to file with unique path"""
        unique_path = self.get_unique_filepath(base_path)
        self.context.scene.render.filepath = unique_path
        bpy.ops.render.render(write_still=True)
        print(f"Saved: '{unique_path}'")
        return unique_path

    def cleanup(self):
        """Restore original settings and clean up"""
        # First clean up cameras
        camera_objects = [
            obj
            for obj in bpy.data.objects
            if obj.type == "CAMERA"
            and (
                obj.name.startswith("Render_Camera")
                or obj.name.startswith("Top_Down_Camera")
            )
        ]

        camera_data = [
            cam
            for cam in bpy.data.cameras
            if cam.name.startswith("Render_Camera")
            or cam.name.startswith("Top_Down_Camera")
        ]

        # Remove camera objects first
        for obj in camera_objects:
            bpy.data.objects.remove(obj, do_unlink=True)

        # Then remove camera data
        for cam in camera_data:
            bpy.data.cameras.remove(cam)

        # Clean up lights
        if hasattr(self, "original_lights"):
            light_objects = [
                obj
                for obj in self.context.scene.objects
                if obj.type == "LIGHT"
                and obj.name.startswith(
                    ("Key_Light", "Fill_Light", "Back_Light", "Sun_Light")
                )
            ]

            for obj in light_objects:
                light = obj.data
                bpy.data.objects.remove(obj, do_unlink=True)
                bpy.data.lights.remove(light)

        # Clean up any temporary materials
        for material in bpy.data.materials:
            if material.name.startswith(("Icon_Material", "Render_Material")):
                bpy.data.materials.remove(material, do_unlink=True)

        # Reset render settings
        self.context.scene.render.engine = self.original_settings["engine"]
        self.context.scene.render.film_transparent = False
        self.context.scene.render.filter_size = 1.5  # Reset to default
        self.context.scene.render.image_settings.file_format = "PNG"
        self.context.scene.render.image_settings.color_mode = "RGBA"
        self.context.scene.render.image_settings.color_depth = "8"

        # Reset view settings
        self.context.scene.view_settings.view_transform = "Standard"
        self.context.scene.view_settings.look = "None"
        self.context.scene.view_settings.exposure = self.original_settings["exposure"]
        self.context.scene.view_settings.gamma = 1.0

        # Restore original camera and world settings
        self.context.scene.camera = self.original_settings["camera"]
        self._restore_world_lighting(self.original_settings["world"])

        # Restore cycles samples if needed
        if (
            "samples" in self.original_settings
            and self.context.scene.render.engine == "CYCLES"
        ):
            self.context.scene.cycles.samples = self.original_settings["samples"]

        # Force viewport update
        self.context.view_layer.update()

    def render_all_scenes(self, output_dir):
        """Render all camera scenes"""
        mesh_name = self.mesh.name

        for camera_settings in self.context.scene.mesh_properties.cameras:
            # Setup render settings for this camera
            self.setup_render_settings(camera_settings)

            # Setup HDRI if path is set
            hdri_settings = self.context.scene.mesh_properties
            if hdri_settings.hdri_path:
                self.setup_hdri(hdri_settings, camera_settings)
            else:
                self.setup_transparent_world()

            # Setup camera
            self.setup_camera(camera_settings)

            # Setup 3-point lighting if enabled
            if camera_settings.lighting_enabled == "ENABLED":
                self.setup_three_point_lighting(camera_settings)

            # Set output path using suffix with unique filepath
            safe_suffix = "".join(
                c
                for c in camera_settings.filename_suffix
                if c.isalnum() or c in (" ", "-", "_")
            ).rstrip()
            filename = f"{mesh_name}_{safe_suffix}.png"
            filepath = os.path.join(output_dir, filename)
            unique_filepath = self.get_unique_filepath(filepath)
            self.context.scene.render.filepath = unique_filepath

            # Render
            bpy.ops.render.render(write_still=True)
