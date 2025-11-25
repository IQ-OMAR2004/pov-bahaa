# POV Holographic Fan Display

A Persistence of Vision (POV) display system for Raspberry Pi with WS2815 LED strips.

## Features

- **Static Images**: Display pre-processed images from `.npy` files
- **GIF Animations**: Play animated sequences
- **Shape Generation**: Built-in circle and square shapes
- **Button Controls**: Switch modes with physical buttons
- **Robust Timing**: Noise filtering and RPM smoothing for stable display
- **Configurable**: Easy configuration through `config.py`

## Hardware Requirements

### Components

| Component | Specification | GPIO Pin |
|-----------|--------------|----------|
| LED Strip | WS2815, 72 LEDs | GPIO 18 (PWM) |
| Hall Sensor | A3144 or similar | GPIO 4 |
| Button 1 | Circle mode | GPIO 17 |
| Button 2 | Square mode | GPIO 27 |
| Button 3 | Image/GIF cycle | GPIO 22 |

### Wiring Diagram

```
Raspberry Pi               Components
─────────────              ──────────
GPIO 18 (Pin 12) ────────> LED Strip Data In
GPIO 4  (Pin 7)  ────────> Hall Sensor Output
GPIO 17 (Pin 11) ────────> Button 1 (to GND)
GPIO 27 (Pin 13) ────────> Button 2 (to GND)
GPIO 22 (Pin 15) ────────> Button 3 (to GND)
5V      (Pin 2)  ────────> LED Strip VCC
GND     (Pin 6)  ────────> LED Strip GND, Hall Sensor GND
3.3V    (Pin 1)  ────────> Hall Sensor VCC
```

### Notes

- **Power**: WS2815 LEDs require 12V power supply. Use a separate power supply for the LED strip, sharing only GND with the Pi.
- **Level Shifter**: Recommended for 3.3V to 5V data line conversion (though many WS2815 work without it).
- **Hall Sensor**: Place magnet on rotating blade to trigger once per rotation.
- **Buttons**: Connect between GPIO and GND (internal pull-ups are enabled).

## Installation

### 1. Clone or copy the project

```bash
cd /home/pi
git clone <repository-url> POV-new
cd POV-new
```

### 2. Install dependencies

```bash
sudo pip3 install -r requirements.txt
```

### 3. Enable SPI/PWM (if not already)

```bash
sudo raspi-config
# Navigate to: Interface Options > SPI > Enable
# Reboot after changes
```

## Configuration

Edit `config.py` to customize your setup:

```python
# Key settings to adjust:

NUM_LEDS = 72              # Number of LEDs on your strip
NUM_DIVISIONS = 100        # Angular resolution (reduce for faster motors)
BRIGHTNESS_RATIO = 0.3     # Brightness (0.0-1.0)
DEFAULT_RPM = 600          # Expected motor RPM
LINES_TO_SHIFT = -15       # Adjust if image appears rotated
```

### RPM vs Divisions Guide

| Motor RPM | Recommended Divisions |
|-----------|----------------------|
| 300-600   | 100 (best quality)   |
| 600-900   | 50                   |
| 900-1200  | 36                   |
| 1200-1500 | 24                   |
| 1500+     | 16                   |

## Usage

### Running the Display

```bash
# Must run as root for GPIO/PWM access
sudo python3 pov_display.py
```

### Controls

- **Button 1 (GPIO 17)**: Switch to circle mode (press again to change color)
- **Button 2 (GPIO 27)**: Switch to square mode (press again to change color)
- **Button 3 (GPIO 22)**: Cycle through images and GIF sequences

### Keyboard

- **Ctrl+C**: Graceful shutdown

## Processing Your Own Images

### Static Images

1. Place your image in the `images/` folder
2. Run the processor:

```bash
python3 process_image.py images/myimage.png
```

3. Output saves to `colors/douple_resolution/douple_res_myimage.npy`

### GIF Animations

1. Place your GIF in the `gifs/` folder
2. Run the processor:

```bash
python3 process_gif.py gifs/myanimation.gif
```

3. Output saves to `gif_colors/myanimation/`

### Image Tips

- **Square images** work best (circular crop is applied)
- **Simple, high-contrast** designs are most visible
- **Centered designs** display better
- Image is sampled radially from center outward

## File Structure

```
POV-new/
├── pov_display.py          # Main display script
├── config.py               # Configuration settings
├── process_image.py        # Static image processor
├── process_gif.py          # GIF/animation processor
├── requirements.txt        # Python dependencies
├── README.md               # This file
├── images/                 # Source images
│   └── Smiley_face.png
├── colors/                 # Processed static images
│   └── douple_resolution/
│       └── douple_res_Smiley_face.npy
├── gifs/                   # Source GIF files
│   └── earth.gif
├── gif_sequences/          # Extracted GIF frames
│   └── earth/
├── gif_colors/             # Processed GIF sequences
│   └── earth/
└── 3d_printing_files/      # CAD files for hardware
```

## Troubleshooting

### Display not showing / flickering

1. **Check power supply**: LEDs need adequate current (72 LEDs × 60mA = 4.3A max)
2. **Reduce brightness**: Lower `BRIGHTNESS_RATIO` in `config.py`
3. **Reduce divisions**: Lower `NUM_DIVISIONS` for faster motors
4. **Check connections**: Ensure GND is shared between Pi and LED strip

### Image appears rotated

Adjust `LINES_TO_SHIFT` in `config.py` (positive or negative values)

### Unstable RPM readings

1. Check hall sensor placement and magnet strength
2. Increase `HALL_DEBOUNCE_US` in config
3. Increase `RPM_HISTORY_SIZE` for more smoothing

### Colors look wrong

Your LED strip might use RGB instead of GRB. Set `LED_IS_GRB = False` in `config.py`

### Permission denied

Always run with `sudo`:
```bash
sudo python3 pov_display.py
```

## Advanced: Creating Custom Shapes

You can add custom shape generators in `pov_display.py`:

```python
def generate_custom_shape(color_rgb=(255, 255, 255)):
    data = []
    for angle_idx in range(NUM_DIVISIONS):
        line = [make_color(0, 0, 0)] * NUM_LEDS
        # Your shape logic here
        # Set pixels: line[led_position] = make_color(r, g, b)
        data.append(line)
    return data
```

## License

MIT License - Feel free to modify and share!

## Credits

Combined from POV-new and Pov-fan projects for optimal performance.
