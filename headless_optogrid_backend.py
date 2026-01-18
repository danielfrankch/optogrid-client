import asyncio
import struct
import threading
from typing import Optional
import os
import zmq
import numpy as np
import csv
import datetime
from ahrs.filters import EKF
from ahrs.common.orientation import q2euler
import logging
from bleak import BleakScanner, BleakClient, BLEDevice
import signal
import socket
import time
import json

try:
    from gpiozero import Button, OutputDevice
    GPIO_AVAILABLE = True
except ImportError:
    GPIO_AVAILABLE = False

# Constants and mappings
UUID_NAME_MAP = {
    # Services
    "56781400-5678-1234-1234-5678abcdeff0": "Device Info",
    "56781401-5678-1234-1234-5678abcdeff0": "Opto Control",
    "56781402-5678-1234-1234-5678abcdeff0": "Data Streaming",
    "0000fe59-0000-1000-8000-00805f9b34fb": "Secure DFU",

    # Device Info Characteristics
    "56781500-5678-1234-1234-5678abcdeff0": "Device ID",
    "56781501-5678-1234-1234-5678abcdeff0": "Firmware Version",
    "56781503-5678-1234-1234-5678abcdeff0": "uLED Color",
    "56781504-5678-1234-1234-5678abcdeff0": "uLED Check",
    "56781506-5678-1234-1234-5678abcdeff0": "Battery Voltage",
    "56781507-5678-1234-1234-5678abcdeff0": "Status LED state",
    "56781508-5678-1234-1234-5678abcdeff0": "Sham LED state",
    "56781509-5678-1234-1234-5678abcdeff0": "Device Log",
    "5678150a-5678-1234-1234-5678abcdeff0": "Last Stim Time",

    # Opto Control Characteristics
    "56781600-5678-1234-1234-5678abcdeff0": "Sequence Length",
    "56781601-5678-1234-1234-5678abcdeff0": "LED Selection",
    "56781602-5678-1234-1234-5678abcdeff0": "Duration",
    "56781603-5678-1234-1234-5678abcdeff0": "Period",
    "56781604-5678-1234-1234-5678abcdeff0": "Pulse Width",
    "56781605-5678-1234-1234-5678abcdeff0": "Amplitude",
    "56781606-5678-1234-1234-5678abcdeff0": "PWM Frequency",
    "56781607-5678-1234-1234-5678abcdeff0": "Ramp Up Time",
    "56781608-5678-1234-1234-5678abcdeff0": "Ramp Down Time",
    "56781609-5678-1234-1234-5678abcdeff0": "Trigger",

    # IMU Characteristics
    "56781700-5678-1234-1234-5678abcdeff0": "IMU Enable",
    "56781701-5678-1234-1234-5678abcdeff0": "IMU Sample Rate",
    "56781702-5678-1234-1234-5678abcdeff0": "IMU Resolution",
    "56781703-5678-1234-1234-5678abcdeff0": "IMU Data",

    # Secure DFU Characteristics
    "8ec90003-f315-4f60-9fb8-838830daea50": "Buttonless DFU Without Bonds"
}

uuid_to_type = {
    # Device Info
    "56781500-5678-1234-1234-5678abcdeff0": "string",
    "56781501-5678-1234-1234-5678abcdeff0": "string",
    "56781503-5678-1234-1234-5678abcdeff0": "string",
    "56781504-5678-1234-1234-5678abcdeff0": "uint64",
    "56781506-5678-1234-1234-5678abcdeff0": "uint16",
    "56781507-5678-1234-1234-5678abcdeff0": "bool",
    "56781508-5678-1234-1234-5678abcdeff0": "bool",
    "56781509-5678-1234-1234-5678abcdeff0": "string",
    "5678150a-5678-1234-1234-5678abcdeff0": "uint32",

    # Opto Control
    "56781600-5678-1234-1234-5678abcdeff0": "uint8",
    "56781601-5678-1234-1234-5678abcdeff0": "uint64",
    "56781602-5678-1234-1234-5678abcdeff0": "uint16",
    "56781603-5678-1234-1234-5678abcdeff0": "uint16",
    "56781604-5678-1234-1234-5678abcdeff0": "uint16",
    "56781605-5678-1234-1234-5678abcdeff0": "uint8",
    "56781606-5678-1234-1234-5678abcdeff0": "uint32",
    "56781607-5678-1234-1234-5678abcdeff0": "uint16",
    "56781608-5678-1234-1234-5678abcdeff0": "uint16",
    "56781609-5678-1234-1234-5678abcdeff0": "bool",

    # IMU
    "56781700-5678-1234-1234-5678abcdeff0": "bool",
    "56781701-5678-1234-1234-5678abcdeff0": "uint8",
    "56781702-5678-1234-1234-5678abcdeff0": "uint8",
    "56781703-5678-1234-1234-5678abcdeff0": "uint32+int16[9]",

    # Secure DFU
    "8ec90003-f315-4f60-9fb8-838830daea50": "bool"
}

def decode_value(uuid: str, data: bytes) -> str:
    """Decode byte data based on UUID type mapping"""
    type_str = uuid_to_type.get(uuid, "hex")
    try:
        if type_str == "string":
            return data.decode("utf-8").rstrip("\x00")
        elif type_str == "uint8":
            return str(data[0])
        elif type_str == "uint16":
            return str(int.from_bytes(data[:2], byteorder='little'))
        elif type_str == "uint32":
            return str(int.from_bytes(data[:4], byteorder='little'))
        elif type_str == "uint64":
            return str(int.from_bytes(data[:8], byteorder='little'))
        elif type_str == "float":
            return str(struct.unpack('<f', data[:4])[0])
        elif type_str == "bool":
            return "True" if data[0] == 1 else "False"
        elif type_str == "uint32+int16[9]":
            # First 4 bytes: uint32 sample count
            sample_count = int.from_bytes(data[:4], byteorder='little')
            # Next 18 bytes: 9 int16 values (2 bytes each)
            imu_values = [struct.unpack('<h', data[4+i:4+i+2])[0] for i in range(0, 18, 2)]
            return f"{sample_count}, " + ", ".join(str(val) for val in imu_values)
        else:
            return data.hex()
    except Exception:
        return "<decode error>"

def encode_value(uuid: str, value_str: str) -> bytes:
    """Convert string input to bytes for writing to BLE characteristic"""
    type_str = uuid_to_type.get(uuid, "hex")
    try:
        if type_str == "string":
            return value_str.encode("utf-8")
        elif type_str == "uint8":
            return struct.pack('<B', int(value_str))
        elif type_str == "uint16":
            return struct.pack('<H', int(value_str))
        elif type_str == "uint32":
            return struct.pack('<I', int(value_str))
        elif type_str == "uint64":
            return struct.pack('<Q', int(value_str))
        elif type_str == "float":
            return struct.pack('<f', float(value_str))
        elif type_str == "bool":
            return struct.pack('<B', 1 if value_str.lower() in ['true', '1', 'yes'] else 0)
        else:
            return bytes.fromhex(value_str.replace(' ', ''))
    except Exception as e:
        raise ValueError(f"Failed to encode value '{value_str}' as {type_str}: {e}")

class HeadlessOptoGridClient:
    """Headless OptoGrid BLE client controlled by ZMQ"""
    
    def __init__(self):
        self.setup_logging()
        
        # BLE client state
        self.client: Optional[BleakClient] = None
        self.selected_device: Optional[BLEDevice] = None
        self.led_selection_value = 0
        self.imu_enable_state = False
        self.imu_counter = 0
        
        # REQ/REP ZMQ socket for MATLAB commands
        self.zmq_context = zmq.Context()
        self.zmq_socket = self.zmq_context.socket(zmq.REP)
        ip = get_ip()
        self.zmq_socket.bind(f"tcp://0.0.0.0:5555")
        self.logger.info(f"ZMQ REP server listening on tcp://{ip}:5555...")
        
        # PUB/SUB ZMQ socket for streaming GUI updates
        self.zmq_pub_socket = self.zmq_context.socket(zmq.PUB)
        self.zmq_pub_socket.bind(f"tcp://0.0.0.0:5556")
        self.logger.info(f"ZMQ PUB server publishing on tcp://{ip}:5556...")
        
        # IMU processing setup
        self.setup_imu_processing()
        
        # Data buffers and file handling
        self.imu_data_buffer = []
        self.imu_logging_active = False
        self.current_battery_voltage = None
        self.parquet_writer = None
        
        # Setup GPIO with nuclear option
        if GPIO_AVAILABLE:
            try:
                # GPIO setup
                self.gpio_pin = 17  # GPIO pin to monitor
                self.setup_gpio_trigger(self.gpio_pin)
                

                self.pulse_pin = 27  # GPIO pin for pulse output
                self.pulse_out = OutputDevice(self.pulse_pin, initial_value=False)
            except Exception as e:
                self.logger.error(f"GPIO setup completely failed: {e}")
                # Don't exit, continue without GPIO
        
        # Store the main event loop
        self.loop = asyncio.get_event_loop()

        # Start a new loop just for BLE operations
        self.ble_loop = asyncio.new_event_loop()  # Dedicated event loop for BLE
        threading.Thread(target=self.start_ble_loop, daemon=True).start()

        # Signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
        
        self.running = True
        
    def start_ble_loop(self):
        """Start the dedicated BLE event loop"""
        asyncio.set_event_loop(self.ble_loop)
        self.ble_loop.run_forever()

    def setup_logging(self):
        """Setup logging configuration"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.StreamHandler(),
                logging.FileHandler('optogrid_headless.log')
            ]
        )
        self.logger = logging.getLogger(__name__)

    def setup_imu_processing(self):
        """Initialize IMU processing parameters"""
        self.var_acc = 0.0001
        self.var_gyro = 10
        self.var_mag = 0.1
        self.var_declination = 0.0
        
        self.fusion_filter = EKF(
            frequency=100,  # Default 100Hz
            var_acc=self.var_acc,
            var_gyro=self.var_gyro,
            var_mag=self.var_mag,
            declination=self.var_declination
        )
        self.q = np.array([1.0, 0.0, 0.0, 0.0])
        
        # Initialize magnetometer calibration parameters
        self.mag_offset = np.array([0.0, 0.0, 0.0])
        self.mag_scale = np.array([1.0, 1.0, 1.0])
        
        # Posture smoothing parameters
        self.last_roll = None
        self.last_pitch = None
        self.last_yaw = None
        self.last_mag = np.zeros(3)
    
    def setup_gpio_trigger(self, pin):
        """Setup GPIO pin for rising edge detection using gpiozero"""
        try:
            self.logger.info(f"Setting up GPIO {pin} for rising edge detection...")
            
            # Create a Button object for the pin
            self.button = Button(pin, pull_up=False)
            
            # Attach the callback to the rising edge
            self.button.when_pressed = self.gpio_trigger_callback
            
            self.logger.info(f"GPIO {pin} successfully configured using gpiozero")
        except Exception as e:
            self.logger.error(f"Failed to setup GPIO {pin} using gpiozero: {e}")
    
    def gpio_trigger_callback(self):
        """Callback function for GPIO interrupt"""
        # Trigger device if connected
        if self.client and self.client.is_connected:
            try:
                # Schedule trigger immediately (no latency)
                future = asyncio.run_coroutine_threadsafe(self.do_send_trigger(), self.loop)
                # Add non-blocking callback to check result
                future.add_done_callback(self._on_gpio_trigger_complete)
                self.logger.info("GPIO trigger scheduled")
            except Exception as e:
                self.logger.error(f"Failed to schedule trigger from GPIO: {e}")
        else:
            self.logger.warning("GPIO trigger ignored - device not connected")

        print(f"[GPIOZERO] Rising edge detected on GPIO {self.gpio_pin}")
        self.logger.info(f"Rising edge detected on GPIO {self.gpio_pin}")

    def _on_gpio_trigger_complete(self, future):
        """Handle GPIO trigger completion (success/failure)"""
        try:
            future.result()  # This will raise if there was an exception
            self.logger.info("GPIO trigger executed successfully")
        except Exception as e:
            self.logger.error(f"GPIO trigger failed: {e}")

    def signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        self.logger.info(f"Received signal {signum}, shutting down...")
        self.running = False

    async def run(self):
        """Main run loop"""
        self.logger.info("OptoGrid Headless Client Started")
        
        
        while self.running:
            try:
                # Non-blocking receive with timeout
                try:
                    message = self.zmq_socket.recv_string(zmq.NOBLOCK)
                    self.logger.info(f"Received ZMQ command: {message}")
                    response = await self.handle_command(message)
                    self.zmq_socket.send_string(response)
                except zmq.Again:
                    # No message available, sleep briefly
                    await asyncio.sleep(0.01)
                    continue
                    
            except Exception as e:
                self.logger.error(f"Error in main loop: {e}")
                if self.zmq_socket:
                    try:
                        self.zmq_socket.send_string(f"ERROR: {str(e)}")
                    except:
                        pass
                        
        await self.cleanup()

    async def handle_command(self, message: str) -> str:
        """Handle incoming ZMQ commands"""
        try:
            if "optogrid.trigger" in message:
                return await self.send_trigger()
            
            elif "optogrid.scan" in message:
                return await self.scan_devices()
            
            elif "optogrid.status" in message:
                return await self.get_status()
            
            elif "optogrid.connect" in message:
                device_name = message.split('=')[1].strip()
                return await self.connect_device(device_name)
                
            elif "optogrid.gattread" in message:
                # Check if UUID is specified
                if '=' in message:
                    uuid = message.split('=')[1].strip()
                    return await self.gatt_read(uuid)
                else:
                # Otherwise perform full GATT read
                    return await self.gatt_read()
                
            elif "optogrid.enableIMU" in message:
                return await self.enable_imu()
                
            elif "optogrid.disableIMU" in message:
                return await self.disable_imu()
            
            elif "optogrid.startIMULog" in message:
                # Parse subjid and sessid from message: "optogrid.startIMULog = subjid, sessid"
                try:
                    params = message.split('=')[1].strip()
                    subjid, sessid = [param.strip() for param in params.split(',')]
                    return await self.enable_imu(subjid, sessid)
                except Exception as e:
                    return f"ERROR: Invalid startIMULog parameters: {e}"
            
            elif "optogrid.stopIMULog" in message:
                return await self.disable_imu()
                
            elif "optogrid.readbattery" in message:
                return await self.read_battery()
            
            elif "optogrid.readuLEDCheck" in message:
                return await self.read_uled_check()
            
            elif "optogrid.readlastStim" in message:
                return await self.read_last_stim_time()
                
            elif "optogrid.gattread" in message:
                # Check if UUID is specified
                if '=' in message:
                    uuid = message.split('=')[1].strip()
                    return await self.gatt_read(uuid)
                else:
                    return await self.gatt_read()
                
            elif "optogrid.sync" in message:
                sync_value = int(message.split('=')[1].strip())
                return self.handle_sync(sync_value)
                
            elif "optogrid.toggleStatusLED" in message:
                # Parse value (should be 0 or 1)
                try:
                    led_value = int(message.split('=')[1].strip())
                    return await self.toggle_status_led(led_value)
                except Exception as e:
                    return f"ERROR: Invalid value for toggleStatusLED: {e}"
                
            elif "optogrid.toggleShamLED" in message:
                # Parse value (should be 0 or 1)
                try:
                    led_value = int(message.split('=')[1].strip())
                    return await self.toggle_sham_led(led_value)
                except Exception as e:
                    return f"ERROR: Invalid value for toggleShamLED: {e}"
                
            elif "optogrid.program" in message:
                # Expect program data in the next message
                self.zmq_socket.send_string("Ready for program data")
                program_data = self.zmq_socket.recv_string()
                return await self.program_device(eval(program_data))
            
            return f"Unknown command: {message}"
            
        except Exception as e:
            self.logger.error(f"Command error: {e}")
            return f"ERROR: {str(e)}"

    async def toggle_status_led(self, value: int) -> str:
        """Toggle Status LED on the device (0=off, 1=on)"""
        if not self.client or not self.client.is_connected:
            return "Not connected to device"
        try:
            uuid = "56781507-5678-1234-1234-5678abcdeff0"  # Status LED state
            encoded_value = encode_value(uuid, str(value))
            await self.client.write_gatt_char(uuid, encoded_value)
            state = "on" if value else "off"
            self.logger.info(f"Status LED turned {state}")
            return f"Status LED turned {state}"
        except Exception as e:
            self.logger.error(f"Failed to toggle Status LED: {e}")
            return f"Failed to toggle Status LED: {str(e)}"

    async def toggle_sham_led(self, value: int) -> str:
        """Toggle Sham LED on the device (0=off, 1=on)"""
        if not self.client or not self.client.is_connected:
            return "Not connected to device"
        try:
            uuid = "56781508-5678-1234-1234-5678abcdeff0"  # Sham LED state
            encoded_value = encode_value(uuid, str(value))
            await self.client.write_gatt_char(uuid, encoded_value)
            state = "on" if value else "off"
            self.logger.info(f"Sham LED turned {state}")
            return f"Sham LED turned {state}"
        except Exception as e:
            self.logger.error(f"Failed to toggle Sham LED: {e}")
            return f"Failed to toggle Sham LED: {str(e)}"

    async def scan_devices(self) -> str:
        """Scan for available BLE devices"""
        try:
            self.logger.info("Scanning for BLE devices...")
            devices = await BleakScanner.discover(timeout=4)
            # Filter devices that contain 'O' in their name (capital O only)
            device_list = [f"{d.name} ({d.address})" for d in devices if d.name and 'O' in d.name]
            if device_list:
                self.logger.info(f"Found devices: {device_list}")
                return "\n".join(device_list)
            else:
                self.logger.info("No BLE devices containing 'O' found")
                return "No BLE devices found"
        except Exception as e:
            self.logger.error(f"Scan error: {e}")
            return f"Scan failed: {str(e)}"
    
    async def get_status(self) -> str:
        """Get current connection status"""
        try:
            if self.client and self.client.is_connected:
                if self.selected_device:
                    device_name = getattr(self.selected_device, 'name', 'Unknown Device')
                    device_address = getattr(self.selected_device, 'address', 'Unknown Address')
                    return f"Connected to {device_name} ({device_address})"
                else:
                    return "Connected to Unknown Device"
            else:
                return "Disconnected"
        except Exception as e:
            self.logger.error(f"Status check error: {e}")
            return "Disconnected"
        
    async def connect_device(self, device_identifier: str) -> str:
        """Connect to specified BLE device by UUID/address or name"""
        try:
            # Disconnect existing connection
            if self.client and self.client.is_connected:
                await self.client.disconnect()
                self.client = None
            
            # Check if device_identifier looks like a UUID/MAC address
            # UUID format: XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX
            # MAC format: XX:XX:XX:XX:XX:XX or similar
            is_uuid_or_address = (
                len(device_identifier) == 36 and device_identifier.count('-') == 4 or  # UUID format
                len(device_identifier) == 17 and ':' in device_identifier or  # MAC address format
                len(device_identifier) > 10 and all(c in '0123456789ABCDEFabcdef:-' for c in device_identifier)  # General address format
            )
            
            if is_uuid_or_address:
                # Connect directly using UUID/address without scanning
                self.logger.info(f"Connecting directly to device address: {device_identifier}")
                self.client = BleakClient(
                    device_identifier,
                    disconnected_callback=self.on_disconnect_callback
                )
                await self.client.connect()
                
                # Setup notifications
                await self.setup_notifications()
                
                # For direct connection, we don't have device name initially
                # Try to read device name from GATT characteristic
                device_name = device_identifier
                try:
                    device_name = await self.read_characteristic("56781500-5678-1234-1234-5678abcdeff0")  # Device ID
                except:
                    device_name = f"OptoGrid-{device_identifier[-4:]}"  # Fallback name
                
                # Load magnetometer calibration using device name
                self.load_magnetometer_calibration(device_name)
                
                # Create a mock device object for compatibility
                self.selected_device = type('Device', (), {
                    'name': device_name,
                    'address': device_identifier
                })()
                
                self.logger.info(f"Connected to {device_name} at {device_identifier}")
                return f"{device_name} Connected"
                
            else:
                # Original scanning method for device names
                self.logger.info(f"Scanning for device: {device_identifier}")
                devices = await BleakScanner.discover(timeout=4)
                matching_device = next((d for d in devices if d.name and device_identifier in d.name), None)
                
                if not matching_device:
                    return f"Device {device_identifier} not found"
                
                self.logger.info(f"Connecting to {matching_device.name}...")
                self.client = BleakClient(
                    matching_device.address,
                    disconnected_callback=self.on_disconnect_callback
                )
                await self.client.connect()
                
                # Setup notifications
                await self.setup_notifications()
                
                # Load magnetometer calibration
                self.load_magnetometer_calibration(matching_device.name)
                
                self.selected_device = matching_device
                self.logger.info(f"Connected to {matching_device.name}")
                return f"{matching_device.name} Connected"
            
        except Exception as e:
            self.logger.error(f"Connection error: {e}")
            return f"Connection failed: {str(e)}"

    async def gatt_read(self, uuid: str = None) -> str:
        """Read GATT characteristic(s) - single UUID or all characteristics"""
        if not self.client or not self.client.is_connected:
            return "Not connected to device"
            
        try:
            if uuid:
                # Read single characteristic
                value = await self.read_characteristic(uuid)
                char_name = UUID_NAME_MAP.get(uuid, "Unknown Characteristic")
                return f"{char_name}: {value}"
            else:
                # Read all GATT characteristics - only Opto Control Service plus LED/IMU states
                gatt_table = []
                gatt_table.append("Service,Characteristic,UUID,Value,Unit")
                
                # Opto Control Service characteristics
                opto_control_chars = [
                    ("56781600-5678-1234-1234-5678abcdeff0", "Sequence Length", "count"),
                    ("56781601-5678-1234-1234-5678abcdeff0", "LED Selection", "bitmap"),
                    ("56781602-5678-1234-1234-5678abcdeff0", "Duration", "ms"),
                    ("56781603-5678-1234-1234-5678abcdeff0", "Period", "ms"),
                    ("56781604-5678-1234-1234-5678abcdeff0", "Pulse Width", "us"),
                    ("56781605-5678-1234-1234-5678abcdeff0", "Amplitude", "%"),
                    ("56781606-5678-1234-1234-5678abcdeff0", "PWM Frequency", "Hz"),
                    ("56781607-5678-1234-1234-5678abcdeff0", "Ramp Up Time", "ms"),
                    ("56781608-5678-1234-1234-5678abcdeff0", "Ramp Down Time", "ms")
                ]
                
                for char_uuid, char_name, unit in opto_control_chars:
                    try:
                        value = await self.read_characteristic(char_uuid)
                        service_name = "Opto Control" if char_uuid == opto_control_chars[0][0] else ""
                        gatt_table.append(f"{service_name},{char_name},{char_uuid},{value},{unit}")
                    except Exception as e:
                        gatt_table.append(f",{char_name},{char_uuid},ERROR: {str(e)},{unit}")
                
                # Device state characteristics for GUI updates
                state_chars = [
                    ("56781507-5678-1234-1234-5678abcdeff0", "Status LED state", "bool"),
                    ("56781508-5678-1234-1234-5678abcdeff0", "Sham LED state", "bool"),
                    ("56781700-5678-1234-1234-5678abcdeff0", "IMU Enable", "bool")
                ]
                
                for char_uuid, char_name, unit in state_chars:
                    try:
                        value = await self.read_characteristic(char_uuid)
                        service_name = "Device State" if char_uuid == state_chars[0][0] else ""
                        gatt_table.append(f"{service_name},{char_name},{char_uuid},{value},{unit}")
                    except Exception as e:
                        gatt_table.append(f",{char_name},{char_uuid},ERROR: {str(e)},{unit}")
                
                return "\n".join(gatt_table)
                
        except Exception as e:
            self.logger.error(f"GATT read error: {e}")
            return f"GATT read failed: {str(e)}"

    async def setup_notifications(self):
        """Setup BLE notifications"""
        try:
            # Device log notifications
            device_log_uuid = "56781509-5678-1234-1234-5678abcdeff0"
            await self.client.start_notify(device_log_uuid, self.handle_device_log_notification)
            
            # IMU data notifications
            imu_data_uuid = "56781703-5678-1234-1234-5678abcdeff0"
            await self.client.start_notify(imu_data_uuid, self.handle_imu_data_notification)
            
            # LED check notifications
            # led_check_uuid = "56781504-5678-1234-1234-5678abcdeff0"
            # await self.client.start_notify(led_check_uuid, self.handle_led_check_notification)
            
            self.logger.info("BLE notifications enabled")
            
            # Update IMU filter frequency from device
            await self.update_imu_filter_frequency()
            
        except Exception as e:
            self.logger.error(f"Notification setup error: {e}")
            raise

    async def update_imu_filter_frequency(self):
        """Update IMU filter frequency from device settings"""
        try:
            imu_sample_rate_uuid = "56781701-5678-1234-1234-5678abcdeff0"
            val = await self.client.read_gatt_char(imu_sample_rate_uuid)
            imu_sample_rate = int.from_bytes(val[:2], byteorder='little')
            if imu_sample_rate > 0:
                self.fusion_filter = EKF(
                    frequency=imu_sample_rate,
                    var_acc=self.var_acc,
                    var_gyro=self.var_gyro,
                    var_mag=self.var_mag,
                    declination=self.var_declination
                )
                self.logger.info(f"EKF filter frequency set to {imu_sample_rate} Hz")
        except Exception as e:
            self.logger.warning(f"Could not read IMU sample rate: {e}")

    def on_disconnect_callback(self, client):
        """Handle unexpected disconnections"""
        self.logger.warning(f"BLE device disconnected unexpectedly at sample {self.imu_counter}")
        
        # Flush any remaining IMU data
        if self.imu_data_buffer:
            self.flush_imu_buffer()
            self.logger.info(f"Flushed {len(self.imu_data_buffer)} remaining samples")
        
        # Close IMU file if open
        if self.imu_logging_active:
            self.stop_IMU_logging()
            self.rsync_imu_log()
            self.imu_enable_state = False

    async def handle_device_log_notification(self, sender: int, data: bytearray):
        """Handle device log notifications"""
        try:
            null_index = data.find(0)
            if null_index != -1:
                message = data[:null_index].decode('utf-8', errors='replace')
            else:
                message = data.decode('utf-8', errors='replace')
            self.logger.info(f"ble_log: {message}")
        except Exception as e:
            self.logger.error(f"Error in device log handler: {str(e)}")

    async def handle_led_check_notification(self, sender: int, data: bytearray):
        """Handle LED check notifications"""
        try:
            led_check_val = int.from_bytes(data[:8], byteorder='little')
            self.logger.info(f"LED check updated: {led_check_val:064b}")
        except Exception as e:
            self.logger.error(f"Error in LED check handler: {str(e)}")

    async def handle_imu_data_notification(self, sender: int, data: bytearray):
        """Handle IMU data notifications"""
        try:
            imu_uuid = "56781703-5678-1234-1234-5678abcdeff0"
            imu_values_str = decode_value(imu_uuid, data)
            imu_values = [int(x.strip()) for x in imu_values_str.split(",")]
            self.imu_counter += 1
            
            if self.imu_counter % 30000 == 0:  # Log every 30000th message
                self.logger.debug(f"IMU Data: {imu_values_str}")

            # Process orientation using AHRS sensor fusion
            smooth_roll, smooth_pitch, smooth_yaw = self.process_imu_orientation(imu_values)

            if self.imu_counter % 30000 == 0:  # Log orientation every 30000th sample
                self.logger.info(f"Orientation - Roll: {smooth_roll:.1f}°, Pitch: {smooth_pitch:.1f}°, Yaw: {smooth_yaw:.1f}°")

            # Buffer IMU data if logging is enabled
            if self.imu_enable_state:
                uncertainty = None
                if hasattr(self.fusion_filter, "P"):
                    try:
                        uncertainty = float(np.trace(self.fusion_filter.P))
                    except Exception:
                        uncertainty = None

                # Prepare data for logging
                imu_data_with_sync = imu_values + [0]  # Add sync value (default 0)
                
                battery_v = None
                if self.current_battery_voltage is not None:
                    battery_v = self.current_battery_voltage
                    self.current_battery_voltage = None

                row = imu_data_with_sync + [smooth_roll, smooth_pitch, smooth_yaw, uncertainty, battery_v]
                self.imu_data_buffer.append(row)
                
                if len(self.imu_data_buffer) >= 100:
                    self.flush_imu_buffer()

            # Publish orientation update via ZMQ PUB socket
            self.publish_imu_data(smooth_roll, smooth_pitch, smooth_yaw)
            


        except Exception as e:
            self.logger.error(f"Error in IMU data handler: {str(e)}")

    def process_imu_orientation(self, imu_values):
        """Process IMU data and calculate orientation"""
        acc_x, acc_y, acc_z = imu_values[1:4]
        gyro_x, gyro_y, gyro_z = imu_values[4:7]
        mag_x, mag_y, mag_z = imu_values[7:10]

        # Apply calibration to magnetometer
        mag_raw = np.array([mag_x, mag_y, mag_z])
        mag_calibrated = (mag_raw - self.mag_offset) * self.mag_scale
        
        # Convert units
        acc = np.array([acc_x, acc_y, acc_z]) * (32.0 / 65536.0)  # g
        gyr = np.array([gyro_x, gyro_y, gyro_z]) * (4000.0 / 65536.0)  # dps
        mag = mag_calibrated * (100.0 / 65536.0)  # gauss

        # Transform to device frame
        acc_world = np.array([acc[0], -acc[1], -acc[2]])  
        gyr_world = np.array([gyr[0], -gyr[1], -gyr[2]])
        mag_world = np.array([mag[1], -mag[0], -mag[2]])  

        # Zero small gyro values
        gyro_noise_threshold = 5
        gyr_world = np.where(np.abs(gyr_world) < gyro_noise_threshold, 0, gyr_world)

        # Validate magnetometer
        mag_magnitude = np.linalg.norm(mag)
        is_mag_valid = mag_magnitude > 0.01
        
        if hasattr(self, 'last_mag'):
            mag_change = np.linalg.norm(mag - self.last_mag)
            if mag_change > 2.0:
                is_mag_valid = False
        
        self.last_mag = mag.copy()

        # Update fusion filter
        if is_mag_valid:
            acc_si = acc_world * 9.80665  # Convert to m/s²
            gyr_si = np.radians(gyr_world)  # Convert to rad/s
            mag_si = mag_world * 100.0  # Convert to µT
            
            self.q = self.fusion_filter.update(
                q=self.q,
                gyr=gyr_si,
                acc=acc_si,
                mag=mag_si
            )
        else:
            acc_si = acc * 9.80665
            gyr_si = np.radians(gyr_world)
            
            self.q = self.fusion_filter.update(
                q=self.q,
                gyr=gyr_si,
                acc=acc_si
            )

        # Convert to Euler angles
        roll, pitch, yaw = np.degrees(q2euler(self.q))
        yaw = (yaw + 360) % 360  # Ensure 0-360 degrees

        # Light smoothing
        if self.last_roll is None:
            smooth_roll, smooth_pitch, smooth_yaw = roll, pitch, yaw
        else:
            alpha_rp = 1  # No smoothing for now
            alpha_yaw = 1
            
            smooth_roll = alpha_rp * roll + (1 - alpha_rp) * self.last_roll
            smooth_pitch = alpha_rp * pitch + (1 - alpha_rp) * self.last_pitch
            
            delta_yaw = ((yaw - self.last_yaw + 180) % 360) - 180
            smooth_yaw = self.last_yaw + alpha_yaw * delta_yaw
            smooth_yaw = (smooth_yaw + 360) % 360

        self.last_roll = smooth_roll
        self.last_pitch = smooth_pitch
        self.last_yaw = smooth_yaw

        return smooth_roll, smooth_pitch, smooth_yaw

    def load_magnetometer_calibration(self, device_name):
        """Load magnetometer calibration from device-specific CSV file"""
        try:
            import pandas as pd
            calibration_filename = f"data/{device_name} Calibration.csv"
            
            if not os.path.exists(calibration_filename):
                self.logger.info(f"Magnetometer calibration file not found: {calibration_filename}")
                self.logger.info("Using default calibration (no offset correction)")
                return False
            
            self.logger.info(f"Loading magnetometer calibration from: {calibration_filename}")
            cal_data = pd.read_csv(calibration_filename)
            
            if not all(col in cal_data.columns for col in ['mag_x', 'mag_y', 'mag_z']):
                self.logger.error("Calibration file missing required magnetometer columns")
                return False
            
            mag_x_data = cal_data['mag_x'].values
            mag_y_data = cal_data['mag_y'].values
            mag_z_data = cal_data['mag_z'].values
            
            # Calculate hard-iron offsets
            mag_x_offset = (np.max(mag_x_data) + np.min(mag_x_data)) / 2
            mag_y_offset = (np.max(mag_y_data) + np.min(mag_y_data)) / 2
            mag_z_offset = (np.max(mag_z_data) + np.min(mag_z_data)) / 2
            
            self.mag_offset = np.array([mag_x_offset, mag_y_offset, mag_z_offset])
            
            # Calculate soft-iron scale factors
            mag_x_range = np.max(mag_x_data) - np.min(mag_x_data)
            mag_y_range = np.max(mag_y_data) - np.min(mag_y_data)
            mag_z_range = np.max(mag_z_data) - np.min(mag_z_data)
            
            avg_range = (mag_x_range + mag_y_range + mag_z_range) / 3
            
            self.mag_scale = np.array([
                avg_range / mag_x_range if mag_x_range > 0 else 1.0,
                avg_range / mag_y_range if mag_y_range > 0 else 1.0,
                avg_range / mag_z_range if mag_z_range > 0 else 1.0
            ])
            
            self.logger.info(f"Magnetometer calibration loaded successfully:")
            self.logger.info(f"  Hard-iron offsets: X={mag_x_offset:.2f}, Y={mag_y_offset:.2f}, Z={mag_z_offset:.2f}")
            self.logger.info(f"  Soft-iron scales: X={self.mag_scale[0]:.3f}, Y={self.mag_scale[1]:.3f}, Z={self.mag_scale[2]:.3f}")
            self.logger.info(f"  Data points used: {len(mag_x_data)}")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error loading magnetometer calibration: {str(e)}")
            return False

    def flush_imu_buffer(self):
        """Write buffered IMU data to parquet"""
        if not self.imu_data_buffer:
            return
            
        try:
            if self.parquet_writer:
                # Write to parquet file using pyarrow
                import pyarrow as pa
                import pandas as pd
                
                # Data is already clean with None values - no conversion needed
                df = pd.DataFrame(self.imu_data_buffer, columns=self.imu_data_columns)
                
                # Handle None values in bat_v column to match schema
                df['bat_v'] = df['bat_v'].astype('float64')
                df['uncertainty'] = df['uncertainty'].astype('float64')
                
                table = pa.Table.from_pandas(df, schema=self.parquet_schema, preserve_index=False)
                self.parquet_writer.write_table(table)
                
            self.imu_data_buffer = []
            
        except Exception as e:
            self.logger.error(f"Error flushing IMU buffer: {e}")

    def start_IMU_logging(self, subjid="NoSubjID", sessid="NoSessID", deviceid="NoDeviceID"):
        """Start IMU logging to parquet file"""
        if self.imu_logging_active:
            self.logger.warning("IMU logging already active")
            return None
            
        filename = None  # Initialize filename variable
        try:
            import pyarrow as pa
            import pyarrow.parquet as pq
            
            # Validate and sanitize input parameters
            if not subjid or str(subjid).strip() == "":
                subjid = "NoSubjID"
            if not sessid or str(sessid).strip() == "":
                sessid = "NoSessID" 
            if not deviceid or str(deviceid).strip() == "":
                deviceid = "NoDeviceID"

            os.makedirs("data/imu_session", exist_ok=True)
            
            timestamp = datetime.datetime.now().strftime("%Y_%m_%d_%H_%M_%S")
            # Ensure sessid is formatted as integer to avoid scientific notation
            try:
                if str(sessid) == "NoSessID":
                    sessid_int = 0  # Default value for "NoSessID"
                else:
                    sessid_int = int(float(str(sessid))) if str(sessid) else 0
            except (ValueError, TypeError):
                self.logger.warning(f"Invalid sessid '{sessid}', using 0")
                sessid_int = 0
            
            filename = f"data/imu_session/{subjid}_{sessid_int}_{deviceid}_{timestamp}.parquet"
            
            # Create column structure for parquet
            self.imu_data_columns = [
                "sample", 
                "acc_x", "acc_y", "acc_z", 
                "gyro_x", "gyro_y", "gyro_z",
                "mag_x", "mag_y", "mag_z", 
                "sync", "roll", "pitch", "yaw", 
                "uncertainty", "bat_v"
            ]
            
            # Define schema for parquet file
            schema = pa.schema([
                pa.field("sample", pa.int64()),
                pa.field("acc_x", pa.int64()),
                pa.field("acc_y", pa.int64()),
                pa.field("acc_z", pa.int64()),
                pa.field("gyro_x", pa.int64()),
                pa.field("gyro_y", pa.int64()),
                pa.field("gyro_z", pa.int64()),
                pa.field("mag_x", pa.int64()),
                pa.field("mag_y", pa.int64()),
                pa.field("mag_z", pa.int64()),
                pa.field("sync", pa.int64()),
                pa.field("roll", pa.float64()),
                pa.field("pitch", pa.float64()),
                pa.field("yaw", pa.float64()),
                pa.field("uncertainty", pa.float64()),
                pa.field("bat_v", pa.float64())
            ])
            
            # Store schema for later use
            self.parquet_schema = schema
            
            # Create parquet writer
            self.parquet_writer = pq.ParquetWriter(filename, schema, compression='snappy')
            self.imu_parquet_file = filename
            self.imu_logging_active = True
            
            self.logger.info(f"IMU logging started: {filename}")
            return filename
            
        except Exception as e:
            self.logger.error(f"Failed to start IMU logging: {e}")
            return None

    def stop_IMU_logging(self):
        """Stop IMU logging and write final parquet file"""
        if not self.imu_logging_active:
            self.logger.warning("No active IMU logging to stop")
            return
            
        try:
            # Flush final buffer to parquet
            if self.imu_data_buffer:
                self.flush_imu_buffer()
            
            # Close parquet writer
            if self.parquet_writer:
                self.parquet_writer.close()
                self.parquet_writer = None
                
            # Reset logging state
            self.imu_logging_active = False
            if hasattr(self, 'imu_parquet_file'):
                self.imu_parquet_file = None
            
            self.logger.info("IMU logging stopped and file closed")
            
        except Exception as e:
            self.logger.error(f"Error stopping IMU logging: {e}")
    
    async def send_trigger(self) -> str:
        """Send trigger command"""
        if not self.client or not self.client.is_connected:
            return "Not connected to device"
            
        try:
            await self.do_send_trigger()
            return "Opto Triggered"
        except Exception as e:
            return f"Trigger failed: {str(e)}"

    async def do_send_trigger(self):
        """Perform the actual trigger operation"""
        trigger_uuid = "56781609-5678-1234-1234-5678abcdeff0"
        encoded_value = encode_value(trigger_uuid, "True")
        await self.client.write_gatt_char(trigger_uuid, encoded_value)
        self.logger.info("Sent opto trigger")
        
        # Record a sync event in IMU logging
        if self.imu_logging_active:
            self.handle_sync(int(65536))
        else:
            self.logger.warning("IMU logging not active, sync event not recorded")
            self.handle_sync(int(65536))

    async def enable_imu(self, subjid="NoSubjID", sessid="NoSessID") -> str:
        """Enable IMU and start logging"""
        if not self.client or not self.client.is_connected:
            return "Not connected to device"
            
        try:
            # Enable IMU
            imu_enable_uuid = "56781700-5678-1234-1234-5678abcdeff0"
            encoded_value = encode_value(imu_enable_uuid, "True")
            await self.client.write_gatt_char(imu_enable_uuid, encoded_value)
            
            # Setup logging using new function
            if not self.imu_logging_active:
                # Try to get device ID for filename
                try:
                    device_id = await self.read_characteristic("56781500-5678-1234-1234-5678abcdeff0")
                except:
                    device_id = "NoDeviceID"
                    
                filename = self.start_IMU_logging(subjid=subjid, sessid=sessid, deviceid=device_id)
                if not filename:
                    return "IMU enabled but logging failed to start"
            
            self.imu_enable_state = True
            return "IMU enabled, and logging started"
            
        except Exception as e:
            return f"IMU enable failed: {str(e)}"

    async def disable_imu(self) -> str:
        """Disable IMU and stop logging"""
        if not self.client or not self.client.is_connected:
            return "Not connected to device"
            
        try:
            # Disable IMU
            imu_enable_uuid = "56781700-5678-1234-1234-5678abcdeff0"
            encoded_value = encode_value(imu_enable_uuid, "False")
            await self.client.write_gatt_char(imu_enable_uuid, encoded_value)
            
            # Stop logging using new function
            self.stop_IMU_logging()
            
            # Rsync IMU log files to remote server
            self.rsync_imu_log()
            
            self.imu_enable_state = False
            return "IMU disabled, and logging stopped"
            
        except Exception as e:
            return f"IMU disable failed: {str(e)}"

    def rsync_imu_log(self):
        """Rsync IMU log files to remote server"""
        try:
            import subprocess
            import glob
            import platform
            
            # Check if data/imu_session directory exists
            imu_session_path = "data/imu_session"
            if not os.path.exists(imu_session_path):
                self.logger.info("No IMU session directory found, creating it")
                os.makedirs(imu_session_path, exist_ok=True)
                return
            
            # Find all parquet files in the imu_session directory
            parquet_files = glob.glob(os.path.join(imu_session_path, "*.parquet"))
            
            if not parquet_files:
                self.logger.info("No parquet files found for rsync")
                return
            
            # Get operating system
            os_type = platform.system()
            
            if os_type == "Linux":
                # Linux: Use rsync
                try:
                    # Rsync all parquet files to remote directory
                    remote_path = f"ogma:/ceph/ogma/IMU"
                    rsync_cmd = f"rsync -avzP --remove-source-files {' '.join(parquet_files)} {remote_path}"
                    
                    self.logger.info(f"Rsyncing {len(parquet_files)} files")
                    self.logger.info(f"Command: {rsync_cmd}")
                    
                    # Execute rsync command
                    result = subprocess.Popen(rsync_cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                    stdout, stderr = result.communicate()
                    
                    if result.returncode == 0:
                        self.logger.info(f"Successfully rsynced all files")
                    else:
                        self.logger.error(f"Rsync failed: {stderr.decode()}")
                        
                except Exception as e:
                    self.logger.error(f"Error rsyncing files: {e}")
            
            elif os_type == "Windows":
                # Windows: TODO - implement Windows-specific file transfer
                self.logger.info("Windows file transfer not implemented yet")
                pass
            
            elif os_type == "Darwin":  # macOS
                # macOS: TODO - implement macOS-specific file transfer
                self.logger.info("macOS file transfer not implemented yet")
                pass
            
            else:
                self.logger.warning(f"Unsupported operating system: {os_type}")
            
        except Exception as e:
            self.logger.error(f"Error in rsync_imu_log: {e}")


    async def read_battery(self) -> str:
        """Read battery voltage"""
        if not self.client or not self.client.is_connected:
            return "Not connected to device"
            
        try:
            device_name = await self.read_characteristic("56781500-5678-1234-1234-5678abcdeff0")
            voltage_str = await self.read_characteristic("56781506-5678-1234-1234-5678abcdeff0")
            voltage = int(voltage_str)
            
            self.current_battery_voltage = voltage / 1000.0  # Store for IMU logging
            return f"{device_name} Battery Voltage = {voltage} mV"
        except Exception as e:
            return f"Battery read failed: {str(e)}"

    async def read_uled_check(self) -> str:
        """Read uLED Check value"""
        if not self.client or not self.client.is_connected:
            return "Not connected to device"
        
        try:
            # UUID for uLED Check characteristic
            uled_check_uuid = "56781504-5678-1234-1234-5678abcdeff0"
            
            # Read the characteristic value
            uled_check_value = await self.read_characteristic(uled_check_uuid)
            
            # Log and return the value
            self.logger.info(f"uLED Check: {uled_check_value}")
            return f"uLED Check = {uled_check_value}"
        except Exception as e:
            self.logger.error(f"Failed to read uLED Check: {e}")
            return f"uLED Check read failed: {str(e)}"
        
    async def read_last_stim_time(self) -> str:
        """Read the last stimulation time"""
        if not self.client or not self.client.is_connected:
            return "Not connected to device"
        
        try:
            # UUID for Last Stim Time characteristic
            last_stim_uuid = "5678150a-5678-1234-1234-5678abcdeff0"
            
            # Read the characteristic value
            last_stim_value = await self.read_characteristic(last_stim_uuid)
            
            # Log and return the value
            self.logger.info(f"Last Stim Time: {last_stim_value} ms")
            return f"Last Stim Time = {last_stim_value} ms"
        except Exception as e:
            self.logger.error(f"Failed to read Last Stim Time: {e}")
            return f"Last Stim Time read failed: {str(e)}"
        
    async def read_characteristic(self, uuid: str) -> str:
        """Read a characteristic value and decode it"""
        val = await self.client.read_gatt_char(uuid)
        return decode_value(uuid, val)

    def handle_sync(self, sync_value: int) -> str:
        """Handle sync value for IMU data"""
        if self.imu_data_buffer:
            self.imu_data_buffer[-1][10] = sync_value  # Update sync value in last sample
            self.logger.info(f"Sync value {sync_value} written to IMU data")
            return "Sync Written"
        return "No IMU data buffer available"

    async def program_device(self, program_data: dict) -> str:
        """Program device parameters"""
        if not self.client or not self.client.is_connected:
            return "Not connected to device"
            
        try:
            opto_char_map = {
                "sequence_length": "56781600-5678-1234-1234-5678abcdeff0",
                "led_selection": "56781601-5678-1234-1234-5678abcdeff0",
                "duration": "56781602-5678-1234-1234-5678abcdeff0",
                "period": "56781603-5678-1234-1234-5678abcdeff0",
                "pulse_width": "56781604-5678-1234-1234-5678abcdeff0",
                "amplitude": "56781605-5678-1234-1234-5678abcdeff0",
                "pwm_frequency": "56781606-5678-1234-1234-5678abcdeff0",
                "ramp_up": "56781607-5678-1234-1234-5678abcdeff0",
                "ramp_down": "56781608-5678-1234-1234-5678abcdeff0"
            }
            
            for setting_name, value in program_data.items():
                if setting_name in opto_char_map:
                    uuid = opto_char_map[setting_name]
                    encoded_value = encode_value(uuid, str(value))
                    await self.client.write_gatt_char(uuid, encoded_value)
                    self.logger.info(f"Written {setting_name}: {value}")
                    
                    if setting_name == "led_selection":
                        try:
                            self.led_selection_value = int(value)
                        except ValueError:
                            pass
            
            return "Opto Programmed"
        except Exception as e:
            return f"Programming failed: {str(e)}"

    # Publishing IMU data
    def publish_imu_data(self, roll, pitch, yaw):
        """Publish IMU data to ZMQ PUB socket"""
        imu_message = {
            "type": "imu_update",
            "timestamp": time.time(),
            "roll": roll,
            "pitch": pitch, 
            "yaw": yaw,
        }
        # Send as JSON string with topic prefix
        self.zmq_pub_socket.send_string(f"IMU {json.dumps(imu_message)}")
    
    # Publishing a gui status message
    def publish_gui_status(self, message):
        """Publish GUI status message to ZMQ PUB socket"""
        status_data = {
            "type": "gui_status",
            "timestamp": time.time(),
            "message": message
        }
        self.zmq_pub_socket.send_string(f"GUI {json.dumps(status_data)}")

    async def cleanup(self):
        """Cleanup resources"""
        self.logger.info("Cleaning up resources...")
        
        # Flush and close IMU file
        if self.imu_logging_active:
            self.flush_imu_buffer()
            self.stop_IMU_logging()
            self.rsync_imu_log()
            self.logger.info("IMU log file closed and rsynced")
        
        # Disconnect BLE
        if self.client and self.client.is_connected:
            try:
                await self.client.disconnect()
                self.logger.info("BLE disconnected")
            except Exception as e:
                self.logger.error(f"Error disconnecting BLE: {e}")
        
        # Close GPIO chip
        if hasattr(self, 'chip'):
            try:
                lgpio.gpiochip_close(self.chip)
                self.logger.info("LGPIO chip closed")
            except Exception as e:
                self.logger.error(f"Failed to close LGPIO chip: {e}")
        
        # Close ZMQ
        try:
            self.zmq_socket.close()
            self.zmq_pub_socket.close()
            self.zmq_context.term()
            self.logger.info("ZMQ closed")
        except Exception as e:
            self.logger.error(f"ZMQ cleanup error: {e}")

def get_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # doesn't have to be reachable
        s.connect(('10.255.255.255', 1))
        IP = s.getsockname()[0]
    except Exception:
        IP = '127.0.0.1'
    finally:
        s.close()
    return IP

async def main():
    """Main entry point"""
    client = HeadlessOptoGridClient()
    try:
        await client.run()
    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        await client.cleanup()

if __name__ == "__main__":
    asyncio.run(main())