"""
POV Display Configuration
=========================
Edit this file to customize your POV fan display settings.
All configuration values are centralized here for easy modification.
"""

# ============== LED STRIP CONFIGURATION ==============
NUM_LEDS = 72                    # Total LEDs on your strip
LED_PIN = 18                     # GPIO pin (must support PWM: 18, 12, 13, 19)
LED_FREQ_HZ = 800000             # Signal frequency (usually 800kHz for WS28xx)
LED_DMA = 10                     # DMA channel (usually 10)
LED_BRIGHTNESS = 150             # Initial brightness (0-255)
LED_INVERT = False               # True if using level shifter that inverts
LED_CHANNEL = 0                  # 0 for GPIO 18/12, 1 for GPIO 13/19

# Color order - WS2815 typically uses GRB
# Set to True for GRB strips, False for RGB strips
LED_IS_GRB = True

# ============== SENSOR PINS ==============
HALL_SENSOR_PIN = 4              # Hall effect sensor (A3144 or similar)

# ============== BUTTON PINS ==============
# Set to None to disable a button
BUTTON_CIRCLE = 17               # Circle shape button
BUTTON_SQUARE = 27               # Square shape button
BUTTON_IMAGE = 22                # Image/GIF cycle button

# ============== DISPLAY SETTINGS ==============
# Number of angular divisions per rotation
# ACTUAL maximums based on 72 LEDs and 2800µs update time:
#   70 divisions: ~300 RPM
#   50 divisions: ~420 RPM
#   40 divisions: ~530 RPM
#   30 divisions: ~700 RPM
#   24 divisions: ~870 RPM
#   16 divisions: ~1300 RPM
NUM_DIVISIONS = 40  # Optimized for 500 RPM (max ~42)

# Brightness multiplier (0.0 to 1.0)
# Lower values = dimmer but less power usage
# Higher values = brighter but may cause flickering at high RPM
BRIGHTNESS_RATIO = 0.3

# Rotational offset to align image with starting position
# Adjust this if your image appears rotated
LINES_TO_SHIFT = -15

# ============== MOTOR/RPM SETTINGS ==============
# Expected motor RPM (used for initial timing)
DEFAULT_RPM = 500

# Valid RPM range (readings outside this are rejected as noise)
MIN_RPM = 200
MAX_RPM = 1500

# ============== TIMING SETTINGS ==============
# Approximate time to update all LEDs (microseconds)
# Calculated as: NUM_LEDS * 24 bits * 1.25µs + reset time
# For 72 LEDs: ~2800µs
LED_UPDATE_TIME_US = 2800

# Safety margin for timing (microseconds)
TIMING_MARGIN_US = 300

# ============== NOISE FILTERING ==============
# Ignore hall sensor triggers within this time (microseconds)
HALL_DEBOUNCE_US = 5000

# Reject RPM changes larger than this percentage
MAX_RPM_CHANGE_PERCENT = 40

# Number of samples for RPM smoothing (more = smoother but slower response)
RPM_HISTORY_SIZE = 15

# ============== FILE PATHS ==============
# Path to pre-processed static images (.npy files)
STATIC_IMAGES_PATH = "colors/douple_resolution/"

# Path to GIF sequence folders
GIF_COLORS_PATH = "gif_colors/"

# ============== ANIMATION SETTINGS ==============
# Number of rotations before advancing to next GIF frame
# Lower = faster animation, Higher = slower animation
ROT_PER_FRAME = 4

# ============== BUTTON SETTINGS ==============
# Button debounce time (seconds)
BUTTON_DEBOUNCE_TIME = 0.3

