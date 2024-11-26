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
            'samples': context.scene.cycles.samples,
            'exposure': context.scene.view_settings.exposure,
            'world': self._save_world_lighting()
        }
        
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
        print(f"Camera Name: {camera_settings.camera_name}")
        print(f"Bounding Sphere Radius: {bounding_sphere_radius}")
        print(f"Model Center: {center}")
        
        # Create camera
        self.cam_data = bpy.data.cameras.new(name='Render_Camera')
        self.cam_obj = bpy.data.objects.new('Render_Camera', self.cam_data)
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
        x = distance * math.cos(v_angle) * math.sin(h_angle)
        y = distance * math.cos(v_angle) * math.cos(h_angle)
        z = distance * math.sin(v_angle)
        
        print("\n=== Pre-Transform Position ===")
        print(f"Initial Position: ({x}, {y}, {z})")
        
        # Apply GAME_MATRIX transformation
        camera_pos = GAME_MATRIX @ Vector((x, y, z))
        
        print(f"After GAME_MATRIX: ({camera_pos.x}, {camera_pos.y}, {camera_pos.z})")
        
        # Set camera position with offsets
        final_pos = Vector((
            center[0] + camera_pos.x + camera_settings.offset_x,
            center[1] + camera_pos.y + camera_settings.offset_y,
            center[2] + camera_pos.z + camera_settings.offset_z
        ))
        self.cam_obj.location = final_pos
        
        print("\n=== Final Camera Setup ===")
        print(f"Final Position: {final_pos}")
        print(f"Offsets: ({camera_settings.offset_x}, {camera_settings.offset_y}, {camera_settings.offset_z})")
        
        # Point camera at model center and apply tilt
        direction = Vector(center) - self.cam_obj.location
        rot_quat = direction.to_track_quat('-Z', 'Y')
        self.cam_obj.rotation_euler = rot_quat.to_euler()
        
        # Apply tilt rotation
        tilt_rotation = Euler((0, 0, math.radians(camera_settings.tilt)), 'XYZ')
        self.cam_obj.rotation_euler.rotate(tilt_rotation)
        
        print(f"Final Rotation: {[math.degrees(a) for a in self.cam_obj.rotation_euler]}")
        
        # Set camera settings
        self.cam_data.type = camera_settings.type
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
        self.context.scene.render.film_transparent = render_settings.transparent
        
    def setup_hdri(self, hdri_settings):
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
            
            # Set strength on the Background node
            background.inputs['Strength'].default_value = hdri_settings.hdri_strength
            
            # Connect nodes
            links.new(tex_coord.outputs['Generated'], mapping.inputs[0])  # Vector input is at index 0
            links.new(mapping.outputs[0], env_tex.inputs[0])  # Vector output/input at index 0
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
        render = self.context.scene.render
        view = self.context.scene.view_settings
        
        # Basic render settings
        render.engine = 'CYCLES'
        render.cycles.samples = 64
        render.resolution_x = 200
        render.resolution_y = 200
        render.film_transparent = True
        render.filter_size = 1.5  # Sharper pixels
        
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
                
                # Position nodes
                output.location = (300, 0)
                mix_shader.location = (100, 0)
                emission.location = (-100, -100)
                transparent.location = (-100, 100)
                
                # Setup emission
                emission.inputs[0].default_value = (1.0, 1.0, 1.0, 1.0)
                emission.inputs[1].default_value = 1.0
                
                # Connect nodes
                links.new(transparent.outputs[0], mix_shader.inputs[1])
                links.new(emission.outputs[0], mix_shader.inputs[2])
                links.new(mix_shader.outputs[0], output.inputs[0])
                
                obj.active_material = icon_mat
                
    def setup_top_down_camera(self, zoom_factor):
        """Setup orthographic top-down camera"""
        bounding_sphere_radius, _, _ = get_bounding_box(self.mesh)
        if not bounding_sphere_radius or bounding_sphere_radius <= 0:
            raise ValueError("Invalid bounding sphere radius")
            
        self.cam_data = bpy.data.cameras.new(name='Top_Down_Camera')
        self.cam_data.type = 'ORTHO'
        
        self.cam_obj = bpy.data.objects.new('Top_Down_Camera', self.cam_data)
        self.context.scene.collection.objects.link(self.cam_obj)
        
    def render(self, output_path):
        """Perform render"""
        self.context.scene.render.filepath = output_path
        bpy.ops.render.render(write_still=True)
        
    def cleanup(self):
        """Restore original settings and clean up"""
        self.context.scene.camera = self.original_settings['camera']
        self.context.scene.render.engine = self.original_settings['engine']
        self.context.scene.cycles.samples = self.original_settings['samples']
        self.context.scene.view_settings.exposure = self.original_settings['exposure']
        self._restore_world_lighting(self.original_settings['world'])
        
        if self.cam_obj:
            bpy.data.objects.remove(self.cam_obj, do_unlink=True)
        if self.cam_data:
            bpy.data.cameras.remove(self.cam_data, do_unlink=True)
        
    def render_all_scenes(self, base_filepath):
        """Render all camera scenes"""
        for i, camera_settings in enumerate(self.context.scene.mesh_properties.cameras):
            # Setup render settings for this camera
            self.setup_render_settings(camera_settings)
            
            # Setup HDRI if path is set
            hdri_settings = self.context.scene.mesh_properties
            if hdri_settings.hdri_path:
                self.setup_hdri(hdri_settings)
            else:
                self.setup_transparent_world()
                
            # Setup camera
            self.setup_camera(camera_settings)
            
            # Set output path
            filename = f"{os.path.splitext(base_filepath)[0]}_{i+1}.png"
            self.context.scene.render.filepath = filename
            
            # Render
            bpy.ops.render.render(write_still=True)