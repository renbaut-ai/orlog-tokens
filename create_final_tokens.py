#!/usr/bin/env python3
"""
Create watertight tokens with relief front, side walls, and flat back.
"""

import os
import json
import numpy as np
import trimesh
from PIL import Image
from stl import mesh as stl_mesh

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
STL_DIR = os.path.join(PROJECT_DIR, "stl")
HEIGHTMAPS_DIR = os.path.join(PROJECT_DIR, "heightmaps")

TOKEN_WIDTH = 28.575
TOKEN_HEIGHT = 59.53
TOKEN_DEPTH = 3.175
RELIEF_DEPTH = 1.5


def safe_filename(name):
    result = name.lower()
    for old, new in {"'": "", " ": "_", "ð": "d", "í": "i", "á": "a", "ö": "o"}.items():
        result = result.replace(old, new)
    return result


def create_watertight_token(heightmap_path, width, height, depth, relief_depth):
    """
    Create a watertight mesh with:
    - Top: Relief surface from heightmap
    - Bottom: Flat surface
    - Sides: Walls connecting top and bottom perimeters
    """
    
    # Load and process heightmap
    img = Image.open(heightmap_path).convert('L')
    heightmap = np.array(img, dtype=np.float32) / 255.0
    
    # Reduce resolution for manageable mesh size
    scale = 0.5  # Half resolution
    new_h = int(heightmap.shape[0] * scale)
    new_w = int(heightmap.shape[1] * scale)
    img_small = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
    heightmap = np.array(img_small, dtype=np.float32) / 255.0
    
    h_pixels, w_pixels = heightmap.shape
    base_z = depth - relief_depth
    
    # Create coordinate grids
    x = np.linspace(0, width, w_pixels)
    y = np.linspace(0, height, h_pixels)
    X, Y = np.meshgrid(x, y)
    
    # Top surface Z values (with relief)
    Z_top = base_z + heightmap * relief_depth
    
    # Bottom surface Z = 0
    Z_bottom = np.zeros_like(Z_top)
    
    all_vertices = []
    all_faces = []
    
    # ===== TOP SURFACE =====
    top_offset = 0
    for j in range(h_pixels):
        for i in range(w_pixels):
            all_vertices.append([X[j, i], Y[j, i], Z_top[j, i]])
    
    for j in range(h_pixels - 1):
        for i in range(w_pixels - 1):
            v0 = top_offset + j * w_pixels + i
            v1 = top_offset + j * w_pixels + i + 1
            v2 = top_offset + (j + 1) * w_pixels + i
            v3 = top_offset + (j + 1) * w_pixels + i + 1
            # Normal facing up
            all_faces.append([v0, v2, v1])
            all_faces.append([v1, v2, v3])
    
    # ===== BOTTOM SURFACE =====
    bottom_offset = len(all_vertices)
    for j in range(h_pixels):
        for i in range(w_pixels):
            all_vertices.append([X[j, i], Y[j, i], 0])
    
    for j in range(h_pixels - 1):
        for i in range(w_pixels - 1):
            v0 = bottom_offset + j * w_pixels + i
            v1 = bottom_offset + j * w_pixels + i + 1
            v2 = bottom_offset + (j + 1) * w_pixels + i
            v3 = bottom_offset + (j + 1) * w_pixels + i + 1
            # Normal facing down (reversed winding)
            all_faces.append([v0, v1, v2])
            all_faces.append([v1, v3, v2])
    
    # ===== SIDE WALLS =====
    # Connect perimeter of top to perimeter of bottom
    
    # Bottom edge (j=0)
    for i in range(w_pixels - 1):
        t0 = top_offset + i
        t1 = top_offset + i + 1
        b0 = bottom_offset + i
        b1 = bottom_offset + i + 1
        all_faces.append([t0, b0, t1])
        all_faces.append([t1, b0, b1])
    
    # Top edge (j=h_pixels-1)
    for i in range(w_pixels - 1):
        t0 = top_offset + (h_pixels - 1) * w_pixels + i
        t1 = top_offset + (h_pixels - 1) * w_pixels + i + 1
        b0 = bottom_offset + (h_pixels - 1) * w_pixels + i
        b1 = bottom_offset + (h_pixels - 1) * w_pixels + i + 1
        all_faces.append([t0, t1, b0])
        all_faces.append([t1, b1, b0])
    
    # Left edge (i=0)
    for j in range(h_pixels - 1):
        t0 = top_offset + j * w_pixels
        t1 = top_offset + (j + 1) * w_pixels
        b0 = bottom_offset + j * w_pixels
        b1 = bottom_offset + (j + 1) * w_pixels
        all_faces.append([t0, t1, b0])
        all_faces.append([t1, b1, b0])
    
    # Right edge (i=w_pixels-1)
    for j in range(h_pixels - 1):
        t0 = top_offset + j * w_pixels + (w_pixels - 1)
        t1 = top_offset + (j + 1) * w_pixels + (w_pixels - 1)
        b0 = bottom_offset + j * w_pixels + (w_pixels - 1)
        b1 = bottom_offset + (j + 1) * w_pixels + (w_pixels - 1)
        all_faces.append([t0, b0, t1])
        all_faces.append([t1, b0, b1])
    
    vertices = np.array(all_vertices)
    faces = np.array(all_faces)
    
    # Create trimesh
    mesh = trimesh.Trimesh(vertices=vertices, faces=faces)
    
    # Fix normals
    mesh.fix_normals()
    
    return mesh


def process_all():
    with open(os.path.join(PROJECT_DIR, "gods_favor_data.json"), "r") as f:
        data = json.load(f)
    
    final_dir = os.path.join(STL_DIR, "final")
    os.makedirs(final_dir, exist_ok=True)
    
    successful = 0
    watertight = 0
    
    for god in data["gods_favor"]:
        god_name = god["name"]
        safe_name = safe_filename(god_name)
        
        print(f"\nProcessing: {god_name}")
        
        heightmap_path = os.path.join(HEIGHTMAPS_DIR, f"{safe_name}.png")
        
        if not os.path.exists(heightmap_path):
            print(f"  ✗ Heightmap not found")
            continue
        
        try:
            mesh = create_watertight_token(
                heightmap_path,
                TOKEN_WIDTH,
                TOKEN_HEIGHT,
                TOKEN_DEPTH,
                RELIEF_DEPTH
            )
            
            output_path = os.path.join(final_dir, f"{safe_name}.stl")
            mesh.export(output_path)
            
            # Check watertight
            is_wt = "✓" if mesh.is_watertight else "✗"
            size_kb = os.path.getsize(output_path) / 1024
            
            print(f"  Watertight: {is_wt} | Size: {size_kb:.0f}KB")
            print(f"  Saved: {output_path}")
            
            successful += 1
            if mesh.is_watertight:
                watertight += 1
            
        except Exception as e:
            print(f"  ✗ Error: {e}")
    
    print(f"\n{'='*50}")
    print(f"Generated: {successful}/{len(data['gods_favor'])}")
    print(f"Watertight: {watertight}/{successful}")


if __name__ == "__main__":
    process_all()
