#!/usr/bin/env python3
"""
Simple GPIO interrupt test script using gpiozero
Tests rising edge detection on GPIO 17
"""

from gpiozero import Button
import time
import signal
import sys

# Configuration
GPIO_PIN = 17

def gpio_callback():
    """Callback function for GPIO interrupt"""
    timestamp = time.strftime('%H:%M:%S.%f')[:-3]
    print(f"GPIO {GPIO_PIN} rising edge detected at {timestamp}")

def signal_handler(sig, frame):
    """Handle Ctrl+C gracefully"""
    print("\nExiting...")
    sys.exit(0)

def main():
    print("GPIO Interrupt Test with gpiozero")
    print(f"Testing rising edge detection on GPIO {GPIO_PIN}")
    print("Connect GPIO 17 to 3.3V to trigger")
    print("Press Ctrl+C to exit")
    print("-" * 40)
    
    try:
        # Setup signal handler for clean exit
        signal.signal(signal.SIGINT, signal_handler)
        
        # Setup GPIO pin with gpiozero
        button = Button(GPIO_PIN, pull_up=False)
        button.when_pressed = gpio_callback
        
        print("GPIO interrupt setup complete. Waiting for triggers...")
        
        # Keep the program running
        while True:
            time.sleep(0.1)
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()