#!/usr/bin/env python3
"""
Hall Sensor Diagnostic Tool
============================
Tests the hall effect sensor (A3144) for proper operation.

This script performs multiple tests:
1. Basic connectivity test
2. Signal monitoring (watch live values)
3. Trigger detection test
4. Bounce/noise analysis
5. RPM measurement test
6. Wiring verification guidance

Hardware: Hall sensor on GPIO 4 (configurable)
Expected: A3144 or similar hall effect sensor

Usage:
    sudo python3 test_hall_sensor.py
"""

import time
import sys
import statistics

# Check if running on Raspberry Pi
try:
    import RPi.GPIO as GPIO
    ON_PI = True
except ImportError:
    print("⚠ RPi.GPIO not available. Running in simulation mode.")
    ON_PI = False


# ============== CONFIGURATION ==============
# Import from config if available, otherwise use defaults
try:
    from config import HALL_SENSOR_PIN, MIN_RPM, MAX_RPM, HALL_DEBOUNCE_US
except ImportError:
    HALL_SENSOR_PIN = 4
    MIN_RPM = 200
    MAX_RPM = 1500
    HALL_DEBOUNCE_US = 5000

# Test parameters
TEST_DURATION_SEC = 10      # Duration for timed tests
SAMPLE_RATE_HZ = 10000      # How fast to sample (approximate)
BOUNCE_WINDOW_US = 1000     # Window to detect bouncing


class Colors:
    """Terminal colors for output"""
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BOLD = '\033[1m'
    END = '\033[0m'


def print_header(text):
    print(f"\n{Colors.BOLD}{Colors.CYAN}{'='*60}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.CYAN}  {text}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.CYAN}{'='*60}{Colors.END}\n")


def print_pass(text):
    print(f"{Colors.GREEN}✓ PASS:{Colors.END} {text}")


def print_fail(text):
    print(f"{Colors.RED}✗ FAIL:{Colors.END} {text}")


def print_warn(text):
    print(f"{Colors.YELLOW}⚠ WARN:{Colors.END} {text}")


def print_info(text):
    print(f"{Colors.BLUE}ℹ INFO:{Colors.END} {text}")


def get_time_micros():
    """Get current time in microseconds"""
    return int(time.perf_counter() * 1_000_000)


def setup_gpio():
    """Initialize GPIO for hall sensor"""
    if not ON_PI:
        return False
    
    try:
        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)
        
        # Try both pull-up and pull-down configurations
        GPIO.setup(HALL_SENSOR_PIN, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
        return True
    except Exception as e:
        print_fail(f"GPIO setup failed: {e}")
        return False


def cleanup_gpio():
    """Clean up GPIO"""
    if ON_PI:
        try:
            GPIO.cleanup()
        except:
            pass


# ============== TEST 1: BASIC CONNECTIVITY ==============
def test_connectivity():
    """Test basic sensor connectivity and initial state"""
    print_header("TEST 1: BASIC CONNECTIVITY")
    
    print_info(f"Testing hall sensor on GPIO {HALL_SENSOR_PIN}")
    
    if not ON_PI:
        print_warn("Not running on Raspberry Pi - skipping hardware test")
        return None
    
    try:
        # Read initial state
        initial_state = GPIO.input(HALL_SENSOR_PIN)
        print_info(f"Initial state: {'HIGH (1)' if initial_state else 'LOW (0)'}")
        
        # Sample for 1 second
        samples = []
        start_time = time.time()
        while time.time() - start_time < 1.0:
            samples.append(GPIO.input(HALL_SENSOR_PIN))
            time.sleep(0.0001)  # 10kHz sampling
        
        high_count = sum(samples)
        low_count = len(samples) - high_count
        
        print_info(f"Sampled {len(samples)} readings in 1 second")
        print_info(f"HIGH readings: {high_count} ({100*high_count/len(samples):.1f}%)")
        print_info(f"LOW readings: {low_count} ({100*low_count/len(samples):.1f}%)")
        
        # Analysis
        if high_count == len(samples):
            print_warn("Sensor ALWAYS HIGH - possible issues:")
            print("        - Magnet is constantly near sensor")
            print("        - Sensor wiring issue (stuck high)")
            print("        - Wrong GPIO pin configured")
            return "always_high"
        elif low_count == len(samples):
            print_warn("Sensor ALWAYS LOW - possible issues:")
            print("        - No magnet detected (normal if no magnet nearby)")
            print("        - Sensor not powered")
            print("        - Wrong GPIO pin configured")
            return "always_low"
        else:
            print_pass("Sensor shows both states - responding to input")
            return "responsive"
            
    except Exception as e:
        print_fail(f"Test failed: {e}")
        return "error"


# ============== TEST 2: LIVE MONITORING ==============
def test_live_monitoring():
    """Show live sensor values in real-time"""
    print_header("TEST 2: LIVE MONITORING")
    
    if not ON_PI:
        print_warn("Not running on Raspberry Pi - skipping")
        return
    
    print_info("Monitoring sensor for 10 seconds...")
    print_info("Move a magnet near the sensor to test response")
    print_info("Press Ctrl+C to skip this test\n")
    
    last_state = GPIO.input(HALL_SENSOR_PIN)
    transitions = 0
    
    try:
        start_time = time.time()
        last_print = start_time
        
        while time.time() - start_time < TEST_DURATION_SEC:
            current_state = GPIO.input(HALL_SENSOR_PIN)
            
            # Detect transitions
            if current_state != last_state:
                transitions += 1
                edge_type = "RISING" if current_state == GPIO.HIGH else "FALLING"
                elapsed = time.time() - start_time
                print(f"  [{elapsed:6.3f}s] {edge_type} edge detected (#{transitions})")
                last_state = current_state
            
            # Print status every second
            if time.time() - last_print >= 1.0:
                state_str = "HIGH" if current_state else "LOW"
                remaining = TEST_DURATION_SEC - (time.time() - start_time)
                print(f"  Status: {state_str} | Transitions: {transitions} | Time remaining: {remaining:.0f}s")
                last_print = time.time()
            
            time.sleep(0.0001)
        
        print(f"\n  Total transitions detected: {transitions}")
        
        if transitions == 0:
            print_warn("No transitions detected during monitoring")
            print("        Try moving a magnet near the sensor")
        elif transitions > 100:
            print_warn(f"Many transitions ({transitions}) - possible noise or bouncing")
        else:
            print_pass(f"Detected {transitions} transitions")
            
    except KeyboardInterrupt:
        print("\n  Monitoring stopped by user")


# ============== TEST 3: TRIGGER DETECTION ==============
def test_trigger_detection():
    """Test trigger detection and timing"""
    print_header("TEST 3: TRIGGER DETECTION")
    
    if not ON_PI:
        print_warn("Not running on Raspberry Pi - skipping")
        return
    
    print_info("Testing edge detection with interrupt...")
    print_info("Wave a magnet near the sensor")
    print_info(f"Waiting up to {TEST_DURATION_SEC} seconds for triggers...\n")
    
    trigger_times = []
    trigger_count = [0]  # Use list to allow modification in callback
    
    def trigger_callback(channel):
        trigger_times.append(get_time_micros())
        trigger_count[0] += 1
        print(f"  Trigger #{trigger_count[0]} detected!")
    
    try:
        # Set up edge detection
        GPIO.add_event_detect(HALL_SENSOR_PIN, GPIO.RISING, callback=trigger_callback)
        
        start_time = time.time()
        while time.time() - start_time < TEST_DURATION_SEC:
            if trigger_count[0] >= 10:
                print("\n  Collected 10 triggers - analyzing...")
                break
            time.sleep(0.1)
        
        GPIO.remove_event_detect(HALL_SENSOR_PIN)
        
        if trigger_count[0] == 0:
            print_fail("No triggers detected!")
            print("        Possible issues:")
            print("        - Magnet not detected by sensor")
            print("        - Sensor polarity issue")
            print("        - Wiring problem")
        else:
            print_pass(f"Detected {trigger_count[0]} triggers")
            
            # Analyze timing
            if len(trigger_times) >= 2:
                intervals = []
                for i in range(1, len(trigger_times)):
                    interval_us = trigger_times[i] - trigger_times[i-1]
                    intervals.append(interval_us)
                
                print(f"\n  Trigger intervals (µs):")
                for i, interval in enumerate(intervals[:5]):
                    print(f"    #{i+1}: {interval:,} µs ({1_000_000/interval:.1f} Hz)")
                
                if len(intervals) > 1:
                    avg_interval = statistics.mean(intervals)
                    std_dev = statistics.stdev(intervals) if len(intervals) > 1 else 0
                    
                    print(f"\n  Average interval: {avg_interval:,.0f} µs")
                    print(f"  Standard deviation: {std_dev:,.0f} µs ({100*std_dev/avg_interval:.1f}%)")
                    
                    if std_dev / avg_interval > 0.3:
                        print_warn("High timing variance - sensor may be noisy")
                    else:
                        print_pass("Timing variance is acceptable")
                        
    except KeyboardInterrupt:
        GPIO.remove_event_detect(HALL_SENSOR_PIN)
        print("\n  Test interrupted by user")
    except Exception as e:
        print_fail(f"Test error: {e}")


# ============== TEST 4: BOUNCE ANALYSIS ==============
def test_bounce_analysis():
    """Analyze signal bouncing/noise"""
    print_header("TEST 4: BOUNCE/NOISE ANALYSIS")
    
    if not ON_PI:
        print_warn("Not running on Raspberry Pi - skipping")
        return
    
    print_info("Analyzing signal for bouncing and noise...")
    print_info("Wave a magnet near the sensor several times")
    print_info(f"Testing for {TEST_DURATION_SEC} seconds...\n")
    
    edges = []
    bounce_events = []
    
    try:
        last_state = GPIO.input(HALL_SENSOR_PIN)
        start_time = get_time_micros()
        last_edge_time = start_time
        
        end_time = start_time + (TEST_DURATION_SEC * 1_000_000)
        
        while get_time_micros() < end_time:
            current_state = GPIO.input(HALL_SENSOR_PIN)
            current_time = get_time_micros()
            
            if current_state != last_state:
                edge_type = "rise" if current_state == GPIO.HIGH else "fall"
                time_since_last = current_time - last_edge_time
                
                edges.append({
                    'time': current_time,
                    'type': edge_type,
                    'interval': time_since_last
                })
                
                # Detect bouncing (rapid transitions < 1ms)
                if time_since_last < BOUNCE_WINDOW_US:
                    bounce_events.append(time_since_last)
                
                last_edge_time = current_time
                last_state = current_state
        
        # Analysis
        print(f"  Total edges detected: {len(edges)}")
        
        if len(edges) == 0:
            print_warn("No signal changes detected")
            return
        
        rising_edges = [e for e in edges if e['type'] == 'rise']
        falling_edges = [e for e in edges if e['type'] == 'fall']
        
        print(f"  Rising edges: {len(rising_edges)}")
        print(f"  Falling edges: {len(falling_edges)}")
        
        if len(bounce_events) > 0:
            print_warn(f"\n  BOUNCING DETECTED: {len(bounce_events)} rapid transitions")
            print(f"    Shortest interval: {min(bounce_events)} µs")
            print(f"    Average bounce interval: {statistics.mean(bounce_events):.0f} µs")
            
            bounce_percentage = 100 * len(bounce_events) / len(edges)
            print(f"    Bounce rate: {bounce_percentage:.1f}%")
            
            if bounce_percentage > 20:
                print_fail("High bounce rate - debouncing strongly recommended")
                print(f"        Suggested debounce time: {max(bounce_events) * 2} µs")
            else:
                print_warn("Some bouncing present - software debouncing recommended")
                print(f"        Current config: HALL_DEBOUNCE_US = {HALL_DEBOUNCE_US}")
        else:
            print_pass("No bouncing detected - signal is clean")
        
        # Analyze intervals for valid triggers
        valid_intervals = [e['interval'] for e in edges if e['interval'] > HALL_DEBOUNCE_US]
        if valid_intervals:
            print(f"\n  Valid trigger intervals (>{HALL_DEBOUNCE_US}µs):")
            print(f"    Min: {min(valid_intervals):,} µs")
            print(f"    Max: {max(valid_intervals):,} µs")
            if len(valid_intervals) > 1:
                print(f"    Avg: {statistics.mean(valid_intervals):,.0f} µs")
                
    except KeyboardInterrupt:
        print("\n  Test interrupted by user")
    except Exception as e:
        print_fail(f"Test error: {e}")


# ============== TEST 5: RPM MEASUREMENT ==============
def test_rpm_measurement():
    """Measure RPM if motor is spinning"""
    print_header("TEST 5: RPM MEASUREMENT")
    
    if not ON_PI:
        print_warn("Not running on Raspberry Pi - skipping")
        return
    
    print_info("Measuring rotation speed...")
    print_info("This test requires the motor to be spinning")
    print_info(f"Expected RPM range: {MIN_RPM} - {MAX_RPM}")
    print_info(f"Testing for {TEST_DURATION_SEC} seconds...\n")
    
    rotation_times = []
    
    def rotation_callback(channel):
        rotation_times.append(get_time_micros())
    
    try:
        GPIO.add_event_detect(HALL_SENSOR_PIN, GPIO.RISING, callback=rotation_callback)
        
        time.sleep(TEST_DURATION_SEC)
        
        GPIO.remove_event_detect(HALL_SENSOR_PIN)
        
        if len(rotation_times) < 2:
            print_warn("Not enough rotations detected for RPM measurement")
            print("        Make sure the motor is spinning with magnet attached")
            return
        
        # Calculate intervals
        intervals_us = []
        for i in range(1, len(rotation_times)):
            interval = rotation_times[i] - rotation_times[i-1]
            # Filter out obvious noise
            if interval > HALL_DEBOUNCE_US:
                intervals_us.append(interval)
        
        if not intervals_us:
            print_fail("All readings appear to be noise")
            return
        
        # Convert to RPM
        rpms = [60_000_000 / interval for interval in intervals_us]
        
        # Filter valid RPMs
        valid_rpms = [rpm for rpm in rpms if MIN_RPM <= rpm <= MAX_RPM]
        
        print(f"  Raw readings: {len(rotation_times)}")
        print(f"  After debounce filter: {len(intervals_us)}")
        print(f"  In valid RPM range: {len(valid_rpms)}")
        
        if valid_rpms:
            avg_rpm = statistics.mean(valid_rpms)
            std_rpm = statistics.stdev(valid_rpms) if len(valid_rpms) > 1 else 0
            
            print(f"\n  {Colors.GREEN}╔═══════════════════════════════╗{Colors.END}")
            print(f"  {Colors.GREEN}║  Average RPM: {avg_rpm:>8.1f}        ║{Colors.END}")
            print(f"  {Colors.GREEN}║  Std Dev:     {std_rpm:>8.1f}        ║{Colors.END}")
            print(f"  {Colors.GREEN}║  Min RPM:     {min(valid_rpms):>8.1f}        ║{Colors.END}")
            print(f"  {Colors.GREEN}║  Max RPM:     {max(valid_rpms):>8.1f}        ║{Colors.END}")
            print(f"  {Colors.GREEN}╚═══════════════════════════════╝{Colors.END}")
            
            # Time per division at current RPM
            rotation_time_us = 60_000_000 / avg_rpm
            divisions = 100  # Default
            time_per_division = rotation_time_us / divisions
            
            print(f"\n  At {avg_rpm:.0f} RPM with 100 divisions:")
            print(f"    Rotation time: {rotation_time_us/1000:.2f} ms")
            print(f"    Time per division: {time_per_division:.0f} µs")
            
            if time_per_division < 2800:
                print_warn(f"Time per division ({time_per_division:.0f}µs) is less than LED update time (~2800µs)")
                print("        Consider reducing NUM_DIVISIONS or motor speed")
            else:
                print_pass("Timing is compatible with POV display")
                
            # Stability check
            if std_rpm > avg_rpm * 0.1:
                print_warn(f"RPM variance is high ({100*std_rpm/avg_rpm:.1f}%) - motor speed unstable")
            else:
                print_pass("RPM is stable")
        else:
            print_fail(f"No readings in valid RPM range ({MIN_RPM}-{MAX_RPM})")
            print(f"        Detected RPMs ranged from {min(rpms):.0f} to {max(rpms):.0f}")
            
    except KeyboardInterrupt:
        GPIO.remove_event_detect(HALL_SENSOR_PIN)
        print("\n  Test interrupted by user")
    except Exception as e:
        print_fail(f"Test error: {e}")


# ============== WIRING GUIDE ==============
def print_wiring_guide():
    """Print wiring verification guide"""
    print_header("WIRING VERIFICATION GUIDE")
    
    print(f"""
  Hall Sensor A3144 Connections:
  ┌─────────────────────────────────────────────┐
  │                                             │
  │   A3144 Pin    →    Raspberry Pi            │
  │   ─────────────────────────────────         │
  │   VCC (left)   →    3.3V or 5V              │
  │   GND (right)  →    Ground                  │
  │   OUT (middle) →    GPIO {HALL_SENSOR_PIN} (with pull-down)     │
  │                                             │
  │   Optional: 10kΩ pull-down resistor         │
  │   between OUT and GND                       │
  │                                             │
  └─────────────────────────────────────────────┘

  Sensor Orientation (front view, flat side facing you):
  ┌─────────────────┐
  │    A 3 1 4 4    │
  │                 │
  │   ┌─┐ ┌─┐ ┌─┐   │
  │   │V│ │O│ │G│   │
  │   │C│ │U│ │N│   │
  │   │C│ │T│ │D│   │
  │   └─┘ └─┘ └─┘   │
  └─────────────────┘
       1   2   3

  Magnet Placement:
  • South pole of magnet should face the FRONT (labeled side)
  • Keep magnet within 10mm of sensor for reliable detection
  
  Common Issues:
  1. ALWAYS HIGH: Check magnet proximity, may be stuck
  2. ALWAYS LOW:  Sensor not powered or wrong polarity
  3. NOISY:       Add pull-down resistor, check wiring
  4. NO TRIGGERS: Wrong GPIO, magnet polarity, or damaged sensor
  """)


# ============== QUICK DIAGNOSTIC ==============
def quick_diagnostic():
    """Run quick diagnostic and report issues"""
    print_header("QUICK DIAGNOSTIC SUMMARY")
    
    issues = []
    
    if not ON_PI:
        print_warn("Cannot perform hardware diagnostics - not on Raspberry Pi")
        return
    
    # Test 1: Read current state
    current = GPIO.input(HALL_SENSOR_PIN)
    print(f"  Current state: {'HIGH' if current else 'LOW'}")
    
    # Test 2: Check for stuck state
    samples = []
    for _ in range(1000):
        samples.append(GPIO.input(HALL_SENSOR_PIN))
        time.sleep(0.0001)
    
    high_pct = 100 * sum(samples) / len(samples)
    
    if high_pct == 100:
        issues.append("Signal stuck HIGH (100%)")
    elif high_pct == 0:
        issues.append("Signal stuck LOW (100%)")
    else:
        print_pass(f"Signal responsive: {high_pct:.1f}% HIGH, {100-high_pct:.1f}% LOW")
    
    # Test 3: Quick edge detection
    print("\n  Checking for signal transitions (2 seconds)...")
    edges = 0
    last = GPIO.input(HALL_SENSOR_PIN)
    start = time.time()
    while time.time() - start < 2:
        curr = GPIO.input(HALL_SENSOR_PIN)
        if curr != last:
            edges += 1
            last = curr
    
    if edges == 0:
        issues.append("No signal transitions in 2 seconds")
    else:
        print_pass(f"Detected {edges} transitions in 2 seconds")
    
    # Report
    print("\n" + "─" * 50)
    if issues:
        print(f"{Colors.RED}  ISSUES FOUND:{Colors.END}")
        for issue in issues:
            print(f"    • {issue}")
        print("\n  Recommended actions:")
        print("    1. Check wiring connections")
        print("    2. Verify sensor power (3.3V or 5V)")
        print("    3. Test with magnet near sensor")
        print("    4. Try opposite magnet polarity")
    else:
        print(f"{Colors.GREEN}  NO OBVIOUS ISSUES DETECTED{Colors.END}")
        print("  Sensor appears to be working correctly.")


# ============== MAIN MENU ==============
def main():
    print("\n")
    print(f"{Colors.BOLD}{Colors.HEADER}╔══════════════════════════════════════════════════════════╗{Colors.END}")
    print(f"{Colors.BOLD}{Colors.HEADER}║         HALL SENSOR DIAGNOSTIC TOOL                      ║{Colors.END}")
    print(f"{Colors.BOLD}{Colors.HEADER}║         For POV Display Project                          ║{Colors.END}")
    print(f"{Colors.BOLD}{Colors.HEADER}╚══════════════════════════════════════════════════════════╝{Colors.END}")
    
    print(f"\n  Sensor Pin: GPIO {HALL_SENSOR_PIN}")
    print(f"  Debounce:   {HALL_DEBOUNCE_US} µs")
    print(f"  RPM Range:  {MIN_RPM} - {MAX_RPM}")
    
    if not setup_gpio():
        print_fail("Failed to initialize GPIO")
        sys.exit(1)
    
    try:
        while True:
            print(f"\n{Colors.CYAN}─────────────────────────────────────────────{Colors.END}")
            print("  Select a test:")
            print("  [1] Basic connectivity test")
            print("  [2] Live signal monitoring (10s)")
            print("  [3] Trigger detection test")
            print("  [4] Bounce/noise analysis")
            print("  [5] RPM measurement (requires spinning)")
            print("  [6] Show wiring guide")
            print("  [7] Quick diagnostic")
            print("  [A] Run ALL tests")
            print("  [Q] Quit")
            print(f"{Colors.CYAN}─────────────────────────────────────────────{Colors.END}")
            
            choice = input("\n  Enter choice: ").strip().upper()
            
            if choice == '1':
                test_connectivity()
            elif choice == '2':
                test_live_monitoring()
            elif choice == '3':
                test_trigger_detection()
            elif choice == '4':
                test_bounce_analysis()
            elif choice == '5':
                test_rpm_measurement()
            elif choice == '6':
                print_wiring_guide()
            elif choice == '7':
                quick_diagnostic()
            elif choice == 'A':
                test_connectivity()
                test_live_monitoring()
                test_trigger_detection()
                test_bounce_analysis()
                test_rpm_measurement()
                quick_diagnostic()
            elif choice == 'Q':
                print("\nExiting...")
                break
            else:
                print_warn("Invalid choice, try again")
                
    except KeyboardInterrupt:
        print("\n\nExiting...")
    finally:
        cleanup_gpio()
        print("GPIO cleaned up. Goodbye!\n")


if __name__ == "__main__":
    main()

