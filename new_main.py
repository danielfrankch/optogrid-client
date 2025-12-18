"""
OptoGrid Client - Main Entry Point
Supports both GUI and headless modes.
"""

import sys
import argparse
import asyncio

# Parse command line arguments
parser = argparse.ArgumentParser(description='OptoGrid BLE Client')
parser.add_argument('--headless', action='store_true', help='Run in headless mode without GUI')
parser.add_argument('--gui', action='store_true', help='Run in GUI mode (default)')
args = parser.parse_args()

# Determine mode
if args.headless:
    mode = 'headless'
elif args.gui:
    mode = 'gui'
else:
    # Default to GUI, but check if PyQt is available
    mode = 'gui'

# Check PyQt availability if GUI mode requested
if mode == 'gui':
    try:
        from PyQt5.QtWidgets import QApplication
        print("PyQt5 detected - starting in GUI mode...")
    except ImportError:
        print("Warning: PyQt5 not available. Falling back to headless mode.")
        print("To run in GUI mode, install: pip install -r requirements-gui.txt")
        mode = 'headless'

# Import backend
from optogrid_client import OptoGridClient


def main():
    """Main application entry point"""
    
    # Create backend client
    client = OptoGridClient()
    
    # Start ZMQ server
    client.start()
    
    try:
        if mode == 'gui':
            # GUI mode
            print("Starting OptoGrid Client in GUI mode...")
            
            # Import GUI (only when needed)
            from gui import OptoGridGUI
            
            # Create Qt application
            app = QApplication(sys.argv)
            app.setApplicationName("OptoGrid BLE Browser")
            app.setApplicationVersion("2.0")
            
            # Create main window with backend client
            window = OptoGridGUI(client)
            window.show()
            window.raise_()
            window.activateWindow()
            
            # Run Qt event loop
            sys.exit(app.exec_())
            
        else:
            # Headless mode
            print("Starting OptoGrid Client in headless mode...")
            print("ZMQ server ready for remote control.")
            print("Press Ctrl+C to exit.")
            
            # Run backend loop
            asyncio.run(client.run())
            
    except KeyboardInterrupt:
        print("\nShutting down...")
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Cleanup
        if mode == 'headless':
            # In headless mode, cleanup is already done in run()
            pass
        else:
            # In GUI mode, ensure cleanup
            try:
                future = client.run_coro_threadsafe(client.cleanup())
                future.result(timeout=5)
            except Exception as e:
                print(f"Cleanup error: {e}")


if __name__ == "__main__":
    main()
