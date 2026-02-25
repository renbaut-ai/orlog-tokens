#!/usr/bin/env python3
"""
Generate OpenSCAD files for each God's Favor token,
then render to STL.
"""

import os
import json
import subprocess
from PIL import Image

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
HEIGHTMAPS_DIR = os.path.join(PROJECT_DIR, "heightmaps")
SCAD_DIR = os.path.join(PROJECT_DIR, "scad")
STL_DIR = os.path.join(PROJECT_DIR, "stl")

# Template for individual token SCAD files
SCAD_TEMPLATE = '''// {god_name} - God's Favor Token
// Auto-generated - do not edit directly

// Parameters
god_name = "{display_name}";
tier1 = "{tier1}";
tier2 = "{tier2}";
tier3 = "{tier3}";
heightmap_file = "{heightmap_file}";
heightmap_width = {width};
heightmap_height = {height};

// Include the template
include <token_template.scad>
'''


def get_heightmap_dimensions(filepath):
    """Get PNG dimensions."""
    with Image.open(filepath) as img:
        return img.size  # (width, height)


def safe_filename(name):
    """Convert god name to safe filename."""
    result = name.lower()
    replacements = {"'": "", " ": "_", "ð": "d", "í": "i", "á": "a", "ö": "o"}
    for old, new in replacements.items():
        result = result.replace(old, new)
    return result


def format_tier(tier_data, god_name):
    """Format tier for display on back of token."""
    cost = tier_data["cost"]
    effect = tier_data["effect"]
    
    # Shorten common phrases
    effect = effect.replace("Health", "HP")
    effect = effect.replace("damage", "dmg")
    effect = effect.replace("per ", "/")
    effect = effect.replace("Heal ", "+")
    effect = effect.replace("Deal ", "")
    effect = effect.replace("Reroll ", "Reroll ")
    effect = effect.replace("Gain ", "+")
    effect = effect.replace("Ban ", "Ban ")
    effect = effect.replace(" die", "")
    effect = effect.replace(" dice", "")
    effect = effect.replace("health", "HP")
    effect = effect.replace("level", "lvl")
    effect = effect.replace("levels", "lvls")
    effect = effect.replace("token", "tkn")
    effect = effect.replace("block", "blk")
    effect = effect.replace("ignore", "ign")
    effect = effect.replace("arrow", "arr")
    effect = effect.replace("helmet", "hlm")
    effect = effect.replace("per", "/")
    
    # Keep it short for small text
    if len(effect) > 15:
        effect = effect[:15]
    
    return f"{cost}: {effect}"


def generate_tokens():
    """Generate SCAD files and render to STL."""
    
    # Load god data
    with open(os.path.join(PROJECT_DIR, "gods_favor_data.json"), "r") as f:
        data = json.load(f)
    
    # Load image mapping
    with open(os.path.join(PROJECT_DIR, "image_mapping.json"), "r") as f:
        mapping = json.load(f)
    
    # Create reverse mapping: god_name -> image_file
    god_to_image = {v: k for k, v in mapping.items()}
    
    os.makedirs(STL_DIR, exist_ok=True)
    
    successful = 0
    
    for god in data["gods_favor"]:
        god_name = god["name"]
        safe_name = safe_filename(god_name)
        
        print(f"\n{'='*50}")
        print(f"Processing: {god_name}")
        
        # Get heightmap file and dimensions
        heightmap_file = os.path.join(HEIGHTMAPS_DIR, f"{safe_name}.png")
        if not os.path.exists(heightmap_file):
            print(f"  ⚠ Heightmap not found: {heightmap_file}")
            continue
        
        width, height = get_heightmap_dimensions(heightmap_file)
        
        # Format tiers
        tiers = god["tiers"]
        tier1 = format_tier(tiers[0], god_name) if len(tiers) > 0 else ""
        tier2 = format_tier(tiers[1], god_name) if len(tiers) > 1 else ""
        tier3 = format_tier(tiers[2], god_name) if len(tiers) > 2 else ""
        
        # Display name (shortened for engraving)
        display_name = god_name.split("'s")[0].upper()  # Just the god's name
        
        print(f"  Display: {display_name}")
        print(f"  Tiers: {tier1} | {tier2} | {tier3}")
        print(f"  Heightmap: {width}x{height}")
        
        # Generate SCAD file
        scad_content = SCAD_TEMPLATE.format(
            god_name=god_name,
            display_name=display_name,
            tier1=tier1,
            tier2=tier2,
            tier3=tier3,
            heightmap_file=f"../heightmaps/{safe_name}.png",
            width=width,
            height=height
        )
        
        scad_file = os.path.join(SCAD_DIR, f"{safe_name}.scad")
        with open(scad_file, "w") as f:
            f.write(scad_content)
        print(f"  Created: {scad_file}")
        
        # Render to STL
        stl_file = os.path.join(STL_DIR, f"{safe_name}.stl")
        print(f"  Rendering STL...")
        
        try:
            result = subprocess.run(
                ["openscad", "-o", stl_file, scad_file],
                capture_output=True,
                text=True,
                timeout=120
            )
            
            if result.returncode == 0:
                print(f"  ✓ Saved: {stl_file}")
                successful += 1
            else:
                print(f"  ✗ Error: {result.stderr[:200]}")
        except subprocess.TimeoutExpired:
            print(f"  ✗ Timeout rendering {god_name}")
        except Exception as e:
            print(f"  ✗ Exception: {e}")
    
    print(f"\n{'='*50}")
    print(f"✓ Generated {successful}/{len(data['gods_favor'])} tokens")


if __name__ == "__main__":
    generate_tokens()
