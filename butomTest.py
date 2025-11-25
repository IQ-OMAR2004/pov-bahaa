import RPi.GPIO as GPIO
import subprocess
import time
import os
import signal

# GPIO pins
BUTTON1 = 17
BUTTON2 = 27
BUTTON3 = 22

# Commands to run
SCRIPTS = {
    BUTTON1: ["sudo", "python", "/home/pi/Desktop/raspry/0.py"],
    BUTTON2: ["sudo", "python", "/home/pi/Desktop/raspry/3.py"],
    BUTTON3: ["sudo", "python", "/home/pi/Desktop/raspry/4.py"]
}

# Setup GPIO
GPIO.setmode(GPIO.BCM)
for pin in SCRIPTS.keys():
    GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)

current_process = None  # track the running process

def stop_current_script():
    global current_process
    if current_process:
        print("🛑 Stopping current script...")
        os.killpg(os.getpgid(current_process.pid), signal.SIGTERM)
        current_process = None
        time.sleep(0.3)

def run_script(cmd):
    global current_process
    stop_current_script()
    print(f"▶️ Running: {' '.join(cmd)}")
    current_process = subprocess.Popen(
        cmd,
        preexec_fn=os.setsid
    )

try:
    while True:
        # Read all buttons
        b1 = GPIO.input(BUTTON1) == GPIO.LOW
        b2 = GPIO.input(BUTTON2) == GPIO.LOW
        b3 = GPIO.input(BUTTON3) == GPIO.LOW
        pressed_count = [b1, b2, b3].count(True)

        # Safety: ignore if multiple pressed
        if pressed_count > 1:
            print("⚠️ Multiple buttons pressed! Ignoring for safety.")
            stop_current_script()
            time.sleep(0.3)
            continue

        # Handle single button presses
        if b1:
            run_script(SCRIPTS[BUTTON1])
            while GPIO.input(BUTTON1) == GPIO.LOW:
                time.sleep(0.1)

        elif b2:
            run_script(SCRIPTS[BUTTON2])
            while GPIO.input(BUTTON2) == GPIO.LOW:
                time.sleep(0.1)

        elif b3:
            run_script(SCRIPTS[BUTTON3])
            while GPIO.input(BUTTON3) == GPIO.LOW:
                time.sleep(0.1)

        time.sleep(0.05)

except KeyboardInterrupt:
    print("\nExiting safely...")
    stop_current_script()
    GPIO.cleanup()
