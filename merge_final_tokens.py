#!/usr/bin/env python3
"""
Merge relief front tokens with engraved backs.
Creates complete tokens with:
- Front: Relief from game images
- Back: Engraved god name + ability tiers + token symbol
"""

import os
import json
import numpy as np
import trimesh
from PIL import Image, ImageDraw, ImageFont

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
STL_DIR = os.path.join(PROJECT_DIR, "stl")
HEIGHTMAPS_DIR = os.path.join(PROJECT_DIR, "heightmaps")

TOKEN_WIDTH = 28.575
TOKEN_HEIGHT = 59.53
TOKEN_DEPTH = 3.175
RELIEF_DEPTH = 1.5
ENGRAVE_DEPTH = 0.5


def safe_filename(name):
    result = name.lower()
    for old, new in {"'": "", " ": "_", "ð": "d", "í": "i", "á": "a", "ö": "o"}.items():
        result = result.replace(old, new)
    return result


def format_tier(tier_data):
    """Format tier for back engraving."""
    cost = tier_data["cost"]
    effect = tier_data["effect"]
    # Shorten
    effect = effect.replace("Health", "HP").replace("damage", "dmg")
    effect = effect.replace("per ", "/").replace("Heal ", "+")
    effect = effect.replace("Deal ", "").replace("Gain ", "+")
    effect = effect.replace("Reroll ", "Re").replace("Ban ", "Ban ")
    effect = effect.replace(" dice", "").replace(" die", "")
    effect = effect.replace("level", "lvl").replace("levels", "lvls")
    effect = effect.replace("health", "HP").replace("token", "tkn")
    if len(effect) > 14:
        effect = effect[:14]
    return f"{cost}: {effect}"


def create_text_heightmap(god_name, tiers, width_px=200, height_px=400):
    """Create a heightmap image with text for boolean subtraction."""
    
    # Create image (white background = no cut, black = cut deep)
    img = Image.new('L', (width_px, height_px), 255)
    draw = ImageDraw.Draw(img)
    
    # Try to use a system font
    try:
        font_large = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 24)
        font_small = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 14)
    except:
        font_large = ImageFont.load_default()
        font_small = ImageFont.load_default()
    
    # God name at top
    display_name = god_name.split("'s")[0].upper()
    bbox = draw.textbbox((0, 0), display_name, font=font_large)
    text_width = bbox[2] - bbox[0]
    x = (width_px - text_width) // 2
    draw.text((x, 30), display_name, fill=0, font=font_large)
    
    # Token symbol (simple cross pattern)
    cx, cy = width_px // 2, height_px // 2 - 20
    size = 25
    # Draw a simplified Bowen knot
    for i in range(4):
        angle = i * 90
        rad = np.radians(angle)
        dx, dy = int(size * 0.4 * np.cos(rad)), int(size * 0.4 * np.sin(rad))
        draw.ellipse([cx + dx - 8, cy + dy - 8, cx + dx + 8, cy + dy + 8], fill=0)
    draw.ellipse([cx - 6, cy - 6, cx + 6, cy + 6], fill=0)
    
    # Tier texts
    tier_texts = [format_tier(t) for t in tiers]
    y_positions = [height_px // 2 + 30, height_px // 2 + 55, height_px // 2 + 80]
    
    for text, y in zip(tier_texts, y_positions):
        bbox = draw.textbbox((0, 0), text, font=font_small)
        text_width = bbox[2] - bbox[0]
        x = (width_px - text_width) // 2
        draw.text((x, y), text, fill=0, font=font_small)
    
    return img


def create_back_engrave_mesh(text_heightmap, width, height, depth):
    """Create a mesh for the back engraving from text heightmap."""
    
    arr = np.array(text_heightmap, dtype=np.float32)
    # Invert: black text becomes the engraving
    arr = 255 - arr
    arr = arr / 255.0 * depth  # Scale to engrave depth
    
    h_px, w_px = arr.shape
    
    # Create vertices
    x = np.linspace(0, width, w_px)
    y = np.linspace(0, height, h_px)
    X, Y = np.meshgrid(x, y)
    
    vertices = []
    faces = []
    
    # Create surface
    for j in range(h_px):
        for i in range(w_px):
            z = -arr[h_px - 1 - j, i]  # Flip Y, negative Z for bottom
            vertices.append([X[j, i], Y[j, i], z])
    
    for j in range(h_px - 1):
        for i in range(w_px - 1):
            v0 = j * w_px + i
            v1 = j * w_px + i + 1
            v2 = (j + 1) * w_px + i
            v3 = (j + 1) * w_px + i + 1
            faces.append([v0, v1, v2])
            faces.append([v1, v3, v2])
    
    return np.array(vertices), np.array(faces)


def create_complete_token(heightmap_path, god_name, tiers):
    """Create a complete token with relief front and engraved back."""
    
    # Load front heightmap
    img = Image.open(heightmap_path).convert('L')
    front_arr = np.array(img, dtype=np.float32) / 255.0
    
    # Reduce resolution
    scale = 0.5
    new_h = int(front_arr.shape[0] * scale)
    new_w = int(front_arr.shape[1] * scale)
    img_small = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
    front_arr = np.array(img_small, dtype=np.float32) / 255.0
    
    h_pixels, w_pixels = front_arr.shape
    
    # Create back text heightmap at same resolution
    text_img = create_text_heightmap(god_name, tiers, w_pixels, h_pixels)
    back_arr = np.array(text_img, dtype=np.float32)
    back_arr = (255 - back_arr) / 255.0 * ENGRAVE_DEPTH  # Invert and scale
    
    # Create coordinate grids
    x = np.linspace(0, TOKEN_WIDTH, w_pixels)
    y = np.linspace(0, TOKEN_HEIGHT, h_pixels)
    X, Y = np.meshgrid(x, y)
    
    # Z values
    base_z = TOKEN_DEPTH - RELIEF_DEPTH
    Z_top = base_z + front_arr * RELIEF_DEPTH
    Z_bottom = -back_arr  # Engravings go below z=0, then we'll shift up
    
    # Shift everything so minimum Z is 0
    min_z = Z_bottom.min()
    Z_top = Z_top - min_z
    Z_bottom = Z_bottom - min_z
    
    all_vertices = []
    all_faces = []
    
    # TOP SURFACE
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
            all_faces.append([v0, v2, v1])
            all_faces.append([v1, v2, v3])
    
    # BOTTOM SURFACE (with engravings)
    bottom_offset = len(all_vertices)
    for j in range(h_pixels):
        for i in range(w_pixels):
            # Flip the back heightmap
            all_vertices.append([X[j, i], Y[h_pixels - 1 - j, i], Z_bottom[j, i]])
    
    for j in range(h_pixels - 1):
        for i in range(w_pixels - 1):
            v0 = bottom_offset + j * w_pixels + i
            v1 = bottom_offset + j * w_pixels + i + 1
            v2 = bottom_offset + (j + 1) * w_pixels + i
            v3 = bottom_offset + (j + 1) * w_pixels + i + 1
            all_faces.append([v0, v1, v2])
            all_faces.append([v1, v3, v2])
    
    # SIDE WALLS
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
    
    mesh = trimesh.Trimesh(vertices=vertices, faces=faces)
    mesh.fix_normals()
    
    return mesh


def main():
    with open(os.path.join(PROJECT_DIR, "gods_favor_data.json"), "r") as f:
        data = json.load(f)
    
    complete_dir = os.path.join(STL_DIR, "complete")
    os.makedirs(complete_dir, exist_ok=True)
    
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
            mesh = create_complete_token(heightmap_path, god_name, god["tiers"])
            
            output_path = os.path.join(complete_dir, f"{safe_name}.stl")
            mesh.export(output_path)
            
            is_wt = "✓" if mesh.is_watertight else "✗"
            size_kb = os.path.getsize(output_path) / 1024
            
            print(f"  Watertight: {is_wt} | Size: {size_kb:.0f}KB")
            print(f"  Saved: {output_path}")
            
            successful += 1
            if mesh.is_watertight:
                watertight += 1
            
        except Exception as e:
            import traceback
            print(f"  ✗ Error: {e}")
            traceback.print_exc()
    
    print(f"\n{'='*50}")
    print(f"Generated: {successful}/{len(data['gods_favor'])}")
    print(f"Watertight: {watertight}/{successful}")
    print(f"Output: {complete_dir}")


if __name__ == "__main__":
    main()
