import asyncio
import sys
import struct
import threading
from typing import Dict, List, Optional, Tuple
import os
import zmq
import numpy as np
import csv
import datetime
from ahrs.filters import EKF
from ahrs.common.orientation import q2euler
import logging
from bleak import BleakScanner, BleakClient, BLEDevice
import queue
import signal

try:
    import lgpio
    GPIO_AVAILABLE = True
except ImportError:
    GPIO_AVAILABLE = False

# Constants and mappings (same as original)
UUID_NAME_MAP = {
    # Services
    "56781400-5678-1234-1234-5678abcdeff0": "Device Info Service",
    "56781401-5678-1234-1234-5678abcdeff0": "Opto Control Service",
    "56781402-5678-1234-1234-5678abcdeff0": "Data Streaming Service",
    "0000fe59-0000-1000-8000-00805f9b34fb": "Secure DFU Service",

    # Device Info Characteristics
    "56781500-5678-1234-1234-5678abcdeff0": "Device ID",
    "56781501-5678-1234-1234-5678abcdeff0": "Firmware Version",
    "56781502-5678-1234-1234-5678abcdeff0": "Implanted Animal",
    "56781503-5678-1234-1234-5678abcdeff0": "uLED Color",
    "56781504-5678-1234-1234-5678abcdeff0": "uLED Check",
    "56781505-5678-1234-1234-5678abcdeff0": "Battery Percentage",
    "56781506-5678-1234-1234-5678abcdeff0": "Battery Voltage",
    "56781507-5678-1234-1234-5678abcdeff0": "Status LED state",
    "56781508-5678-1234-1234-5678abcdeff0": "Sham LED state",
    "56781509-5678-1234-1234-5678abcdeff0": "Device Log",

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
    "56781502-5678-1234-1234-5678abcdeff0": "string",
    "56781503-5678-1234-1234-5678abcdeff0": "string",
    "56781504-5678-1234-1234-5678abcdeff0": "uint64",
    "56781505-5678-1234-1234-5678abcdeff0": "uint16",
    "56781506-5678-1234-1234-5678abcdeff0": "uint16",
    "56781507-5678-1234-1234-5678abcdeff0": "bool",
    "56781508-5678-1234-1234-5678abcdeff0": "bool",
    "56781509-5678-1234-1234-5678abcdeff0": "string",

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
        
        # ZMQ setup
        self.zmq_context = zmq.Context()
        self.zmq_socket = self.zmq_context.socket(zmq.REP)
        self.zmq_socket.bind("tcp://*:5555")
        
        # IMU processing setup
        self.setup_imu_processing()
        
        # Data buffers and file handling
        self.imu_data_buffer = []
        self.imu_csv_file = None
        self.imu_csv_writer = None
        self.current_battery_voltage = None
        
        # Setup GPIO with nuclear option
        if GPIO_AVAILABLE:
            try:
                self.setup_gpio_trigger(pin=17)
            except Exception as e:
                self.logger.error(f"GPIO setup completely failed: {e}")
                # Don't exit, continue without GPIO
        
        # Signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
        
        self.running = True
        
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


    
        def setup_gpio_trigger(self, pin=17):
            """Setup GPIO pin for rising edge detection using LGPIO"""
            try:
                # Open GPIO chip
                self.chip = lgpio.gpiochip_open(0)  # Open GPIO chip 0
                
                # Claim the pin as input
                lgpio.gpio_claim_input(self.chip, pin)
                
                # Set debounce time
                lgpio.gpio_set_debounce(self.chip, pin, 200)  # 200ms debounce
                
                # Register callback for rising edge detection
                lgpio.gpio_register_callback(self.chip, pin, lgpio.RISING_EDGE, self.gpio_trigger_callback)
                
                self.logger.info(f"GPIO {pin} configured successfully for rising edge detection using LGPIO")
            except Exception as e:
                self.logger.error(f"Failed to setup GPIO {pin} using LGPIO: {e}")
    
    def gpio_trigger_callback(self, chip, gpio, level, tick):
        """Callback function for GPIO interrupt"""
        timestamp = time.strftime('%H:%M:%S.%f')[:-3]
        print(f"[LGPIO] GPIO {gpio} rising edge detected at {timestamp}")
        self.logger.info(f"GPIO {gpio} rising edge detected")
        
        # Trigger device if connected
        if self.client and self.client.is_connected:
            try:
                asyncio.run_coroutine_threadsafe(self.do_send_trigger(), asyncio.get_event_loop())
            except Exception as e:
                self.logger.error(f"Failed to send trigger from GPIO: {e}")

    def signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        self.logger.info(f"Received signal {signum}, shutting down...")
        self.running = False

    async def run(self):
        """Main run loop"""
        self.logger.info("Starting OptoGrid Headless Client...")
        self.logger.info("ZMQ server listening on port 5555...")
        
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
            if "optogrid.connect" in message:
                device_name = message.split('=')[1].strip()
                return await self.connect_device(device_name)
                
            elif "optogrid.trigger" in message:
                return await self.send_trigger()
                
            elif "optogrid.enableIMU" in message:
                return await self.enable_imu()
                
            elif "optogrid.disableIMU" in message:
                return await self.disable_imu()
                
            elif "optogrid.readbattery" in message:
                return await self.read_battery()
                
            elif "optogrid.sync" in message:
                sync_value = int(message.split('=')[1].strip())
                return self.handle_sync(sync_value)
                
            elif "optogrid.program" in message:
                # Expect program data in the next message
                self.zmq_socket.send_string("Ready for program data")
                program_data = self.zmq_socket.recv_string()
                return await self.program_device(eval(program_data))
            
            return f"Unknown command: {message}"
            
        except Exception as e:
            self.logger.error(f"Command error: {e}")
            return f"ERROR: {str(e)}"

    async def connect_device(self, device_name: str) -> str:
        """Connect to specified BLE device"""
        try:
            # Disconnect existing connection
            if self.client and self.client.is_connected:
                await self.client.disconnect()
                self.client = None
            
            self.logger.info(f"Scanning for device: {device_name}")
            devices = await BleakScanner.discover(timeout=4)
            matching_device = next((d for d in devices if d.name and device_name in d.name), None)
            
            if not matching_device:
                return f"Device {device_name} not found"
            
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
            led_check_uuid = "56781504-5678-1234-1234-5678abcdeff0"
            await self.client.start_notify(led_check_uuid, self.handle_led_check_notification)
            
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
        if self.imu_csv_file:
            self.imu_csv_file.close()
            self.imu_csv_file = None
            self.imu_csv_writer = None
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
            
            if self.imu_counter % 100 == 0:  # Log every 100th message
                self.logger.debug(f"IMU Data: {imu_values_str}")

            # Process orientation using AHRS sensor fusion
            smooth_roll, smooth_pitch, smooth_yaw = self.process_imu_orientation(imu_values)

            if self.imu_counter % 100 == 0:  # Log orientation every 100th sample
                self.logger.info(f"Orientation - Roll: {smooth_roll:.1f}°, Pitch: {smooth_pitch:.1f}°, Yaw: {smooth_yaw:.1f}°")

            # Buffer IMU data if logging is enabled
            if self.imu_enable_state:
                uncertainty = None
                if hasattr(self.fusion_filter, "P"):
                    try:
                        uncertainty = float(np.trace(self.fusion_filter.P))
                    except Exception:
                        uncertainty = None

                # Prepare data for CSV
                imu_data_with_sync = imu_values + [0]  # Add sync value (default 0)
                
                battery_v = ""
                if self.current_battery_voltage is not None:
                    battery_v = self.current_battery_voltage
                    self.current_battery_voltage = None

                row = imu_data_with_sync + [smooth_roll, smooth_pitch, smooth_yaw, uncertainty, battery_v]
                self.imu_data_buffer.append(row)
                
                if len(self.imu_data_buffer) >= 100:
                    self.flush_imu_buffer()

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
        acc_world = np.array([-acc[2], -acc[0], acc[1]])
        gyr_world = np.array([-gyr[2], -gyr[0], gyr[1]])
        mag_world = np.array([-mag_calibrated[2], -mag_calibrated[1], mag_calibrated[0]])

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
        """Write buffered IMU data to CSV"""
        if self.imu_csv_writer and self.imu_data_buffer:
            self.imu_csv_writer.writerows(self.imu_data_buffer)
            self.imu_csv_file.flush()  # Force write to disk
            self.imu_data_buffer = []

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

    async def enable_imu(self) -> str:
        """Enable IMU and start logging"""
        if not self.client or not self.client.is_connected:
            return "Not connected to device"
            
        try:
            # Enable IMU
            imu_enable_uuid = "56781700-5678-1234-1234-5678abcdeff0"
            encoded_value = encode_value(imu_enable_uuid, "True")
            await self.client.write_gatt_char(imu_enable_uuid, encoded_value)
            
            # Setup CSV logging
            if not self.imu_csv_file:
                os.makedirs("data", exist_ok=True)
                
                # Get device info for filename
                animal_id = await self.read_characteristic("56781502-5678-1234-1234-5678abcdeff0")
                device_id = await self.read_characteristic("56781500-5678-1234-1234-5678abcdeff0")
                
                timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"data/{animal_id}_{device_id}_{timestamp}.csv"
                
                self.imu_csv_file = open(filename, "w", newline="")
                self.imu_csv_writer = csv.writer(self.imu_csv_file)
                self.imu_csv_writer.writerow([
                    "sample", 
                    "acc_x", "acc_y", "acc_z", 
                    "gyro_x", "gyro_y", "gyro_z",
                    "mag_x", "mag_y", "mag_z", 
                    "sync", "roll", "pitch", "yaw", 
                    "uncertainty", "bat_v"
                ])
                
                self.logger.info(f"IMU logging started: {filename}")
            
            self.imu_enable_state = True
            return "IMU enabled and logging started"
            
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
            
            # Close CSV file
            if self.imu_csv_file:
                self.flush_imu_buffer()
                self.imu_csv_file.close()
                self.imu_csv_file = None
                self.imu_csv_writer = None
                self.logger.info("IMU logging stopped and file closed")
            
            self.imu_enable_state = False
            return "IMU disabled and logging stopped"
            
        except Exception as e:
            return f"IMU disable failed: {str(e)}"

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

    async def cleanup(self):
        """Cleanup resources"""
        self.logger.info("Cleaning up resources...")
        
        # Flush and close IMU file
        if self.imu_csv_file:
            self.flush_imu_buffer()
            self.imu_csv_file.close()
            self.imu_csv_file = None
            self.logger.info("IMU log file closed")
        
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
            self.zmq_context.term()
            self.logger.info("ZMQ closed")
        except Exception as e:
            self.logger.error(f"ZMQ cleanup error: {e}")

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