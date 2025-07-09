#!/usr/bin/env python3
"""
Simple GPIO interrupt test script
Tests rising edge detection on GPIO 17
"""

import RPi.GPIO as GPIO
import time
import signal
import sys

# Configuration
GPIO_PIN = 17
BOUNCE_TIME = 200  # milliseconds

def gpio_callback(channel):
    """Callback function for GPIO interrupt"""
    timestamp = time.strftime('%H:%M:%S.%f')[:-3]
    print(f"GPIO {channel} rising edge detected at {timestamp}")

def signal_handler(sig, frame):
    """Handle Ctrl+C gracefully"""
    print("\nCleaning up GPIO and exiting...")
    GPIO.cleanup()
    sys.exit(0)

def main():
    print("GPIO Interrupt Test")
    print(f"Testing rising edge detection on GPIO {GPIO_PIN}")
    print("Connect GPIO 17 to 3.3V to trigger")
    print("Press Ctrl+C to exit")
    print("-" * 40)
    
    try:
        # Setup signal handler for clean exit
        signal.signal(signal.SIGINT, signal_handler)
        
        # Setup GPIO
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(GPIO_PIN, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
        
        # Test initial pin state
        initial_state = GPIO.input(GPIO_PIN)
        print(f"Initial GPIO {GPIO_PIN} state: {initial_state}")
        
        # Add interrupt detection
        GPIO.add_event_detect(
            GPIO_PIN, 
            GPIO.RISING, 
            callback=gpio_callback, 
            bouncetime=BOUNCE_TIME
        )
        
        print("GPIO interrupt setup complete. Waiting for triggers...")
        
        # Keep the program running
        while True:
            time.sleep(0.1)
            
    except RuntimeError as e:
        print(f"GPIO RuntimeError: {e}")
        print("Make sure you're running on a Raspberry Pi")
        
    except Exception as e:
        print(f"Error: {e}")
        
    finally:
        GPIO.cleanup()
        print("GPIO cleaned up")

if __name__ == "__main__":
    main()