"""
OptoGrid Backend Client
Shared backend for both GUI and headless modes.
Handles BLE, ZMQ, IMU processing, and device control.
"""

import asyncio
import threading
import logging
import struct
import signal
import csv
import datetime
import socket
import os
from typing import Dict, List, Optional, Tuple, Callable, Any
from collections import defaultdict
import concurrent.futures

import zmq
import numpy as np
import pandas as pd
from bleak import BleakScanner, BleakClient, BLEDevice
from ahrs.filters import EKF
from ahrs.common.orientation import q2euler

try:
    from gpiozero import Button, OutputDevice
    GPIO_AVAILABLE = True
except ImportError:
    GPIO_AVAILABLE = False

# Constants and mappings
UUID_NAME_MAP = {
    # Services
    "56781400-5678-1234-1234-5678abcdeff0": "Device Info Service",
    "56781401-5678-1234-1234-5678abcdeff0": "Opto Control Service",
    "56781402-5678-1234-1234-5678abcdeff0": "Data Streaming Service",
    "0000fe59-0000-1000-8000-00805f9b34fb": "Secure DFU Service",

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

uuid_to_unit = {
    # Device Info Characteristics
    "56781500-5678-1234-1234-5678abcdeff0": "",
    "56781501-5678-1234-1234-5678abcdeff0": "",
    "56781503-5678-1234-1234-5678abcdeff0": "",
    "56781504-5678-1234-1234-5678abcdeff0": "",
    "56781506-5678-1234-1234-5678abcdeff0": "mV",
    "56781507-5678-1234-1234-5678abcdeff0": "",
    "56781508-5678-1234-1234-5678abcdeff0": "",
    "5678150a-5678-1234-1234-5678abcdeff0": "ms",

    # Opto Control Characteristics
    "56781600-5678-1234-1234-5678abcdeff0": "units",
    "56781601-5678-1234-1234-5678abcdeff0": "",
    "56781602-5678-1234-1234-5678abcdeff0": "ms",
    "56781603-5678-1234-1234-5678abcdeff0": "ms",
    "56781604-5678-1234-1234-5678abcdeff0": "ms",
    "56781605-5678-1234-1234-5678abcdeff0": "percent",
    "56781606-5678-1234-1234-5678abcdeff0": "Hz",
    "56781607-5678-1234-1234-5678abcdeff0": "ms",
    "56781608-5678-1234-1234-5678abcdeff0": "ms",
    "56781609-5678-1234-1234-5678abcdeff0": "",

    # IMU Characteristics
    "56781700-5678-1234-1234-5678abcdeff0": "",
    "56781701-5678-1234-1234-5678abcdeff0": "Hz",
    "56781702-5678-1234-1234-5678abcdeff0": "g",
    "56781703-5678-1234-1234-5678abcdeff0": "",

    # Secure DFU Characteristics
    "8ec90003-f315-4f60-9fb8-838830daea50": ""
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


def get_ip():
    """Get local IP address"""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('10.255.255.255', 1))
        IP = s.getsockname()[0]
    except Exception:
        IP = '127.0.0.1'
    finally:
        s.close()
    return IP


class OptoGridClient:
    """
    OptoGrid BLE client with ZMQ control interface.
    Supports both headless and GUI modes via callback system.
    """

    def __init__(self):
        """Initialize the OptoGrid client"""
        self.setup_logging()
        
        # BLE client state
        self.client: Optional[BleakClient] = None
        self.selected_device: Optional[BLEDevice] = None
        self.led_selection_value = 0
        self.imu_enable_state = False
        self.imu_counter = 0
        
        # Callback system for event notifications
        self._callbacks: Dict[str, List[Callable]] = defaultdict(list)
        
        # ZMQ setup
        self.zmq_context = zmq.Context()
        self.zmq_socket = None
        
        # IMU processing setup
        self.setup_imu_processing()
        
        # Data buffers and file handling
        self.imu_data_buffer = []
        self.imu_csv_file = None
        self.imu_csv_writer = None
        self.current_battery_voltage = None
        
        # Setup GPIO if available
        if GPIO_AVAILABLE:
            try:
                self.gpio_pin = 17
                self.trigger_button = Button(self.gpio_pin, pull_up=False, bounce_time=0.2)
                self.trigger_button.when_pressed = self.gpio_trigger_callback
                self.logger.info(f"GPIO trigger configured on pin {self.gpio_pin}")
            except Exception as e:
                self.logger.warning(f"GPIO setup failed: {e}")
        
        # Create dedicated event loop for BLE operations
        self.loop = asyncio.new_event_loop()
        self._loop_thread = threading.Thread(target=self._run_event_loop, daemon=True)
        self._loop_thread.start()
        
        # Signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
        
        self.running = True

    def _run_event_loop(self):
        """Run the dedicated event loop in background thread"""
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()

    def setup_logging(self):
        """Setup logging configuration"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.StreamHandler(),
                logging.FileHandler('optogrid_client.log')
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
            frequency=100,
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

    # ==================== Callback System ====================
    
    def register_callback(self, event_name: str, callback: Callable[[Any], None]):
        """Register a callback for an event"""
        self._callbacks[event_name].append(callback)
        self.logger.debug(f"Registered callback for event: {event_name}")

    def unregister_callback(self, event_name: str, callback: Callable):
        """Unregister a callback for an event"""
        if callback in self._callbacks[event_name]:
            self._callbacks[event_name].remove(callback)
            self.logger.debug(f"Unregistered callback for event: {event_name}")

    def _emit(self, event_name: str, *args, **kwargs):
        """Emit an event to all registered callbacks"""
        for callback in list(self._callbacks.get(event_name, [])):
            try:
                callback(*args, **kwargs)
            except Exception as e:
                self.logger.error(f"Error in callback for {event_name}: {e}")

    # ==================== Thread-safe Execution ====================
    
    def run_coro_threadsafe(self, coro) -> concurrent.futures.Future:
        """
        Execute a coroutine in the backend event loop from any thread.
        Returns a Future that will contain the result.
        """
        return asyncio.run_coroutine_threadsafe(coro, self.loop)

    def start(self):
        """Start ZMQ server (optional explicit start)"""
        future = self.run_coro_threadsafe(self._start_zmq())
        future.result()  # Wait for ZMQ to bind

    async def _start_zmq(self):
        """Initialize ZMQ server"""
        self.zmq_socket = self.zmq_context.socket(zmq.REP)
        ip = get_ip()
        self.zmq_socket.bind(f"tcp://0.0.0.0:5555")
        self.logger.info(f"ZMQ server listening on tcp://{ip}:5555")
        self.logger.info(f"ZMQ server listening on tcp://localhost:5555")
        self._emit("zmq_started", ip)

    # ==================== BLE Operations ====================
    
    async def scan(self, timeout: int = 4) -> List[BLEDevice]:
        """Scan for BLE devices"""
        self.logger.info(f"Scanning for devices (timeout={timeout}s)...")
        devices = await BleakScanner.discover(timeout=timeout)
        optogrid_devices = [d for d in devices if d.name and "O" in d.name]
        self.logger.info(f"Found {len(optogrid_devices)} OptoGrid devices")
        self._emit("scan_complete", optogrid_devices)
        return optogrid_devices

    async def connect(self, device_name_or_address: str) -> str:
        """Connect to specified BLE device"""
        try:
            self.logger.info(f"Attempting to connect to: {device_name_or_address}")
            
            # Scan for devices
            devices = await BleakScanner.discover(timeout=2)
            matching_device = next(
                (d for d in devices if d.name and device_name_or_address in d.name),
                None
            )
            
            if not matching_device:
                msg = f"Device {device_name_or_address} not found"
                self.logger.error(msg)
                self._emit("connection_failed", msg)
                return msg
            
            # Connect to device
            self.selected_device = matching_device
            self.client = BleakClient(
                matching_device.address,
                disconnected_callback=self.on_disconnect_callback
            )
            
            await self.client.connect(timeout=10.0)
            self.logger.info(f"Connected to {matching_device.name}")
            
            # Setup notifications
            await self.setup_notifications()
            
            # Update IMU filter frequency
            await self.update_imu_filter_frequency()
            
            # Load magnetometer calibration
            self.load_magnetometer_calibration(matching_device.name)
            
            msg = f"Connected to {matching_device.name}"
            self._emit("connected", matching_device.name, matching_device.address)
            return msg
            
        except Exception as e:
            msg = f"Connection failed: {str(e)}"
            self.logger.error(msg)
            self._emit("connection_failed", str(e))
            return msg

    async def disconnect(self) -> None:
        """Disconnect from BLE device"""
        if self.client and self.client.is_connected:
            await self.client.disconnect()
            self.logger.info("Disconnected from device")
            self._emit("disconnected")

    async def setup_notifications(self):
        """Setup BLE notifications"""
        try:
            # Device log
            device_log_uuid = "56781509-5678-1234-1234-5678abcdeff0"
            await self.client.start_notify(device_log_uuid, self.handle_device_log_notification)
            
            # IMU data
            imu_data_uuid = "56781703-5678-1234-1234-5678abcdeff0"
            await self.client.start_notify(imu_data_uuid, self.handle_imu_data_notification)
            
            self.logger.info("Notifications configured")
        except Exception as e:
            self.logger.error(f"Failed to setup notifications: {e}")

    async def read_characteristic(self, uuid: str) -> str:
        """Read a characteristic value"""
        if not self.client or not self.client.is_connected:
            return "Not connected"
        try:
            data = await self.client.read_gatt_char(uuid)
            return decode_value(uuid, data)
        except Exception as e:
            self.logger.error(f"Failed to read {uuid}: {e}")
            return f"Error: {e}"

    async def write_characteristic(self, uuid: str, value: str) -> bool:
        """Write a characteristic value"""
        if not self.client or not self.client.is_connected:
            return False
        try:
            encoded_value = encode_value(uuid, value)
            await self.client.write_gatt_char(uuid, encoded_value)
            self.logger.info(f"Wrote {value} to {UUID_NAME_MAP.get(uuid, uuid)}")
            
            # Update IMU filter if sample rate changed
            if uuid == "56781701-5678-1234-1234-5678abcdeff0":
                await self.update_imu_filter_frequency()
            
            return True
        except Exception as e:
            self.logger.error(f"Failed to write {uuid}: {e}")
            return False

    # ==================== Device Operations ====================
    
    async def send_trigger(self) -> str:
        """Send trigger command to device"""
        if not self.client or not self.client.is_connected:
            return "Not connected"
        
        try:
            trigger_uuid = "56781609-5678-1234-1234-5678abcdeff0"
            
            # Write True then False to create pulse
            await self.write_characteristic(trigger_uuid, "True")
            await asyncio.sleep(0.01)
            await self.write_characteristic(trigger_uuid, "False")
            
            self.logger.info("Trigger sent")
            self._emit("trigger_sent")
            return "Trigger sent successfully"
        except Exception as e:
            msg = f"Trigger failed: {e}"
            self.logger.error(msg)
            return msg

    async def enable_imu(self) -> str:
        """Enable IMU and start logging"""
        if not self.client or not self.client.is_connected:
            return "Not connected"
        
        try:
            # Start IMU logging
            import os
            os.makedirs("data", exist_ok=True)
            
            device_id_uuid = "56781500-5678-1234-1234-5678abcdeff0"
            device_id = await self.read_characteristic(device_id_uuid)
            now_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"data/{device_id}_{now_str}.csv"
            
            self.imu_csv_file = open(filename, "w", newline="")
            self.imu_csv_writer = csv.writer(self.imu_csv_file)
            self.imu_csv_writer.writerow([
                "sample", "acc_x", "acc_y", "acc_z",
                "gyro_x", "gyro_y", "gyro_z",
                "mag_x", "mag_y", "mag_z", "sync",
                "roll", "pitch", "yaw", "uncertainty", "bat_v"
            ])
            
            # Enable IMU
            imu_enable_uuid = "56781700-5678-1234-1234-5678abcdeff0"
            await self.write_characteristic(imu_enable_uuid, "True")
            
            self.imu_enable_state = True
            self.logger.info(f"IMU enabled, logging to {filename}")
            self._emit("imu_enabled", filename)
            return f"IMU enabled: {filename}"
        except Exception as e:
            msg = f"Failed to enable IMU: {e}"
            self.logger.error(msg)
            return msg

    async def disable_imu(self) -> str:
        """Disable IMU and stop logging"""
        if not self.client or not self.client.is_connected:
            return "Not connected"
        
        try:
            # Disable IMU
            imu_enable_uuid = "56781700-5678-1234-1234-5678abcdeff0"
            await self.write_characteristic(imu_enable_uuid, "False")
            
            # Close log file
            if self.imu_csv_file:
                self.imu_csv_file.close()
                self.imu_csv_file = None
                self.imu_csv_writer = None
            
            self.imu_enable_state = False
            self.logger.info("IMU disabled and logging stopped")
            self._emit("imu_disabled")
            return "IMU disabled"
        except Exception as e:
            msg = f"Failed to disable IMU: {e}"
            self.logger.error(msg)
            return msg

    async def program_device(self, program_data: dict) -> str:
        """Program device with opto settings"""
        if not self.client or not self.client.is_connected:
            return "Not connected"
        
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
                    await self.write_characteristic(uuid, str(value))
            
            self.logger.info("Device programmed successfully")
            self._emit("program_applied", program_data)
            return "Device programmed successfully"
        except Exception as e:
            msg = f"Programming failed: {e}"
            self.logger.error(msg)
            return msg

    async def read_battery(self) -> str:
        """Read battery voltage"""
        if not self.client or not self.client.is_connected:
            return "Not connected"
        
        try:
            battery_uuid = "56781506-5678-1234-1234-5678abcdeff0"
            voltage_str = await self.read_characteristic(battery_uuid)
            voltage = int(voltage_str)
            self.current_battery_voltage = voltage
            self.logger.info(f"Battery voltage: {voltage} mV")
            self._emit("battery_update", voltage)
            return f"{voltage} mV"
        except Exception as e:
            msg = f"Failed to read battery: {e}"
            self.logger.error(msg)
            return msg

    async def read_uled_check(self) -> str:
        """Read uLED check value"""
        if not self.client or not self.client.is_connected:
            return "Not connected"
        
        try:
            uled_check_uuid = "56781504-5678-1234-1234-5678abcdeff0"
            value = await self.read_characteristic(uled_check_uuid)
            self.logger.info(f"uLED Check: {value}")
            self._emit("led_check", int(value))
            return value
        except Exception as e:
            msg = f"Failed to read uLED check: {e}"
            self.logger.error(msg)
            return msg

    # ==================== Notification Handlers ====================
    
    async def handle_device_log_notification(self, sender: int, data: bytearray):
        """Handle device log notifications"""
        try:
            device_log_uuid = "56781509-5678-1234-1234-5678abcdeff0"
            log_message = decode_value(device_log_uuid, data)
            self.logger.info(f"Device log: {log_message}")
            self._emit("device_log", log_message)
        except Exception as e:
            self.logger.error(f"Error handling device log: {e}")

    async def handle_led_check_notification(self, sender: int, data: bytearray):
        """Handle LED check notifications"""
        try:
            led_check_uuid = "56781504-5678-1234-1234-5678abcdeff0"
            led_check_value = decode_value(led_check_uuid, data)
            self._emit("led_check", int(led_check_value))
        except Exception as e:
            self.logger.error(f"Error handling LED check: {e}")

    async def handle_imu_data_notification(self, sender: int, data: bytearray):
        """Handle IMU data notifications"""
        try:
            # Parse IMU data
            timestamp = struct.unpack('<I', data[:4])[0]
            values = struct.unpack('<9h', data[4:22])
            
            imu_values = [
                timestamp, values[0], values[1], values[2],
                values[3], values[4], values[5],
                values[6], values[7], values[8], 0
            ]
            
            # Process orientation
            roll, pitch, yaw = self.process_imu_orientation(imu_values)
            
            # Emit IMU update event
            self._emit("imu_update", roll, pitch, yaw, imu_values)
            
            # Log to file if enabled
            if self.imu_csv_writer:
                self.imu_counter += 1
                imu_values[10] = 0  # sync value
                row = [self.imu_counter] + imu_values[1:11] + [
                    roll, pitch, yaw, 0.0,
                    self.current_battery_voltage or 0
                ]
                self.imu_csv_writer.writerow(row)
                self.imu_data_buffer.append(row)
                
                if len(self.imu_data_buffer) >= 100:
                    self.flush_imu_buffer()
                    
        except Exception as e:
            self.logger.error(f"Error handling IMU data: {e}")

    def process_imu_orientation(self, imu_values):
        """Process IMU data and calculate orientation"""
        acc_x, acc_y, acc_z = imu_values[1:4]
        gyro_x, gyro_y, gyro_z = imu_values[4:7]
        mag_x, mag_y, mag_z = imu_values[7:10]

        # Apply calibration
        mag_raw = np.array([mag_x, mag_y, mag_z])
        mag_calibrated = (mag_raw - self.mag_offset) * self.mag_scale
        
        # Convert units
        acc = np.array([acc_x, acc_y, acc_z]) * (32.0 / 65536.0)
        gyr = np.array([gyro_x, gyro_y, gyro_z]) * (4000.0 / 65536.0)
        mag = mag_calibrated * (100.0 / 65536.0)

        # Transform to device frame
        acc_world = np.array([acc[0], -acc[1], -acc[2]])
        gyr_world = np.array([gyr[0], -gyr[1], -gyr[2]])
        mag_world = np.array([mag_calibrated[1], -mag_calibrated[0], -mag_calibrated[2]])

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

        # Update filter
        if is_mag_valid:
            acc_si = acc_world * 9.80665
            gyr_si = np.radians(gyr_world)
            mag_si = mag_world * 100.0
            
            self.q = self.fusion_filter.update(
                q=self.q,
                gyr=gyr_si,
                acc=acc_si,
                mag=mag_si
            )
        else:
            acc_si = acc_world * 9.80665
            gyr_si = np.radians(gyr_world)
            
            self.q = self.fusion_filter.update(
                q=self.q,
                gyr=gyr_si,
                acc=acc_si
            )

        # Convert to Euler angles
        roll, pitch, yaw = np.degrees(q2euler(self.q))
        yaw = (yaw + 360) % 360

        # Light smoothing
        if self.last_roll is None:
            smooth_roll, smooth_pitch, smooth_yaw = roll, pitch, yaw
        else:
            alpha_rp = 1
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

    def flush_imu_buffer(self):
        """Flush IMU data buffer to file"""
        if self.imu_csv_file:
            self.imu_csv_file.flush()
        self.imu_data_buffer = []

    def load_magnetometer_calibration(self, device_name):
        """Load magnetometer calibration from CSV file"""
        try:
            calibration_filename = f"data/{device_name} Calibration.csv"
            
            if not os.path.exists(calibration_filename):
                self.logger.info(f"No calibration file found: {calibration_filename}")
                return False
            
            self.logger.info(f"Loading magnetometer calibration from: {calibration_filename}")
            cal_data = pd.read_csv(calibration_filename)
            
            if not all(col in cal_data.columns for col in ['mag_x', 'mag_y', 'mag_z']):
                self.logger.error("Calibration file missing required columns")
                return False
            
            mag_x_data = cal_data['mag_x'].values
            mag_y_data = cal_data['mag_y'].values
            mag_z_data = cal_data['mag_z'].values
            
            # Calculate offsets
            mag_x_offset = (np.max(mag_x_data) + np.min(mag_x_data)) / 2
            mag_y_offset = (np.max(mag_y_data) + np.min(mag_y_data)) / 2
            mag_z_offset = (np.max(mag_z_data) + np.min(mag_z_data)) / 2
            
            self.mag_offset = np.array([mag_x_offset, mag_y_offset, mag_z_offset])
            
            # Calculate scale factors
            mag_x_range = np.max(mag_x_data) - np.min(mag_x_data)
            mag_y_range = np.max(mag_y_data) - np.min(mag_y_data)
            mag_z_range = np.max(mag_z_data) - np.min(mag_z_data)
            
            avg_range = (mag_x_range + mag_y_range + mag_z_range) / 3
            
            mag_x_scale = avg_range / mag_x_range if mag_x_range > 0 else 1.0
            mag_y_scale = avg_range / mag_y_range if mag_y_range > 0 else 1.0
            mag_z_scale = avg_range / mag_z_range if mag_z_range > 0 else 1.0
            
            self.mag_scale = np.array([mag_x_scale, mag_y_scale, mag_z_scale])
            
            self.logger.info(f"Calibration loaded: offsets={self.mag_offset}, scales={self.mag_scale}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error loading calibration: {e}")
            return False

    async def update_imu_filter_frequency(self):
        """Update IMU filter frequency from device settings"""
        try:
            imu_sample_rate_uuid = "56781701-5678-1234-1234-5678abcdeff0"
            rate_str = await self.read_characteristic(imu_sample_rate_uuid)
            imu_sample_rate = int(rate_str)
            
            if imu_sample_rate > 0:
                self.fusion_filter = EKF(
                    frequency=imu_sample_rate,
                    var_acc=self.var_acc,
                    var_gyro=self.var_gyro,
                    var_mag=self.var_mag,
                    declination=self.var_declination
                )
                self.logger.info(f"Updated EKF filter frequency to {imu_sample_rate} Hz")
        except Exception as e:
            self.logger.error(f"Failed to update IMU filter frequency: {e}")

    def on_disconnect_callback(self, client):
        """Handle unexpected disconnections"""
        self.logger.warning(f"BLE device disconnected unexpectedly at sample {self.imu_counter}")
        
        if self.imu_data_buffer:
            self.flush_imu_buffer()
        
        if self.imu_csv_file:
            self.imu_csv_file.close()
            self.imu_csv_file = None
            self.imu_csv_writer = None
        
        self._emit("disconnected")

    def gpio_trigger_callback(self):
        """GPIO trigger callback"""
        if self.client and self.client.is_connected:
            self.logger.info("GPIO trigger detected")
            future = self.run_coro_threadsafe(self.send_trigger())
            # Don't block waiting for result

    # ==================== Headless ZMQ Loop ====================
    
    async def run(self):
        """Main headless run loop processing ZMQ commands"""
        self.logger.info("OptoGrid Client Started (Headless Mode)")
        
        # Start ZMQ if not already started
        if not self.zmq_socket:
            await self._start_zmq()
        
        while self.running:
            try:
                # Non-blocking receive with timeout
                if self.zmq_socket.poll(100, zmq.POLLIN):
                    message = self.zmq_socket.recv_string()
                    self.logger.info(f"ZMQ received: {message}")
                    
                    reply = await self.handle_command(message)
                    self.zmq_socket.send_string(reply)
                    
            except zmq.Again:
                continue
            except Exception as e:
                self.logger.error(f"Error in run loop: {e}")
                await asyncio.sleep(0.1)
        
        await self.cleanup()

    async def handle_command(self, message: str) -> str:
        """Handle incoming ZMQ commands"""
        try:
            if "connect" in message.lower():
                device_name = message.split("=")[1].strip() if "=" in message else "OptoGrid"
                return await self.connect(device_name)
            
            elif "trigger" in message.lower():
                return await self.send_trigger()
            
            elif "sync" in message.lower():
                sync_value = int(message.split("=")[1].strip())
                if self.imu_data_buffer:
                    self.imu_data_buffer[-1][10] = sync_value
                    return f"Sync {sync_value} written"
                return "No IMU data buffer"
            
            elif "program" in message.lower():
                # Expect next message to be program data dict
                return "Ready for program data"
            
            elif "enable_imu" in message.lower():
                return await self.enable_imu()
            
            elif "disable_imu" in message.lower():
                return await self.disable_imu()
            
            elif "battery" in message.lower():
                return await self.read_battery()
            
            elif "uled_check" in message.lower():
                return await self.read_uled_check()
            
            elif "status_led" in message.lower():
                value = int(message.split("=")[1].strip())
                status_led_uuid = "56781507-5678-1234-1234-5678abcdeff0"
                success = await self.write_characteristic(status_led_uuid, str(value))
                return f"Status LED {'on' if value else 'off'}" if success else "Failed"
            
            else:
                return f"Unknown command: {message}"
                
        except Exception as e:
            return f"Command error: {e}"

    def signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        self.logger.info(f"Received signal {signum}, shutting down...")
        self.running = False

    # ==================== Cleanup ====================
    
    async def cleanup(self):
        """Clean up resources"""
        self.logger.info("Cleaning up...")
        
        # Disconnect BLE
        if self.client and self.client.is_connected:
            await self.disconnect()
        
        # Close IMU file
        if self.imu_csv_file:
            self.imu_csv_file.close()
            self.imu_csv_file = None
        
        # Close ZMQ
        if self.zmq_socket:
            self.zmq_socket.close()
        if self.zmq_context:
            self.zmq_context.term()
        
        # Stop event loop
        self.loop.call_soon_threadsafe(self.loop.stop)
        
        self.logger.info("Cleanup complete")
