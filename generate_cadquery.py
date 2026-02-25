#!/usr/bin/env python3
"""
Generate Orlog tokens using CadQuery (native Python CAD).
Creates solid tokens with front relief and back engravings.
"""

import os
import json
import numpy as np
from PIL import Image
import cadquery as cq

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
HEIGHTMAPS_DIR = os.path.join(PROJECT_DIR, "heightmaps")
STL_DIR = os.path.join(PROJECT_DIR, "stl")

# Dimensions in mm
TOKEN_WIDTH = 28.575      # 1.125"
TOKEN_HEIGHT = 59.53      # 2.34375"
TOKEN_DEPTH = 3.175       # 0.125"
RELIEF_DEPTH = 1.2        # Front relief height
ENGRAVE_DEPTH = 0.5       # Back text depth


def safe_filename(name):
    """Convert god name to safe filename."""
    result = name.lower()
    replacements = {"'": "", " ": "_", "ð": "d", "í": "i", "á": "a", "ö": "o"}
    for old, new in replacements.items():
        result = result.replace(old, new)
    return result


def format_tier(tier_data):
    """Format tier for display."""
    cost = tier_data["cost"]
    effect = tier_data["effect"]
    # Shorten
    effect = effect.replace("Health", "HP").replace("damage", "dmg")
    effect = effect.replace("per ", "/").replace("Heal ", "+")
    if len(effect) > 12:
        effect = effect[:12]
    return f"{cost}: {effect}"


def create_tablet_base():
    """Create the basic tablet shape (rounded top, chamfered bottom)."""
    w = TOKEN_WIDTH
    h = TOKEN_HEIGHT
    d = TOKEN_DEPTH
    chamfer = 2.5  # Bottom corner chamfer
    
    # Create base rectangle
    base = (cq.Workplane("XY")
        .rect(w, h)
        .extrude(d)
    )
    
    # Round the top edge
    top_radius = w / 2.5
    base = base.edges("|Z and >Y").fillet(top_radius * 0.8)
    
    # Chamfer bottom corners
    base = base.edges("|Z and <Y").chamfer(chamfer * 0.5)
    
    return base


def load_heightmap(filepath):
    """Load heightmap and return as normalized numpy array."""
    img = Image.open(filepath).convert('L')
    arr = np.array(img, dtype=np.float32) / 255.0
    return arr


def create_relief_surface(heightmap, width, height, relief_depth):
    """
    Create a relief surface from heightmap.
    This is a simplified approach using lofted profiles.
    """
    h_pixels, w_pixels = heightmap.shape
    
    # Scale factors
    scale_x = width / w_pixels
    scale_y = height / h_pixels
    
    # Sample the heightmap at intervals to create profiles
    # CadQuery can't directly import heightmaps, so we approximate
    # with a series of cross-sections
    
    num_profiles = 20  # Number of Y slices
    points_per_profile = 30  # Points per slice
    
    profiles = []
    for j in range(num_profiles):
        y_idx = int(j * h_pixels / num_profiles)
        y_pos = (j / num_profiles - 0.5) * height
        
        points = []
        for i in range(points_per_profile):
            x_idx = int(i * w_pixels / points_per_profile)
            x_pos = (i / points_per_profile - 0.5) * width
            z_val = heightmap[y_idx, x_idx] * relief_depth
            points.append((x_pos, y_pos, z_val))
        
        profiles.append(points)
    
    return profiles


def create_back_text(god_name, tiers):
    """Create engraved text for the back."""
    display_name = god_name.split("'s")[0].upper()
    
    tier_texts = [format_tier(t) for t in tiers]
    
    # Create text objects using CadQuery
    text_objects = []
    
    # God name at top
    try:
        name_text = (cq.Workplane("XY")
            .text(display_name, fontsize=4, distance=ENGRAVE_DEPTH, 
                  cut=False, halign='center', valign='center')
            .translate((0, TOKEN_HEIGHT/2 - 10, 0))
        )
        text_objects.append(name_text)
    except Exception as e:
        print(f"    Warning: Could not create name text: {e}")
    
    # Tier texts
    y_positions = [5, -2, -9]
    for i, (tier_text, y_pos) in enumerate(zip(tier_texts, y_positions)):
        try:
            t = (cq.Workplane("XY")
                .text(tier_text, fontsize=2.5, distance=ENGRAVE_DEPTH,
                      cut=False, halign='center', valign='center')
                .translate((0, y_pos, 0))
            )
            text_objects.append(t)
        except Exception as e:
            print(f"    Warning: Could not create tier {i+1} text: {e}")
    
    return text_objects


def create_simple_token(god_name, tiers, heightmap_path):
    """
    Create a simplified token without heightmap relief.
    Just the base shape with back engravings.
    """
    # Create base tablet
    token = create_tablet_base()
    
    # For now, skip the front relief (heightmap import is complex in CadQuery)
    # We can add it later or use a different approach
    
    # Create back engravings
    display_name = god_name.split("'s")[0].upper()
    tier_texts = [format_tier(t) for t in tiers]
    
    # CadQuery text engraving
    try:
        # Engrave god name on back (Z=0 face)
        token = (token
            .faces("<Z")
            .workplane()
            .text(display_name, fontsize=4, distance=-ENGRAVE_DEPTH,
                  cut=True, halign='center', valign='center')
            .translate((0, TOKEN_HEIGHT/4, 0))
        )
    except Exception as e:
        print(f"    Note: Text engraving not supported: {e}")
    
    return token


def generate_tokens():
    """Generate all tokens."""
    
    # Load data
    with open(os.path.join(PROJECT_DIR, "gods_favor_data.json"), "r") as f:
        data = json.load(f)
    
    os.makedirs(STL_DIR, exist_ok=True)
    
    successful = 0
    
    for god in data["gods_favor"]:
        god_name = god["name"]
        safe_name = safe_filename(god_name)
        
        print(f"\nProcessing: {god_name}")
        
        heightmap_path = os.path.join(HEIGHTMAPS_DIR, f"{safe_name}.png")
        
        try:
            # Create token
            token = create_simple_token(god_name, god["tiers"], heightmap_path)
            
            # Export to STL
            stl_path = os.path.join(STL_DIR, f"{safe_name}_solid.stl")
            cq.exporters.export(token, stl_path)
            
            print(f"  ✓ Saved: {stl_path}")
            successful += 1
            
        except Exception as e:
            print(f"  ✗ Error: {e}")
    
    print(f"\n{'='*50}")
    print(f"✓ Generated {successful}/{len(data['gods_favor'])} solid tokens")


if __name__ == "__main__":
    generate_tokens()
