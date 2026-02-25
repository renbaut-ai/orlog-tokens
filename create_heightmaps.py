#!/usr/bin/env python3
"""
Convert token images to grayscale heightmaps for OpenSCAD.
OpenSCAD surface() expects: white = high, black = low
"""

import os
import json
import cv2
import numpy as np
from PIL import Image, ImageOps, ImageFilter

def create_heightmap(image_path, output_path, target_width=200):
    """Convert image to grayscale heightmap PNG."""
    
    # Load with OpenCV for better edge detection
    img = cv2.imread(image_path)
    if img is None:
        print(f"  Error: Could not load {image_path}")
        return False
    
    # Convert to grayscale
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    
    # Detect the tablet outline (it's lighter than black background)
    _, mask = cv2.threshold(gray, 25, 255, cv2.THRESH_BINARY)
    
    # Find contours to get bounding box
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        print(f"  Error: No contours found")
        return False
    
    # Get largest contour (the token)
    largest = max(contours, key=cv2.contourArea)
    x, y, w, h = cv2.boundingRect(largest)
    
    # Crop to bounding box with small padding
    pad = 5
    x1 = max(0, x - pad)
    y1 = max(0, y - pad)
    x2 = min(img.shape[1], x + w + pad)
    y2 = min(img.shape[0], y + h + pad)
    
    cropped = gray[y1:y2, x1:x2]
    cropped_mask = mask[y1:y2, x1:x2]
    
    # Enhance contrast on the relief details
    # Apply CLAHE (Contrast Limited Adaptive Histogram Equalization)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(cropped)
    
    # Apply mask - set background to black
    enhanced = cv2.bitwise_and(enhanced, enhanced, mask=cropped_mask)
    
    # Resize maintaining aspect ratio
    aspect = cropped.shape[0] / cropped.shape[1]  # height/width
    target_height = int(target_width * aspect)
    resized = cv2.resize(enhanced, (target_width, target_height), interpolation=cv2.INTER_LANCZOS4)
    
    # Slight blur to smooth noise
    smoothed = cv2.GaussianBlur(resized, (3, 3), 0)
    
    # Save as PNG
    cv2.imwrite(output_path, smoothed)
    print(f"  Saved: {output_path} ({target_width}x{target_height})")
    return True


def main():
    project_dir = os.path.dirname(os.path.abspath(__file__))
    images_dir = os.path.join(project_dir, "images")
    heightmaps_dir = os.path.join(project_dir, "heightmaps")
    
    # Load mapping
    with open(os.path.join(project_dir, "image_mapping.json"), "r") as f:
        mapping = json.load(f)
    
    os.makedirs(heightmaps_dir, exist_ok=True)
    
    successful = 0
    for filename, god_name in mapping.items():
        print(f"\nProcessing: {god_name}")
        
        image_path = os.path.join(images_dir, filename)
        
        # Create safe filename
        safe_name = god_name.lower()
        for char in ["'", " ", "ð", "í", "á", "ö"]:
            safe_name = safe_name.replace(char, {"'": "", " ": "_", "ð": "d", "í": "i", "á": "a", "ö": "o"}.get(char, ""))
        
        output_path = os.path.join(heightmaps_dir, f"{safe_name}.png")
        
        if create_heightmap(image_path, output_path):
            successful += 1
    
    print(f"\n✓ Created {successful}/{len(mapping)} heightmaps")


if __name__ == "__main__":
    main()
