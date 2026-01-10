import zmq
import json
import time

class OptoGrid:
    """Python version of the MATLAB OptoGrid class for controlling OptoGrid devices via ZMQ"""
    
    def __init__(self):
        self.device_name = "OptoGrid 1"
        self.opto_setting = {
            'sequence_length': 1,
            'led_selection': 34359738368,  # uint64 value
            'duration': 550,
            'period': 25,
            'pulse_width': 10,
            'amplitude': 100,
            'pwm_frequency': 50000,
            'ramp_up': 0,
            'ramp_down': 200
        }
        self.battery_reading = None
        self.zmq_socket_address = "tcp://localhost:5555"
        self.context = None
        self.socket = None
        self.trigger_success_flag = 0  # Defaults to 0, when trigger success, set 1
        
    def start(self):
        """Initialize ZMQ connection"""
        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.REQ)
        self.socket.connect(self.zmq_socket_address)
        self.socket.setsockopt(zmq.RCVTIMEO, 10000)  # 10s timeout in ms
        
    def connect(self):
        """Connect to OptoGrid device"""
        success = False
        for attempt in range(3):
            try:
                self.socket.send_string(f'optogrid.connect = {self.device_name}')
                reply = self.socket.recv_string()
                if f'{self.device_name} Connected' in reply:
                    success = True
                    break
            except zmq.Again:
                # Timeout occurred
                continue
            except Exception:
                continue
        return success
    
    def enable_imu(self):
        """Enable IMU data collection and logging"""
        try:
            self.socket.send_string('optogrid.enableIMU')
            reply = self.socket.recv_string()
            if 'IMU enabled and logging started' in reply:
                return True
            else:
                return False
        except Exception:
            return False
    
    def disable_imu(self):
        """Disable IMU data collection and logging"""
        try:
            self.socket.send_string('optogrid.disableIMU')
            reply = self.socket.recv_string()
            if 'IMU disabled and logging stopped' in reply:
                return True
            else:
                return False
        except Exception:
            return False
    
    def trigger(self):
        """Send trigger command to OptoGrid device"""
        try:
            self.socket.send_string('optogrid.trigger')
            reply = self.socket.recv_string()
            if 'Opto Triggered' in reply:
                self.trigger_success_flag = 1
                return True
            else:
                self.trigger_success_flag = 0
                return False
        except Exception:
            self.trigger_success_flag = 0
            return False
    
    def read_battery(self):
        """Read battery voltage from device
        
        Returns:
            tuple: (success, device_name, battery_voltage_mV)
        """
        try:
            self.socket.send_string('optogrid.readbattery')
            reply = self.socket.recv_string()
            
            # Default values
            success = False
            device_name = self.device_name
            battery_voltage_mv = 0
            
            if 'Battery Voltage' in reply:
                success = True
                # Parse reply: "DeviceName Battery Voltage = XXXX mV"
                import re
                
                # Extract device name
                device_pattern = r'^(.*?) Battery Voltage'
                device_match = re.search(device_pattern, reply)
                if device_match:
                    device_name = device_match.group(1)
                
                # Extract voltage
                voltage_pattern = r'Battery Voltage = (\d+) mV'
                voltage_match = re.search(voltage_pattern, reply)
                if voltage_match:
                    battery_voltage_mv = int(voltage_match.group(1))
                    
                self.battery_reading = battery_voltage_mv
                
            return success, device_name, battery_voltage_mv
            
        except Exception:
            return False, self.device_name, 0
    
    def program(self):
        """Program OptoGrid device with current opto settings"""
        try:
            # Send program command
            self.socket.send_string('optogrid.program')
            reply = self.socket.recv_string()
            
            # Send settings as JSON
            settings_json = json.dumps(self.opto_setting)
            self.socket.send_string(settings_json)
            reply2 = self.socket.recv_string()
            
            if 'Opto Programmed' in reply2:
                return True
            else:
                return False
        except Exception:
            return False
    
    def sync(self, val=1):
        """Send sync marker to IMU data stream
        
        Args:
            val (int): Sync value to write (default: 1)
        """
        try:
            self.socket.send_string(f'optogrid.sync = {val}')
            reply = self.socket.recv_string()
            if 'Sync Written' in reply:
                return True
            else:
                return False
        except Exception:
            return False
    
    def cleanup(self):
        """Close ZMQ connection and cleanup resources"""
        if self.socket:
            self.socket.close()
        if self.context:
            self.context.term()
    
    def __del__(self):
        """Destructor to ensure cleanup"""
        self.cleanup()