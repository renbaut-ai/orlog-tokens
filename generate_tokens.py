#!/usr/bin/env python3
"""
Orlog God's Favor Token Generator
Converts 2D relief images to 3D printable STL files.

Dimensions: 1.125" x 2.34375" x 0.125" (28.575mm x 59.53mm x 3.175mm)
"""

import os
import json
import numpy as np
from PIL import Image, ImageOps, ImageFilter
from stl import mesh
import cv2

# Dimensions in mm
WIDTH_MM = 28.575
HEIGHT_MM = 59.53125
DEPTH_MM = 3.175
RELIEF_DEPTH_MM = 1.5  # How deep the relief is carved
BACK_ENGRAVE_DEPTH_MM = 0.5  # Depth of back text engraving

# Resolution for mesh generation (higher = more detail but bigger files)
MESH_RESOLUTION = 200  # points along height

class TokenGenerator:
    def __init__(self, project_dir):
        self.project_dir = project_dir
        self.images_dir = os.path.join(project_dir, "images")
        self.stl_dir = os.path.join(project_dir, "stl")
        self.svg_dir = os.path.join(project_dir, "svg")
        
        # Load gods favor data
        with open(os.path.join(project_dir, "gods_favor_data.json"), "r") as f:
            self.data = json.load(f)
    
    def load_image(self, image_path):
        """Load and preprocess image for heightmap generation."""
        img = Image.open(image_path)
        
        # Convert to grayscale
        gray = img.convert('L')
        
        # Enhance contrast
        gray = ImageOps.autocontrast(gray)
        
        return gray
    
    def create_heightmap(self, image, target_width, target_height):
        """
        Convert grayscale image to heightmap array.
        Lighter pixels = higher relief.
        """
        # Resize to target resolution
        aspect = image.width / image.height
        target_aspect = target_width / target_height
        
        if aspect > target_aspect:
            # Image is wider, fit to width
            new_width = int(target_height * aspect)
            new_height = target_height
        else:
            # Image is taller, fit to height
            new_width = target_width
            new_height = int(target_width / aspect)
        
        resized = image.resize((new_width, new_height), Image.Resampling.LANCZOS)
        
        # Center crop to exact dimensions
        left = (new_width - target_width) // 2
        top = (new_height - target_height) // 2
        cropped = resized.crop((left, top, left + target_width, top + target_height))
        
        # Convert to numpy array and normalize to 0-1
        heightmap = np.array(cropped, dtype=np.float32) / 255.0
        
        return heightmap
    
    def create_tablet_mask(self, width, height):
        """
        Create a mask for the tablet shape (rounded top, angular corners).
        This defines the outline of the token.
        """
        mask = np.zeros((height, width), dtype=np.float32)
        
        # Main body rectangle
        border_pixels = int(width * 0.05)  # 5% border for the frame edge
        
        # Fill main area
        mask[border_pixels:height-border_pixels, border_pixels:width-border_pixels] = 1.0
        
        # Create rounded top
        center_x = width // 2
        top_radius = int(width * 0.45)
        for y in range(int(height * 0.2)):
            for x in range(width):
                dist = np.sqrt((x - center_x)**2 + (y - int(height * 0.15))**2)
                if dist < top_radius:
                    mask[y, x] = 1.0
        
        # Cut angular corners at bottom
        corner_size = int(width * 0.1)
        for y in range(height - corner_size, height):
            for x in range(corner_size):
                if x + (height - y) < corner_size:
                    mask[y, x] = 0.0
            for x in range(width - corner_size, width):
                if (width - x) + (height - y) < corner_size:
                    mask[y, x] = 0.0
        
        # Smooth the edges
        mask_img = Image.fromarray((mask * 255).astype(np.uint8))
        mask_img = mask_img.filter(ImageFilter.GaussianBlur(radius=2))
        mask = np.array(mask_img, dtype=np.float32) / 255.0
        
        return mask
    
    def detect_tablet_outline(self, image_path):
        """
        Use OpenCV to detect the actual tablet outline from the image.
        Returns a binary mask of the tablet shape.
        """
        # Load image
        img = cv2.imread(image_path)
        if img is None:
            return None
        
        # Convert to grayscale
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        # Threshold to find the token (it's lighter than black background)
        _, thresh = cv2.threshold(gray, 30, 255, cv2.THRESH_BINARY)
        
        # Find contours
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        if not contours:
            return None
        
        # Get largest contour (the token)
        largest = max(contours, key=cv2.contourArea)
        
        # Create mask
        mask = np.zeros_like(gray)
        cv2.drawContours(mask, [largest], -1, 255, -1)
        
        return mask
    
    def heightmap_to_mesh(self, heightmap, mask, width_mm, height_mm, base_depth_mm, relief_depth_mm):
        """
        Convert heightmap to 3D mesh.
        """
        h, w = heightmap.shape
        
        # Create coordinate grids
        x = np.linspace(0, width_mm, w)
        y = np.linspace(0, height_mm, h)
        X, Y = np.meshgrid(x, y)
        
        # Apply mask and calculate Z
        masked_height = heightmap * mask
        Z = base_depth_mm + (masked_height * relief_depth_mm)
        
        # Create vertices
        vertices = []
        faces = []
        
        # Top surface
        for j in range(h):
            for i in range(w):
                if mask[j, i] > 0.1:
                    vertices.append([X[j, i], Y[j, i], Z[j, i]])
        
        # This is simplified - for a proper mesh we need triangulation
        # Using trimesh would be better for complex shapes
        
        print(f"  Generated {len(vertices)} vertices")
        return vertices, faces
    
    def generate_simple_stl(self, heightmap, mask, output_path, god_name):
        """
        Generate a simple extruded STL from heightmap.
        Uses numpy-stl for mesh creation.
        """
        h, w = heightmap.shape
        
        # Scale to physical dimensions
        scale_x = WIDTH_MM / w
        scale_y = HEIGHT_MM / h
        
        # Apply mask
        masked_height = heightmap * mask
        
        # Create triangular mesh
        # Each pixel becomes two triangles
        num_faces = 0
        faces_list = []
        
        for j in range(h - 1):
            for i in range(w - 1):
                # Only create faces where mask is valid
                if mask[j, i] > 0.5 and mask[j+1, i] > 0.5 and mask[j, i+1] > 0.5:
                    # Calculate Z values (base + relief)
                    z00 = DEPTH_MM - RELIEF_DEPTH_MM + (masked_height[j, i] * RELIEF_DEPTH_MM)
                    z01 = DEPTH_MM - RELIEF_DEPTH_MM + (masked_height[j, i+1] * RELIEF_DEPTH_MM)
                    z10 = DEPTH_MM - RELIEF_DEPTH_MM + (masked_height[j+1, i] * RELIEF_DEPTH_MM)
                    z11 = DEPTH_MM - RELIEF_DEPTH_MM + (masked_height[j+1, i+1] * RELIEF_DEPTH_MM)
                    
                    # Triangle 1
                    v0 = [i * scale_x, j * scale_y, z00]
                    v1 = [(i+1) * scale_x, j * scale_y, z01]
                    v2 = [i * scale_x, (j+1) * scale_y, z10]
                    faces_list.append([v0, v1, v2])
                    
                    # Triangle 2
                    if mask[j+1, i+1] > 0.5:
                        v0 = [(i+1) * scale_x, j * scale_y, z01]
                        v1 = [(i+1) * scale_x, (j+1) * scale_y, z11]
                        v2 = [i * scale_x, (j+1) * scale_y, z10]
                        faces_list.append([v0, v1, v2])
        
        if not faces_list:
            print(f"  Warning: No faces generated for {god_name}")
            return False
        
        # Create the mesh
        token_mesh = mesh.Mesh(np.zeros(len(faces_list), dtype=mesh.Mesh.dtype))
        for i, face in enumerate(faces_list):
            token_mesh.vectors[i] = np.array(face)
        
        # Save
        token_mesh.save(output_path)
        print(f"  Saved: {output_path} ({len(faces_list)} faces)")
        return True
    
    def process_image(self, image_filename, god_name, god_data):
        """Process a single god's favor image."""
        print(f"\nProcessing: {god_name}")
        
        image_path = os.path.join(self.images_dir, image_filename)
        if not os.path.exists(image_path):
            print(f"  Image not found: {image_path}")
            return False
        
        # Load and create heightmap
        img = self.load_image(image_path)
        
        # Calculate resolution based on aspect ratio
        aspect = HEIGHT_MM / WIDTH_MM
        res_x = MESH_RESOLUTION
        res_y = int(MESH_RESOLUTION * aspect)
        
        heightmap = self.create_heightmap(img, res_x, res_y)
        print(f"  Heightmap: {heightmap.shape}")
        
        # Detect tablet outline from image
        detected_mask = self.detect_tablet_outline(image_path)
        if detected_mask is not None:
            # Resize detected mask to match heightmap
            mask_img = Image.fromarray(detected_mask)
            mask_img = mask_img.resize((res_x, res_y), Image.Resampling.LANCZOS)
            mask = np.array(mask_img, dtype=np.float32) / 255.0
            print(f"  Using detected tablet outline")
        else:
            # Fall back to generated mask
            mask = self.create_tablet_mask(res_x, res_y)
            print(f"  Using generated tablet mask")
        
        # Generate STL
        safe_name = god_name.lower().replace("'", "").replace(" ", "_").replace("ð", "d").replace("í", "i").replace("á", "a")
        output_path = os.path.join(self.stl_dir, f"{safe_name}_front.stl")
        
        return self.generate_simple_stl(heightmap, mask, output_path, god_name)
    
    def run(self, image_mapping):
        """
        Process all gods favor tokens.
        image_mapping: dict of {filename: god_name}
        """
        os.makedirs(self.stl_dir, exist_ok=True)
        
        successful = 0
        for filename, god_name in image_mapping.items():
            # Find god data
            god_data = None
            for god in self.data["gods_favor"]:
                if god["name"] == god_name:
                    god_data = god
                    break
            
            if self.process_image(filename, god_name, god_data):
                successful += 1
        
        print(f"\n✓ Generated {successful}/{len(image_mapping)} token meshes")
        return successful


def main():
    project_dir = os.path.dirname(os.path.abspath(__file__))
    generator = TokenGenerator(project_dir)
    
    # Load verified image mapping from JSON
    mapping_file = os.path.join(project_dir, "image_mapping.json")
    with open(mapping_file, "r") as f:
        image_mapping = json.load(f)
    
    print(f"Loaded {len(image_mapping)} image mappings")
    generator.run(image_mapping)


if __name__ == "__main__":
    main()
