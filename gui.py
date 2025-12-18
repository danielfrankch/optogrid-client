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
    IMU3DWidget,
    IMUPlotWidget,
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
        self.window_width = int(size.width() * 0.5)   # 50% of screen width
        self.window_height = int(size.height() * 0.87)  # 90% of screen height
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
        self.imu_3d_widget = IMU3DWidget()
        self.imu_3d_widget.setFixedSize(int(self.window_width * 0.3), int(self.window_height * 0.16)) 
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
        
        self.brain_map = BrainMapWidget(font_mini=self.font_mini)
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
        
        self.imu_plot_widget = IMUPlotWidget()
        self.imu_plot_widget.setFixedSize(int(self.window_width * 0.45), int(self.window_height * 0.43))
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
    
    def __init__(self, font_mini=12, parent=None):
        super().__init__(parent)
        self.font_mini = font_mini  # Store font size
        self.led_positions: List[LEDPosition] = []
        self.led_selection_value = 0
        self.brain_pixmap: Optional[QPixmap] = None
        self.sham_led_state = False
        self.status_led_state = False
        self.led_width = 13
        self.led_height = 24
        self.log_message = None  # Store any log messages for parent
        self.led_check_mask = (1 << 64) - 1  # All intact by default
        
        self.setMinimumSize(358, 300)
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

            max_width = 358
            w, h = brain_image.size
            scale = min(max_width / w, 1)
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
            self.brain_pixmap = QPixmap(358, 300)
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
            
            self.setFixedSize(358, 300)
            self.calculate_led_positions(358, 300)
        except Exception as e:
            # Handle any other image loading errors
            self.log_message = f"Error loading brain map: {str(e)}. Using placeholder."
            self.brain_pixmap = QPixmap(358, 300)
            self.brain_pixmap.fill(QColor(255, 200, 200))  # Light red to indicate error
            
            # Draw error message
            from PyQt5.QtGui import QPainter, QPen
            painter = QPainter(self.brain_pixmap)
            painter.setPen(QPen(QColor(150, 0, 0)))
            painter.setFont(QFont('Arial', 10))
            painter.drawText(10, 150, "Error loading brain map image")
            painter.drawText(10, 170, str(e)[:40] + "..." if len(str(e)) > 40 else str(e))
            painter.end()
            
            self.setFixedSize(358, 300)
            self.calculate_led_positions(358, 300)
    
    def calculate_led_positions(self, canvas_width: int, canvas_height: int):
        """Calculate LED positions on the brain map"""
        self.led_positions = []
        
        # LED positioning parameters
        X_space = 15
        Y_space = 44
        Center_X = 172
        Center_Y = 10
        
        # LED pixel coordinates mapping (X_space multipliers doubled)
        led_pixel_map = {
            # Row 1 (bits 0-7)
            0:  [Center_X - 11*X_space + 14,     Center_Y + 5*Y_space],
            1:  [Center_X - 5*X_space + 2,       Center_Y],
            2:  [Center_X - 3*X_space + 1,       Center_Y],
            3:  [Center_X - 1*X_space,           Center_Y],
            4:  [Center_X + 1*X_space,           Center_Y],
            5:  [Center_X + 3*X_space - 1,       Center_Y],
            6:  [Center_X + 5*X_space - 2,       Center_Y],
            7:  [Center_X + 11*X_space - 14,     Center_Y + 5*Y_space],

            # Row 2 (bits 8-15)
            8:  [Center_X - 7*X_space + 5,       Center_Y + 1*Y_space],
            9:  [Center_X - 5*X_space + 2,       Center_Y + 1*Y_space],
            10: [Center_X - 3*X_space + 1,       Center_Y + 1*Y_space],
            11: [Center_X - 1*X_space,           Center_Y + 1*Y_space],
            12: [Center_X + 1*X_space,           Center_Y + 1*Y_space],
            13: [Center_X + 3*X_space - 1,       Center_Y + 1*Y_space],
            14: [Center_X + 5*X_space - 2,       Center_Y + 1*Y_space],
            15: [Center_X + 7*X_space - 5,       Center_Y + 1*Y_space],

            # Row 3 (bits 16-23)
            16: [Center_X - 7*X_space + 5,       Center_Y + 2*Y_space],
            17: [Center_X - 5*X_space + 2,       Center_Y + 2*Y_space],
            18: [Center_X - 3*X_space + 1,       Center_Y + 2*Y_space],
            19: [Center_X - 1*X_space,           Center_Y + 2*Y_space],
            20: [Center_X + 1*X_space,           Center_Y + 2*Y_space],
            21: [Center_X + 3*X_space - 1,       Center_Y + 2*Y_space],
            22: [Center_X + 5*X_space - 2,       Center_Y + 2*Y_space],
            23: [Center_X + 7*X_space - 5,       Center_Y + 2*Y_space],

            # Row 4 (bits 24-31)
            24: [Center_X - 7*X_space + 5,       Center_Y + 3*Y_space],
            25: [Center_X - 5*X_space + 2,       Center_Y + 3*Y_space],
            26: [Center_X - 3*X_space + 1,       Center_Y + 3*Y_space],
            27: [Center_X - 1*X_space,           Center_Y + 3*Y_space],
            28: [Center_X + 1*X_space,           Center_Y + 3*Y_space],
            29: [Center_X + 3*X_space - 1,       Center_Y + 3*Y_space],
            30: [Center_X + 5*X_space - 2,       Center_Y + 3*Y_space],
            31: [Center_X + 7*X_space - 5,       Center_Y + 3*Y_space],

            # Row 5 (bits 32-39)
            32: [Center_X - 7*X_space + 5,       Center_Y + 4*Y_space],
            33: [Center_X - 5*X_space + 2,       Center_Y + 4*Y_space],
            34: [Center_X - 3*X_space + 1,       Center_Y + 4*Y_space],
            35: [Center_X - 1*X_space,           Center_Y + 4*Y_space],
            36: [Center_X + 1*X_space,           Center_Y + 4*Y_space],
            37: [Center_X + 3*X_space - 1,       Center_Y + 4*Y_space],
            38: [Center_X + 5*X_space - 2,       Center_Y + 4*Y_space],
            39: [Center_X + 7*X_space - 5,       Center_Y + 4*Y_space],

            # Row 6 (bits 40-47)
            40: [Center_X - 7*X_space + 5,       Center_Y + 5*Y_space],
            41: [Center_X - 5*X_space + 2,       Center_Y + 5*Y_space],
            42: [Center_X - 3*X_space + 1,       Center_Y + 5*Y_space],
            43: [Center_X - 1*X_space,           Center_Y + 5*Y_space],
            44: [Center_X + 1*X_space,           Center_Y + 5*Y_space],
            45: [Center_X + 3*X_space - 1,       Center_Y + 5*Y_space],
            46: [Center_X + 5*X_space - 2,       Center_Y + 5*Y_space],
            47: [Center_X + 7*X_space - 5,       Center_Y + 5*Y_space],

            # Row 7 (bits 48-55)
            48: [Center_X - 7*X_space + 5,       Center_Y + 6*Y_space],
            49: [Center_X - 5*X_space + 2,       Center_Y + 6*Y_space],
            50: [Center_X - 3*X_space + 1,       Center_Y + 6*Y_space],
            51: [Center_X - 1*X_space,           Center_Y + 6*Y_space],
            52: [Center_X + 1*X_space,           Center_Y + 6*Y_space],
            53: [Center_X + 3*X_space - 1,       Center_Y + 6*Y_space],
            54: [Center_X + 5*X_space - 2,       Center_Y + 6*Y_space],
            55: [Center_X + 7*X_space - 5,       Center_Y + 6*Y_space],

            # Row 8 (bits 56-63)
            56: [Center_X - 9*X_space + 8,       Center_Y + 6*Y_space],
            57: [Center_X - 9*X_space + 8,       Center_Y + 5*Y_space],
            58: [Center_X - 9*X_space + 8,       Center_Y + 4*Y_space],
            59: [Center_X - 9*X_space + 8,       Center_Y + 3*Y_space],
            60: [Center_X + 9*X_space - 8,       Center_Y + 3*Y_space],
            61: [Center_X + 9*X_space - 8,       Center_Y + 4*Y_space],
            62: [Center_X + 9*X_space - 8,       Center_Y + 5*Y_space],
            63: [Center_X + 9*X_space - 8,       Center_Y + 6*Y_space],
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

# For backward compatibility
__all__ = ['OptoGridGUI']
