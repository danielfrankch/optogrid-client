import asyncio
from bleak import BleakScanner, BleakClient
import tkinter as tk
from tkinter import messagebox, ttk
import struct
from PIL import Image, ImageTk
import threading
import concurrent.futures

# Mapping of known custom UUIDs to names (must match those from your GATT profile)
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
    "56781506-5678-1234-1234-5678abcdeff0": "Status LED state",
    "56781507-5678-1234-1234-5678abcdeff0": "Sham LED state",

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
    "56781500-5678-1234-1234-5678abcdeff0": "",        # Device ID
    "56781501-5678-1234-1234-5678abcdeff0": "",        # Firmware Version
    "56781502-5678-1234-1234-5678abcdeff0": "",        # Implanted Animal
    "56781503-5678-1234-1234-5678abcdeff0": "",        # ULED Color
    "56781504-5678-1234-1234-5678abcdeff0": "",        # ULED Check
    "56781505-5678-1234-1234-5678abcdeff0": "percent",  # Battery Percentage
    "56781506-5678-1234-1234-5678abcdeff0": "",        # Status LED
    "56781507-5678-1234-1234-5678abcdeff0": "",        # Sham LED

    # Opto Control Characteristics
    "56781600-5678-1234-1234-5678abcdeff0": "units",      # Sequence Length
    "56781601-5678-1234-1234-5678abcdeff0": "",        # LED Selection
    "56781602-5678-1234-1234-5678abcdeff0": "ms",         # Duration
    "56781603-5678-1234-1234-5678abcdeff0": "ms",         # Period
    "56781604-5678-1234-1234-5678abcdeff0": "ms",         # Pulse Width
    "56781605-5678-1234-1234-5678abcdeff0": "percent",    # Amplitude
    "56781606-5678-1234-1234-5678abcdeff0": "Hz",         # PWM Frequency
    "56781607-5678-1234-1234-5678abcdeff0": "ms",         # Ramp Up Time
    "56781608-5678-1234-1234-5678abcdeff0": "ms",         # Ramp Down Time
    "56781609-5678-1234-1234-5678abcdeff0": "",        # Trigger

    # IMU Characteristics
    "56781700-5678-1234-1234-5678abcdeff0": "",        # IMU Enable
    "56781701-5678-1234-1234-5678abcdeff0": "Hz",         # IMU Sample Rate
    "56781702-5678-1234-1234-5678abcdeff0": "g",          # IMU Resolution
    "56781703-5678-1234-1234-5678abcdeff0": "",         # IMU Data

    # Secure DFU Characteristics
    "8ec90003-f315-4f60-9fb8-838830daea50": ""
}

uuid_to_type = {
    # Device Info
    "56781500-5678-1234-1234-5678abcdeff0": "string",   # device_id
    "56781501-5678-1234-1234-5678abcdeff0": "string",   # firmware_version
    "56781502-5678-1234-1234-5678abcdeff0": "string",   # implanted_animal
    "56781503-5678-1234-1234-5678abcdeff0": "string",   # uled_color
    "56781504-5678-1234-1234-5678abcdeff0": "uint64",   # uled_check
    "56781505-5678-1234-1234-5678abcdeff0": "uint8",    # battery_percentage
    "56781506-5678-1234-1234-5678abcdeff0": "bool",     # Status LED
    "56781507-5678-1234-1234-5678abcdeff0": "bool",     # Sham LED

    # Opto Control
    "56781600-5678-1234-1234-5678abcdeff0": "uint8",    # sequence_length
    "56781601-5678-1234-1234-5678abcdeff0": "uint64",   # led_selection
    "56781602-5678-1234-1234-5678abcdeff0": "uint16",   # duration
    "56781603-5678-1234-1234-5678abcdeff0": "uint16",   # period
    "56781604-5678-1234-1234-5678abcdeff0": "uint16",   # pulse_width
    "56781605-5678-1234-1234-5678abcdeff0": "uint8",    # amplitude
    "56781606-5678-1234-1234-5678abcdeff0": "uint32",    # pwm_freq
    "56781607-5678-1234-1234-5678abcdeff0": "uint16",   # ramp_up_time
    "56781608-5678-1234-1234-5678abcdeff0": "uint16",   # ramp_down_time
    "56781609-5678-1234-1234-5678abcdeff0": "bool",     # trigger

    # IMU
    "56781700-5678-1234-1234-5678abcdeff0": "bool",     # imu_enable
    "56781701-5678-1234-1234-5678abcdeff0": "uint8",    # imu_sample_rate
    "56781702-5678-1234-1234-5678abcdeff0": "uint8",    # imu_resolution
    "56781703-5678-1234-1234-5678abcdeff0": "int16[6]", # imu_data

    # Secure DFU
    "8ec90003-f315-4f60-9fb8-838830daea50": "bool"
}

def decode_value(uuid, data):
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
        elif type_str == "int16[6]":
            return ", ".join(str(struct.unpack('<h', data[i:i+2])[0]) for i in range(0, 12, 2))
        else:
            return data.hex()
    except Exception:
        return "<decode error>"

def encode_value(uuid, value_str):
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
        elif type_str == "int16[6]":
            # Parse comma-separated values like "1, 2, 3, 4, 5, 6"
            values = [int(x.strip()) for x in value_str.split(',')]
            if len(values) != 6:
                raise ValueError("Expected 6 comma-separated values")
            return b''.join(struct.pack('<h', val) for val in values)
        else:
            # Try to interpret as hex
            return bytes.fromhex(value_str.replace(' ', ''))
    except Exception as e:
        raise ValueError(f"Failed to encode value '{value_str}' as {type_str}: {e}")
    
    
class BLEClientUI:
    def __init__(self, root):
        self.root = root
        self.root.title("OptoGrid BLE Browser")
        
        # Bring window to front
        self.root.lift()
        self.root.attributes('-topmost', True)
        self.root.after_idle(self.root.attributes, '-topmost', False)

        self.top_frame = tk.Frame(root)
        self.top_frame.pack(anchor="w", padx=10, pady=5)

        self.right_frame = tk.Frame(self.top_frame)
        self.right_frame.pack(side="right", padx=20, pady=10)

        self.device_list = []
        self.selected_device = None
        self.client = None  # Store client reference for read/write operations
        self.char_uuid_map = {}  # Map treeview items to characteristic UUIDs
        self.char_writable_map = {}  # Map treeview items to writability status
        self.led_selection_value = 0  # Current LED selection bit pattern
        self.brain_canvas = None  # Canvas for brain map visualization
        self.brain_image_obj = None  # PIL Image object
        self.led_rectangles = []  # Store LED rectangle coordinates
        
        # Create event loop for async operations
        self.loop = None
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        self.setup_event_loop()

        self.scan_button = tk.Button(self.top_frame, text="Scan", command=self.start_scan)
        self.scan_button.pack(anchor="w")

        self.devices_box = ttk.Combobox(self.top_frame, width=30, state="readonly")
        self.devices_box.pack(anchor="w", pady=2)

        self.connect_button = tk.Button(self.top_frame, text="Connect", command=self.connect_to_device)
        self.connect_button.pack(anchor="w", pady=2)

        self.log_label = tk.Label(self.top_frame, text="Log Output:")
        self.log_label.pack(anchor="w", pady=(10, 0))
        self.output = tk.Text(self.top_frame, height=14, width=50)
        self.output.pack(anchor="w", padx=0, pady=(0, 10))

        # Load and place brain map image with LED visualization
        self.setup_brain_map_canvas()

        # Add control buttons frame
        self.control_frame = tk.Frame(root)
        self.control_frame.pack(pady=5)

        self.read_button = tk.Button(self.control_frame, text="Read All Values", 
                                   command=self.read_all_values, state="disabled")
        self.read_button.pack(side="left", padx=5)

        self.write_button = tk.Button(self.control_frame, text="Write Values", 
                                    command=self.write_values, state="disabled")
        self.write_button.pack(side="left", padx=5)

        # Add trigger button
        self.trigger_button = tk.Button(self.control_frame, text="TRIGGER", 
                                      command=self.send_trigger, state="disabled",
                                      bg="#ff4444", fg="black", font=("Arial", 10, "bold"))
        self.trigger_button.pack(side="left", padx=5)

        self.gatt_label = tk.Label(root, text="GATT Table:")
        self.gatt_label.pack()
        
        # Updated treeview without Properties column
        self.gatt_output = ttk.Treeview(root, columns=("Service", "Characteristic", "Value", "WriteValue", "Unit"), show="headings")
        self.gatt_output.heading("Service", text="Service Name")
        self.gatt_output.heading("Characteristic", text="Characteristic Name")
        self.gatt_output.heading("Value", text="Current Value")
        self.gatt_output.heading("WriteValue", text="Write Value")
        self.gatt_output.heading("Unit", text="Unit")
        
        self.gatt_output.column("Service", width=150)
        self.gatt_output.column("Characteristic", width=150)
        self.gatt_output.column("Value", width=150)
        self.gatt_output.column("WriteValue", width=150)
        self.gatt_output.column("Unit", width=80)
        
        self.gatt_output.pack(padx=10, pady=5, expand=True, fill="both")
        
        # Configure tags for different styles
        self.gatt_output.tag_configure("writable", background="#e8f5e8")  # Light green for writable
        self.gatt_output.tag_configure("readonly", background="#f5f5f5")   # Light gray for read-only
        
        # Make WriteValue column editable
        self.gatt_output.bind("<Double-1>", self.on_double_click)
        
        # Bind to value changes for real-time LED updates
        self.gatt_output.bind("<<TreeviewSelect>>", self.on_tree_select)

    def setup_brain_map_canvas(self):
        """Setup the brain map canvas with LED visualization capability"""
        try:
            # Load and resize brain map image
            self.brain_image_obj = Image.open("brainmap.png")
            max_width = 358
            w, h = self.brain_image_obj.size
            scale = min(max_width / w, 1)
            new_size = (int(w * scale), int(h * scale))
            
            self.brain_image_obj = self.brain_image_obj.resize(new_size, Image.LANCZOS)
            brain_img = ImageTk.PhotoImage(self.brain_image_obj)
            
            # Create canvas for interactive brain map
            self.brain_canvas = tk.Canvas(self.right_frame, width=new_size[0], height=new_size[1])
            self.brain_canvas.pack()
            
            # Draw brain map image on canvas
            self.brain_canvas.create_image(0, 0, anchor=tk.NW, image=brain_img)
            self.brain_canvas.image = brain_img  # Keep reference
            
            # Calculate LED rectangle positions (8x8 grid)
            self.calculate_led_positions(new_size[0], new_size[1])
            
            # Bind click events for LED interaction
            self.brain_canvas.bind("<Button-1>", self.on_led_click)
            
        except FileNotFoundError:
            # If brain map image not found, just skip it
            pass

    def calculate_led_positions(self, canvas_width, canvas_height):
        """Calculate the positions of LED rectangles on the brain map using pixel coordinates"""
        self.led_rectangles = []
        
        # Define LED dimensions (uniform for all LEDs) - CHANGE THESE TO RESIZE ALL LEDS
        led_width = 13
        led_height = 23
        
        # Define pixel coordinates for each LED (you can fine-tune these)
        # Format: [Top-left X, Top-left Y] - Width and Height are taken from variables above
        # Arranged as 8 rows x 8 columns (bit 0-7 = row 1, bit 8-15 = row 2, etc.)
        # Canvas size: {canvas_width} x {canvas_height}
        
        X_space = 26
        Y_space = 26+11+3
        ARB_X = 106
        ARB_Y = 25

        led_pixel_map = {
            # Row 1 (Y=1, bits 0-7) - Top row
            0:  [ARB_X-X_space*3, ARB_Y+Y_space*5],    # X=1, Y=1 (bit 0)
            1:  [ARB_X, 24],    # X=2, Y=1 (bit 1)
            2:  [ARB_X+X_space*1, ARB_Y],   # X=3, Y=1 (bit 2)
            3:  [ARB_X+X_space*2, ARB_Y],   # X=4, Y=1 (bit 3)
            4:  [ARB_X+X_space*3, ARB_Y],   # X=5, Y=1 (bit 4)
            5:  [ARB_X+X_space*4, ARB_Y],   # X=6, Y=1 (bit 5)
            6:  [ARB_X+X_space*5, ARB_Y],   # X=7, Y=1 (bit 6)
            7:  [ARB_X+X_space*8, ARB_Y+Y_space*5],   # X=8, Y=1 (bit 7)
            
            # Row 2 (Y=2, bits 8-15)
            8:  [ARB_X-X_space*1, ARB_Y+Y_space*1],    # X=1, Y=2 (bit 8)
            9:  [ARB_X, ARB_Y+Y_space*1],    # X=2, Y=2 (bit 9)
            10: [ARB_X+X_space*1, ARB_Y+Y_space*1],   # X=3, Y=2 (bit 10)
            11: [ARB_X+X_space*2, ARB_Y+Y_space*1],   # X=4, Y=2 (bit 11)
            12: [ARB_X+X_space*3, ARB_Y+Y_space*1],   # X=5, Y=2 (bit 12)
            13: [ARB_X+X_space*4, ARB_Y+Y_space*1],   # X=6, Y=2 (bit 13)
            14: [ARB_X+X_space*5, ARB_Y+Y_space*1],   # X=7, Y=2 (bit 14)
            15: [ARB_X+X_space*6, ARB_Y+Y_space*1],   # X=8, Y=2 (bit 15)
            
            # Row 3 (Y=3, bits 16-23)
            16: [ARB_X-X_space*1, ARB_Y+Y_space*2],   # X=1, Y=3 (bit 16)
            17: [ARB_X, ARB_Y+Y_space*2],   # X=2, Y=3 (bit 17)
            18: [ARB_X+X_space*1, ARB_Y+Y_space*2],  # X=3, Y=3 (bit 18)
            19: [ARB_X+X_space*2, ARB_Y+Y_space*2],  # X=4, Y=3 (bit 19)
            20: [ARB_X+X_space*3, ARB_Y+Y_space*2],  # X=5, Y=3 (bit 20)
            21: [ARB_X+X_space*4, ARB_Y+Y_space*2],  # X=6, Y=3 (bit 21)
            22: [ARB_X+X_space*5, ARB_Y+Y_space*2],  # X=7, Y=3 (bit 22)
            23: [ARB_X+X_space*6, ARB_Y+Y_space*2],  # X=8, Y=3 (bit 23)
            
            # Row 4 (Y=4, bits 24-31)
            24: [ARB_X-X_space*1, ARB_Y+Y_space*3],   # X=1, Y=4 (bit 24)
            25: [ARB_X, ARB_Y+Y_space*3],   # X=2, Y=4 (bit 25)
            26: [ARB_X+X_space*1, ARB_Y+Y_space*3],   # X=3, Y=4 (bit 26)
            27: [ARB_X+X_space*2, ARB_Y+Y_space*3],  # X=4, Y=4 (bit 27)
            28: [ARB_X+X_space*3, ARB_Y+Y_space*3],  # X=5, Y=4 (bit 28)
            29: [ARB_X+X_space*4, ARB_Y+Y_space*3],  # X=6, Y=4 (bit 29)
            30: [ARB_X+X_space*5, ARB_Y+Y_space*3],  # X=7, Y=4 (bit 30)
            31: [ARB_X+X_space*6, ARB_Y+Y_space*3],  # X=8, Y=4 (bit 31)
            
            # Row 5 (Y=5, bits 32-39)
            32: [ARB_X-X_space*1, ARB_Y+Y_space*4],   # X=1, Y=5 (bit 32)
            33: [ARB_X, ARB_Y+Y_space*4],   # X=2, Y=5 (bit 33)
            34: [ARB_X+X_space*1, ARB_Y+Y_space*4],   # X=3, Y=5 (bit 34)
            35: [ARB_X+X_space*2, ARB_Y+Y_space*4],  # X=4, Y=5 (bit 35)
            36: [ARB_X+X_space*3, ARB_Y+Y_space*4],  # X=5, Y=5 (bit 36)
            37: [ARB_X+X_space*4, ARB_Y+Y_space*4],  # X=6, Y=5 (bit 37)
            38: [ARB_X+X_space*5, ARB_Y+Y_space*4],  # X=7, Y=5 (bit 38)
            39: [ARB_X+X_space*6, ARB_Y+Y_space*4],  # X=8, Y=5 (bit 39)
            
            # Row 6 (Y=6, bits 40-47)
            40: [ARB_X-X_space*1, ARB_Y+Y_space*5],   # X=1, Y=6 (bit 40)
            41: [ARB_X, ARB_Y+Y_space*5],   # X=2, Y=6 (bit 41)
            42: [ARB_X+X_space*1, ARB_Y+Y_space*5],   # X=3, Y=6 (bit 42)
            43: [ARB_X+X_space*2, ARB_Y+Y_space*5],  # X=4, Y=6 (bit 43)
            44: [ARB_X+X_space*3, ARB_Y+Y_space*5],  # X=5, Y=6 (bit 44)
            45: [ARB_X+X_space*4, ARB_Y+Y_space*5],  # X=6, Y=6 (bit 45)
            46: [ARB_X+X_space*5, ARB_Y+Y_space*5],  # X=7, Y=6 (bit 46)
            47: [ARB_X+X_space*6, ARB_Y+Y_space*5],  # X=8, Y=6 (bit 47)
            
            # Row 7 (Y=7, bits 48-55)
            48: [ARB_X-X_space*1, ARB_Y+Y_space*6],   # X=1, Y=7 (bit 48)
            49: [ARB_X, ARB_Y+Y_space*6],   # X=2, Y=7 (bit 49)
            50: [ARB_X+X_space*1, ARB_Y+Y_space*6],   # X=3, Y=7 (bit 50)
            51: [ARB_X+X_space*2, ARB_Y+Y_space*6],  # X=4, Y=7 (bit 51)
            52: [ARB_X+X_space*3, ARB_Y+Y_space*6],  # X=5, Y=7 (bit 52)
            53: [ARB_X+X_space*4, ARB_Y+Y_space*6],  # X=6, Y=7 (bit 53)
            54: [ARB_X+X_space*5, ARB_Y+Y_space*6],  # X=7, Y=7 (bit 54)
            55: [ARB_X+X_space*6, ARB_Y+Y_space*6],  # X=8, Y=7 (bit 55)
            
            # Row 8 (Y=8, bits 56-63) - Bottom row
            56: [ARB_X-X_space*2, ARB_Y+Y_space*3],   # X=1, Y=8 (bit 56)
            57: [ARB_X-X_space*2, ARB_Y+Y_space*4],   # X=2, Y=8 (bit 57)
            58: [ARB_X-X_space*2, ARB_Y+Y_space*5],   # X=3, Y=8 (bit 58)
            59: [ARB_X-X_space*2, ARB_Y+Y_space*6],  # X=4, Y=8 (bit 59)
            60: [ARB_X+X_space*7, ARB_Y+Y_space*3],  # X=5, Y=8 (bit 60)
            61: [ARB_X+X_space*7, ARB_Y+Y_space*4],  # X=6, Y=8 (bit 61)
            62: [ARB_X+X_space*7, ARB_Y+Y_space*5],  # X=7, Y=8 (bit 62)
            63: [ARB_X+X_space*7, ARB_Y+Y_space*6],  # X=8, Y=8 (bit 63)
        }
    
        # Create LED rectangles from the pixel map
        for bit_position in range(64):
            if bit_position in led_pixel_map:
                x, y = led_pixel_map[bit_position]
                x1, y1 = x, y
                x2, y2 = x + led_width, y + led_height  # Use current led_width and led_height
                
                grid_x = (bit_position % 8) + 1  # X coordinate (1-8)
                grid_y = (bit_position // 8) + 1  # Y coordinate (1-8)
                
                self.led_rectangles.append({
                    'x': grid_x,
                    'y': grid_y,
                    'bit': bit_position,
                    'coords': (x1, y1, x2, y2),
                    'canvas_id': None,
                    'text_id': None  # New field to store text canvas ID
                })
        
        # Show all LEDs immediately for positioning adjustment
        self.update_led_visualization()
        
    def bit_to_coordinates(self, bit_position):
        """Convert bit position (0-63) to X,Y coordinates (1-8, 1-8)"""
        y = (bit_position // 8) + 1
        x = (bit_position % 8) + 1
        return x, y

    def coordinates_to_bit(self, x, y):
        """Convert X,Y coordinates (1-8, 1-8) to bit position (0-63)"""
        return (y - 1) * 8 + (x - 1)

    def update_led_visualization(self):
        """Update the LED visualization based on current selection"""
        if not self.brain_canvas:
            return
            
        # Clear existing LED rectangles and text
        for led in self.led_rectangles:
            if led['canvas_id']:
                self.brain_canvas.delete(led['canvas_id'])
                led['canvas_id'] = None
            if led['text_id']:
                self.brain_canvas.delete(led['text_id'])
                led['text_id'] = None
        
        # Only draw selected LEDs
        for led in self.led_rectangles:
            bit_position = led['bit']
            
            if self.led_selection_value & (1 << bit_position):  # Check if bit is set
                x1, y1, x2, y2 = led['coords']
                
                # Calculate center position for text
                center_x = x1 + (x2 - x1) / 2
                center_y = y1 + (y2 - y1) / 2
                
                # LED index is bit_position + 1 (1-64 instead of 0-63)
                led_index = bit_position + 1
                
                # Draw selected LED as light blue with matching outline
                led['canvas_id'] = self.brain_canvas.create_rectangle(
                    x1, y1, x2, y2, 
                    fill='blue', 
                    outline='blue', 
                    width=2
                )
                # Add centered text with contrasting color
                led['text_id'] = self.brain_canvas.create_text(
                    center_x, center_y,
                    text=str(led_index),
                    fill='white',
                    font=('Arial', '10', 'bold')
                )

    def on_led_click(self, event):
        """Handle clicks on the brain map to toggle LED selection"""
        if not self.brain_canvas:
            return
            
        # Find which LED was clicked
        clicked_led = None
        for led in self.led_rectangles:
            x1, y1, x2, y2 = led['coords']
            if x1 <= event.x <= x2 and y1 <= event.y <= y2:
                clicked_led = led
                break
        
        if clicked_led:
            # Toggle the bit for this LED
            bit_position = clicked_led['bit']
            self.led_selection_value ^= (1 << bit_position)  # XOR to toggle
            
            # Update the GATT table with new value
            self.update_led_selection_in_gatt()
            
            # Update visualization
            self.update_led_visualization()

    def update_led_selection_in_gatt(self):
        """Update the LED Selection value in the GATT table"""
        led_selection_uuid = "56781601-5678-1234-1234-5678abcdeff0"
        
        # Find the LED Selection item in the tree
        for item in self.gatt_output.get_children():
            char_uuid = self.char_uuid_map.get(item)
            if char_uuid == led_selection_uuid:
                values = list(self.gatt_output.item(item, "values"))
                values[3] = str(self.led_selection_value)  # Update WriteValue column
                self.gatt_output.item(item, values=values)
                break

    def on_tree_select(self, event):
        """Handle tree selection for real-time updates"""
        # This could be used for additional real-time features if needed
        pass

    def log(self, text):
        self.output.insert(tk.END, text + "\n")
        self.output.see(tk.END)

    def start_scan(self):
        self.log("Scanning for BLE devices containing 'OptoGrid'...")
        self.scan_button.config(state="disabled", text="Scanning...")
        try:
            self.run_async(self.scan(), callback=self.on_scan_complete)
        except Exception as e:
            self.log(f"Scan failed: {e}")
            self.scan_button.config(state="normal", text="Scan")

    def on_scan_complete(self, result):
        """Called when scan completes"""
        self.scan_button.config(state="normal", text="Scan")

    async def scan(self):
        all_devices = await BleakScanner.discover()
        self.device_list = [d for d in all_devices if d.name and "OptoGrid" in d.name]
        names = [f"{d.name}" for d in self.device_list]
        
        # Update UI in main thread
        self.root.after(0, lambda: self._update_device_list(names))

    def _update_device_list(self, names):
        """Update device list in main thread"""
        self.devices_box['values'] = names
        if names:
            self.devices_box.current(0)
        self.log(f"Found {len(self.device_list)} matching devices.")

    def connect_to_device(self):
        if not self.device_list:
            messagebox.showwarning("No Devices", "Scan first!")
            return
        index = self.devices_box.current()
        if index == -1:
            messagebox.showwarning("No Selection", "Select a device first!")
            return
        self.selected_device = self.device_list[index]
        self.log(f"Connecting to {self.selected_device.name} ...")
        self.connect_button.config(state="disabled", text="Connecting...")
        try:
            self.run_async(self.connect_and_browse(self.selected_device), callback=self.on_connect_complete)
        except Exception as e:
            self.log(f"Connection failed: {e}")
            self.connect_button.config(state="normal", text="Connect")

    def on_connect_complete(self, result):
        """Called when connection completes"""
        self.connect_button.config(state="normal", text="Connect")

    async def connect_and_browse(self, device):
        try:
            # Disconnect any existing client
            if self.client and self.client.is_connected:
                await self.client.disconnect()
            
            self.client = BleakClient(device.address)
            await self.client.connect()
            self.log("Connected. Discovering services...")
            
            # Enable read/write buttons in main thread
            self.root.after(0, lambda: self._enable_buttons())
            
            await self.populate_gatt_table()
            
        except Exception as e:
            self.log(f"Connection failed: {e}")
            self.client = None
            # Disable buttons in main thread
            self.root.after(0, lambda: self._disable_buttons())

    def _enable_buttons(self):
        """Enable read/write buttons in main thread"""
        self.read_button.config(state="normal")
        self.write_button.config(state="normal")
        self.trigger_button.config(state="normal")

    def _disable_buttons(self):
        """Disable read/write buttons in main thread"""
        self.read_button.config(state="disabled")
        self.write_button.config(state="disabled")
        self.trigger_button.config(state="disabled")

    async def populate_gatt_table(self):
        # Clear existing data
        self.char_uuid_map.clear()
        self.char_writable_map.clear()
        data_to_insert = []
        
        past_svc_name = "None"
        for service in self.client.services:
            svc_uuid = str(service.uuid).lower()
            svc_name = UUID_NAME_MAP.get(svc_uuid, 'Unknown Service')
            
            for char in service.characteristics:
                char_uuid = str(char.uuid).lower()
                char_name = UUID_NAME_MAP.get(char_uuid, 'Unknown Characteristic')
                props = char.properties
                
                # Check if characteristic is writable
                is_writable = "write" in props or "write-without-response" in props
                
                try:
                    val = await self.client.read_gatt_char(char.uuid)
                    val_display = decode_value(char_uuid, val)
                    
                    # Update LED selection if this is the LED Selection characteristic
                    if char_uuid == "56781601-5678-1234-1234-5678abcdeff0":  # LED Selection
                        try:
                            self.led_selection_value = int.from_bytes(val[:8], byteorder='little')
                        except:
                            self.led_selection_value = 0
                            
                except Exception:
                    val_display = "<not readable>"

                unit_name = uuid_to_unit.get(char_uuid, 'Unknown')
                
                service_display = svc_name if svc_name != past_svc_name else ""
                
                # For write value, show current value if writable, otherwise show as read-only
                write_value_display = val_display if is_writable else "<read-only>"
                
                data_to_insert.append((
                    service_display, char_name, val_display, write_value_display, unit_name, char_uuid, is_writable
                ))
                past_svc_name = svc_name
        
        # Update UI in main thread
        self.root.after(0, lambda: self._update_gatt_table(data_to_insert))

    def _update_gatt_table(self, data_to_insert):
        """Update GATT table in main thread"""
        # Clear existing data
        for i in self.gatt_output.get_children():
            self.gatt_output.delete(i)
        
        # Insert new data
        for data in data_to_insert:
            char_uuid = data[5]
            is_writable = data[6]
            values = data[:5]  # Only take first 5 values (excluding char_uuid and is_writable)
            
            # Choose tag based on writability
            tag = "writable" if is_writable else "readonly"
            
            item = self.gatt_output.insert("", "end", values=values, tags=(tag,))
            self.char_uuid_map[item] = char_uuid
            self.char_writable_map[item] = is_writable
        
        # Update LED visualization after populating table
        self.update_led_visualization()

    def on_double_click(self, event):
        """Handle double-click on treeview to edit WriteValue column"""
        item = self.gatt_output.selection()[0] if self.gatt_output.selection() else None
        if not item:
            return
        
        # Check if this is a writable characteristic
        if not self.char_writable_map.get(item, False):
            return  # Don't allow editing read-only characteristics
            
        # Get column clicked
        column = self.gatt_output.identify_column(event.x)
        if column == "#4":  # WriteValue column
            self.edit_write_value(item)

    def edit_write_value(self, item):
        """Open a dialog to edit the write value"""
        current_value = self.gatt_output.item(item, "values")[3]
        char_name = self.gatt_output.item(item, "values")[1]
        
        # Create input dialog
        dialog = tk.Toplevel(self.root)
        dialog.title(f"Edit {char_name}")
        dialog.geometry("300x150")
        dialog.transient(self.root)
        dialog.grab_set()
        
        tk.Label(dialog, text=f"Enter new value for {char_name}:").pack(pady=10)
        
        entry = tk.Entry(dialog, width=40)
        entry.pack(pady=5)
        entry.insert(0, current_value)
        entry.select_range(0, tk.END)
        entry.focus()
        
        def save_value():
            new_value = entry.get()
            values = list(self.gatt_output.item(item, "values"))
            values[3] = new_value  # Update WriteValue column
            self.gatt_output.item(item, values=values)
            
            # If this is LED Selection, update the visualization
            char_uuid = self.char_uuid_map.get(item)
            if char_uuid == "56781601-5678-1234-1234-5678abcdeff0":  # LED Selection
                try:
                    self.led_selection_value = int(new_value)
                    self.update_led_visualization()
                except ValueError:
                    pass  # Invalid value, ignore
            
            dialog.destroy()
        
        tk.Button(dialog, text="Save", command=save_value).pack(pady=10)
        
        # Bind Enter key to save
        entry.bind('<Return>', lambda e: save_value())

    def send_trigger(self):
        """Send trigger signal to the device"""
        if not self.client or not self.client.is_connected:
            messagebox.showwarning("Not Connected", "Please connect to a device first!")
            return
        
        self.log("Sending opto trigger...")
        self.trigger_button.config(state="disabled", text="Triggering...")
        try:
            self.run_async(self.do_send_trigger(), callback=self.on_trigger_complete)
        except Exception as e:
            self.log(f"Error sending trigger: {e}")
            self.trigger_button.config(state="normal", text="TRIGGER")

    def on_trigger_complete(self, result):
        """Called when trigger send completes"""
        self.trigger_button.config(state="normal", text="TRIGGER")

    async def do_send_trigger(self):
        trigger_uuid = "56781609-5678-1234-1234-5678abcdeff0"  # Trigger characteristic UUID
        
        try:
            # Find the trigger characteristic object
            char_obj = None
            for service in self.client.services:
                for char in service.characteristics:
                    if str(char.uuid).lower() == trigger_uuid:
                        char_obj = char
                        break
                if char_obj:
                    break
            
            if not char_obj:
                self.log("Trigger characteristic not found!")
                return
            
            # Check if it's writable
            if "write" not in char_obj.properties and "write-without-response" not in char_obj.properties:
                self.log("Trigger characteristic is not writable!")
                return
            
            # Encode "True" as boolean value
            encoded_value = encode_value(trigger_uuid, "True")
            
            # Write the trigger value
            await self.client.write_gatt_char(char_obj.uuid, encoded_value)
            self.log("Sent an opto trigger!")
            
            # Update the GATT table to show the trigger was sent
            self.root.after(0, lambda: self._update_trigger_in_gatt("True"))
            
        except Exception as e:
            self.log(f"Error sending trigger: {e}")

    def _update_trigger_in_gatt(self, value):
        """Update the trigger value in the GATT table"""
        trigger_uuid = "56781609-5678-1234-1234-5678abcdeff0"
        
        # Find the Trigger item in the tree
        for item in self.gatt_output.get_children():
            char_uuid = self.char_uuid_map.get(item)
            if char_uuid == trigger_uuid:
                values = list(self.gatt_output.item(item, "values"))
                values[2] = value  # Update Current Value column
                values[3] = value  # Update WriteValue column
                self.gatt_output.item(item, values=values)
                break

    def setup_event_loop(self):
        """Set up a persistent event loop in a separate thread"""
        def run_loop():
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)
            self.loop.run_forever()
        
        self.loop_thread = threading.Thread(target=run_loop, daemon=True)
        self.loop_thread.start()
        
        # Wait for loop to be ready
        while self.loop is None:
            pass

    def run_async(self, coro, callback=None):
        """Run an async coroutine in the background event loop"""
        if self.loop and not self.loop.is_closed():
            future = asyncio.run_coroutine_threadsafe(coro, self.loop)
            if callback:
                # Run callback in main thread when done
                def on_done(fut):
                    try:
                        result = fut.result()
                        self.root.after(0, lambda: callback(result))
                    except Exception as e:
                        self.root.after(0, lambda: self.log(f"Error: {e}"))
                future.add_done_callback(on_done)
            return future
        else:
            raise RuntimeError("Event loop not available")

    def read_all_values(self):
        """Read all current values from the device"""
        if not self.client or not self.client.is_connected:
            messagebox.showwarning("Not Connected", "Please connect to a device first!")
            return
        
        self.log("Reading all values...")
        self.read_button.config(state="disabled", text="Reading...")
        try:
            self.run_async(self.do_read_all(), callback=self.on_read_complete)
        except Exception as e:
            self.log(f"Error reading values: {e}")
            self.read_button.config(state="normal", text="Read All Values")

    def on_read_complete(self, result):
        """Called when read completes"""
        self.read_button.config(state="normal", text="Read All Values")

    async def do_read_all(self):
        try:
            await self.populate_gatt_table()
            self.log("All values read successfully.")
        except Exception as e:
            self.log(f"Error reading values: {e}")

    def write_values(self):
        """Write all modified values to the device"""
        if not self.client or not self.client.is_connected:
            messagebox.showwarning("Not Connected", "Please connect to a device first!")
            return
        
        self.log("Writing values...")
        self.write_button.config(state="disabled", text="Writing...")
        try:
            self.run_async(self.do_write_values(), callback=self.on_write_complete)
        except Exception as e:
            self.log(f"Error writing values: {e}")
            self.write_button.config(state="normal", text="Write Values")

    def on_write_complete(self, result):
        """Called when write completes"""
        self.write_button.config(state="normal", text="Write Values")

    async def do_write_values(self):
        write_count = 0
        error_count = 0
        skipped_count = 0
        updates = []  # Store updates for main thread
        
        # Get all current tree data
        tree_data = []
        for item in self.gatt_output.get_children():
            values = self.gatt_output.item(item, "values")
            tree_data.append((item, values))
        
        for item, values in tree_data:
            current_value = values[2]  # Current Value
            write_value = values[3]    # Write Value
            char_name = values[1]      # Characteristic Name
            
            # Skip if not writable
            if not self.char_writable_map.get(item, False):
                if write_value != "<read-only>" and write_value != current_value and write_value.strip():
                    self.log(f"Skipping read-only characteristic: {char_name}")
                    skipped_count += 1
                continue
            
            # Only write if the write value is different from current value and is not empty
            if write_value != current_value and write_value.strip() and write_value != "<read-only>":
                char_uuid = self.char_uuid_map.get(item)
                if not char_uuid:
                    self.log(f"No UUID found for characteristic: {char_name}")
                    error_count += 1
                    continue
                
                try:
                    # Find the characteristic object
                    char_obj = None
                    for service in self.client.services:
                        for char in service.characteristics:
                            if str(char.uuid).lower() == char_uuid:
                                char_obj = char
                                break
                        if char_obj:
                            break
                    
                    if not char_obj:
                        self.log(f"Characteristic object not found: {char_name}")
                        error_count += 1
                        continue
                    
                    # Double-check writability (should already be filtered, but being extra safe)
                    if "write" not in char_obj.properties and "write-without-response" not in char_obj.properties:
                        self.log(f"Characteristic not writable (double-check): {char_name}")
                        skipped_count += 1
                        continue
                    
                    # Encode the value
                    encoded_value = encode_value(char_uuid, write_value)
                    
                    # Write the value
                    await self.client.write_gatt_char(char_obj.uuid, encoded_value)
                    self.log(f"Written to {char_name}: {write_value}")
                    write_count += 1
                    
                    # If this is LED Selection, update our local value and visualization
                    if char_uuid == "56781601-5678-1234-1234-5678abcdeff0":  # LED Selection
                        try:
                            self.led_selection_value = int(write_value)
                            # Update visualization in main thread
                            self.root.after(0, self.update_led_visualization)
                        except ValueError:
                            pass
                    
                    # Store update for main thread
                    new_values = list(values)
                    new_values[2] = write_value  # Update current value to match written value
                    updates.append((item, new_values))
                    
                except Exception as e:
                    self.log(f"Error writing to {char_name}: {e}")
                    error_count += 1
        
        # Update UI in main thread
        self.root.after(0, lambda: self._apply_write_updates(updates))
        
        # Log summary
        summary_parts = []
        if write_count > 0:
            summary_parts.append(f"{write_count} written")
        if skipped_count > 0:
            summary_parts.append(f"{skipped_count} skipped (read-only)")
        if error_count > 0:
            summary_parts.append(f"{error_count} errors")
        
        summary = ", ".join(summary_parts) if summary_parts else "no operations performed"
        self.log(f"Write operation complete: {summary}")

    def _apply_write_updates(self, updates):
        """Apply write updates to the UI in main thread"""
        for item, new_values in updates:
            self.gatt_output.item(item, values=new_values)

if __name__ == "__main__":
    root = tk.Tk()
    root.geometry("950x1000")  # Adjusted width since we removed Properties column
    app = BLEClientUI(root)
    root.mainloop()