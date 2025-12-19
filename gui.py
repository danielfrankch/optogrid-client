"""
OptoGrid GUI Frontend
PyQt5 interface that connects to the OptoGridClient backend.
"""

import os
import sys
import time
import csv
import datetime
from typing import Dict, List, Optional, Tuple
import numpy as np
from functools import partial

# Set Qt environment variables before importing PyQt
os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "0"
os.environ["QT_SCALE_FACTOR"] = "1"
os.environ["QT_ENABLE_HIGHDPI_SCALING"] = "0"
os.environ['QT_LOGGING_RULES'] = '*.warning=false'

# Import PyQt5 components
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QComboBox, QTextEdit, QTreeWidget, QTreeWidgetItem,
    QLabel, QMessageBox, QDialog, QLineEdit, QDialogButtonBox,
    QFrame, QHeaderView, QCheckBox, QProgressBar, QOpenGLWidget
)
from PyQt5.QtCore import Qt, QTimer, QRect, pyqtSignal
from PyQt5.QtGui import QPainter, QPen, QBrush, QFont, QPixmap, QColor, QVector3D
from PIL import Image
import pyqtgraph as pg
from OpenGL.GL import glLineWidth

# Import backend
from optogrid_client import OptoGridClient, UUID_NAME_MAP, uuid_to_unit, decode_value, encode_value

# Import widget classes from original (these are pure GUI)
from pyqt_optogrid_python_client import (
    EditValueDialog
)

from bleak import BLEDevice


class OptoGridGUI(QMainWindow):
    """
    Main GUI application window that interfaces with OptoGridClient backend.
    """
    
    def __init__(self, backend_client: OptoGridClient):
        """
        Initialize GUI with shared backend client.
        
        Args:
            backend_client: OptoGridClient instance for BLE/ZMQ operations
        """
        super().__init__()
        
        # Store backend reference
        self.backend_client = backend_client
        
        # Window setup
        self.setWindowTitle("OptoGrid BLE Browser")
        screen = QApplication.primaryScreen()
        size = screen.size()
        self.window_height = int(size.height() * 0.87)  # 87% of screen height
        self.window_width = int(self.window_height * 1.13)   # width is 50% of height
        
        self.setGeometry(0, 0, self.window_width, self.window_height)
        
        # Make window non-resizable
        self.setFixedSize(self.window_width, self.window_height)
        
        # Proportional font sizes (based on window height)
        self.font_large = int(self.window_height * 0.0165)   # ~16px at 972px height
        self.font_medium = int(self.window_height * 0.0144)  # ~14px at 972px height
        self.font_small = int(self.window_height * 0.0123)   # ~12px at 972px height
        self.font_mini = int(self.window_height * 0.0102)  # ~10px at 972 px height

        # GUI state
        self.device_list: List[BLEDevice] = []
        self.selected_device: Optional[BLEDevice] = None
        self.char_uuid_map: Dict[int, str] = {}
        self.char_writable_map: Dict[int, bool] = {}
        self.led_selection_value = 0
        self.item_counter = 0
        self.current_battery_voltage = None
        self.imu_enable_state = False
        self.sham_led_state = False
        self.status_led_state = False
        
        # IMU data for GUI
        self.imu_csv_file = None
        self.imu_csv_writer = None
        self.imu_counter = 0
        
        # Battery voltage auto-read timer
        self.battery_timer = QTimer()
        self.battery_timer.timeout.connect(self.read_battery_voltage)
        
        # Set consistent font across platforms
        app = QApplication.instance()
        if app:
            default_font = QFont("Arial", self.font_mini)
            default_font.setStyleHint(QFont.SansSerif)
            app.setFont(default_font)
        
        # Setup UI components
        self.setup_ui()
        self.setup_connections()
        
        # Register callbacks from backend
        self._setup_backend_callbacks()
        
        # Start in non-debug mode
        self.toggle_debug_mode(False)
        self.debug_button.setEnabled(True)
        
        self.log("OptoGrid GUI initialized")
    
    
    def _setup_backend_callbacks(self):
        """Register callbacks to receive events from backend"""
        
        # Scan complete
        self.backend_client.register_callback(
            "scan_complete",
            lambda devices: QTimer.singleShot(0, partial(self.on_scan_complete, devices))
        )
        
        # Connection events  
        self.backend_client.register_callback(
            "connected",
            lambda name, addr: QTimer.singleShot(0, partial(self.on_connected, name, addr))
        )

        # Connection failed
        self.backend_client.register_callback(
            "connection_failed",
            lambda error: QTimer.singleShot(0, partial(self.on_connection_failed, error))
        )
        
        self.backend_client.register_callback(
            "disconnected",
            lambda: QTimer.singleShot(0, self.on_disconnected)
        )
        
        # Device log messages
        self.backend_client.register_callback(
            "device_log",
            lambda msg: QTimer.singleShot(0, partial(self.log, f"Device: {msg}"))
        )
        
        # IMU updates
        self.backend_client.register_callback(
            "imu_update",
            lambda roll, pitch, yaw, imu_values: QTimer.singleShot(
                0, partial(self._on_imu_update, roll, pitch, yaw, imu_values)
            )
        )
        
        # Battery updates
        self.backend_client.register_callback(
            "battery_update",
            lambda voltage: QTimer.singleShot(0, partial(self._on_battery_update, voltage))
        )
        
        # LED check updates
        self.backend_client.register_callback(
            "led_check",
            lambda value: QTimer.singleShot(0, partial(self.brain_map.update_led_check_overlay, value))
        )
        
        # ZMQ started
        self.backend_client.register_callback(
            "zmq_started",
            lambda ip: QTimer.singleShot(0, partial(self.log, f"ZMQ server listening on tcp://{ip}:5555"))
        )
    
    def setup_ui(self):
        """Setup the user interface"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        # --- Top Section ---
        top_section = QHBoxLayout()

        # Left: Device controls, log, and buttons
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setSpacing(int(self.window_height * 0.004))
        left_layout.setContentsMargins(int(self.window_width * 0.004), int(self.window_height * 0.004), 
                                       int(self.window_width * 0.004), int(self.window_height * 0.004))

        device_frame = QFrame()
        device_layout = QHBoxLayout(device_frame)
        controls_container = QVBoxLayout()
        controls_container.setSpacing(int(self.window_height * 0.004))
        controls_container.setContentsMargins(0, 0, 0, 0)
        
        self.scan_button = QPushButton("Scan")
        self.scan_button.setStyleSheet(f"font-size: {self.font_large}px;")
        self.scan_button.setFixedWidth(int(self.window_width * 0.24))
        controls_container.addWidget(self.scan_button)
        controls_container.addSpacing(int(self.window_width * 0.01))

        self.devices_combo = QComboBox()
        self.devices_combo.setFixedWidth(int(self.window_width * 0.24))
        self.devices_combo.setStyleSheet(f"font-size: {self.font_large}px;")
        controls_container.addWidget(self.devices_combo)
        controls_container.addSpacing(int(self.window_width * 0.01))

        self.connect_button = QPushButton("Connect")
        self.connect_button.setStyleSheet(f"font-size: {self.font_large}px;")
        self.connect_button.setFixedWidth(int(self.window_width * 0.24))
        controls_container.addWidget(self.connect_button)
        controls_container.addSpacing(int(self.window_width * 0.015))

        self.debug_button = QCheckBox("Debug Mode")
        self.debug_button.setStyleSheet(f"""
            QCheckBox {{ spacing: {int(self.window_width * 0.017)}px; font-weight: bold; font-size: {self.font_large}px;}}
            QCheckBox::indicator {{ width: {int(self.window_width * 0.0625)}px; height: {int(self.window_height * 0.015)}px; border: 2px solid #8f8f91; border-radius: 8px; }}
            QCheckBox::indicator:unchecked {{ background-color: #f0f0f0; }}
            QCheckBox::indicator:checked {{ background-color: #90EE90; border-color: #4CAF50; }}
        """)
        controls_container.addWidget(self.debug_button)

        device_layout.addLayout(controls_container)
        left_layout.addWidget(device_frame)

        # Add IMU 3D display
        self.imu_3d_widget = IMU3DWidget(window_width=self.window_width, window_height=self.window_height)
        device_layout.addWidget(self.imu_3d_widget)
        
        # Log output
        self.log_text = QTextEdit()
        self.log_text.setFixedSize(int(self.window_width * 0.6), int(self.window_height * 0.22)) 
        log_font = QFont("Consolas", self.font_large)
        if not log_font.exactMatch():
            log_font = QFont("Courier New", self.font_large)
        self.log_text.setFont(log_font)
        self.log_text.setStyleSheet(f"""
            QTextEdit {{
                line-height: 1.2;
                font-family: "Consolas", "Courier New", monospace;
                font-size: {self.font_large}pt;
                border: 1px solid #ccc;
            }}
        """)
        left_layout.addWidget(self.log_text)
        left_layout.addSpacing(int(self.window_height * 0.002))

        # Control buttons
        control_frame = QFrame()
        control_layout = QHBoxLayout(control_frame)
        control_layout.setSpacing(0)
        control_layout.setContentsMargins(0, 0, 0, 0)
        
        self.read_button = QPushButton("Read All Values")
        self.read_button.setStyleSheet(f"font-size: {self.font_large}px; font-weight: bold;")
        self.read_button.setFixedSize(int(self.window_width * 0.18), int(self.window_height * 0.044))
        self.read_button.setEnabled(False)
        control_layout.addWidget(self.read_button)
        control_layout.addSpacing(int(self.window_width * 0.02))
        
        self.write_button = QPushButton("Write Values")
        self.write_button.setStyleSheet(f"font-size: {self.font_large}px; font-weight: bold;")
        self.write_button.setFixedSize(int(self.window_width * 0.18), int(self.window_height * 0.044))
        self.write_button.setEnabled(False)
        control_layout.addWidget(self.write_button)
        control_layout.addSpacing(int(self.window_width * 0.02))

        self.trigger_button = QPushButton("TRIGGER")
        self.trigger_button.setEnabled(False)
        self.trigger_button.setStyleSheet(f"background-color: #ff4444; font-weight: bold;font-size: {self.font_large}px;")
        self.trigger_button.setFixedSize(int(self.window_width * 0.18), int(self.window_height * 0.034)) 
        control_layout.addWidget(self.trigger_button)
        left_layout.addWidget(control_frame)
        top_section.addWidget(left_panel, 2)

        # Right: Brain map and LED controls
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setSpacing(int(self.window_height * 0.004))
        right_layout.setContentsMargins(int(self.window_width * 0.004), int(self.window_height * 0.004),
                                        int(self.window_width * 0.004), int(self.window_height * 0.004))
        
        label = QLabel("Toggle the LEDs to select:")
        label.setStyleSheet(f"font-size: {self.font_large}px;font-weight: bold;")
        right_layout.addWidget(label)
        
        self.brain_map = BrainMapWidget(font_mini=self.font_mini, window_width=self.window_width, window_height=self.window_height)
        right_layout.addWidget(self.brain_map)
        
        led_state_frame = QFrame()
        led_state_layout = QHBoxLayout(led_state_frame)
        right_layout.addSpacing(int(self.window_height * 0.001))

        self.sham_led_button = QPushButton("SHAM LED")
        self.sham_led_button.setEnabled(False)
        self.sham_led_button.setFixedSize(int(self.window_width * 0.1), int(self.window_height * 0.034))
        self.sham_led_button.setStyleSheet(f"background-color: #888888; font-weight: bold; font-size: {self.font_large}px;")
        led_state_layout.addWidget(self.sham_led_button)
        led_state_layout.addSpacing(int(self.window_width * 0.02))

        self.imu_enable_button = QPushButton("IMU ENABLE")
        self.imu_enable_button.setEnabled(False)
        self.imu_enable_button.setFixedSize(int(self.window_width * 0.11), int(self.window_height * 0.034))
        self.imu_enable_button.setStyleSheet(f"background-color: #888888; font-weight: bold; font-size: {self.font_large}px;")
        led_state_layout.addWidget(self.imu_enable_button)
        led_state_layout.addSpacing(int(self.window_width * 0.02))

        self.status_led_button = QPushButton("STATUS LED")
        self.status_led_button.setEnabled(False)
        self.status_led_button.setFixedSize(int(self.window_width * 0.11), int(self.window_height * 0.034))
        self.status_led_button.setStyleSheet(f"background-color: #888888; font-weight: bold; font-size: {self.font_large}px;")
        led_state_layout.addWidget(self.status_led_button)
        led_state_layout.addStretch()
        right_layout.addWidget(led_state_frame)
        
        led_state_layout2 = QHBoxLayout()
        right_layout.addSpacing(int(self.window_height * 0.001))
        
        # Battery display
        battery_row_layout = QHBoxLayout()
        battery_row_layout.setSpacing(int(self.window_width * 0.008))

        self.battery_voltage_bar = QProgressBar()
        self.battery_voltage_bar.setFixedSize(int(self.window_width * 0.1), int(self.window_height * 0.034))
        self.battery_voltage_bar.setRange(3500, 4200)
        self.battery_voltage_bar.setValue(4200)
        self.battery_voltage_bar.setAlignment(Qt.AlignCenter)
        self.battery_voltage_bar.setFormat("")
        self.battery_voltage_bar.setStyleSheet("""
            QProgressBar {
                border: 1px solid #bbb;
                border-radius: 5px;
                text-align: center;
            }
            QProgressBar::chunk {
                background-color: #4caf50;
                width: 1px;
            }
        """)
        battery_row_layout.addWidget(self.battery_voltage_bar)

        self.battery_voltage_button = QPushButton("Read Battery")
        self.battery_voltage_button.setStyleSheet(f"font-size: {self.font_small}px;")
        self.battery_voltage_button.setEnabled(False)
        self.battery_voltage_button.setFixedSize(int(self.window_width * 0.09), int(self.window_height * 0.034))

        self.read_uLEDCheck_button = QPushButton("uLED Scan")
        self.read_uLEDCheck_button.setStyleSheet(f"font-size: {self.font_small}px;")
        self.read_uLEDCheck_button.setEnabled(False)
        self.read_uLEDCheck_button.setFixedSize(int(self.window_width * 0.09), int(self.window_height * 0.034))

        self.read_lastStim_button = QPushButton("Last Stim")
        self.read_lastStim_button.setStyleSheet(f"font-size: {self.font_small}px;")
        self.read_lastStim_button.setEnabled(False)
        self.read_lastStim_button.setFixedSize(int(self.window_width * 0.09), int(self.window_height * 0.034))

        led_state_layout2.addWidget(self.battery_voltage_button, alignment=Qt.AlignLeft)
        led_state_layout2.addWidget(self.read_uLEDCheck_button, alignment=Qt.AlignLeft)
        led_state_layout2.addWidget(self.read_lastStim_button, alignment=Qt.AlignLeft)
        led_state_layout2.addLayout(battery_row_layout)
        
        right_layout.addLayout(led_state_layout2)
        top_section.addWidget(right_panel, 1)

        main_layout.addLayout(top_section)

        # --- Bottom Section ---
        bottom_section = QHBoxLayout()

        # Left: GATT Table
        gatt_panel = QWidget()
        gatt_layout = QVBoxLayout(gatt_panel)
        gatt_layout.setSpacing(int(self.window_height * 0.004))
        gatt_layout.setContentsMargins(int(self.window_width * 0.004), int(self.window_height * 0.004),
                                       int(self.window_width * 0.004), int(self.window_height * 0.004))
        
        label = QLabel("GATT Table:")
        label.setStyleSheet(f"font-size: {self.font_large}px; font-weight: bold;")
        gatt_layout.addWidget(label)
        
        self.gatt_tree = QTreeWidget()
        self.gatt_tree.setHeaderLabels(["Service", "Characteristic", "Value", "Write Value", "Unit"])
        self.gatt_tree.setStyleSheet(f"""
            QHeaderView::section {{
                font-size: {self.font_medium}px;
                font-weight: bold;
            }}
        """)
        self.gatt_tree.setMaximumWidth(int(self.window_width * 0.5))
        header = self.gatt_tree.header()
        self.gatt_tree.setColumnWidth(0, int(self.window_width * 0.08))
        self.gatt_tree.setColumnWidth(1, int(self.window_width * 0.14))
        self.gatt_tree.setColumnWidth(2, int(self.window_width * 0.1))
        self.gatt_tree.setColumnWidth(3, int(self.window_width * 0.1))
        self.gatt_tree.setColumnWidth(4, int(self.window_width * 0.08))
        header.setSectionResizeMode(QHeaderView.Interactive)
        gatt_layout.addWidget(self.gatt_tree, 1)
        bottom_section.addWidget(gatt_panel, 2)

        # Right: IMU Data Visualization
        imu_panel = QWidget()
        imu_layout = QVBoxLayout(imu_panel)
        imu_layout.setSpacing(int(self.window_height * 0.004))
        imu_layout.setContentsMargins(int(self.window_width * 0.004), int(self.window_height * 0.004),
                                      int(self.window_width * 0.004), int(self.window_height * 0.004))
        
        label = QLabel("IMU Data (last 200 samples):")
        label.setStyleSheet(f"font-size: {self.font_large}px; font-weight: bold;")
        imu_layout.addWidget(label)
        
        self.imu_plot_widget = IMUPlotWidget(window_width=self.window_width, window_height=self.window_height)
        imu_layout.addWidget(self.imu_plot_widget, stretch=1)
        bottom_section.addWidget(imu_panel, 1)

        main_layout.addLayout(bottom_section)
    
    def setup_connections(self):
        """Setup signal-slot connections"""
        self.scan_button.clicked.connect(self.start_scan)
        self.connect_button.clicked.connect(self.connect_to_device)
        self.debug_button.toggled.connect(self.toggle_debug_mode)
        self.read_button.clicked.connect(self.read_all_values)
        self.write_button.clicked.connect(self.write_values)
        self.trigger_button.clicked.connect(self.send_trigger)
        
        self.gatt_tree.itemDoubleClicked.connect(self.edit_characteristic_value)
        self.brain_map.led_clicked.connect(self.toggle_led)

        self.sham_led_button.clicked.connect(self.toggle_sham_led)
        self.imu_enable_button.clicked.connect(self.toggle_imu_enable)
        self.status_led_button.clicked.connect(self.toggle_status_led)
        self.battery_voltage_button.clicked.connect(self.read_battery_voltage)
        self.read_uLEDCheck_button.clicked.connect(self.read_uLEDCheck)
        self.read_lastStim_button.clicked.connect(self.read_lastStim)
    
    # ==================== Logging ====================
    
    def log(self, message: str, max_lines=100):
        """Add a message to the log"""
        timestamp = time.strftime("%H:%M:%S")
        formatted_message = f"[{timestamp}] {message}"
        
        self.log_text.append(formatted_message)
        
        # Limit log size
        document = self.log_text.document()
        if document.lineCount() > max_lines:
            cursor = self.log_text.textCursor()
            cursor.movePosition(cursor.Start)
            cursor.select(cursor.LineUnderCursor)
            cursor.removeSelectedText()
            cursor.deleteChar()
    
    def toggle_debug_mode(self, enabled: bool):
        """Toggle debug mode"""
        # Debug mode doesn't affect backend, just UI behavior
        self.log(f"Debug mode: {'enabled' if enabled else 'disabled'}")
    
    # ==================== Device Scanning and Connection ====================
    
    def start_scan(self):
        """Start scanning for BLE devices"""
        self.log("Scanning for devices...")
        self.scan_button.setEnabled(False)
        self.devices_combo.clear()
        
        # Call backend scan
        future = self.backend_client.run_coro_threadsafe(
            self.backend_client.scan(timeout=4)
        )
        # Result will come via scan_complete callback
    
    def on_scan_complete(self, devices: List[BLEDevice]):
        """Handle scan completion from backend"""
        self.scan_button.setEnabled(True)
        self.device_list = devices
        
        if devices:
            for device in devices:
                self.devices_combo.addItem(f"{device.name} ({device.address})")
            self.connect_button.setEnabled(True)
            self.log(f"Found {len(devices)} OptoGrid devices")
        else:
            self.log("No OptoGrid devices found")
            self.connect_button.setEnabled(False)
    
    def connect_to_device(self):
        """Connect to selected device"""
        if self.devices_combo.currentIndex() < 0:
            return
        
        self.selected_device = self.device_list[self.devices_combo.currentIndex()]
        self.log(f"Connecting to {self.selected_device.name}...")
        self.connect_button.setEnabled(False)
        self.scan_button.setEnabled(False)
        
        # Call backend connect
        future = self.backend_client.run_coro_threadsafe(
            self.backend_client.connect(self.selected_device.name)
        )
        # Result will come via connected callback
    
    def on_connected(self, name: str, address: str):
        """Handle successful connection from backend"""
        self.log(f"Connected to {name}")
        self.connect_button.setEnabled(True)
        self.scan_button.setEnabled(True)
        
        # Enable control buttons
        self.read_button.setEnabled(True)
        self.write_button.setEnabled(True)
        self.trigger_button.setEnabled(True)
        self.sham_led_button.setEnabled(True)
        self.imu_enable_button.setEnabled(True)
        self.status_led_button.setEnabled(True)
        self.battery_voltage_button.setEnabled(True)
        self.read_uLEDCheck_button.setEnabled(True)
        self.read_lastStim_button.setEnabled(True)
        
        # Populate GATT table
        self.populate_gatt_table()
    
    def on_connection_failed(self, error: str):
        """Handle connection failure from backend"""
        self.log(f"Connection failed: {error}")
        self.connect_button.setEnabled(True)
        self.scan_button.setEnabled(True)

    def on_disconnected(self):
        """Handle disconnection from backend"""
        self.log("Device disconnected")
        self.connect_button.setEnabled(True)
        self.scan_button.setEnabled(True)
        
        # Disable control buttons
        self.read_button.setEnabled(False)
        self.write_button.setEnabled(False)
        self.trigger_button.setEnabled(False)
        self.sham_led_button.setEnabled(False)
        self.imu_enable_button.setEnabled(False)
        self.status_led_button.setEnabled(False)
        self.battery_voltage_button.setEnabled(False)
        self.read_uLEDCheck_button.setEnabled(False)
        self.read_lastStim_button.setEnabled(False)
    
    def populate_gatt_table(self):
        """Populate GATT table - requests backend to read GATT and populate"""
        self.log("Populating GATT table...")
        
        async def do_populate():
            self.char_uuid_map.clear()
            self.char_writable_map.clear()
            self.gatt_tree.clear()
            self.item_counter = 0
            
            if not self.backend_client.client or not self.backend_client.client.is_connected:
                return
            
            past_svc_name = "None"
            
            for service in self.backend_client.client.services:
                svc_uuid = str(service.uuid).lower()
                svc_name = UUID_NAME_MAP.get(svc_uuid, None)
                
                # Skip unknown services
                if svc_name is None:
                    continue
                
                for char in service.characteristics:
                    char_uuid = str(char.uuid).lower()
                    char_name = UUID_NAME_MAP.get(char_uuid, None)
                    
                    # Skip unknown characteristics
                    if char_name is None:
                        continue
                    
                    props = char.properties
                    
                    # Check if characteristic is writable
                    is_writable = "write" in props or "write-without-response" in props
                    
                    try:
                        val = await self.backend_client.client.read_gatt_char(char.uuid)
                        val_display = decode_value(char_uuid, val)
                        
                        # Update LED selection if this is the LED Selection characteristic
                        if char_uuid == "56781601-5678-1234-1234-5678abcdeff0":
                            try:
                                self.led_selection_value = int.from_bytes(val[:8], byteorder='little')
                            except:
                                self.led_selection_value = 0
                        # Update SHAM LED state
                        elif char_uuid == "56781508-5678-1234-1234-5678abcdeff0":
                            try:
                                self.sham_led_state = val[0] == 1
                            except:
                                self.sham_led_state = False
                        # Update STATUS LED state
                        elif char_uuid == "56781507-5678-1234-1234-5678abcdeff0":
                            try:
                                self.status_led_state = val[0] == 1
                            except:
                                self.status_led_state = False
                                
                    except Exception:
                        val_display = "<not readable>"
                    
                    unit_name = uuid_to_unit.get(char_uuid, '')
                    service_display = svc_name if svc_name != past_svc_name else ""
                    write_value_display = val_display if is_writable else "<read-only>"
                    
                    # Create tree item (must be done in Qt thread)
                    item_data = {
                        'service': service_display,
                        'char_name': char_name,
                        'val_display': val_display,
                        'write_value_display': write_value_display,
                        'unit_name': unit_name,
                        'is_writable': is_writable,
                        'char_uuid': char_uuid,
                        'item_id': self.item_counter
                    }
                    
                    QTimer.singleShot(0, partial(self._add_gatt_item, item_data))
                    
                    self.item_counter += 1
                    past_svc_name = svc_name
            
            # Update LED visualization in Qt thread
            QTimer.singleShot(0, lambda: self.brain_map.update_led_selection(self.led_selection_value))
            QTimer.singleShot(0, self.update_led_button_states)
        
        future = self.backend_client.run_coro_threadsafe(do_populate())
        future.add_done_callback(lambda f: QTimer.singleShot(0, lambda: self.log("GATT table populated")))
    
    def _add_gatt_item(self, item_data):
        """Add GATT item to tree (must be called in Qt thread)"""
        item = QTreeWidgetItem([
            item_data['service'],
            item_data['char_name'],
            item_data['val_display'],
            item_data['write_value_display'],
            item_data['unit_name']
        ])
        
        # Bold the Service column if there's text
        if item_data['service']:
            font = item.font(0)
            font.setBold(True)
            item.setFont(0, font)
        
        # Color the Write Value column based on writability
        if item_data['is_writable']:
            item.setBackground(3, QColor(245, 245, 245))
        else:
            item.setBackground(3, QColor(255, 255, 255))
        
        # Store item ID and mappings
        item.setData(0, Qt.UserRole, item_data['item_id'])
        self.char_uuid_map[item_data['item_id']] = item_data['char_uuid']
        self.char_writable_map[item_data['item_id']] = item_data['is_writable']
        
        self.gatt_tree.addTopLevelItem(item)
    
    def update_led_button_states(self):
        """Update LED button visual states"""
        # Update SHAM LED button
        if self.sham_led_state:
            self.sham_led_button.setStyleSheet(f"background-color: #90EE90; font-weight: bold; font-size: {self.font_large}px;")
        else:
            self.sham_led_button.setStyleSheet(f"background-color: #888888; font-weight: bold; font-size: {self.font_large}px;")
        
        # Update STATUS LED button
        if self.status_led_state:
            self.status_led_button.setStyleSheet(f"background-color: #90EE90; font-weight: bold; font-size: {self.font_large}px;")
        else:
            self.status_led_button.setStyleSheet(f"background-color: #888888; font-weight: bold; font-size: {self.font_large}px;")
    
    # ==================== GATT Operations ====================
    
    def read_all_values(self):
        """Read all characteristic values"""
        self.log("Reading all values...")
        self.read_button.setEnabled(False)
        
        async def do_read_all():
            for item_id, uuid in self.char_uuid_map.items():
                try:
                    value = await self.backend_client.read_characteristic(uuid)
                    # Update GUI in Qt thread
                    QTimer.singleShot(0, lambda v=value, iid=item_id: self._update_gatt_value(iid, v))
                except Exception as e:
                    self.log(f"Error reading {UUID_NAME_MAP.get(uuid, uuid)}: {e}")
        
        future = self.backend_client.run_coro_threadsafe(do_read_all())
        future.add_done_callback(lambda f: QTimer.singleShot(0, self._on_read_all_complete))
    
    def _update_gatt_value(self, item_id: int, value: str):
        """Update GATT tree item value"""
        for i in range(self.gatt_tree.topLevelItemCount()):
            item = self.gatt_tree.topLevelItem(i)
            if item.data(0, Qt.UserRole) == item_id:
                item.setText(2, value)
                break
    
    def _on_read_all_complete(self):
        """Handle read all completion"""
        self.read_button.setEnabled(True)
        self.log("Read all complete")
    
    def write_values(self):
        """Write all modified values"""
        self.log("Writing modified values...")
        self.write_button.setEnabled(False)
        
        async def do_write_values():
            write_count = 0
            for i in range(self.gatt_tree.topLevelItemCount()):
                item = self.gatt_tree.topLevelItem(i)
                write_value = item.text(3)
                
                if write_value:  # Has write value
                    item_id = item.data(0, Qt.UserRole)
                    uuid = self.char_uuid_map.get(item_id)
                    
                    if uuid:
                        try:
                            success = await self.backend_client.write_characteristic(uuid, write_value)
                            if success:
                                write_count += 1
                                # Update current value
                                QTimer.singleShot(0, lambda it=item, wv=write_value: it.setText(2, wv))
                        except Exception as e:
                            self.log(f"Error writing {UUID_NAME_MAP.get(uuid, uuid)}: {e}")
            
            return write_count
        
        future = self.backend_client.run_coro_threadsafe(do_write_values())
        future.add_done_callback(
            lambda f: QTimer.singleShot(0, lambda: self._on_write_complete(f.result()))
        )
    
    def _on_write_complete(self, count: int):
        """Handle write completion"""
        self.write_button.setEnabled(True)
        self.log(f"Wrote {count} values")
    
    def edit_characteristic_value(self, item: QTreeWidgetItem, column: int):
        """Edit characteristic value via dialog"""
        if column not in [1, 2, 3]:  # Only allow editing name, value, or write value
            return
        
        item_id = item.data(0, Qt.UserRole)
        if item_id is None:
            return
        
        char_name = item.text(1)
        current_value = item.text(2)
        
        dialog = EditValueDialog(char_name, current_value, self)
        if dialog.exec_() == QDialog.Accepted:
            new_value = dialog.get_value()
            item.setText(3, new_value)  # Set write value
            self.log(f"Set write value for {char_name}: {new_value}")
    
    # ==================== Device Control ====================
    
    def send_trigger(self):
        """Send trigger to device"""
        self.log("Sending trigger...")
        self.trigger_button.setEnabled(False)
        
        future = self.backend_client.run_coro_threadsafe(
            self.backend_client.send_trigger()
        )
        future.add_done_callback(
            lambda f: QTimer.singleShot(0, lambda: self._on_trigger_complete(f.result()))
        )
    
    def _on_trigger_complete(self, result: str):
        """Handle trigger completion"""
        self.trigger_button.setEnabled(True)
        self.log(result)
    
    def toggle_led(self, bit_position: int):
        """Toggle LED selection bit"""
        self.led_selection_value ^= (1 << bit_position)
        self.brain_map.update_led_selection(self.led_selection_value)
        
        # Write to device
        led_selection_uuid = "56781601-5678-1234-1234-5678abcdeff0"
        future = self.backend_client.run_coro_threadsafe(
            self.backend_client.write_characteristic(led_selection_uuid, str(self.led_selection_value))
        )
        self.log(f"LED {bit_position} toggled. Selection: {self.led_selection_value}")
    
    def toggle_sham_led(self):
        """Toggle SHAM LED"""
        self.sham_led_state = not self.sham_led_state
        
        sham_led_uuid = "56781508-5678-1234-1234-5678abcdeff0"
        value = "True" if self.sham_led_state else "False"
        
        future = self.backend_client.run_coro_threadsafe(
            self.backend_client.write_characteristic(sham_led_uuid, value)
        )
        
        # Update button appearance
        if self.sham_led_state:
            self.sham_led_button.setStyleSheet(f"background-color: #90EE90; font-weight: bold; font-size: {self.font_large}px;")
        else:
            self.sham_led_button.setStyleSheet(f"background-color: #888888; font-weight: bold; font-size: {self.font_large}px;")
        
        self.log(f"SHAM LED: {value}")
    
    def toggle_status_led(self):
        """Toggle STATUS LED"""
        self.status_led_state = not self.status_led_state
        
        status_led_uuid = "56781507-5678-1234-1234-5678abcdeff0"
        value = "True" if self.status_led_state else "False"
        
        future = self.backend_client.run_coro_threadsafe(
            self.backend_client.write_characteristic(status_led_uuid, value)
        )
        
        # Update button appearance
        if self.status_led_state:
            self.status_led_button.setStyleSheet(f"background-color: #90EE90; font-weight: bold; font-size: {self.font_large}px;")
        else:
            self.status_led_button.setStyleSheet(f"background-color: #888888; font-weight: bold; font-size: {self.font_large}px;")
        
        self.log(f"STATUS LED: {value}")
    
    def toggle_imu_enable(self):
        """Toggle IMU enable/disable"""
        if not self.imu_enable_state:
            # Enable IMU
            future = self.backend_client.run_coro_threadsafe(
                self.backend_client.enable_imu()
            )
            future.add_done_callback(
                lambda f: QTimer.singleShot(0, lambda: self._on_imu_enabled(f.result()))
            )
        else:
            # Disable IMU
            future = self.backend_client.run_coro_threadsafe(
                self.backend_client.disable_imu()
            )
            future.add_done_callback(
                lambda f: QTimer.singleShot(0, lambda: self._on_imu_disabled(f.result()))
            )
    
    def _on_imu_enabled(self, result: str):
        """Handle IMU enable completion"""
        self.imu_enable_state = True
        self.imu_enable_button.setStyleSheet(f"background-color: #90EE90; font-weight: bold; font-size: {self.font_large}px;")
        self.log(result)
    
    def _on_imu_disabled(self, result: str):
        """Handle IMU disable completion"""
        self.imu_enable_state = False
        self.imu_enable_button.setStyleSheet(f"background-color: #888888; font-weight: bold; font-size: {self.font_large}px;")
        self.log(result)
    
    def read_battery_voltage(self):
        """Read battery voltage"""
        self.log("Reading battery voltage...")
        self.battery_voltage_button.setEnabled(False)
        
        future = self.backend_client.run_coro_threadsafe(
            self.backend_client.read_battery()
        )
        future.add_done_callback(
            lambda f: QTimer.singleShot(0, lambda: self._on_battery_read_complete(f.result()))
        )
    
    def _on_battery_read_complete(self, result: str):
        """Handle battery read completion"""
        self.battery_voltage_button.setEnabled(True)
        self.log(f"Battery: {result}")
    
    def _on_battery_update(self, voltage: int):
        """Handle battery update from backend"""
        self.current_battery_voltage = voltage
        self.battery_voltage_bar.setValue(voltage)
        self.battery_voltage_bar.setFormat(f"{voltage} mV")
    
    def read_uLEDCheck(self):
        """Read uLED check"""
        self.log("Reading uLED check...")
        self.read_uLEDCheck_button.setEnabled(False)
        
        future = self.backend_client.run_coro_threadsafe(
            self.backend_client.read_uled_check()
        )
        future.add_done_callback(
            lambda f: QTimer.singleShot(0, lambda: self._on_uled_check_complete(f.result()))
        )
    
    def _on_uled_check_complete(self, result: str):
        """Handle uLED check completion"""
        self.read_uLEDCheck_button.setEnabled(True)
        self.log(f"uLED Check: {result}")
    
    def read_lastStim(self):
        """Read last stim time"""
        self.log("Reading last stim time...")
        self.read_lastStim_button.setEnabled(False)
        
        # Read last stim characteristic
        last_stim_uuid = "5678150a-5678-1234-1234-5678abcdeff0"
        future = self.backend_client.run_coro_threadsafe(
            self.backend_client.read_characteristic(last_stim_uuid)
        )
        future.add_done_callback(
            lambda f: QTimer.singleShot(0, lambda: self._on_last_stim_complete(f.result()))
        )
    
    def _on_last_stim_complete(self, result: str):
        """Handle last stim read completion"""
        self.read_lastStim_button.setEnabled(True)
        self.log(f"Last Stim: {result} ms")
    
    # ==================== IMU Updates ====================
    
    def _on_imu_update(self, roll: float, pitch: float, yaw: float, imu_values: list):
        """Handle IMU update from backend (already in Qt thread)"""
        # Update 3D visualization
        self.imu_3d_widget.set_orientation(roll, pitch, yaw)
        
        # Update plots
        self.imu_plot_widget.update_plot(imu_values)
    
    # ==================== Cleanup ====================
    
    def closeEvent(self, event):
        """Handle window close event"""
        try:
            self.log("Shutting down GUI...")
            
            # Stop battery timer
            if self.battery_timer:
                self.battery_timer.stop()
            
            # Close IMU file if open
            if self.imu_csv_file:
                self.imu_csv_file.close()
                self.imu_csv_file = None
            
            self.log("GUI shutdown complete")
            
        except Exception as e:
            print(f"Error during GUI cleanup: {e}")
        finally:
            event.accept()

class LEDPosition:
    """Data class for LED position information"""
    def __init__(self, x: int, y: int, bit: int, coords: Tuple[int, int, int, int]):
        self.x = x
        self.y = y
        self.bit = bit
        self.coords = coords  # (x1, y1, x2, y2)

class BrainMapWidget(QWidget):
    """Custom widget for brain map visualization with LED interaction"""
    
    led_clicked = pyqtSignal(int)  # Signal emitted when LED is clicked
    
    def __init__(self, font_mini=12, window_width=950, window_height=800, parent=None):
        super().__init__(parent)
        self.font_mini = font_mini  # Store font size
        self.window_width = window_width
        self.window_height = window_height
        self.led_positions: List[LEDPosition] = []
        self.led_selection_value = 0
        self.brain_pixmap: Optional[QPixmap] = None
        self.sham_led_state = False
        self.status_led_state = False
        
        # Scale LED dimensions based on window size
        self.led_width = int(window_width * 0.0142)  # ~13px at 950px width
        self.led_height = int(window_height * 0.03)  # ~24px at 800px height
        
        self.log_message = None  # Store any log messages for parent
        self.led_check_mask = (1 << 64) - 1  # All intact by default
        
        # Calculate brain map size based on window dimensions
        self.brain_map_width = int(window_width * 0.377)  # ~358px at 950px width
        self.brain_map_height = int(window_height * 0.375)  # ~300px at 800px height
        
        self.setMinimumSize(self.brain_map_width, self.brain_map_height)
        self.setup_brain_map()
        
    def setup_brain_map(self):
        """Load brain map image and calculate LED positions"""
        try:
            import os
            import sys
            # Try to load brain map image
            if getattr(sys, 'frozen', False):
                # For PyInstaller .app bundle on Mac
                bundle_dir = sys._MEIPASS if hasattr(sys, '_MEIPASS') else os.path.dirname(sys.executable)
            else:
                bundle_dir = os.path.dirname(os.path.abspath(__file__))

            brainmap_path = os.path.join(bundle_dir, "brainmap.png")
            brain_image = Image.open(brainmap_path)

            # Scale to fit the calculated brain map dimensions
            w, h = brain_image.size
            scale = min(self.brain_map_width / w, self.brain_map_height / h)
            new_size = (int(w * scale), int(h * scale))
            
            brain_image = brain_image.resize(new_size, Image.LANCZOS)
            
            # Convert PIL to QPixmap more reliably
            import tempfile
            import os
            
            # Save to temporary file and load as QPixmap
            fd, tmp_path = tempfile.mkstemp(suffix='.png')
            os.close(fd)  # Close file descriptor immediately

            brain_image.save(tmp_path, 'PNG')
            self.brain_pixmap = QPixmap(tmp_path)
            os.unlink(tmp_path)  # Delete temp file after loading

            self.setFixedSize(new_size[0], new_size[1])
            self.calculate_led_positions(new_size[0], new_size[1])
            
        except FileNotFoundError:
            # If brain map image not found, create a placeholder
            self.log_message = "Brain map image 'brainmap.png' not found. Using placeholder."
            self.brain_pixmap = QPixmap(self.brain_map_width, self.brain_map_height)
            self.brain_pixmap.fill(QColor(220, 220, 220))
            
            # Draw placeholder text
            from PyQt5.QtGui import QPainter, QPen
            painter = QPainter(self.brain_pixmap)
            painter.setPen(QPen(QColor(100, 100, 100)))
            painter.setFont(QFont('Arial', 12))
            painter.drawText(50, 150, "Brain Map Placeholder")
            painter.drawText(50, 170, "Place 'brainmap.png' in working directory")
            painter.drawText(10, 190, f"Attempted path:")
            painter.drawText(10, 210, brainmap_path)
            painter.end()
            
            self.setFixedSize(self.brain_map_width, self.brain_map_height)
            self.calculate_led_positions(self.brain_map_width, self.brain_map_height)
        except Exception as e:
            # Handle any other image loading errors
            self.log_message = f"Error loading brain map: {str(e)}. Using placeholder."
            self.brain_pixmap = QPixmap(self.brain_map_width, self.brain_map_height)
            self.brain_pixmap.fill(QColor(255, 200, 200))  # Light red to indicate error
            
            # Draw error message
            from PyQt5.QtGui import QPainter, QPen
            painter = QPainter(self.brain_pixmap)
            painter.setPen(QPen(QColor(150, 0, 0)))
            painter.setFont(QFont('Arial', 10))
            painter.drawText(10, 150, "Error loading brain map image")
            painter.drawText(10, 170, str(e)[:40] + "..." if len(str(e)) > 40 else str(e))
            painter.end()
            
            self.setFixedSize(self.brain_map_width, self.brain_map_height)
            self.calculate_led_positions(self.brain_map_width, self.brain_map_height)
    
    def calculate_led_positions(self, canvas_width: int, canvas_height: int):
        """Calculate LED positions on the brain map"""
        self.led_positions = []
        
        # LED positioning parameters - scale based on canvas size
        # Original values were at 358x300 canvas
        scale_x = canvas_width / 358
        scale_y = canvas_height / 300
        
        X_space = int(15 * scale_x)
        Y_space = int(40 * scale_y)
        Center_X = int(172 * scale_x)
        Center_Y = int(10 * scale_y)
        
        # LED pixel coordinates mapping with scaled offsets
        # Original offsets scaled by scale_x or scale_y
        led_pixel_map = {
            # Row 1 (bits 0-7)
            0:  [Center_X - 11*X_space + int(14*scale_x),     Center_Y + 5*Y_space],
            1:  [Center_X - 5*X_space + int(2*scale_x),       Center_Y],
            2:  [Center_X - 3*X_space + int(1*scale_x),       Center_Y],
            3:  [Center_X - 1*X_space,                        Center_Y],
            4:  [Center_X + 1*X_space,                        Center_Y],
            5:  [Center_X + 3*X_space - int(1*scale_x),       Center_Y],
            6:  [Center_X + 5*X_space - int(2*scale_x),       Center_Y],
            7:  [Center_X + 11*X_space - int(14*scale_x),     Center_Y + 5*Y_space],

            # Row 2 (bits 8-15)
            8:  [Center_X - 7*X_space + int(5*scale_x),       Center_Y + 1*Y_space],
            9:  [Center_X - 5*X_space + int(2*scale_x),       Center_Y + 1*Y_space],
            10: [Center_X - 3*X_space + int(1*scale_x),       Center_Y + 1*Y_space],
            11: [Center_X - 1*X_space,                        Center_Y + 1*Y_space],
            12: [Center_X + 1*X_space,                        Center_Y + 1*Y_space],
            13: [Center_X + 3*X_space - int(1*scale_x),       Center_Y + 1*Y_space],
            14: [Center_X + 5*X_space - int(2*scale_x),       Center_Y + 1*Y_space],
            15: [Center_X + 7*X_space - int(5*scale_x),       Center_Y + 1*Y_space],

            # Row 3 (bits 16-23)
            16: [Center_X - 7*X_space + int(5*scale_x),       Center_Y + 2*Y_space],
            17: [Center_X - 5*X_space + int(2*scale_x),       Center_Y + 2*Y_space],
            18: [Center_X - 3*X_space + int(1*scale_x),       Center_Y + 2*Y_space],
            19: [Center_X - 1*X_space,                        Center_Y + 2*Y_space],
            20: [Center_X + 1*X_space,                        Center_Y + 2*Y_space],
            21: [Center_X + 3*X_space - int(1*scale_x),       Center_Y + 2*Y_space],
            22: [Center_X + 5*X_space - int(2*scale_x),       Center_Y + 2*Y_space],
            23: [Center_X + 7*X_space - int(5*scale_x),       Center_Y + 2*Y_space],

            # Row 4 (bits 24-31)
            24: [Center_X - 7*X_space + int(5*scale_x),       Center_Y + 3*Y_space],
            25: [Center_X - 5*X_space + int(2*scale_x),       Center_Y + 3*Y_space],
            26: [Center_X - 3*X_space + int(1*scale_x),       Center_Y + 3*Y_space],
            27: [Center_X - 1*X_space,                        Center_Y + 3*Y_space],
            28: [Center_X + 1*X_space,                        Center_Y + 3*Y_space],
            29: [Center_X + 3*X_space - int(1*scale_x),       Center_Y + 3*Y_space],
            30: [Center_X + 5*X_space - int(2*scale_x),       Center_Y + 3*Y_space],
            31: [Center_X + 7*X_space - int(5*scale_x),       Center_Y + 3*Y_space],

            # Row 5 (bits 32-39)
            32: [Center_X - 7*X_space + int(5*scale_x),       Center_Y + 4*Y_space],
            33: [Center_X - 5*X_space + int(2*scale_x),       Center_Y + 4*Y_space],
            34: [Center_X - 3*X_space + int(1*scale_x),       Center_Y + 4*Y_space],
            35: [Center_X - 1*X_space,                        Center_Y + 4*Y_space],
            36: [Center_X + 1*X_space,                        Center_Y + 4*Y_space],
            37: [Center_X + 3*X_space - int(1*scale_x),       Center_Y + 4*Y_space],
            38: [Center_X + 5*X_space - int(2*scale_x),       Center_Y + 4*Y_space],
            39: [Center_X + 7*X_space - int(5*scale_x),       Center_Y + 4*Y_space],

            # Row 6 (bits 40-47)
            40: [Center_X - 7*X_space + int(5*scale_x),       Center_Y + 5*Y_space],
            41: [Center_X - 5*X_space + int(2*scale_x),       Center_Y + 5*Y_space],
            42: [Center_X - 3*X_space + int(1*scale_x),       Center_Y + 5*Y_space],
            43: [Center_X - 1*X_space,                        Center_Y + 5*Y_space],
            44: [Center_X + 1*X_space,                        Center_Y + 5*Y_space],
            45: [Center_X + 3*X_space - int(1*scale_x),       Center_Y + 5*Y_space],
            46: [Center_X + 5*X_space - int(2*scale_x),       Center_Y + 5*Y_space],
            47: [Center_X + 7*X_space - int(5*scale_x),       Center_Y + 5*Y_space],

            # Row 7 (bits 48-55)
            48: [Center_X - 7*X_space + int(5*scale_x),       Center_Y + 6*Y_space],
            49: [Center_X - 5*X_space + int(2*scale_x),       Center_Y + 6*Y_space],
            50: [Center_X - 3*X_space + int(1*scale_x),       Center_Y + 6*Y_space],
            51: [Center_X - 1*X_space,                        Center_Y + 6*Y_space],
            52: [Center_X + 1*X_space,                        Center_Y + 6*Y_space],
            53: [Center_X + 3*X_space - int(1*scale_x),       Center_Y + 6*Y_space],
            54: [Center_X + 5*X_space - int(2*scale_x),       Center_Y + 6*Y_space],
            55: [Center_X + 7*X_space - int(5*scale_x),       Center_Y + 6*Y_space],

            # Row 8 (bits 56-63)
            56: [Center_X - 9*X_space + int(8*scale_x),       Center_Y + 6*Y_space],
            57: [Center_X - 9*X_space + int(8*scale_x),       Center_Y + 5*Y_space],
            58: [Center_X - 9*X_space + int(8*scale_x),       Center_Y + 4*Y_space],
            59: [Center_X - 9*X_space + int(8*scale_x),       Center_Y + 3*Y_space],
            60: [Center_X + 9*X_space - int(8*scale_x),       Center_Y + 3*Y_space],
            61: [Center_X + 9*X_space - int(8*scale_x),       Center_Y + 4*Y_space],
            62: [Center_X + 9*X_space - int(8*scale_x),       Center_Y + 5*Y_space],
            63: [Center_X + 9*X_space - int(8*scale_x),       Center_Y + 6*Y_space],
        }



        
        # Create LED position objects
        for bit_position in range(64):
            if bit_position in led_pixel_map:
                x, y = led_pixel_map[bit_position]
                x1, y1 = x, y
                x2, y2 = x + self.led_width, y + self.led_height
                
                grid_x = (bit_position % 8) + 1
                grid_y = (bit_position // 8) + 1
                
                led_pos = LEDPosition(grid_x, grid_y, bit_position, (x1, y1, x2, y2))
                self.led_positions.append(led_pos)
    
    def update_led_selection(self, value: int):
        """Update LED selection value and repaint"""
        self.led_selection_value = value
        self.update()

    def update_led_check_overlay(self, led_check_mask: int):
        """Update the overlay mask for broken LEDs and repaint"""
        self.led_check_mask = led_check_mask
        self.update()

    def paintEvent(self, event):
        """Paint the brain map and LEDs"""
        painter = QPainter(self)
        
        # Draw brain map background
        if self.brain_pixmap:
            painter.drawPixmap(0, 0, self.brain_pixmap)
        
        # Draw selected LEDs
        painter.setFont(QFont('Arial', self.font_mini, QFont.Bold))
        
        for led_pos in self.led_positions:
            x1, y1, x2, y2 = led_pos.coords

            if self.led_selection_value & (1 << led_pos.bit):
                # Draw LED rectangle
                painter.setPen(QPen(QColor(0, 190, 255), 2))
                painter.setBrush(QBrush(QColor(0, 190, 255)))
                painter.drawRect(QRect(x1, y1, x2-x1, y2-y1))

            # Draw red overlay if LED is broken (corresponding uLED check bit is 0)
            # if ((self.led_check_mask >> led_pos.bit) & 1) == 0:
            #     x1, y1, x2, y2 = led_pos.coords
            #     painter.setPen(Qt.NoPen)
            #     painter.setBrush(QBrush(QColor(255, 0, 0, 120)))  # Semi-transparent red
            #     painter.drawRect(QRect(x1, y1, x2-x1, y2-y1))
            # Draw X overlay if LED is broken (corresponding uLED check bit is 0)
            if ((self.led_check_mask >> led_pos.bit) & 1) == 0:
                painter.setPen(QPen(QColor(255, 0, 0), 3))
                painter.drawLine(x1, y1, x2, y2)
                painter.drawLine(x1, y2, x2, y1)

            # Always draw LED number on top
            font = QFont('Arial', self.font_mini, QFont.Bold)
            painter.setFont(font)
            painter.setPen(QPen(QColor(0, 0, 0)))
            
            # Calculate centered position for text
            text = str(led_pos.bit + 1)
            font_metrics = painter.fontMetrics()
            text_width = font_metrics.horizontalAdvance(text)
            text_height = font_metrics.height()
            
            center_x = x1 + (x2 - x1) / 2
            center_y = y1 + (y2 - y1) / 2
            
            # Draw text centered
            text_x = int(center_x - text_width / 2)
            text_y = int(center_y + text_height / 4)  # Adjust baseline
            painter.drawText(text_x, text_y, text)
    
    def mousePressEvent(self, event):
        """Handle mouse clicks for LED selection"""
        if event.button() == Qt.LeftButton:
            x, y = event.x(), event.y()
            
            # Find clicked LED
            for led_pos in self.led_positions:
                x1, y1, x2, y2 = led_pos.coords
                if x1 <= x <= x2 and y1 <= y <= y2:
                    self.led_clicked.emit(led_pos.bit)
                    break

class IMU3DWidget(QOpenGLWidget):
    """A simple 3D widget to visualize device orientation with a rat head model"""
    def __init__(self, window_width=950, window_height=800, parent=None):
        super().__init__(parent)
        self.roll = 0
        self.pitch = 0
        self.yaw = 0
        
        # Scale widget size based on window dimensions
        imu_width = int(window_width * 0.3)  # ~285px at 950px width
        imu_height = int(window_height * 0.16)  # ~128px at 800px height
        self.setFixedSize(imu_width, imu_height)
        self.setMinimumSize(imu_width, imu_height)

        # Disable this timer, Let IMU drive frame updates
        # self.timer = QTimer(self)
        # self.timer.timeout.connect(self.update)
        # self.timer.start(10)  # ~100 FPS

    def set_orientation(self, roll, pitch, yaw):
        self.roll = roll
        self.pitch = pitch
        self.yaw = yaw
        self.update()

    def initializeGL(self):
        from OpenGL.GL import glClearColor, glEnable, GL_DEPTH_TEST
        glClearColor(0.5, 0.6, 0.6, 1)
        glEnable(GL_DEPTH_TEST)

    def resizeGL(self, w, h):
        from OpenGL.GL import glViewport, glMatrixMode, glLoadIdentity, GL_PROJECTION, GL_MODELVIEW
        from OpenGL.GLU import gluPerspective
        glViewport(0, 0, w, h)
        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        gluPerspective(45, w / h if h != 0 else 1, 0.1, 100.0)
        glMatrixMode(GL_MODELVIEW)

    def draw_sphere(self, radius, slices=8, stacks=8):
        """Draw a simple sphere using quads"""
        from OpenGL.GL import glBegin, glEnd, glVertex3f, GL_QUADS
        import math
        
        glBegin(GL_QUADS)
        for i in range(stacks):
            lat0 = math.pi * (-0.5 + float(i) / stacks)
            z0 = radius * math.sin(lat0)
            zr0 = radius * math.cos(lat0)
            
            lat1 = math.pi * (-0.5 + float(i + 1) / stacks)
            z1 = radius * math.sin(lat1)
            zr1 = radius * math.cos(lat1)
            
            for j in range(slices):
                lng = 2 * math.pi * float(j) / slices
                x = math.cos(lng)
                y = math.sin(lng)
                
                lng1 = 2 * math.pi * float(j + 1) / slices
                x1 = math.cos(lng1)
                y1 = math.sin(lng1)
                
                glVertex3f(x * zr0, y * zr0, z0)
                glVertex3f(x1 * zr0, y1 * zr0, z0)
                glVertex3f(x1 * zr1, y1 * zr1, z1)
                glVertex3f(x * zr1, y * zr1, z1)
        glEnd()
    

    def draw_ellipsoid(self, rx, ry, rz, slices=8, stacks=8):
        """Draw an ellipsoid with proper vertex counting"""
        from OpenGL.GL import glBegin, glEnd, glVertex3f, GL_TRIANGLES
        import math
        
        # Use triangles instead of quads for more reliable rendering
        glBegin(GL_TRIANGLES)
        
        for i in range(stacks):
            lat0 = math.pi * (-0.5 + float(i) / stacks)
            z0 = rz * math.sin(lat0)
            zr0 = math.cos(lat0)
            
            lat1 = math.pi * (-0.5 + float(i + 1) / stacks)
            z1 = rz * math.sin(lat1)
            zr1 = math.cos(lat1)
            
            for j in range(slices):
                lng = 2 * math.pi * float(j) / slices
                x0 = rx * math.cos(lng) * zr0
                y0 = ry * math.sin(lng) * zr0
                
                lng1 = 2 * math.pi * float(j + 1) / slices
                x1 = rx * math.cos(lng1) * zr0
                y1 = ry * math.sin(lng1) * zr0
                
                x0_1 = rx * math.cos(lng) * zr1
                y0_1 = ry * math.sin(lng) * zr1
                x1_1 = rx * math.cos(lng1) * zr1
                y1_1 = ry * math.sin(lng1) * zr1
                
                # First triangle
                glVertex3f(x0, y0, z0)
                glVertex3f(x1, y1, z0)
                glVertex3f(x0_1, y0_1, z1)
                
                # Second triangle
                glVertex3f(x1, y1, z0)
                glVertex3f(x1_1, y1_1, z1)
                glVertex3f(x0_1, y0_1, z1)
        
        glEnd()


    def draw_cone(self, base_radius, height, slices=8):
        """Draw a cone pointing in +Z direction"""
        from OpenGL.GL import glBegin, glEnd, glVertex3f, GL_TRIANGLES, GL_TRIANGLE_FAN
        import math
        
        # Draw base
        glBegin(GL_TRIANGLE_FAN)
        glVertex3f(0, 0, 0)  # Center of base
        for i in range(slices + 1):
            angle = 2 * math.pi * i / slices
            x = base_radius * math.cos(angle)
            y = base_radius * math.sin(angle)
            glVertex3f(x, y, 0)
        glEnd()
        
        # Draw sides
        glBegin(GL_TRIANGLES)
        for i in range(slices):
            angle1 = 2 * math.pi * i / slices
            angle2 = 2 * math.pi * (i + 1) / slices
            
            x1 = base_radius * math.cos(angle1)
            y1 = base_radius * math.sin(angle1)
            x2 = base_radius * math.cos(angle2)
            y2 = base_radius * math.sin(angle2)
            
            glVertex3f(0, 0, height)  # Tip
            glVertex3f(x1, y1, 0)     # Base point 1
            glVertex3f(x2, y2, 0)     # Base point 2
        glEnd()

    def paintGL(self):
        from OpenGL.GL import (
        glClear, GL_COLOR_BUFFER_BIT, GL_DEPTH_BUFFER_BIT, glLoadIdentity,
        glTranslatef, glRotatef, glColor3f, glPushMatrix, glPopMatrix, glScalef,
        glBegin, glEnd, glVertex3f, GL_LINES, GL_TRIANGLES
        )
        
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        glLoadIdentity()
        glTranslatef(0.0, 0.0, -6.0)
        
        # Apply rotations
        glRotatef(self.pitch, 1, 0, 0)
        glRotatef(-self.roll, 0, 0, 1)
        glRotatef(self.yaw, 0, 1, 0)
        
        # glRotatef(0, 0, 0, 1)
        # glRotatef(0, 1, 0, 0)
        # glRotatef(180, 0, 1, 0)
        

        # Draw rat head (5 shapes total)
        
        # 1. Main head (ellipsoid) - pinkish color
        glPushMatrix()
        glColor3f(0.9, 0.7, 0.7)  # Light pink
        glScalef(0.8, 0.6, 1.0)   # Elongated head shape
        self.draw_ellipsoid(1.5, 2, 1.5)
        glPopMatrix()
        
        # 2. Snout (cone) - dark 
        glPushMatrix()
        glColor3f(0.2, 0.2, 0.2)  # Darker pink
        glTranslatef(0, 0, 1.5)   # Move to front of head
        glScalef(0.6, 0.6, 0.4)   # Small pointy snout
        self.draw_cone(0.5, 1.0)
        glPopMatrix()
        
        # 3. Left ear (ellipsoid) - Dark
        glPushMatrix()
        glColor3f(0.2, 0.2, 0.3)  # 
        glTranslatef(-1.0, 0.7, -0.2)  # Left side, top, slightly forward
        glRotatef(30, 0, 0, 1)    # Tilt ear outward
        glScalef(0.8, 0.9, 0.3) # Thin, tall ear
        self.draw_ellipsoid(1.0, 1.0, 1.0)
        glPopMatrix()
        
        # 4. Right ear (ellipsoid) - Dark
        glPushMatrix()
        glColor3f(0.2, 0.2, 0.3)  # 
        glTranslatef(1.0, 0.7, -0.2)    # Right side, top, slightly forward
        glRotatef(-30, 0, 0, 1)   # Tilt ear outward
        glScalef(0.8, 0.9, 0.3) # Thin, tall ear
        self.draw_ellipsoid(1.0, 1.0, 1.0)
        glPopMatrix()
        
        # 5. Eyes (two small spheres, counted as one shape since they're identical)
        glColor3f(0.1, 0.1, 0.1)  # Black eyes
        
        # Left eye
        glPushMatrix()
        glTranslatef(-0.5, 0.5, 1)  # Left side of head, forward
        glScalef(0.2, 0.2, 0.2)      # Small eye
        self.draw_sphere(1.0)
        glPopMatrix()
        
        # Right eye
        glPushMatrix()
        glTranslatef(0.5, 0.5, 1)   # Right side of head, forward
        glScalef(0.2, 0.2, 0.2)      # Small eye
        self.draw_sphere(1.0)
        glPopMatrix()

        # Draw coordinate axes (thicker lines)
        glLineWidth(3.0)
        glBegin(GL_LINES)

        # X axis (red) - pointing right
        glColor3f(1, 0, 0)
        glVertex3f(0, 0, 0)
        glVertex3f(2, 0, 0)

        # Y axis (green) - pointing up
        glColor3f(0, 1, 0)
        glVertex3f(0, 0, 0)
        glVertex3f(0, 2, 0)

        # Z axis (blue) - pointing forward
        glColor3f(0, 0, 1)
        glVertex3f(0, 0, 0)
        glVertex3f(0, 0, 3)

        glEnd()


        # # Draw coordinate axes (thinner lines)
        # from OpenGL.GL import glLineWidth
        # glLineWidth(3.0)
        # glBegin(GL_LINES)
        # # Rat head local reference frame:
        # # X axis (red) - pointing left
        # glColor3f(1, 0, 0)
        # glVertex3f(0, 0, 0)
        # glVertex3f(-2, 0, 0)
        # # Y axis (green) - pointing up
        # glColor3f(0, 1, 0)
        # glVertex3f(0, 0, 0)
        # glVertex3f(0, 2, 0)
        # # Z axis (blue) - pointing out of the screen
        # glColor3f(0, 0, 1)
        # glVertex3f(0, 0, 0)
        # glVertex3f(0, 0, -2)
        # glEnd()

        # # Draw global reference frame in upper right corner
        # glPushMatrix()
        # glLoadIdentity()
        # glTranslatef(1.9, 0.6, -3)  # Position in upper right
        
        # glLineWidth(2.0)
        # glBegin(GL_LINES)
        # # Reference X (RED) - up
        # glColor3f(1, 0, 0)
        # glVertex3f(0, 0, 0)
        # glVertex3f(0.5, 0, 0)
        # # Reference Y (GREEN) - right
        # glColor3f(0, 1, 0)  
        # glVertex3f(0, 0, 0)
        # glVertex3f(0, 0.5, 0)
        # # Reference Z (BLUE) - out
        # glColor3f(0, 0, 1)
        # glVertex3f(-0.05, -0.05, 0); glVertex3f(0.05, -0.05, 0)
        # glVertex3f(0.05, -0.05, 0); glVertex3f(0.05, 0.05, 0)  
        # glVertex3f(0.05, 0.05, 0); glVertex3f(-0.05, 0.05, 0)
        # glVertex3f(-0.05, 0.05, 0); glVertex3f(-0.05, -0.05, 0)
        # glEnd()
        
        
        # glPopMatrix()

class IMUPlotWidget(QWidget):
    def __init__(self, window_width=950, window_height=800, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        self.plot_widget = pg.GraphicsLayoutWidget()
        layout.addWidget(self.plot_widget)
        
        # Scale widget size based on window dimensions
        plot_width = int(window_width * 0.45)  # ~427px at 950px width
        plot_height = int(window_height * 0.43)  # ~344px at 800px height
        self.setFixedSize(plot_width, plot_height)
        
        self.max_points = 200
        self.data = [np.zeros(self.max_points) for _ in range(9)]

        self.curves = []
        self.plots = []

        # Initialize plots to certain refresh rate
        self.plot_timer = QTimer()
        self.plot_timer.timeout.connect(self.update_display)
        self.plot_timer.start(50)  # Update at 20 Hz
        self.pending_data = None

        # Colors for each sensor type
        line_colors = [
            'r', 'g', (100, 200, 255),  # X: Accel, Gyro, Mag
            'r', 'g', (100, 200, 255),  # Y: Accel, Gyro, Mag
            'r', 'g', (100, 200, 255),  # Z: Accel, Gyro, Mag
        ]
        title_colors = [
            (255, 80, 80), (80, 255, 80), (100, 200, 255),  # X
            (255, 80, 80), (80, 255, 80), (100, 200, 255),  # Y
            (255, 80, 80), (80, 255, 80), (100, 200, 255),  # Z
        ]
        titles = [
            "Accel X", "Gyro X", "Mag X",
            "Accel Y", "Gyro Y", "Mag Y",
            "Accel Z", "Gyro Z", "Mag Z"
        ]
            
        # Layout: columns = Accel, Gyro, Mag; rows = X, Y, Z
        for axis in range(3):  # rows: 0=X, 1=Y, 2=Z
            self.plot_widget.nextRow()
            for sensor in range(3):  # columns: 0=Accel, 1=Gyro, 2=Mag
                idx = axis * 3 + sensor  # 0: Accel X, 1: Gyro X, 2: Mag X, 3: Accel Y, ...
                p = self.plot_widget.addPlot()
                
                # AutoRange
                p.enableAutoRange(axis='y')
                p.setXRange(0, self.max_points)
                    
                # Set title with color
                title_style = f"<span style='color: rgb{title_colors[idx]}; font-size:14pt'><b>{titles[idx]}</b></span>"
                p.setTitle(title_style)

                # Update yticks to show only min/max when y-range changes
                def make_updater(plot):
                    def update_ticks():
                        try:
                            ymin, ymax = plot.viewRange()[1]
                            if ymax > ymin:
                                ticks = [(ymin, f"{int(ymin)}"), (ymax, f"{int(ymax)}")]
                                plot.getAxis('left').setTicks([ticks])
                        except:
                            pass
                    return update_ticks
                
                p.vb.sigYRangeChanged.connect(make_updater(p))

                # Reduce x-axis ticks (show only start, middle, end)
                p.getAxis('bottom').setTicks([[(0, '0'), (self.max_points//2, str(self.max_points//2)), (self.max_points, str(self.max_points))]])
                
                curve = p.plot(self.data[idx], pen=pg.mkPen(line_colors[idx], width=2))
                self.curves.append(curve)
                self.plots.append(p)

    # Replace update_plot with:
    def update_plot(self, imu_values):
        # Store the latest data
        self.pending_data = imu_values

    def update_display(self):
        # Only update if we have new data
        if self.pending_data is None:
            return
            
        imu_values = self.pending_data
        for axis in range(3):  # 0=X, 1=Y, 2=Z
            for sensor in range(3):  # 0=Accel, 1=Gyro, 2=Mag
                idx = axis * 3 + sensor
                data_idx = 1 + sensor * 3 + axis  # skip timestamp
                if sensor == 2:
                    self.data[idx] = np.roll(self.data[idx], -1)
                    self.data[idx][-1] = imu_values[data_idx]
                    self.curves[idx].setData(self.data[idx])
                else:
                    self.data[idx] = np.roll(self.data[idx], -1)
                    self.data[idx][-1] = imu_values[data_idx]
                    self.curves[idx].setData(self.data[idx])
        self.pending_data = None

# For backward compatibility
__all__ = ['OptoGridGUI']
