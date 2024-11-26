class IconProcessor:
    def __init__(self, target_size=(200, 200)):
        self.target_width, self.target_height = target_size
        
    def process_icon(self, image_path):
        """Convert render to icon using Blender's built-in image processing"""
        try:
            source_image = self._load_image(image_path)
            if not source_image:
                return False
                
            pixel_array = self._create_alpha_map(source_image)
            result_image = self._create_silhouette(
                pixel_array, 
                source_image.size[0],
                source_image.size[1]
            )
            
            self._save_and_cleanup(image_path, source_image, result_image)
            return True
            
        except Exception as e:
            print(f"Error in post-processing: {str(e)}")
            return False
            
    def _load_image(self, image_path):
        """Load image from path"""
        img = bpy.data.images.load(image_path, check_existing=True)
        if img is None:
            print("Failed to load source image")
            return None
        return img
        
    def _create_alpha_map(self, image):
        """Convert image pixels to 2D alpha map"""
        pixels = list(image.pixels[:])
        width = image.size[0]
        height = image.size[1]
        
        pixel_array = []
        for y in range(height):
            row = []
            for x in range(width):
                idx = (y * width + x) * 4
                alpha = pixels[idx + 3] > 0.5  # Use alpha threshold
                row.append(alpha)
            pixel_array.append(row)
            
        return pixel_array
        
    def _create_silhouette(self, pixel_array, source_width, source_height):
        """Create white silhouette image from alpha map"""
        result = bpy.data.images.new(
            name="processed_icon",
            width=self.target_width,
            height=self.target_height,
            alpha=True
        )
        
        scale_x = source_width / self.target_width
        scale_y = source_height / self.target_height
        
        new_pixels = []
        for y in range(self.target_height):
            for x in range(self.target_width):
                orig_x = int(x * scale_x)
                orig_y = int(y * scale_y)
                is_model = pixel_array[orig_y][orig_x]
                
                if is_model:
                    # Inside model - pure white
                    new_pixels.extend([1.0, 1.0, 1.0, 1.0])
                else:
                    # Transparent
                    new_pixels.extend([0.0, 0.0, 0.0, 0.0])
                    
        result.pixels = new_pixels
        return result
        
    def _save_and_cleanup(self, image_path, source_image, result_image):
        """Save processed image and cleanup"""
        result_image.save_render(image_path)
        bpy.data.images.remove(source_image)
        bpy.data.images.remove(result_image)