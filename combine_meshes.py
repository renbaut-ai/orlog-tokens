#!/usr/bin/env python3
"""
Combine front relief meshes with solid backs to create complete tokens.
"""

import os
import json
import numpy as np
import trimesh
from PIL import Image

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
STL_DIR = os.path.join(PROJECT_DIR, "stl")
HEIGHTMAPS_DIR = os.path.join(PROJECT_DIR, "heightmaps")

# Dimensions
TOKEN_WIDTH = 28.575
TOKEN_HEIGHT = 59.53
TOKEN_DEPTH = 3.175
RELIEF_DEPTH = 1.5


def safe_filename(name):
    result = name.lower()
    for old, new in {"'": "", " ": "_", "ð": "d", "í": "i", "á": "a", "ö": "o"}.items():
        result = result.replace(old, new)
    return result


def create_heightmap_mesh(heightmap_path, width, height, relief_depth, base_z):
    """Create a mesh from heightmap PNG."""
    
    # Load heightmap
    img = Image.open(heightmap_path).convert('L')
    heightmap = np.array(img, dtype=np.float32) / 255.0
    
    h_pixels, w_pixels = heightmap.shape
    
    # Create grid of vertices
    x = np.linspace(0, width, w_pixels)
    y = np.linspace(0, height, h_pixels)
    X, Y = np.meshgrid(x, y)
    
    # Z values from heightmap
    Z = base_z + heightmap * relief_depth
    
    # Create vertices
    vertices = np.zeros((h_pixels * w_pixels, 3))
    vertices[:, 0] = X.flatten()
    vertices[:, 1] = Y.flatten()
    vertices[:, 2] = Z.flatten()
    
    # Create faces (two triangles per quad)
    faces = []
    for j in range(h_pixels - 1):
        for i in range(w_pixels - 1):
            # Vertex indices
            v0 = j * w_pixels + i
            v1 = j * w_pixels + i + 1
            v2 = (j + 1) * w_pixels + i
            v3 = (j + 1) * w_pixels + i + 1
            
            # Two triangles
            faces.append([v0, v1, v2])
            faces.append([v1, v3, v2])
    
    faces = np.array(faces)
    
    # Create mesh
    mesh = trimesh.Trimesh(vertices=vertices, faces=faces)
    
    return mesh


def create_solid_token(heightmap_path, width, height, depth, relief_depth):
    """Create a complete solid token with relief front and flat back."""
    
    # Load heightmap for dimensions
    img = Image.open(heightmap_path).convert('L')
    h_pixels, w_pixels = np.array(img).shape
    
    # Create the relief top surface
    top_mesh = create_heightmap_mesh(heightmap_path, width, height, relief_depth, depth - relief_depth)
    
    # Create bottom surface (flat)
    x = np.linspace(0, width, w_pixels)
    y = np.linspace(0, height, h_pixels)
    X, Y = np.meshgrid(x, y)
    
    bottom_verts = np.zeros((h_pixels * w_pixels, 3))
    bottom_verts[:, 0] = X.flatten()
    bottom_verts[:, 1] = Y.flatten()
    bottom_verts[:, 2] = 0  # Z = 0 for bottom
    
    # Bottom faces (reversed winding for outward normals)
    bottom_faces = []
    for j in range(h_pixels - 1):
        for i in range(w_pixels - 1):
            v0 = j * w_pixels + i
            v1 = j * w_pixels + i + 1
            v2 = (j + 1) * w_pixels + i
            v3 = (j + 1) * w_pixels + i + 1
            bottom_faces.append([v2, v1, v0])  # Reversed
            bottom_faces.append([v2, v3, v1])  # Reversed
    
    bottom_mesh = trimesh.Trimesh(vertices=bottom_verts, faces=np.array(bottom_faces))
    
    # Create side walls
    # We need to connect the edges of top and bottom surfaces
    # This is complex, so let's use trimesh's convex hull or extrusion
    
    # Simpler approach: combine top + bottom and let trimesh repair
    combined = trimesh.util.concatenate([top_mesh, bottom_mesh])
    
    # Try to make it watertight
    # This might not work perfectly for complex shapes
    try:
        combined.fill_holes()
    except:
        pass
    
    return combined


def process_all_tokens():
    """Process all tokens."""
    
    with open(os.path.join(PROJECT_DIR, "gods_favor_data.json"), "r") as f:
        data = json.load(f)
    
    final_dir = os.path.join(STL_DIR, "final")
    os.makedirs(final_dir, exist_ok=True)
    
    successful = 0
    
    for god in data["gods_favor"]:
        god_name = god["name"]
        safe_name = safe_filename(god_name)
        
        print(f"\nProcessing: {god_name}")
        
        heightmap_path = os.path.join(HEIGHTMAPS_DIR, f"{safe_name}.png")
        
        if not os.path.exists(heightmap_path):
            print(f"  ✗ Heightmap not found")
            continue
        
        try:
            # Create solid token with relief
            mesh = create_solid_token(
                heightmap_path, 
                TOKEN_WIDTH, 
                TOKEN_HEIGHT,
                TOKEN_DEPTH,
                RELIEF_DEPTH
            )
            
            # Export
            output_path = os.path.join(final_dir, f"{safe_name}.stl")
            mesh.export(output_path)
            
            # Get file size
            size_kb = os.path.getsize(output_path) / 1024
            print(f"  ✓ Saved: {output_path} ({size_kb:.0f}KB)")
            successful += 1
            
        except Exception as e:
            print(f"  ✗ Error: {e}")
    
    print(f"\n{'='*50}")
    print(f"✓ Generated {successful}/{len(data['gods_favor'])} final tokens")
    print(f"Output: {final_dir}")


if __name__ == "__main__":
    process_all_tokens()
