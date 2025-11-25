#!/usr/bin/env python3
"""
POV GIF/Animation Processor
===========================
Convert GIF files or image sequences to .npy format for POV display.

Usage:
    python process_gif.py <gif_file_or_folder> [output_name]
    
Examples:
    python process_gif.py gifs/animation.gif
    python process_gif.py gif_sequences/myfolder custom_name

The output will be saved to gif_colors/<name>/
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
    Extract colors from circular region of image.
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
                if len(pixel_color) == 4:
                    pixel_color = pixel_color[:3]
                slice_colors.append(pixel_color)
            else:
                slice_colors.append((0, 0, 0))
        
        image_colors.append(slice_colors)
    
    return image_colors


def extract_gif_frames(gif_path, output_folder):
    """
    Extract frames from GIF file and save as PNG images.
    
    Args:
        gif_path: Path to GIF file
        output_folder: Folder to save frames
    
    Returns:
        List of saved frame paths
    """
    os.makedirs(output_folder, exist_ok=True)
    
    gif = Image.open(gif_path)
    frames = []
    frame_num = 0
    
    try:
        while True:
            frame = gif.copy()
            if frame.mode != 'RGB':
                frame = frame.convert('RGB')
            
            frame_path = os.path.join(output_folder, f"frame_{frame_num}.png")
            frame.save(frame_path)
            frames.append(frame_path)
            
            frame_num += 1
            gif.seek(frame_num)
    except EOFError:
        pass
    
    print(f"Extracted {len(frames)} frames from GIF")
    return frames


def process_gif(input_path, output_name=None):
    """
    Process a GIF file or image sequence folder.
    
    Args:
        input_path: Path to GIF file or folder of images
        output_name: Optional custom output name
    
    Returns:
        Path to output folder
    """
    if not os.path.exists(input_path):
        print(f"Error: Not found: {input_path}")
        return None
    
    # Determine if input is GIF or folder
    is_gif = input_path.lower().endswith('.gif')
    
    if output_name is None:
        output_name = Path(input_path).stem
    
    # Setup output folder
    output_folder = f"gif_colors/{output_name}"
    os.makedirs(output_folder, exist_ok=True)
    
    # Get list of frames
    if is_gif:
        print(f"Processing GIF: {input_path}")
        
        # Create temp folder for extracted frames
        temp_folder = f"gif_sequences/{output_name}"
        frame_paths = extract_gif_frames(input_path, temp_folder)
    else:
        print(f"Processing image sequence: {input_path}")
        
        # Get all image files from folder
        supported_ext = ('.png', '.jpg', '.jpeg', '.bmp')
        frame_paths = sorted([
            os.path.join(input_path, f) 
            for f in os.listdir(input_path) 
            if f.lower().endswith(supported_ext)
        ])
    
    if not frame_paths:
        print("Error: No frames found!")
        return None
    
    print(f"Processing {len(frame_paths)} frames...")
    
    # Process each frame
    for i, frame_path in enumerate(frame_paths):
        image = Image.open(frame_path)
        
        if image.mode != 'RGB':
            image = image.convert('RGB')
        
        # Make square
        width, height = image.size
        if width != height:
            size = min(width, height)
            left = (width - size) // 2
            top = (height - size) // 2
            image = image.crop((left, top, left + size, top + size))
        
        radius = min(image.size) // 2 - 1
        
        # Extract colors
        image_colors = extract_colors_by_slices(image, radius)
        image_colors = np.array(image_colors)
        
        # Save frame
        frame_name = Path(frame_path).stem
        output_path = f"{output_folder}/{frame_name}.npy"
        np.save(output_path, image_colors)
        
        # Progress indicator
        if (i + 1) % 5 == 0 or i == len(frame_paths) - 1:
            print(f"  Processed {i + 1}/{len(frame_paths)} frames")
    
    print(f"✓ Saved to: {output_folder}/")
    return output_folder


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        
        print("\nAvailable GIFs in gifs/:")
        if os.path.exists("gifs"):
            for f in os.listdir("gifs"):
                if f.lower().endswith('.gif'):
                    print(f"  - {f}")
        
        print("\nAvailable sequences in gif_sequences/:")
        if os.path.exists("gif_sequences"):
            for d in os.listdir("gif_sequences"):
                if os.path.isdir(os.path.join("gif_sequences", d)):
                    print(f"  - {d}/")
        return
    
    input_path = sys.argv[1]
    output_name = sys.argv[2] if len(sys.argv) > 2 else None
    
    process_gif(input_path, output_name)


if __name__ == "__main__":
    main()

