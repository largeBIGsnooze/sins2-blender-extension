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
            'camera': context.scene.camera,
            'engine': context.scene.render.engine,
            'exposure': context.scene.view_settings.exposure,
            'world': self._save_world_lighting()
        }
        
        # Store cycles samples only if using cycles
        if context.scene.render.engine == 'CYCLES':
            self.original_settings['samples'] = context.scene.cycles.samples
        
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
            'camera': self.context.scene.camera,
            'engine': self.context.scene.render.engine,
            'samples': self.context.scene.cycles.samples,
            'exposure': self.context.scene.view_settings.exposure,
            'world': self._save_world_lighting()
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
        camera_name = camera_settings.filename_suffix if camera_settings.filename_suffix else "Unnamed Camera"
        self.cam_data = bpy.data.cameras.new(name=f'Render_Camera_{camera_name}')
        self.cam_obj = bpy.data.objects.new(f'Render_Camera_{camera_name}', self.cam_data)
        self.context.scene.collection.objects.link(self.cam_obj)
        
        # Set camera as active
        self.context.scene.camera = self.cam_obj
        
        # Calculate camera position using spherical coordinates
        distance = camera_settings.distance * bounding_sphere_radius * camera_settings.extra_zoom
        h_angle = math.radians(camera_settings.horizontal_angle)
        v_angle = math.radians(camera_settings.vertical_angle)
        
        print("\n=== Camera Settings ===")
        print(f"Distance: {distance} (base: {camera_settings.distance}, zoom: {camera_settings.extra_zoom})")
        print(f"Horizontal Angle: {math.degrees(h_angle)}°")
        print(f"Vertical Angle: {math.degrees(v_angle)}°")
        print(f"Tilt: {camera_settings.tilt}°")
        
        # Convert spherical to Cartesian coordinates
        # Vertical angle: 0° = horizontal, 90° = up, -90° = down
        # Horizontal angle: 0° = front (-Y), 90° = left (-X), -90° = right (+X)
        horizontal_distance = distance * math.cos(v_angle)  # Distance projected onto XY plane
        x = -horizontal_distance * math.sin(h_angle)        # X = -horizontal_distance * sin(h)
        y = -horizontal_distance * math.cos(h_angle)       # Y = -horizontal_distance * cos(h)
        z = distance * math.sin(v_angle)                   # Z = distance * sin(v)
        
        print("\n=== Pre-Transform Position ===")
        print(f"Initial Position: ({x}, {y}, {z})")
        
        # Set camera position with offsets
        final_pos = Vector((
            center[0] + x + camera_settings.offset_x,
            center[1] + y + camera_settings.offset_y,
            center[2] + z + camera_settings.offset_z
        ))
        self.cam_obj.location = final_pos
        
        print("\n=== Final Camera Setup ===")
        print(f"Final Position: {final_pos}")
        print(f"Offsets: ({camera_settings.offset_x}, {camera_settings.offset_y}, {camera_settings.offset_z})")
        
        # Point camera at model center
        direction = Vector(center) - self.cam_obj.location
        rot_quat = direction.to_track_quat('-Z', 'Y')
        self.cam_obj.rotation_euler = rot_quat.to_euler()
        
        # Apply tilt rotation around local X axis
        tilt_rad = math.radians(camera_settings.tilt)
        local_rotation = Euler((tilt_rad, 0, 0), 'XYZ')
        
        # Convert to quaternions for proper local rotation
        rot_quat = self.cam_obj.rotation_euler.to_quaternion()
        tilt_quat = local_rotation.to_quaternion()
        final_rot = rot_quat @ tilt_quat
        
        # Apply final rotation
        self.cam_obj.rotation_euler = final_rot.to_euler()
        
        print(f"Final Rotation: {[math.degrees(a) for a in self.cam_obj.rotation_euler]}")
        
        # Set camera settings
        self.cam_data.type = camera_settings.type
        if camera_settings.type == 'ORTHO':
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
        self.context.scene.render.engine = 'CYCLES'
        self.context.scene.cycles.samples = render_settings.samples
        self.context.scene.render.resolution_x = render_settings.resolution_x
        self.context.scene.render.resolution_y = render_settings.resolution_y
        self.context.scene.render.film_transparent = (render_settings.transparent == "TRANSPARENT")
        
    def setup_hdri(self, hdri_settings, camera_settings):
        """Setup HDRI world lighting"""
        if hdri_settings.hdri_path:
            self.context.scene.world.use_nodes = True
            nodes = self.context.scene.world.node_tree.nodes
            links = self.context.scene.world.node_tree.links
            
            nodes.clear()
            background = nodes.new('ShaderNodeBackground')
            env_tex = nodes.new('ShaderNodeTexEnvironment')
            mapping = nodes.new('ShaderNodeMapping')
            tex_coord = nodes.new('ShaderNodeTexCoord')
            output = nodes.new('ShaderNodeOutputWorld')
            
            # Load HDRI image
            env_tex.image = bpy.data.images.load(hdri_settings.hdri_path)
            
            # Set strength from camera settings
            background.inputs['Strength'].default_value = camera_settings.hdri_strength
            
            # Connect nodes
            links.new(tex_coord.outputs['Generated'], mapping.inputs[0])
            links.new(mapping.outputs[0], env_tex.inputs[0])
            links.new(env_tex.outputs['Color'], background.inputs['Color'])
            links.new(background.outputs['Background'], output.inputs['Surface'])
            
            # Position nodes
            output.location = (300, 0)
            background.location = (100, 0)
            env_tex.location = (-100, 0)
            mapping.location = (-300, 0)
            tex_coord.location = (-500, 0)
            
    def setup_icon_render_settings(self):
        """Setup specific render settings for icon rendering"""
        print("\n=== Setting up Icon Render Settings ===")
        render = self.context.scene.render
        view = self.context.scene.view_settings
        
        print(f"Original Engine: {render.engine}")
        render.engine = 'CYCLES'
        print(f"Setting Engine to: {render.engine}")
        
        # Basic render settings
        render.resolution_x = 200
        render.resolution_y = 200
        render.film_transparent = True
        render.filter_size = 1.5
        print(f"Resolution: {render.resolution_x}x{render.resolution_y}")
        print(f"Transparent: {render.film_transparent}")
        
        # Set cycles settings
        if hasattr(self.context.scene, 'cycles'):
            self.context.scene.cycles.samples = 64
            print(f"Cycles Samples: {self.context.scene.cycles.samples}")
        
        # Image settings
        render.image_settings.file_format = 'PNG'
        render.image_settings.color_mode = 'RGBA'
        render.image_settings.color_depth = '8'
        
        # View transform settings
        view.view_transform = 'Standard'
        view.look = 'None'
        view.exposure = 0
        view.gamma = 1.0
        
    def setup_transparent_world(self):
        """Setup transparent world background"""
        self.context.scene.world.use_nodes = True
        nodes = self.context.scene.world.node_tree.nodes
        nodes["Background"].inputs[0].default_value = (0, 0, 0, 0)
        
    def setup_icon_materials(self):
        """Setup white emission materials for icon rendering"""
        self.original_materials = {}
        
        for obj in self.context.scene.objects:
            if obj.type == 'MESH':
                # Store original material
                self.original_materials[obj] = obj.active_material
                
                # Create icon material
                icon_mat = bpy.data.materials.new(name="Icon_Material")
                icon_mat.use_nodes = True
                nodes = icon_mat.node_tree.nodes
                links = icon_mat.node_tree.links
                
                nodes.clear()
                
                # Create nodes
                output = nodes.new('ShaderNodeOutputMaterial')
                emission = nodes.new('ShaderNodeEmission')
                transparent = nodes.new('ShaderNodeBsdfTransparent')
                mix_shader = nodes.new('ShaderNodeMixShader')
                geometry = nodes.new('ShaderNodeNewGeometry')  # Add geometry node for backface detection
                
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
                links.new(geometry.outputs['Backfacing'], mix_shader.inputs[0])
                links.new(transparent.outputs[0], mix_shader.inputs[1])
                links.new(emission.outputs[0], mix_shader.inputs[2])
                links.new(mix_shader.outputs[0], output.inputs[0])
                
                obj.active_material = icon_mat
                
    def cleanup_icon_materials(self):
        """Restore original materials after icon rendering"""
        if hasattr(self, 'original_materials'):
            for obj, material in self.original_materials.items():
                obj.active_material = material
                
            # Clean up temporary icon materials
            for material in bpy.data.materials:
                if material.name.startswith("Icon_Material"):
                    bpy.data.materials.remove(material, do_unlink=True)
        
    def setup_top_down_camera(self, zoom_factor):
        """Setup orthographic top-down camera"""
        bounding_sphere_radius, center_x, center_y = get_bounding_box(self.mesh)
        if not bounding_sphere_radius or bounding_sphere_radius <= 0:
            raise ValueError("Invalid bounding sphere radius")
        
        self.cam_data = bpy.data.cameras.new(name='Top_Down_Camera')
        self.cam_data.type = 'ORTHO'
        
        self.cam_obj = bpy.data.objects.new('Top_Down_Camera', self.cam_data)
        self.context.scene.collection.objects.link(self.cam_obj)
        
        # Position camera above mesh
        self.cam_obj.location = (
            self.mesh.location.x,
            self.mesh.location.y,
            self.mesh.location.z + bounding_sphere_radius * 2
        )
        
        # Rotate camera to look down (-90 degrees around X)
        self.cam_obj.rotation_euler = (0, 0, math.radians(-90))
        
        # Set orthographic scale based on bounding sphere and zoom
        self.cam_data.ortho_scale = bounding_sphere_radius * zoom_factor
        
        # Set as active camera
        self.context.scene.camera = self.cam_obj
        
    def setup_three_point_lighting(self, camera_settings):
        """Setup 3-point lighting for perspective renders"""
        bounding_sphere_radius, _, _, center = get_bounding_box(self.mesh)
        if not bounding_sphere_radius or bounding_sphere_radius <= 0:
            raise ValueError("Invalid bounding sphere radius")
        
        distance = bounding_sphere_radius * camera_settings.lighting_distance
        
        # Store original lights to restore later
        self.original_lights = []
        for obj in self.context.scene.objects:
            if obj.type == 'LIGHT':
                self.original_lights.append(obj)
        
        # Create key light (main light)
        key_light = bpy.data.lights.new(name="Key_Light", type='AREA')
        key_light.energy = 1000
        key_light.size = bounding_sphere_radius
        key_obj = bpy.data.objects.new("Key_Light", key_light)
        self.context.scene.collection.objects.link(key_obj)
        
        # Create fill light (softer, secondary light)
        fill_light = bpy.data.lights.new(name="Fill_Light", type='AREA')
        fill_light.energy = 500
        fill_light.size = bounding_sphere_radius
        fill_obj = bpy.data.objects.new("Fill_Light", fill_light)
        self.context.scene.collection.objects.link(fill_obj)
        
        # Create back light (rim light)
        back_light = bpy.data.lights.new(name="Back_Light", type='AREA')
        back_light.energy = 750
        back_light.size = bounding_sphere_radius
        back_obj = bpy.data.objects.new("Back_Light", back_light)
        self.context.scene.collection.objects.link(back_obj)
        
        # Position lights relative to camera
        cam_direction = self.cam_obj.matrix_world.to_quaternion() @ Vector((0.0, 0.0, -1.0))
        cam_right = self.cam_obj.matrix_world.to_quaternion() @ Vector((1.0, 0.0, 0.0))
        cam_up = self.cam_obj.matrix_world.to_quaternion() @ Vector((0.0, 1.0, 0.0))
        
        # Key light - 45° up and to the side
        key_pos = center + (cam_right + cam_up).normalized() * distance
        key_obj.location = key_pos
        
        # Fill light - opposite side, lower intensity
        fill_pos = center + (-cam_right + cam_up * 0.5).normalized() * distance
        fill_obj.location = fill_pos
        
        # Back light - behind and above
        back_pos = center + (-cam_direction + cam_up).normalized() * distance
        back_obj.location = back_pos
        
        # Make lights face the center
        for light in [key_obj, fill_obj, back_obj]:
            direction = center - light.location
            rot_quat = direction.to_track_quat('-Z', 'Y')
            light.rotation_euler = rot_quat.to_euler()
        
    def render(self, output_path):
        """Perform render"""
        self.context.scene.render.filepath = output_path
        bpy.ops.render.render(write_still=True)
        
    def cleanup(self):
        """Restore original settings and clean up"""
        self.context.scene.camera = self.original_settings['camera']
        self.context.scene.render.engine = self.original_settings['engine']
        self.context.scene.view_settings.exposure = self.original_settings['exposure']
        self._restore_world_lighting(self.original_settings['world'])

        # Restore cycles samples only if they were stored and we're using cycles
        if ('samples' in self.original_settings and 
            self.context.scene.render.engine == 'CYCLES'):
            self.context.scene.cycles.samples = self.original_settings['samples']
        
        # Clean up all cameras and camera data
        for obj in bpy.data.objects:
            if obj.type == 'CAMERA' and obj.name.startswith('Render_Camera'):
                bpy.data.objects.remove(obj, do_unlink=True)
            if obj.type == 'CAMERA' and obj.name.startswith('Top_Down_Camera'):
                bpy.data.objects.remove(obj, do_unlink=True)
        
        for cam in bpy.data.cameras:
            if cam.name.startswith('Render_Camera'):
                bpy.data.cameras.remove(cam, do_unlink=True)
            if cam.name.startswith('Top_Down_Camera'):
                bpy.data.cameras.remove(cam, do_unlink=True)

        # Restore original lights
        if hasattr(self, 'original_lights'):
            # Remove temporary lights
            for obj in self.context.scene.objects:
                if obj.type == 'LIGHT' and obj.name.startswith(('Key_Light', 'Fill_Light', 'Back_Light')):
                    light = obj.data
                    bpy.data.objects.remove(obj, do_unlink=True)
                    bpy.data.lights.remove(light)
        
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
            # if camera_settings.lighting_enabled == "ENABLED":
            #     self.setup_three_point_lighting(camera_settings)
            
            # Set output path using suffix
            safe_suffix = "".join(c for c in camera_settings.filename_suffix if c.isalnum() or c in (' ', '-', '_')).rstrip()
            filename = f"{mesh_name}_{safe_suffix}.png"
            self.context.scene.render.filepath = os.path.join(output_dir, filename)
            
            # Render
            bpy.ops.render.render(write_still=True)