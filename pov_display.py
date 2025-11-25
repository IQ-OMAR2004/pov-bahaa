#!/usr/bin/env python3
"""
POV Holographic Fan Display - Combined & Optimized
===================================================
Combines functionality from POV-new (image/GIF loading) with 
Pov-fan hardware configuration (pins, buttons, timing).

Features:
- Load pre-processed .npy images (static images)
- GIF/animation sequence playback
- Shape generation (circle, square)
- Button controls for mode switching
- Robust RPM filtering and noise rejection
- Optimized timing for stable display

Hardware:
- WS2815 LED Strip (72 LEDs) on GPIO 18
- Hall Sensor (A3144) on GPIO 4
- Button 1 (Circle) on GPIO 17
- Button 2 (Square) on GPIO 27  
- Button 3 (Image/Next) on GPIO 22

Author: Combined from POV-new and Pov-fan projects
"""

import time
import os
import math
import threading
from rpi_ws281x import PixelStrip, Color
import numpy as np
import RPi.GPIO as GPIO

# ============== LOAD CONFIGURATION ==============
# Try to import from config.py, fall back to defaults if not found
try:
    from config import (
        NUM_LEDS, LED_PIN, LED_FREQ_HZ, LED_DMA, LED_BRIGHTNESS,
        LED_INVERT, LED_CHANNEL, LED_IS_GRB,
        HALL_SENSOR_PIN, BUTTON_CIRCLE, BUTTON_SQUARE, BUTTON_IMAGE,
        NUM_DIVISIONS, BRIGHTNESS_RATIO, LINES_TO_SHIFT,
        LED_UPDATE_TIME_US, DEFAULT_RPM, MIN_RPM, MAX_RPM, TIMING_MARGIN_US,
        HALL_DEBOUNCE_US, MAX_RPM_CHANGE_PERCENT, RPM_HISTORY_SIZE,
        STATIC_IMAGES_PATH, GIF_COLORS_PATH, ROT_PER_FRAME,
        BUTTON_DEBOUNCE_TIME
    )
    print("✓ Loaded configuration from config.py")
except ImportError:
    print("⚠ config.py not found, using default values")
    # ============== DEFAULT CONFIGURATION ==============
    NUM_LEDS = 72
    LED_PIN = 18
    LED_FREQ_HZ = 800000
    LED_DMA = 10
    LED_BRIGHTNESS = 150
    LED_INVERT = False
    LED_CHANNEL = 0
    LED_IS_GRB = True
    HALL_SENSOR_PIN = 4
    BUTTON_CIRCLE = 17
    BUTTON_SQUARE = 27
    BUTTON_IMAGE = 22
    NUM_DIVISIONS = 100
    BRIGHTNESS_RATIO = 0.3
    LINES_TO_SHIFT = -15
    LED_UPDATE_TIME_US = 2800
    DEFAULT_RPM = 600
    MIN_RPM = 200
    MAX_RPM = 1500
    TIMING_MARGIN_US = 300
    HALL_DEBOUNCE_US = 5000
    MAX_RPM_CHANGE_PERCENT = 40
    RPM_HISTORY_SIZE = 15
    STATIC_IMAGES_PATH = "colors/douple_resolution/"
    GIF_COLORS_PATH = "gif_colors/"
    ROT_PER_FRAME = 4
    BUTTON_DEBOUNCE_TIME = 0.3

# ============== GLOBAL VARIABLES ==============

# Display modes
MODES = ["circle", "square", "static_image", "gif_sequence"]
current_mode_index = 0
current_mode = MODES[0]

# Image/sequence data
static_images = []               # List of available static images
gif_sequences = []               # List of available GIF sequences
current_static_index = 0
current_gif_index = 0
current_frame_index = 0
rot_per_frame = ROT_PER_FRAME    # Rotations before advancing GIF frame

# Display buffer
display_data = []                # Current frame to display [divisions][leds]
sequence_colors = []             # All frames for GIF sequence

# Timing variables
last_rotation_micros = 0
rotation_time_micros = int(60_000_000 / DEFAULT_RPM)
time_per_line_micros = rotation_time_micros // NUM_DIVISIONS
current_line = 0
rotation_active = False

# RPM tracking
current_rpm = DEFAULT_RPM
stable_rpm = DEFAULT_RPM
rpm_history = []

# Counters
rotation_count = 0
valid_rotation_count = 0
noise_rejected_count = 0
missed_lines_count = 0

# Hall sensor tracking
last_hall_state = GPIO.LOW
last_hall_trigger_time = 0

# Button tracking
last_button_states = {
    BUTTON_CIRCLE: GPIO.HIGH,
    BUTTON_SQUARE: GPIO.HIGH,
    BUTTON_IMAGE: GPIO.HIGH
}
last_button_time = {
    BUTTON_CIRCLE: 0,
    BUTTON_SQUARE: 0,
    BUTTON_IMAGE: 0
}
DEBOUNCE_TIME = BUTTON_DEBOUNCE_TIME

# Threading event for rotation sync
rotation_end_event = threading.Event()

# ============== GPIO SETUP ==============
GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)

try:
    GPIO.cleanup()
    time.sleep(0.1)
except:
    pass

GPIO.setmode(GPIO.BCM)
GPIO.setup(HALL_SENSOR_PIN, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
GPIO.setup(BUTTON_CIRCLE, GPIO.IN, pull_up_down=GPIO.PUD_UP)
GPIO.setup(BUTTON_SQUARE, GPIO.IN, pull_up_down=GPIO.PUD_UP)
GPIO.setup(BUTTON_IMAGE, GPIO.IN, pull_up_down=GPIO.PUD_UP)

# Initialize LED strip
strip = PixelStrip(NUM_LEDS, LED_PIN, LED_FREQ_HZ, LED_DMA, LED_INVERT, LED_BRIGHTNESS, LED_CHANNEL)
strip.begin()


# ============== UTILITY FUNCTIONS ==============

def make_color(r, g, b):
    """Create color value handling GRB vs RGB order"""
    if LED_IS_GRB:
        return Color(int(g), int(r), int(b))
    else:
        return Color(int(r), int(g), int(b))


def clear_strip():
    """Turn off all LEDs"""
    for i in range(NUM_LEDS):
        strip.setPixelColor(i, make_color(0, 0, 0))
    strip.show()


def get_time_micros():
    """Get current time in microseconds"""
    return int(time.perf_counter() * 1_000_000)


def precise_micros_delay(micros_to_delay):
    """Precise busy-wait delay in microseconds"""
    start = time.perf_counter() * 1_000_000
    while (time.perf_counter() * 1_000_000 - start) < micros_to_delay:
        if rotation_end_event.is_set():
            break


# ============== FILE DISCOVERY ==============

def discover_static_images():
    """Find all .npy files in the static images directory"""
    global static_images
    static_images = []
    
    if os.path.exists(STATIC_IMAGES_PATH):
        for f in sorted(os.listdir(STATIC_IMAGES_PATH)):
            if f.endswith('.npy'):
                static_images.append(f)
    
    print(f"Found {len(static_images)} static images")
    return static_images


def discover_gif_sequences():
    """Find all GIF sequence folders"""
    global gif_sequences
    gif_sequences = []
    
    if os.path.exists(GIF_COLORS_PATH):
        for d in sorted(os.listdir(GIF_COLORS_PATH)):
            path = os.path.join(GIF_COLORS_PATH, d)
            if os.path.isdir(path):
                # Check if it has .npy files
                npy_files = [f for f in os.listdir(path) if f.endswith('.npy')]
                if npy_files:
                    gif_sequences.append(d)
    
    print(f"Found {len(gif_sequences)} GIF sequences")
    return gif_sequences


# ============== NPY IMAGE LOADING (from POV-new) ==============

def load_npy_image(npy_path):
    """
    Load a pre-processed .npy image file and convert to display format.
    
    The .npy files contain color data in format:
    [num_divisions][num_leds][3] where [3] is RGB
    """
    try:
        slices_colors = np.load(npy_path)
        slices_colors = slices_colors.tolist()
        return arrange_colors_for_display(slices_colors)
    except Exception as e:
        print(f"Error loading {npy_path}: {e}")
        return None


def arrange_colors_for_display(slices_colors):
    """
    Arrange colors from .npy format to display format.
    Handles the two-sided LED strip arrangement.
    
    The strip has two halves:
    - LEDs 0 to 35: One side (inner to outer)
    - LEDs 36 to 71: Other side (inner to outer)
    """
    arranged_colors = []
    num_leds_one_side = NUM_LEDS // 2
    num_divs = len(slices_colors)
    
    for line_iter in range(num_divs):
        line_array = [make_color(0, 0, 0) for _ in range(NUM_LEDS)]
        
        # First half of strip (reversed - outer LEDs first in data)
        for i in range(num_leds_one_side):
            if i * 2 + 1 < len(slices_colors[line_iter]):
                color_arr = slices_colors[line_iter][i * 2 + 1]
                color = make_color(
                    int(color_arr[0] * BRIGHTNESS_RATIO),
                    int(color_arr[1] * BRIGHTNESS_RATIO),
                    int(color_arr[2] * BRIGHTNESS_RATIO)
                )
                line_array[num_leds_one_side - i - 1] = color
        
        # Second half of strip (opposite angle, 180 degrees offset)
        opposite_line = (line_iter + num_divs // 2) % num_divs
        for i in range(num_leds_one_side):
            if i * 2 < len(slices_colors[opposite_line]):
                color_arr = slices_colors[opposite_line][i * 2]
                color = make_color(
                    int(color_arr[0] * BRIGHTNESS_RATIO),
                    int(color_arr[1] * BRIGHTNESS_RATIO),
                    int(color_arr[2] * BRIGHTNESS_RATIO)
                )
                line_array[num_leds_one_side + i] = color
        
        arranged_colors.append(line_array)
    
    return arranged_colors


def load_gif_sequence(sequence_name):
    """
    Load all frames of a GIF sequence.
    Returns list of arranged color arrays (one per frame).
    """
    global sequence_colors, current_frame_index
    
    sequence_path = os.path.join(GIF_COLORS_PATH, sequence_name)
    if not os.path.exists(sequence_path):
        print(f"Sequence not found: {sequence_path}")
        return None
    
    files = sorted([f for f in os.listdir(sequence_path) if f.endswith('.npy')])
    if not files:
        print(f"No .npy files in: {sequence_path}")
        return None
    
    sequence_colors = []
    for frame_file in files:
        frame_path = os.path.join(sequence_path, frame_file)
        frame_data = load_npy_image(frame_path)
        if frame_data:
            sequence_colors.append(frame_data)
    
    current_frame_index = 0
    print(f"Loaded GIF sequence '{sequence_name}' with {len(sequence_colors)} frames")
    return sequence_colors


# ============== SHAPE GENERATION (from Pov-fan) ==============

def generate_circle_data(radius_leds=28, color_rgb=(0, 255, 255)):
    """Generate circle display data"""
    data = []
    center_led = NUM_LEDS // 2
    r, g, b = color_rgb
    
    circle_thickness = max(2, 5 - NUM_DIVISIONS // 30)
    pixel_color = make_color(r * BRIGHTNESS_RATIO, g * BRIGHTNESS_RATIO, b * BRIGHTNESS_RATIO)
    off_color = make_color(0, 0, 0)
    
    for angle_idx in range(NUM_DIVISIONS):
        line = [off_color] * NUM_LEDS
        
        if radius_leds < NUM_LEDS // 2:
            for offset in range(-circle_thickness // 2, circle_thickness // 2 + 1):
                led_pos_1 = center_led - radius_leds + offset
                led_pos_2 = center_led + radius_leds + offset
                
                if 0 <= led_pos_1 < NUM_LEDS:
                    line[led_pos_1] = pixel_color
                if 0 <= led_pos_2 < NUM_LEDS:
                    line[led_pos_2] = pixel_color
        
        data.append(line)
    
    return data


def generate_square_data(side_length_leds=24, color_rgb=(255, 0, 255)):
    """Generate square display data using polar math"""
    data = []
    center_led = NUM_LEDS // 2
    r, g, b = color_rgb
    
    edge_thickness = max(2, 5 - NUM_DIVISIONS // 30)
    half_side = side_length_leds // 2
    
    pixel_color = make_color(r * BRIGHTNESS_RATIO, g * BRIGHTNESS_RATIO, b * BRIGHTNESS_RATIO)
    off_color = make_color(0, 0, 0)
    
    for angle_idx in range(NUM_DIVISIONS):
        line = [off_color] * NUM_LEDS
        
        angle_rad = (angle_idx * 2 * math.pi / NUM_DIVISIONS)
        cos_a = abs(math.cos(angle_rad))
        sin_a = abs(math.sin(angle_rad))
        max_trig = max(cos_a, sin_a, 0.001)
        
        distance = int(half_side / max_trig)
        distance = min(distance, center_led - 2)
        
        for offset in range(-edge_thickness // 2, edge_thickness // 2 + 1):
            led_pos_1 = center_led - distance + offset
            led_pos_2 = center_led + distance + offset
            
            if 0 <= led_pos_1 < NUM_LEDS:
                line[led_pos_1] = pixel_color
            if 0 <= led_pos_2 < NUM_LEDS:
                line[led_pos_2] = pixel_color
        
        data.append(line)
    
    return data


def generate_filled_circle_data(radius_leds=28, color_rgb=(0, 100, 255)):
    """Generate filled circle (disk) display data"""
    data = []
    center_led = NUM_LEDS // 2
    r, g, b = color_rgb
    
    pixel_color = make_color(r * BRIGHTNESS_RATIO, g * BRIGHTNESS_RATIO, b * BRIGHTNESS_RATIO)
    off_color = make_color(0, 0, 0)
    
    for angle_idx in range(NUM_DIVISIONS):
        line = [off_color] * NUM_LEDS
        
        # Fill from center to radius
        for dist in range(radius_leds):
            led_pos_1 = center_led - dist - 1
            led_pos_2 = center_led + dist
            
            if 0 <= led_pos_1 < NUM_LEDS:
                line[led_pos_1] = pixel_color
            if 0 <= led_pos_2 < NUM_LEDS:
                line[led_pos_2] = pixel_color
        
        data.append(line)
    
    return data


# ============== MODE SWITCHING ==============

def set_mode_circle():
    """Switch to circle shape mode"""
    global display_data, current_mode
    current_mode = "circle"
    display_data = generate_circle_data(radius_leds=28, color_rgb=(0, 255, 255))
    print("Mode: CIRCLE (cyan)")
    flash_mode_change()


def set_mode_square():
    """Switch to square shape mode"""
    global display_data, current_mode
    current_mode = "square"
    display_data = generate_square_data(side_length_leds=24, color_rgb=(255, 0, 255))
    print("Mode: SQUARE (magenta)")
    flash_mode_change()


def set_mode_static_image():
    """Switch to static image mode"""
    global display_data, current_mode, current_static_index
    
    if not static_images:
        print("No static images found!")
        return
    
    current_mode = "static_image"
    img_file = static_images[current_static_index]
    img_path = os.path.join(STATIC_IMAGES_PATH, img_file)
    
    loaded = load_npy_image(img_path)
    if loaded:
        display_data = loaded
        print(f"Mode: STATIC IMAGE - {img_file}")
    else:
        display_data = generate_circle_data()
    flash_mode_change()


def set_mode_gif_sequence():
    """Switch to GIF sequence mode"""
    global display_data, current_mode, current_gif_index, sequence_colors, current_frame_index
    
    if not gif_sequences:
        print("No GIF sequences found!")
        return
    
    current_mode = "gif_sequence"
    seq_name = gif_sequences[current_gif_index]
    
    loaded = load_gif_sequence(seq_name)
    if loaded:
        display_data = sequence_colors[0]
        current_frame_index = 0
        print(f"Mode: GIF SEQUENCE - {seq_name} ({len(sequence_colors)} frames)")
    else:
        display_data = generate_circle_data()
    flash_mode_change()


def cycle_content():
    """Cycle to next content in current mode"""
    global current_static_index, current_gif_index, display_data
    
    if current_mode == "static_image" and static_images:
        current_static_index = (current_static_index + 1) % len(static_images)
        set_mode_static_image()
    elif current_mode == "gif_sequence" and gif_sequences:
        current_gif_index = (current_gif_index + 1) % len(gif_sequences)
        set_mode_gif_sequence()
    elif current_mode == "circle":
        # Cycle circle colors
        colors = [(0, 255, 255), (255, 255, 0), (255, 0, 255), (0, 255, 0)]
        display_data = generate_circle_data(radius_leds=28, color_rgb=colors[rotation_count % len(colors)])
        print(f"Circle color changed")
        flash_mode_change()
    elif current_mode == "square":
        colors = [(255, 0, 255), (255, 255, 0), (0, 255, 255), (255, 128, 0)]
        display_data = generate_square_data(side_length_leds=24, color_rgb=colors[rotation_count % len(colors)])
        print(f"Square color changed")
        flash_mode_change()


# ============== BUTTON HANDLING ==============

def flash_mode_change():
    """Flash LEDs to indicate mode change and show preview"""
    # Brief flash of white to indicate change
    for i in range(NUM_LEDS):
        strip.setPixelColor(i, make_color(50, 50, 50))
    strip.show()
    time.sleep(0.1)
    
    # Show a static preview of the new mode (first line of display_data)
    show_static_preview()


def show_static_preview():
    """Show a static preview of current display_data on LEDs"""
    global display_data
    
    if not display_data or len(display_data) == 0:
        return
    
    # Show the first line (or middle line for better preview)
    preview_line = len(display_data) // 4  # Show at 90 degrees for variety
    
    if preview_line < len(display_data):
        line_data = display_data[preview_line]
        for i in range(min(NUM_LEDS, len(line_data))):
            strip.setPixelColor(i, line_data[i])
        strip.show()


def check_buttons():
    """Poll buttons for mode changes"""
    global last_button_states, last_button_time, current_static_index, current_mode
    
    current_time = time.time()
    
    # Button 1: Circle mode
    state = GPIO.input(BUTTON_CIRCLE)
    if state == GPIO.LOW and last_button_states[BUTTON_CIRCLE] == GPIO.HIGH:
        if current_time - last_button_time[BUTTON_CIRCLE] > DEBOUNCE_TIME:
            if current_mode == "circle":
                cycle_content()
            else:
                set_mode_circle()
            last_button_time[BUTTON_CIRCLE] = current_time
    last_button_states[BUTTON_CIRCLE] = state
    
    # Button 2: Square mode
    state = GPIO.input(BUTTON_SQUARE)
    if state == GPIO.LOW and last_button_states[BUTTON_SQUARE] == GPIO.HIGH:
        if current_time - last_button_time[BUTTON_SQUARE] > DEBOUNCE_TIME:
            if current_mode == "square":
                cycle_content()
            else:
                set_mode_square()
            last_button_time[BUTTON_SQUARE] = current_time
    last_button_states[BUTTON_SQUARE] = state
    
    # Button 3: Image/GIF mode (cycles through modes and content)
    state = GPIO.input(BUTTON_IMAGE)
    if state == GPIO.LOW and last_button_states[BUTTON_IMAGE] == GPIO.HIGH:
        if current_time - last_button_time[BUTTON_IMAGE] > DEBOUNCE_TIME:
            if current_mode == "static_image":
                if static_images and current_static_index < len(static_images) - 1:
                    cycle_content()
                else:
                    set_mode_gif_sequence()
            elif current_mode == "gif_sequence":
                if gif_sequences and current_gif_index < len(gif_sequences) - 1:
                    cycle_content()
                else:
                    # Cycle back to static images
                    current_static_index = 0
                    set_mode_static_image()
            else:
                # From shapes, go to static images
                current_static_index = 0
                set_mode_static_image()
            last_button_time[BUTTON_IMAGE] = current_time
    last_button_states[BUTTON_IMAGE] = state


# ============== HALL SENSOR HANDLING ==============

def check_hall_sensor():
    """
    Poll hall sensor with noise filtering and debouncing.
    Updates timing variables for display synchronization.
    """
    global last_hall_state, last_rotation_micros, rotation_time_micros
    global time_per_line_micros, current_line, rotation_count, rotation_active
    global current_rpm, stable_rpm, rpm_history
    global last_hall_trigger_time, valid_rotation_count, noise_rejected_count
    global current_frame_index
    
    current_state = GPIO.input(HALL_SENSOR_PIN)
    
    # Detect rising edge (magnet detected = 0° position)
    if current_state == GPIO.HIGH and last_hall_state == GPIO.LOW:
        current_time = get_time_micros()
        
        # Debounce: ignore triggers too close together
        time_since_last = current_time - last_hall_trigger_time
        if time_since_last < HALL_DEBOUNCE_US:
            last_hall_state = current_state
            noise_rejected_count += 1
            return
        
        last_hall_trigger_time = current_time
        rotation_end_event.set()
        
        # Calculate rotation time
        if last_rotation_micros > 0:
            measured_rotation_time = current_time - last_rotation_micros
            
            # Validate: check if in valid RPM range
            min_rotation_time = int(60_000_000 / MAX_RPM)
            max_rotation_time = int(60_000_000 / MIN_RPM)
            
            if not (min_rotation_time <= measured_rotation_time <= max_rotation_time):
                noise_rejected_count += 1
                last_hall_state = current_state
                current_line = 0
                rotation_count += 1
                last_rotation_micros = current_time
                return
            
            # Calculate instant RPM
            instant_rpm = 60_000_000 / measured_rotation_time
            
            # Reject sudden RPM jumps
            if len(rpm_history) >= 3:
                avg_rpm = sum(rpm_history) / len(rpm_history)
                rpm_change_percent = abs(instant_rpm - avg_rpm) / avg_rpm * 100
                
                if rpm_change_percent > MAX_RPM_CHANGE_PERCENT:
                    noise_rejected_count += 1
                    last_hall_state = current_state
                    current_line = 0
                    rotation_count += 1
                    last_rotation_micros = current_time
                    return
            
            # Valid reading - add to history
            rpm_history.append(instant_rpm)
            if len(rpm_history) > RPM_HISTORY_SIZE:
                rpm_history.pop(0)
            
            valid_rotation_count += 1
            
            # Calculate smoothed RPM (trimmed mean)
            if len(rpm_history) >= 5:
                sorted_rpm = sorted(rpm_history)
                trimmed = sorted_rpm[1:-1]
                stable_rpm = sum(trimmed) / len(trimmed) if trimmed else instant_rpm
            else:
                stable_rpm = sum(rpm_history) / len(rpm_history)
            
            current_rpm = stable_rpm
            
            # Update timing
            rotation_time_micros = int(60_000_000 / stable_rpm)
            time_per_line_micros = rotation_time_micros // NUM_DIVISIONS
            
            # Ensure minimum time for LED update
            if time_per_line_micros < LED_UPDATE_TIME_US:
                time_per_line_micros = LED_UPDATE_TIME_US
            
            # Status update (periodic)
            if valid_rotation_count % 100 == 0:
                print(f"RPM: {stable_rpm:.0f} | Line time: {time_per_line_micros}µs | Mode: {current_mode}")
        
        # GIF frame advancement
        if current_mode == "gif_sequence" and sequence_colors:
            if rotation_count % rot_per_frame == 0:
                current_frame_index = (current_frame_index + 1) % len(sequence_colors)
        
        # Reset position
        current_line = 0
        rotation_active = True
        rotation_count += 1
        last_rotation_micros = current_time
        
        if rotation_count == 1:
            print("\n✓ ROTATION DETECTED! Display active.")
    
    last_hall_state = current_state


# ============== DISPLAY FUNCTION ==============

def display_current_line():
    """Display the current angular line with optimized timing"""
    global current_line, missed_lines_count, display_data
    
    if not rotation_active or time_per_line_micros <= 0:
        return
    
    if rotation_end_event.is_set():
        rotation_end_event.clear()
        current_line = 0
    
    # Get current display data (handle GIF frame switching)
    frame_data = display_data
    if current_mode == "gif_sequence" and sequence_colors:
        frame_data = sequence_colors[current_frame_index]
    
    # Calculate which line to show (with offset)
    num_divs = len(frame_data) if frame_data else NUM_DIVISIONS
    line_to_show = (current_line + LINES_TO_SHIFT + num_divs * 2) % num_divs
    
    # Start timing
    line_start_time = get_time_micros()
    
    # Update LEDs
    if frame_data and line_to_show < len(frame_data):
        line_data = frame_data[line_to_show]
        for i in range(min(NUM_LEDS, len(line_data))):
            strip.setPixelColor(i, line_data[i])
        strip.show()
    
    # Calculate remaining time
    update_time = get_time_micros() - line_start_time
    remaining = time_per_line_micros - update_time - TIMING_MARGIN_US
    
    if remaining > 0:
        # Precise wait
        target_time = get_time_micros() + remaining
        while get_time_micros() < target_time:
            pass
    elif remaining < -1000:
        # Running behind - skip lines to catch up
        lines_to_skip = int((-remaining) / time_per_line_micros)
        if lines_to_skip > 0:
            current_line += lines_to_skip
            missed_lines_count += lines_to_skip
    
    # Advance to next line
    current_line += 1
    if current_line >= num_divs:
        current_line = 0


# ============== MAIN ==============

def main():
    global display_data
    
    print("\n" + "=" * 60)
    print("  POV HOLOGRAPHIC FAN DISPLAY")
    print("  Combined from POV-new + Pov-fan")
    print("=" * 60)
    
    print("\n▸ HARDWARE CONFIG:")
    print(f"  • LEDs: {NUM_LEDS} on GPIO {LED_PIN}")
    print(f"  • Hall Sensor: GPIO {HALL_SENSOR_PIN}")
    print(f"  • Buttons: GPIO {BUTTON_CIRCLE}, {BUTTON_SQUARE}, {BUTTON_IMAGE}")
    print(f"  • Brightness: {int(BRIGHTNESS_RATIO * 100)}%")
    
    print("\n▸ DISPLAY CONFIG:")
    print(f"  • Divisions: {NUM_DIVISIONS}")
    print(f"  • Expected RPM: {DEFAULT_RPM}")
    print(f"  • LED update time: ~{LED_UPDATE_TIME_US}µs")
    
    # Discover available content
    discover_static_images()
    discover_gif_sequences()
    
    print("\n▸ CONTROLS:")
    print(f"  • GPIO {BUTTON_CIRCLE}: Circle shape (press again to change color)")
    print(f"  • GPIO {BUTTON_SQUARE}: Square shape (press again to change color)")
    print(f"  • GPIO {BUTTON_IMAGE}: Cycle images & GIFs")
    
    print("\n" + "=" * 60)
    print("  Starting with circle mode. Spin the fan!")
    print("=" * 60 + "\n")
    
    # Initialize with circle
    set_mode_circle()
    
    # Startup indicator (green LEDs)
    for i in range(3):
        strip.setPixelColor(i, make_color(0, 50, 0))
    strip.show()
    
    try:
        while True:
            check_buttons()
            check_hall_sensor()
            display_current_line()
            
    except KeyboardInterrupt:
        print("\n\n" + "-" * 50)
        print("SHUTDOWN STATS:")
        print(f"  • Total rotations: {rotation_count}")
        print(f"  • Valid rotations: {valid_rotation_count}")
        print(f"  • Final RPM: {stable_rpm:.1f}")
        print(f"  • Noise rejected: {noise_rejected_count}")
        if missed_lines_count > 0:
            print(f"  • Missed lines: {missed_lines_count}")
        print("-" * 50)
        clear_strip()
        
    finally:
        GPIO.cleanup()
        print("Done!\n")


if __name__ == "__main__":
    main()

