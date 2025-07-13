"""
Test script for OptoGrid Python class
Python version of test_optogrid_class.m
"""

from optogrid import OptoGrid
import time

def main():
    print("Starting OptoGrid Python test...")
    
    # Test 0: Create and start OptoGrid object
    print("\n=== Test 0: Initialize OptoGrid ===")
    og = OptoGrid()
    og.start()
    print("OptoGrid object created and started")
    
    # Test 4: Program OptoGrid
    print("\n=== Test 4: Program OptoGrid ===")
    print(f"Programming with settings: {og.opto_setting}")
    result = og.program()
    if result:
        print("Program: Success")
    else:
        print("Program: Failed")
        
    # Wait a moment after trigger
    time.sleep(2)
    
    

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nTest interrupted by user")
    except Exception as e:
        print(f"\nTest failed with error: {e}")