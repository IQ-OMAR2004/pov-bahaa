#!/usr/bin/env python3
"""
POV Image Processor
===================
Convert images to .npy format for POV display.

Usage:
    python process_image.py <image_path> [output_name]
    
Examples:
    python process_image.py images/mylogo.png
    python process_image.py images/mylogo.png custom_name

The output will be saved to colors/douple_resolution/
"""

import numpy as np
from PIL import Image
import math
from pathlib import Path
import sys
import os

# Import configuration
try:
    from config import NUM_DIVISIONS, NUM_LEDS
except ImportError:
    NUM_DIVISIONS = 100
    NUM_LEDS = 72

def extract_colors_by_slices(image, radius, num_slices=NUM_DIVISIONS, num_leds=NUM_LEDS):
    """
    Extract colors from circular region of image, sampling along radial lines.
    
    Args:
        image: PIL Image in RGB mode
        radius: Radius of the circular region to sample
        num_slices: Number of angular divisions
        num_leds: Number of LEDs (samples per slice)
    
    Returns:
        2D list: [slice][led] = (R, G, B)
    """
    width, height = image.size
    center_x, center_y = width // 2, height // 2
    
    image_colors = []
    angle_increment = 360 / num_slices
    
    for slice_idx in range(num_slices):
        slice_colors = []
        angle_deg = slice_idx * angle_increment
        angle_rad = math.radians(angle_deg)
        
        for led_idx in range(num_leds):
            radial_distance = (led_idx + 1) * (radius / num_leds)
            
            x = int(center_x + radial_distance * math.cos(angle_rad))
            y = int(center_y + radial_distance * math.sin(angle_rad))
            
            if 0 <= x < width and 0 <= y < height:
                pixel_color = image.getpixel((x, y))
                # Ensure RGB format (handle RGBA)
                if len(pixel_color) == 4:
                    pixel_color = pixel_color[:3]
                slice_colors.append(pixel_color)
            else:
                slice_colors.append((0, 0, 0))
        
        image_colors.append(slice_colors)
    
    return image_colors


def process_image(image_path, output_name=None):
    """
    Process an image file and save as .npy for POV display.
    
    Args:
        image_path: Path to input image
        output_name: Optional custom output name (without extension)
    
    Returns:
        Path to saved .npy file
    """
    # Validate input
    if not os.path.exists(image_path):
        print(f"Error: Image not found: {image_path}")
        return None
    
    # Load image
    print(f"Loading: {image_path}")
    image = Image.open(image_path)
    
    # Get output name from input if not specified
    if output_name is None:
        path = Path(image_path)
        output_name = path.stem
    
    # Convert to RGB if needed
    if image.mode != 'RGB':
        print(f"Converting from {image.mode} to RGB...")
        image = image.convert('RGB')
    
    # Make square if not already
    width, height = image.size
    if width != height:
        size = min(width, height)
        left = (width - size) // 2
        top = (height - size) // 2
        image = image.crop((left, top, left + size, top + size))
        print(f"Cropped to square: {size}x{size}")
    
    # Calculate radius
    radius = min(image.size) // 2 - 1
    
    # Extract colors
    print(f"Extracting colors ({NUM_DIVISIONS} divisions, {NUM_LEDS} LEDs)...")
    image_colors = extract_colors_by_slices(image, radius)
    image_colors = np.array(image_colors)
    
    # Ensure output directory exists
    output_dir = "colors/douple_resolution"
    os.makedirs(output_dir, exist_ok=True)
    
    # Save
    output_path = f"{output_dir}/douple_res_{output_name}.npy"
    np.save(output_path, image_colors)
    
    print(f"✓ Saved: {output_path}")
    print(f"  Shape: {image_colors.shape}")
    
    return output_path


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        print("\nAvailable images in images/:")
        if os.path.exists("images"):
            for f in os.listdir("images"):
                if f.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp')):
                    print(f"  - {f}")
        return
    
    image_path = sys.argv[1]
    output_name = sys.argv[2] if len(sys.argv) > 2 else None
    
    process_image(image_path, output_name)


if __name__ == "__main__":
    main()

