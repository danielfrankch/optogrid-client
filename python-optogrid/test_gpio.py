#!/usr/bin/env python3
"""
Simple GPIO interrupt test script using LGPIO
Tests rising edge detection on GPIO 17
"""

import lgpio
import time
import signal
import sys

# Configuration
GPIO_PIN = 17
BOUNCE_TIME_MS = 200  # milliseconds

def gpio_callback(chip, gpio, level, tick):
    """Callback function for GPIO interrupt"""
    timestamp = time.strftime('%H:%M:%S.%f')[:-3]
    print(f"GPIO {gpio} rising edge detected at {timestamp}")

def signal_handler(sig, frame):
    """Handle Ctrl+C gracefully"""
    print("\nCleaning up GPIO and exiting...")
    lgpio.gpiochip_close(chip)
    sys.exit(0)

def main():
    print("GPIO Interrupt Test with LGPIO")
    print(f"Testing rising edge detection on GPIO {GPIO_PIN}")
    print("Connect GPIO 17 to 3.3V to trigger")
    print("Press Ctrl+C to exit")
    print("-" * 40)
    
    try:
        # Setup signal handler for clean exit
        signal.signal(signal.SIGINT, signal_handler)
        
        # Open GPIO chip
        global chip
        chip = lgpio.gpiochip_open(0)  # Open GPIO chip 0
        
        # Setup GPIO pin
        lgpio.gpio_claim_input(chip, GPIO_PIN)
        
        # Add interrupt detection
        lgpio.gpio_set_debounce(chip, GPIO_PIN, BOUNCE_TIME_MS)
        lgpio.gpio_register_callback(chip, GPIO_PIN, lgpio.RISING_EDGE, gpio_callback)
        
        print("GPIO interrupt setup complete. Waiting for triggers...")
        
        # Keep the program running
        while True:
            time.sleep(0.1)
            
    except Exception as e:
        print(f"Error: {e}")
    finally:
        lgpio.gpiochip_close(chip)
        print("GPIO cleaned up")

if __name__ == "__main__":
    main()