import asyncio
import sys
import struct
import threading
from typing import Dict, List, Optional, Tuple

import os
import zmq
import matplotlib
matplotlib.use('Qt5Agg')

import numpy as np
import csv
import datetime
from ahrs.filters import Madgwick
from ahrs.common.orientation import q2euler
from ahrs.filters import EKF
import pyqtgraph as pg
import queue
import pandas as pd
from PyQt5.QtGui import QFont
import socket
try:
    import RPi.GPIO as GPIO
    GPIO_AVAILABLE = True
except ImportError:
    GPIO_AVAILABLE = False
    

os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "0"
os.environ["QT_SCALE_FACTOR"] = "1"
os.environ["QT_ENABLE_HIGHDPI_SCALING"] = "0"

# Suppress Qt warnings about meta types
os.environ['QT_LOGGING_RULES'] = '*.warning=false'

from bleak import BleakScanner, BleakClient, BLEDevice
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QComboBox, QTextEdit, QTreeWidget, QTreeWidgetItem,
    QLabel, QMessageBox, QDialog, QLineEdit, QDialogButtonBox,
    QSplitter, QFrame, QHeaderView, QCheckBox
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer, QRect, QObject
from PyQt5.QtGui import QPainter, QPen, QBrush, QFont, QPixmap, QColor
from PIL import Image
from zmq.eventloop.zmqstream import ZMQStream
from tornado.ioloop import IOLoop
from PyQt5.QtWidgets import QProgressBar
from PyQt5.QtCore import pyqtSignal

from PyQt5.QtWidgets import QOpenGLWidget
from PyQt5.QtGui import QVector3D
from PyQt5.QtCore import QTimer
from OpenGL.GL import glLineWidth

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

uuid_to_unit = {
    # Device Info Characteristics
    "56781500-5678-1234-1234-5678abcdeff0": "",
    "56781501-5678-1234-1234-5678abcdeff0": "",
    "56781502-5678-1234-1234-5678abcdeff0": "",
    "56781503-5678-1234-1234-5678abcdeff0": "",
    "56781504-5678-1234-1234-5678abcdeff0": "",
    "56781505-5678-1234-1234-5678abcdeff0": "percent",
    "56781506-5678-1234-1234-5678abcdeff0": "mV",
    "56781507-5678-1234-1234-5678abcdeff0": "",
    "56781508-5678-1234-1234-5678abcdeff0": "",

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

class IMU3DWidget(QOpenGLWidget):
    """A simple 3D widget to visualize device orientation with a rat head model"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.roll = 0
        self.pitch = 0
        self.yaw = 0
        self.setMinimumSize(120, 120)

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
        glRotatef(-self.roll, 0, 0, 1)
        glRotatef(self.pitch, 1, 0, 0)
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
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.led_positions: List[LEDPosition] = []
        self.led_selection_value = 0
        self.brain_pixmap: Optional[QPixmap] = None
        self.sham_led_state = False
        self.status_led_state = False
        self.led_width = 13
        self.led_height = 23
        self.log_message = None  # Store any log messages for parent
        self.led_check_mask = (1 << 64) - 1  # All intact by default
        
        self.setMinimumSize(358, 300)
        self.setup_brain_map()
        
    def setup_brain_map(self):
        """Load brain map image and calculate LED positions"""
        try:
            # Try to load brain map image
            brain_image = Image.open("brainmap.png")
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
        X_space = 26
        Y_space = 26 + 11 + 3
        ARB_X = 106
        ARB_Y = 25
        
        # LED pixel coordinates mapping (same as original)
        led_pixel_map = {
            # Row 1 (bits 0-7)
            0: [ARB_X-X_space*3, ARB_Y+Y_space*5], 1: [ARB_X, 24], 2: [ARB_X+X_space*1, ARB_Y],
            3: [ARB_X+X_space*2, ARB_Y], 4: [ARB_X+X_space*3, ARB_Y], 5: [ARB_X+X_space*4, ARB_Y],
            6: [ARB_X+X_space*5, ARB_Y], 7: [ARB_X+X_space*8, ARB_Y+Y_space*5],
            
            # Row 2 (bits 8-15)
            8: [ARB_X-X_space*1, ARB_Y+Y_space*1], 9: [ARB_X, ARB_Y+Y_space*1],
            10: [ARB_X+X_space*1, ARB_Y+Y_space*1], 11: [ARB_X+X_space*2, ARB_Y+Y_space*1],
            12: [ARB_X+X_space*3, ARB_Y+Y_space*1], 13: [ARB_X+X_space*4, ARB_Y+Y_space*1],
            14: [ARB_X+X_space*5, ARB_Y+Y_space*1], 15: [ARB_X+X_space*6, ARB_Y+Y_space*1],
            
            # Row 3 (bits 16-23)
            16: [ARB_X-X_space*1, ARB_Y+Y_space*2], 17: [ARB_X, ARB_Y+Y_space*2],
            18: [ARB_X+X_space*1, ARB_Y+Y_space*2], 19: [ARB_X+X_space*2, ARB_Y+Y_space*2],
            20: [ARB_X+X_space*3, ARB_Y+Y_space*2], 21: [ARB_X+X_space*4, ARB_Y+Y_space*2],
            22: [ARB_X+X_space*5, ARB_Y+Y_space*2], 23: [ARB_X+X_space*6, ARB_Y+Y_space*2],
            
            # Row 4 (bits 24-31)
            24: [ARB_X-X_space*1, ARB_Y+Y_space*3], 25: [ARB_X, ARB_Y+Y_space*3],
            26: [ARB_X+X_space*1, ARB_Y+Y_space*3], 27: [ARB_X+X_space*2, ARB_Y+Y_space*3],
            28: [ARB_X+X_space*3, ARB_Y+Y_space*3], 29: [ARB_X+X_space*4, ARB_Y+Y_space*3],
            30: [ARB_X+X_space*5, ARB_Y+Y_space*3], 31: [ARB_X+X_space*6, ARB_Y+Y_space*3],
            
            # Row 5 (bits 32-39)
            32: [ARB_X-X_space*1, ARB_Y+Y_space*4], 33: [ARB_X, ARB_Y+Y_space*4],
            34: [ARB_X+X_space*1, ARB_Y+Y_space*4], 35: [ARB_X+X_space*2, ARB_Y+Y_space*4],
            36: [ARB_X+X_space*3, ARB_Y+Y_space*4], 37: [ARB_X+X_space*4, ARB_Y+Y_space*4],
            38: [ARB_X+X_space*5, ARB_Y+Y_space*4], 39: [ARB_X+X_space*6, ARB_Y+Y_space*4],
            
            # Row 6 (bits 40-47)
            40: [ARB_X-X_space*1, ARB_Y+Y_space*5], 41: [ARB_X, ARB_Y+Y_space*5],
            42: [ARB_X+X_space*1, ARB_Y+Y_space*5], 43: [ARB_X+X_space*2, ARB_Y+Y_space*5],
            44: [ARB_X+X_space*3, ARB_Y+Y_space*5], 45: [ARB_X+X_space*4, ARB_Y+Y_space*5],
            46: [ARB_X+X_space*5, ARB_Y+Y_space*5], 47: [ARB_X+X_space*6, ARB_Y+Y_space*5],
            
            # Row 7 (bits 48-55)
            48: [ARB_X-X_space*1, ARB_Y+Y_space*6], 49: [ARB_X, ARB_Y+Y_space*6],
            50: [ARB_X+X_space*1, ARB_Y+Y_space*6], 51: [ARB_X+X_space*2, ARB_Y+Y_space*6],
            52: [ARB_X+X_space*3, ARB_Y+Y_space*6], 53: [ARB_X+X_space*4, ARB_Y+Y_space*6],
            54: [ARB_X+X_space*5, ARB_Y+Y_space*6], 55: [ARB_X+X_space*6, ARB_Y+Y_space*6],
            
            # Row 8 (bits 56-63)
            56: [ARB_X-X_space*2, ARB_Y+Y_space*6], 57: [ARB_X-X_space*2, ARB_Y+Y_space*5],
            58: [ARB_X-X_space*2, ARB_Y+Y_space*4], 59: [ARB_X-X_space*2, ARB_Y+Y_space*3],
            60: [ARB_X+X_space*7, ARB_Y+Y_space*3], 61: [ARB_X+X_space*7, ARB_Y+Y_space*4],
            62: [ARB_X+X_space*7, ARB_Y+Y_space*5], 63: [ARB_X+X_space*7, ARB_Y+Y_space*6],
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
        painter.setFont(QFont('Arial', 10, QFont.Bold))
        
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
            painter.setFont(QFont('Arial', 11, QFont.Bold))
            painter.setPen(QPen(QColor(0, 0, 0)))
            center_x = x1 + (x2 - x1) / 2
            center_y = y1 + (y2 - y1) / 2
            painter.drawText(int(center_x-5), int(center_y+3), str(led_pos.bit + 1))
    
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

class BLEManager(QObject):
    """Singleton BLE manager with persistent event loop"""
    
    operation_finished = pyqtSignal(object)
    operation_error = pyqtSignal(str)
    
    _instance = None
    _initialized = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if BLEManager._initialized:
            return
        
        super().__init__()
        BLEManager._initialized = True
        
        self.loop = None
        self.thread = None
        self.client = None
        self.start_event_loop()
    
    def start_event_loop(self):
        """Start a persistent event loop in a separate thread"""
        def run_loop():
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)
            self.loop.run_forever()
        
        self.thread = threading.Thread(target=run_loop, daemon=True)
        self.thread.start()
        
        # Wait for loop to be ready
        import time
        timeout = 5  # 5 second timeout
        start_time = time.time()
        while self.loop is None:
            if time.time() - start_time > timeout:
                raise RuntimeError("Failed to start event loop within timeout")
            time.sleep(0.01)
    
    def run_async(self, coro):
        """Run async operation in the persistent event loop"""
        if self.loop and not self.loop.is_closed():
            future = asyncio.run_coroutine_threadsafe(coro, self.loop)
            return future
        else:
            raise RuntimeError("Event loop not available")
    
    def stop(self):
        """Stop the event loop"""
        if self.loop and not self.loop.is_closed():
            self.loop.call_soon_threadsafe(self.loop.stop)

class AsyncWorker(QThread):
    """Simplified worker that uses the persistent BLE manager"""
    
    finished = pyqtSignal(object)
    error = pyqtSignal(str)
    
    def __init__(self, coro):
        super().__init__()
        self.coro = coro
        self.ble_manager = BLEManager()
    
    def run(self):
        try:
            future = self.ble_manager.run_async(self.coro)
            result = future.result(timeout=30)  # 30 second timeout
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))

class EditValueDialog(QDialog):
    """Dialog for editing characteristic values"""
    
    def __init__(self, char_name: str, current_value: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Edit {char_name}")
        self.setModal(True)
        
        layout = QVBoxLayout()
        
        layout.addWidget(QLabel(f"Enter new value for {char_name}:"))
        
        self.value_edit = QLineEdit(current_value)
        self.value_edit.selectAll()
        layout.addWidget(self.value_edit)
        
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        
        self.setLayout(layout)
        self.value_edit.setFocus()
    
    def get_value(self) -> str:
        return self.value_edit.text()
    


class IMUPlotWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        self.plot_widget = pg.GraphicsLayoutWidget()
        layout.addWidget(self.plot_widget)
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
                if sensor == 2:  # Magnetometer
                    p.setYRange(-500, 500)
                    p.setXRange(0, 200)
                    yticks = [(-500, '-500'), (500, '500')]
                    p.getAxis('left').setTicks([yticks])
                else:
                    p.setYRange(-3000, 3000)
                    p.setXRange(0, self.max_points)
                    yticks = [(-3000, '-3000'), (0, '0'), (3000, '3000')]
                    p.getAxis('left').setTicks([yticks])
                # Set title with color
                title_style = f"<span style='color: rgb{title_colors[idx]}; font-size:14pt'><b>{titles[idx]}</b></span>"
                p.setTitle(title_style)
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





class ZMQListener(QThread):
    """Dedicated thread for ZMQ message handling"""
    message_received = pyqtSignal(str)
    trigger_requested = pyqtSignal()
    sync_requested = pyqtSignal(int)
    program_requested = pyqtSignal(dict)
    connect_requested = pyqtSignal(str)  
    enable_imu_requested = pyqtSignal()  
    disable_imu_requested = pyqtSignal() 
    read_battery_requested = pyqtSignal() 
    startup_message = pyqtSignal(str)
    reply_ready = pyqtSignal(str)
    toggle_status_led_requested = pyqtSignal(int)
    
    def __init__(self, context):
        super().__init__()
        self.context = context
        self.running = True
        self.socket = None
        self.expecting_program_data = False
        self.reply_queue = queue.Queue()

    def run(self):
        try:
            self.socket = self.context.socket(zmq.REP)
            # Add timeout to prevent blocking
            self.socket.setsockopt(zmq.RCVTIMEO, 100)  # 100ms timeout
            self.socket.setsockopt(zmq.LINGER, 0)      # Don't wait when closing
            
            ip = get_ip()
            self.socket.bind(f"tcp://localhost:5555")
            self.startup_message.emit(f"ZMQ server listening on tcp://localhost:5555")
            while self.running:
                try:
                    # Non-blocking receive
                    message = self.socket.recv_string()
                    
                    # Skip processing if we're shutting down
                    if not self.running:
                        break
                        
                    self.message_received.emit(message)
                    
                    # Handle messages based on type
                    if self.expecting_program_data:
                        try:
                            program_data = eval(message)
                            self.program_requested.emit(program_data)
                            reply = self.reply_queue.get()  # Wait for BLE thread to put reply
                            self.socket.send_string(reply)
                            
                        except Exception as e:
                            self.socket.send_string(f"Error programming: {str(e)}")
                        self.expecting_program_data = False
                        
                    elif "optogrid.trigger" in message:
                        self.trigger_requested.emit()
                        reply = self.reply_queue.get()
                        self.socket.send_string(reply)
                        
                    elif "optogrid.readbattery" in message:
                        self.read_battery_requested.emit()
                        reply = self.reply_queue.get()
                        self.socket.send_string(reply)

                    elif "optogrid.sync" in message:
                        try:
                            sync_value = int(message.split('=')[1].strip())
                            self.sync_requested.emit(sync_value)
                            reply = self.reply_queue.get()
                            self.socket.send_string(reply)
                        except Exception as e:
                            self.socket.send_string(f"Error writing sync: {str(e)}")
                    
                    elif "optogrid.connect" in message:
                        # Extract device name after "="
                        device_name = message.split('=')[1].strip()
                        self.connect_requested.emit(device_name)
                        reply = self.reply_queue.get()
                        self.socket.send_string(reply)
                        
                    elif "optogrid.enableIMU" in message:
                        self.enable_imu_requested.emit()
                        reply = self.reply_queue.get()
                        self.socket.send_string(reply)
                        
                    elif "optogrid.disableIMU" in message:
                        self.disable_imu_requested.emit()
                        reply = self.reply_queue.get()
                        self.socket.send_string(reply)
                        
                    elif "optogrid.toggleStatusLED" in message:
                        # Parse value (should be 0 or 1)
                        try:
                            led_value = int(message.split('=')[1].strip())
                            self.toggle_status_led_requested.emit(led_value)
                            reply = self.reply_queue.get()
                            self.socket.send_string(reply)
                        except Exception as e:
                            return f"ERROR: Invalid value for toggleStatusLED: {e}"
                        
                    elif "optogrid.program" in message:
                        self.expecting_program_data = True
                        self.socket.send_string("Ready for program data")
                        
                    else:
                        self.socket.send_string("Unknown command")
                        
                except zmq.Again:
                    # Timeout occurred, just continue the loop
                    continue
                except zmq.ZMQError as e:
                    if self.running:  # Only log if not shutting down
                        print(f"ZMQ Error: {e}")
                    break
                    
        finally:
            # Only close socket in the same thread that created it
            if hasattr(self, 'socket') and self.socket:
                try:
                    self.socket.close()
                except Exception as e:
                    print(f"Error closing ZMQ socket: {e}")
                self.socket = None



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


    def send_reply(self, reply: str):
        if self.socket:
            try:
                self.socket.send_string(reply)
            except Exception as e:
                print(f"Error sending ZMQ reply: {e}")

    def stop(self):
        """Stop the listener thread safely"""
        self.running = False  # Set this first
        # if self.socket:
        #     try:
        #         self.socket.setsockopt(zmq.LINGER, 0)  # Set LINGER to 0
        #         self.socket.close()                    # Just close, don't unbind
        #         self.socket = None
        #     except Exception as e:
        #         print(f"Error closing ZMQ socket: {e}")



class OptoGridBLEClient(QMainWindow):
    """Main application window"""
    battery_voltage_read = pyqtSignal(int)


    def __init__(self):
        super().__init__()
        self.setWindowTitle("OptoGrid BLE Browser")
        
        self.imu_counter = 0
        self.yaw_angle = 0.0
        # self.fusion_beta = 0.8 # Madgwick filter beta value

        self.battery_voltage_read.connect(self.update_battery_voltage_bar)
        self.imu_data_buffer = []
        # self.fusion_filter = Madgwick(frequency=100, beta=self.fusion_beta)  # Initialize with 100hz data rate, lower beta
        # self.q = np.array([1.0, 0.0, 0.0, 0.0])        # Initial quaternion

        # Add battery voltage tracking
        self.current_battery_voltage = None  # Store current voltage
        
        # Battery voltage auto-read timer (1 minute = 60000 ms)
        self.battery_timer = QTimer()
        self.battery_timer.timeout.connect(self.read_battery_voltage)
        

        self.var_acc = 0.0001  # Lower value = trust accelerometer more for tilt
        self.var_gyro = 10   # Higher value = less gyro drift
        self.var_mag = 0.1   # Lower value = trust magnetometer more for yaw 
        self.var_declination = 0.0
        
        self.fusion_filter = EKF(
            frequency=100,  # Base sample rate
            var_acc=self.var_acc,   # Lower value = trust accelerometer more for tilt
            var_gyro=self.var_gyro,   # Higher value = less gyro drift
            var_mag=self.var_mag,    # Lower value = trust magnetometer more for heading
            declination=self.var_declination # Set local magnetic declination here
        )
        self.q = np.array([1.0, 0.0, 0.0, 0.0])       # Initial quaternion

        # Complementary filter parameters
        # self.dt = 0.01  # 100Hz sample rate, adjust based on IMU rate
        # self.alpha = 0.96  # Complementary filter coefficient
        # self.last_angles = [0, 0, 0]  # [roll, pitch, yaw]
        
        # Drift correction parameters
        self.last_mag = np.zeros(3)

        # Posture smoothing parameters
        self.last_roll = None
        self.last_pitch = None
        self.last_yaw = None
        
        # Configure window position and sizef
        self.setGeometry(0, 0, 950, 1000)  # x, y, width, height
        
        # BLE client state
        self.device_list: List[BLEDevice] = []
        self.selected_device: Optional[BLEDevice] = None
        self.client: Optional[BleakClient] = None
        self.char_uuid_map: Dict[int, str] = {}
        self.char_writable_map: Dict[int, bool] = {}
        self.led_selection_value = 0
        self.item_counter = 0
        self.current_worker: Optional[AsyncWorker] = None
        self.ble_manager = BLEManager()

        # ZMQ initialization with proper signal connections
        self.zmq_context = zmq.Context()
        self.zmq_listener = ZMQListener(self.zmq_context)
        self.zmq_listener.startup_message.connect(self.log)
        self.zmq_listener.message_received.connect(lambda msg: self.log(f"ZMQ received: {msg}"))
        self.zmq_listener.trigger_requested.connect(self.handle_trigger_request)
        self.zmq_listener.sync_requested.connect(self.handle_sync_request)
        self.zmq_listener.program_requested.connect(self.handle_program_request)
        self.zmq_listener.start()
        self.zmq_listener.connect_requested.connect(self.handle_connect_request)
        self.zmq_listener.enable_imu_requested.connect(self.handle_enable_imu_request)
        self.zmq_listener.disable_imu_requested.connect(self.handle_disable_imu_request)
        self.zmq_listener.read_battery_requested.connect(self.handle_read_battery_request)
        self.imu_enable_state = False
        self.zmq_listener.reply_ready.connect(self.zmq_listener.send_reply)
        self.zmq_listener.toggle_status_led_requested.connect(self.handle_toggle_status_led_request)
        
        # Initialize magnetometer calibration parameters
        self.mag_offset = np.array([0.0, 0.0, 0.0])  # Hard-iron offsets
        self.mag_scale = np.array([1.0, 1.0, 1.0])   # Soft-iron scale factors
        
        self.setup_ui()
        self.setup_connections()

        # Setup GPIO trigger only if GPIO is available
        if GPIO_AVAILABLE:
            self.setup_gpio_trigger(pin=17)  # Use GPIO pin 17 for rising edge detection
        else:
            self.log("Skipping GPIO setup: Not available on this device.")
            
        # Start in non-debug mode
        self.toggle_debug_mode(False)
        self.debug_button.setEnabled(True)  # Keep debug button always enabled
    





    def setup_gpio_trigger(self, pin=17):
        """Setup GPIO pin for rising edge detection to trigger send_trigger."""
        if not GPIO_AVAILABLE:
            self.log("GPIO functionality is not available on this device.")
            return
    
        GPIO.setmode(GPIO.BCM)  # Use BCM numbering
        GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)  # Set pin as input with pull-down resistor
    
        # Add event detection for rising edge
        GPIO.add_event_detect(pin, GPIO.RISING, callback=self.gpio_trigger_callback, bouncetime=200)
        self.log(f"GPIO pin {pin} configured for rising edge detection.")

    def gpio_trigger_callback(self, channel):
        """Callback function for GPIO rising edge detection."""
        if not GPIO_AVAILABLE:
            self.log("GPIO functionality is not available on this device.")
            return
    
        self.log(f"Rising edge detected on GPIO pin {channel}. Sending trigger...")
        self.send_trigger()

    def handle_toggle_status_led_request(self, led_value):
        async def do_toggle():
            try:
                status_led_uuid = "56781507-5678-1234-1234-5678abcdeff0"
                encoded_value = encode_value(status_led_uuid, str(led_value))
                await self.client.write_gatt_char(status_led_uuid, encoded_value)
                state = "on" if led_value else "off"
                self.zmq_listener.reply_queue.put(f"Status LED turned {state}")
            except Exception as e:
                self.zmq_listener.reply_queue.put(f"Failed to toggle Status LED: {str(e)}")
        self.current_worker = AsyncWorker(do_toggle())
        self.current_worker.finished.connect(lambda _: None)
        self.current_worker.error.connect(lambda error: self.log(f"Error: {error}"))
        self.current_worker.start()

    def process_imu_orientation(self, imu_values):
        """Process IMU data and calculate orientation with magnetometer as compass"""
        acc_x = imu_values[1]
        acc_y = imu_values[2]
        acc_z = imu_values[3]
        gyro_x = imu_values[4]
        gyro_y = imu_values[5]
        gyro_z = imu_values[6]
        mag_x = imu_values[7]
        mag_y = imu_values[8]
        mag_z = imu_values[9]

        # --- STEP 1: Apply calibration to raw sensor data ---
        mag_raw = np.array([mag_x, mag_y, mag_z]) # Raw magnetometer data
        if hasattr(self, 'mag_offset') and hasattr(self, 'mag_scale'):
            mag_calibrated = (mag_raw - self.mag_offset) * self.mag_scale
        else:
            mag_calibrated = mag_raw
        
        # Convert units using sensor ranges and 16-bit signed integer output
        acc = np.array([acc_x, acc_y, acc_z]) * (32.0 / 65536.0)  # g
        gyr = np.array([gyro_x, gyro_y, gyro_z]) * (4000.0 / 65536.0)  # dps
        mag = mag_calibrated * (100.0 / 65536.0)  # gauss

        # --- Compute heading from calibrated magnetometer (relative to North) ---
        # Heading (degrees) = arctan2(Y, X) in horizontal plane
        # Assume device is flat (no tilt compensation)
        # heading_rad = np.arctan2(mag[0], mag[1])
        # heading_deg = (np.degrees(heading_rad) + 360) % 360  # Normalize to 0-360

        # # Optional: log or print heading for debugging
        # if self.imu_counter % 100 == 0:  # Log every 100th sample
        #     self.log(f"Magnetometer heading (deg): {heading_deg:.1f}")

        # Use magnetometer magnitude to determine validity
        mag_magnitude = np.linalg.norm(mag)
        
        # Use very lenient magnetometer validation - we want to use it as much as possible
        is_mag_valid = mag_magnitude > 0.01  # Very low threshold
        
        # Only reject magnetometer for truly extreme disturbances
        if hasattr(self, 'last_mag_calibrated'):
            mag_change = np.linalg.norm(mag - self.last_mag)
            if mag_change > 2.0:  # Much higher threshold - only reject extreme disturbances
                is_mag_valid = False
                self.log("Extreme magnetic disturbance detected")
        
        self.last_mag = mag.copy()

        # --- STEP 2: Unify all sensors into a common DEVICE FRAME ---
        # The Accelerometer and Gyroscope are already in our desired Device Frame.
        # The Magnetometer is not, so we remap it to match the others.
        # Your mapping: Mag_Device_X = Mag_Y, Mag_Device_Y = Mag_X, Mag_Device_Z = Mag_Z
        acc_device = acc.copy()
        gyr_device = gyr.copy()
        mag_device = np.array([mag_calibrated[0], mag_calibrated[1], mag_calibrated[2]])

        # Remap 2: match IMU and Magnetometer axes to rat local reference frame
        # IMU_X_Local_Frame = IMU_X
        # IMU_Y_Local_Frame = IMU_Y
        # IMU_Z_Local_Frame = IMU_Z
        acc_world = np.array([-acc_device[2], -acc_device[0], acc_device[1]])  
        gyr_world = np.array([-gyr_device[2], -gyr_device[0], gyr_device[1]])
        mag_world = np.array([-mag_device[2], -mag_device[1], mag_device[0]])  

        # acc_local_frame = acc.copy()  # Already in local frame
        # gyr_local_frame = gyr.copy()  # Already in local frame
        # mag_local_frame = mag_imu_frame.copy()  # Already in local frame
        
        # Zeros gyr if it is below a threshold
        gyro_noise_threshold = 5  # Adjust this threshold as needed
        gyr_world = np.where(np.abs(gyr_world) < gyro_noise_threshold, 0, gyr_world)

        
        if is_mag_valid:
            # EKF expects measurements in SI units
            acc_si = acc_world * 9.80665  # Convert g to m/s²
            gyr_si = np.radians(gyr_world)  # Convert dps to rad/s
            mag_si = mag_world * 100.0  # Convert gauss to µT

            
            # EKF update with 9DOF
            self.q = self.fusion_filter.update(
                q=self.q,
                gyr=gyr_si,
                acc=acc_si,
                mag=mag_si
            )
        else:
            # EKF update with 6DOF (no magnetometer)
            acc_si = acc * 9.80665
            gyr_si = np.radians(gyr_world)
            
            self.q = self.fusion_filter.update(
                q=self.q,
                gyr=gyr_si,
                acc=acc_si
            )

        # Convert quaternion to Euler angles
        roll, pitch, yaw = np.degrees(q2euler(self.q))
        
        # **Ensure yaw is always 0-360 degrees (compass convention)**
        yaw = (yaw + 360) % 360

        # # Store angles for next iteration
        # self.last_angles = [roll, pitch, yaw]

        # Light smoothing only (don't over-smooth the compass!)
        if self.last_roll is None:
            smooth_roll = roll
            smooth_pitch = pitch
            smooth_yaw = yaw
        else:
            # Use lighter smoothing to preserve compass responsiveness
            alpha_rp = 1   # Turn off smoothing for roll/pitch for now
            alpha_yaw = 1  # Turn off smoothing for yaw for now
            
            smooth_roll = alpha_rp * roll + (1 - alpha_rp) * self.last_roll
            smooth_pitch = alpha_rp * pitch + (1 - alpha_rp) * self.last_pitch
            
            # Handle yaw wrap-around for smoothing
            delta_yaw = ((yaw - self.last_yaw + 180) % 360) - 180
            smooth_yaw = self.last_yaw + alpha_yaw * delta_yaw
            smooth_yaw = (smooth_yaw + 360) % 360

        self.last_roll = smooth_roll
        self.last_pitch = smooth_pitch
        self.last_yaw = smooth_yaw

        # self.log(f"Orientation - Roll: {self.last_roll:.1f}°, Pitch: {self.last_pitch:.1f}°, Yaw: {self.last_yaw:.1f}°")

        return smooth_roll, smooth_pitch, smooth_yaw










    def load_magnetometer_calibration(self, device_name):
        """Load magnetometer calibration from device-specific CSV file"""
        try:

            # Create calibration filename based on device name
            calibration_filename = f"data/{device_name} Calibration.csv"
            
            if not os.path.exists(calibration_filename):
                self.log(f"Magnetometer calibration file not found: {calibration_filename}")
                self.log("Using default calibration (no offset correction)")
                self.mag_offset = np.array([0.0, 0.0, 0.0])
                self.mag_scale = np.array([1.0, 1.0, 1.0])
                return False
            
            # Read calibration data
            self.log(f"Loading magnetometer calibration from: {calibration_filename}")
            cal_data = pd.read_csv(calibration_filename)
            
            # Extract magnetometer columns (mag_x, mag_y, mag_z)
            if not all(col in cal_data.columns for col in ['mag_x', 'mag_y', 'mag_z']):
                self.log("Error: Calibration file missing required magnetometer columns (mag_x, mag_y, mag_z)")
                self.mag_offset = np.array([0.0, 0.0, 0.0])
                self.mag_scale = np.array([1.0, 1.0, 1.0])
                return False
            
            mag_x_data = cal_data['mag_x'].values
            mag_y_data = cal_data['mag_y'].values
            mag_z_data = cal_data['mag_z'].values
            
            # Calculate hard-iron offsets (center of measurement range)
            mag_x_offset = (np.max(mag_x_data) + np.min(mag_x_data)) / 2
            mag_y_offset = (np.max(mag_y_data) + np.min(mag_y_data)) / 2
            mag_z_offset = (np.max(mag_z_data) + np.min(mag_z_data)) / 2
            
            self.mag_offset = np.array([mag_x_offset, mag_y_offset, mag_z_offset])
            
            # Calculate soft-iron scale factors (normalize to unit sphere)
            mag_x_range = np.max(mag_x_data) - np.min(mag_x_data)
            mag_y_range = np.max(mag_y_data) - np.min(mag_y_data)
            mag_z_range = np.max(mag_z_data) - np.min(mag_z_data)
            
            # Use the average range as reference
            avg_range = (mag_x_range + mag_y_range + mag_z_range) / 3
            
            mag_x_scale = avg_range / mag_x_range if mag_x_range > 0 else 1.0
            mag_y_scale = avg_range / mag_y_range if mag_y_range > 0 else 1.0
            mag_z_scale = avg_range / mag_z_range if mag_z_range > 0 else 1.0
            
            self.mag_scale = np.array([mag_x_scale, mag_y_scale, mag_z_scale])
            
            # Log calibration parameters
            self.log(f"Magnetometer calibration loaded successfully:")
            self.log(f"  Hard-iron offsets: X={mag_x_offset:.2f}, Y={mag_y_offset:.2f}, Z={mag_z_offset:.2f}")
            self.log(f"  Soft-iron scales: X={mag_x_scale:.3f}, Y={mag_y_scale:.3f}, Z={mag_z_scale:.3f}")
            self.log(f"  Data points used: {len(mag_x_data)}")
            
            return True
            
        except Exception as e:
            self.log(f"Error loading magnetometer calibration: {str(e)}")
            self.mag_offset = np.array([0.0, 0.0, 0.0])
            self.mag_scale = np.array([1.0, 1.0, 1.0])
            return False




    def handle_connect_request(self, device_name):
        """Handle ZMQ connect request"""
        async def do_connect():
            try:

                # Scan for devices
                devices = await BleakScanner.discover(timeout=2)
                matching_device = next((d for d in devices if d.name and device_name in d.name), None)
                
                if matching_device:
                    # Update UI and device selection
                    self.device_list = [matching_device]
                    self.devices_combo.clear()
                    self.devices_combo.addItem(matching_device.name)
                    self.devices_combo.setCurrentIndex(0)
                    self.selected_device = matching_device
                    
                    # Use existing connect_and_browse method
                    await self.connect_and_browse()
                    self.zmq_listener.reply_queue.put(f"{matching_device.name} Connected")
                    return f"{matching_device.name} Connected"  # Return success
                
                else:
                    self.zmq_listener.reply_queue.put(f"Device {device_name} not found")
                    raise Exception(f"Device {device_name} not found")
                
            except Exception as e:
                if "not found" not in str(e):  # Only log if it's not the "device not found" error
                    self.log(f"Connection failed: {str(e)}")
                if f"Device {device_name} not found" not in str(e):
                    self.zmq_listener.reply_queue.put(f"Connection failed: {str(e)}")
                raise  # Re-raise to ensure error handler is called
    
        # Execute the connection
        self.current_worker = AsyncWorker(do_connect())
        self.current_worker.finished.connect(self.on_connect_complete)
        self.current_worker.error.connect(self.on_connect_error)
        self.current_worker.start()

                
    def handle_sync_request(self, sync_value):
        """Handle sync value request from ZMQ"""
        try:
            if hasattr(self, "imu_data_buffer") and self.imu_data_buffer:
                self.imu_data_buffer[-1][-1] = sync_value
                self.log(f"Sync value {sync_value} written to IMU data")
                self.zmq_listener.reply_queue.put("Sync Written")
            else:
                self.log("No IMU data buffer available for sync")
        except Exception as e:
            self.log(f"Error handling sync request: {e}")

    def handle_program_request(self, program_data):
        """Handle program settings request from ZMQ"""
        async def do_program():
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
                        await self.do_write_single(uuid, str(value), setting_name)
                        # Update brain map UI if led_selection is changed
                        if setting_name == "led_selection":
                            try:
                                self.led_selection_value = int(value)
                            except Exception:
                                self.led_selection_value = 0
                            if hasattr(self, "brain_map"):
                                self.brain_map.update_led_selection(self.led_selection_value)
                
                self.zmq_listener.reply_queue.put("Opto Programmed")

            except Exception as e:
                self.log(f"Error handling program request: {e}")

        # Run the async program in the BLE manager thread
        self.current_worker = AsyncWorker(do_program())
        self.current_worker.finished.connect(lambda _: self.log("All program values written."))
        self.current_worker.error.connect(lambda error: self.log(f"Error: {error}"))
        self.current_worker.start()

    def handle_trigger_request(self):
        """Handle ZMQ trigger request and reply only if successful"""
        async def do_trigger():
            try:
                result = await self.do_send_trigger()
                # Only send reply if successful
                self.zmq_listener.reply_queue.put("Opto Triggered")
                return result
            except Exception as e:
                # Send error reply if failed
                self.zmq_listener.reply_queue.put(f"Trigger failed: {e}")
                self.log(f"Error sending trigger via ZMQ: {e}")
                raise
    
        self.current_worker = AsyncWorker(do_trigger())
        self.current_worker.finished.connect(self.on_trigger_complete)
        self.current_worker.error.connect(self.on_trigger_error)
        self.current_worker.start()

    def handle_enable_imu_request(self):
        """Handle ZMQ IMU enable request"""
        if not self.imu_enable_state:  # Only if not already enabled
            self.toggle_imu_enable()  # Use existing method
            self.zmq_listener.reply_queue.put("IMU enabled, and logging started")

    def handle_disable_imu_request(self):
        """Handle ZMQ IMU disable request"""
        if self.imu_enable_state:  # Only if currently enabled
            self.toggle_imu_enable()  # Use existing method
            self.zmq_listener.reply_queue.put("IMU disabled, and logging stopped")

    def handle_read_battery_request(self):
        """Handle ZMQ battery voltage read request"""
        if not self.client or not self.client.is_connected:
            self.zmq_listener.reply_queue.put("Error: Not connected to device")
            return

        # Extract device name from GATT table
        device_name = "Unknown Device"
        for i in range(self.gatt_tree.topLevelItemCount()):
            item = self.gatt_tree.topLevelItem(i)
            if item.text(1) == "Device ID":  # Look for the Device ID characteristic
                device_name = item.text(2)  # Get the current value
                break

        # Use existing read_battery_voltage method but capture the result
        self.battery_voltage_read.disconnect()  # Temporarily disconnect existing handler

        def battery_read_handler(voltage):
            reply = f"{device_name} Battery Voltage = {voltage} mV"
            self.zmq_listener.reply_queue.put(reply)
            self.battery_voltage_read.connect(self.update_battery_voltage_bar)  # Reconnect

        self.battery_voltage_read.connect(battery_read_handler)
        self.read_battery_voltage()  # Trigger the existing read function

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
        left_layout.setSpacing(4)
        left_layout.setContentsMargins(4, 4, 4, 4)

        device_frame = QFrame()
        device_layout = QHBoxLayout(device_frame)
        controls_container = QVBoxLayout()
        controls_container.setSpacing(4)
        controls_container.setContentsMargins(0, 0, 0, 0)
        self.scan_button = QPushButton("Scan")
        self.scan_button.setFixedWidth(240)
        controls_container.addWidget(self.scan_button)
        controls_container.addSpacing(10)  # Add vertical space

        self.devices_combo = QComboBox()
        self.devices_combo.setFixedWidth(230)
        controls_container.addWidget(self.devices_combo)
        controls_container.addSpacing(10)  # Add vertical space

        self.connect_button = QPushButton("Connect")
        self.connect_button.setFixedWidth(240)
        controls_container.addWidget(self.connect_button)
        controls_container.addSpacing(15)  # Add vertical space

        self.debug_button = QCheckBox("Debug Mode")
        self.debug_button.setStyleSheet("""
            QCheckBox { spacing: 5px; font-weight: bold; }
            QCheckBox::indicator { width: 60px; height: 15px; border: 2px solid #8f8f91; border-radius: 8px; }
            QCheckBox::indicator:unchecked { background-color: #f0f0f0; }
            QCheckBox::indicator:checked { background-color: #90EE90; border-color: #4CAF50; }
        """)
        controls_container.addWidget(self.debug_button)

        device_layout.addLayout(controls_container)
        left_layout.addWidget(device_frame)

        # Add row pitch yaw 3D display
        self.imu_3d_widget = IMU3DWidget()
        self.imu_3d_widget.setFixedSize(300, 150) 
        device_layout.addWidget(self.imu_3d_widget)
        

        # left_layout.addWidget(QLabel("Log Output:"))
        self.log_text = QTextEdit()
        self.log_text.setFixedSize(600, 200) 
        # Set a monospace font for consistent spacing
        log_font = QFont("Consolas", 9)  # or "Courier New", "Monaco"
        if not log_font.exactMatch():
            log_font = QFont("Courier New", 9)
        self.log_text.setFont(log_font)
        
        # Set consistent line spacing
        self.log_text.setStyleSheet("""
            QTextEdit {
                line-height: 1.2;
                font-family: "Consolas", "Courier New", monospace;
                font-size: 9pt;
                border: 1px solid #ccc;
            }
        """)
        left_layout.addWidget(self.log_text)
        left_layout.addSpacing(2)  # Add this line for minimal vertical gap


        control_frame = QFrame()
        control_layout = QHBoxLayout(control_frame)
        control_layout.setSpacing(0)
        control_layout.setContentsMargins(0, 0, 0, 0)
        self.read_button = QPushButton("Read All Values")
        self.read_button.setEnabled(False)
        control_layout.addWidget(self.read_button)
        control_layout.addSpacing(20)  # Add spacing
        
        self.write_button = QPushButton("Write Values")
        self.write_button.setEnabled(False)
        control_layout.addWidget(self.write_button)
        control_layout.addSpacing(20)  # Add spacing

        self.trigger_button = QPushButton("TRIGGER")
        self.trigger_button.setEnabled(False)
        self.trigger_button.setStyleSheet("background-color: #ff4444; font-weight: bold;")
        self.trigger_button.setFixedSize(180, 36) 
        control_layout.addWidget(self.trigger_button)
        left_layout.addWidget(control_frame)
        top_section.addWidget(left_panel, 2)

        # Right: Brain map and LED controls
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setSpacing(4)
        right_layout.setContentsMargins(4, 4, 4, 4)
        right_layout.addWidget(QLabel("LED selection GUI:"))
        self.brain_map = BrainMapWidget()
        right_layout.addWidget(self.brain_map)
        led_state_frame = QFrame()
        led_state_layout = QHBoxLayout(led_state_frame)
        right_layout.addSpacing(10)  # Add spacing 


        self.sham_led_button = QPushButton("SHAM LED")
        self.sham_led_button.setEnabled(False)
        self.sham_led_button.setFixedSize(100, 30)
        self.sham_led_button.setStyleSheet("background-color: #888888; font-weight: bold;")
        led_state_layout.addWidget(self.sham_led_button)
        led_state_layout.addSpacing(22)  # Add spacing 

        self.imu_enable_button = QPushButton("IMU ENABLE")
        self.imu_enable_button.setEnabled(False)
        self.imu_enable_button.setFixedSize(100, 30)
        self.imu_enable_button.setStyleSheet("background-color: #888888; font-weight: bold;")
        led_state_layout.addWidget(self.imu_enable_button)
        led_state_layout.addSpacing(22)  # Add spacing

        self.status_led_button = QPushButton("STATUS LED")
        self.status_led_button.setEnabled(False)
        self.status_led_button.setFixedSize(100, 30)
        self.status_led_button.setStyleSheet("background-color: #888888; font-weight: bold;")
        led_state_layout.addWidget(self.status_led_button)
        led_state_layout.addStretch()
        right_layout.addWidget(led_state_frame)
        led_state_layout2 = QHBoxLayout()
        right_layout.addSpacing(15)  # Add vertical space
        
        # Add read battery voltage button and progress bar

        # Create a horizontal layout for the battery display row
        battery_row_layout = QHBoxLayout()
        battery_row_layout.setSpacing(8)

        # Left label
        self.battery_voltage_min_label = QLabel("3.5V")
        self.battery_voltage_min_label.setFixedWidth(36)
        self.battery_voltage_min_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        battery_row_layout.addWidget(self.battery_voltage_min_label)

        # Progress bar
        self.battery_voltage_bar = QProgressBar()
        self.battery_voltage_bar.setFixedSize(110, 30)
        self.battery_voltage_bar.setRange(3500, 4200)  # mV range
        self.battery_voltage_bar.setValue(4000)
        self.battery_voltage_bar.setAlignment(Qt.AlignCenter)
        self.battery_voltage_bar.setFormat("")
        # Set green color for progress bar
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

        # Right label
        self.battery_voltage_max_label = QLabel("4.2V")
        self.battery_voltage_max_label.setFixedWidth(36)
        self.battery_voltage_max_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        battery_row_layout.addWidget(self.battery_voltage_max_label)

        # Read button (left aligned)
        self.battery_voltage_button = QPushButton("Read Battery Voltage")
        self.battery_voltage_button.setEnabled(False)
        self.battery_voltage_button.setFixedSize(160, 30)

        # Add the button and the battery row to your led_state_layout2
        led_state_layout2.addWidget(self.battery_voltage_button, alignment=Qt.AlignLeft)
        led_state_layout2.addLayout(battery_row_layout)
        
        right_layout.addLayout(led_state_layout2)
        top_section.addWidget(right_panel, 1)

        main_layout.addLayout(top_section)

        # --- Bottom Section ---
        bottom_section = QHBoxLayout()

        # Left: GATT Table
        gatt_panel = QWidget()
        gatt_layout = QVBoxLayout(gatt_panel)
        gatt_layout.setSpacing(4)
        gatt_layout.setContentsMargins(4, 4, 4, 4)
        gatt_layout.addWidget(QLabel("GATT Table:"))
        self.gatt_tree = QTreeWidget()
        self.gatt_tree.setHeaderLabels(["Service", "Characteristic", "Value", "Write Value", "Unit"])
        self.gatt_tree.setMaximumWidth(500)
        header = self.gatt_tree.header()
        self.gatt_tree.setColumnWidth(0, 80)
        self.gatt_tree.setColumnWidth(1, 140)
        self.gatt_tree.setColumnWidth(2, 100)
        self.gatt_tree.setColumnWidth(3, 100)
        self.gatt_tree.setColumnWidth(4, 80)
        header.setSectionResizeMode(QHeaderView.Interactive)
        gatt_layout.addWidget(self.gatt_tree, 1)
        bottom_section.addWidget(gatt_panel, 2)

        # Right: IMU Data Visualization
        imu_panel = QWidget()
        imu_layout = QVBoxLayout(imu_panel)
        imu_layout.setSpacing(4)
        imu_layout.setContentsMargins(4, 4, 4, 4)
        imu_layout.addWidget(QLabel("IMU Data (last 200 samples):"))
        self.imu_plot_widget = IMUPlotWidget()
        self.imu_plot_widget.setFixedSize(450, 350) 
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
    
    def toggle_debug_mode(self, enabled: bool):
        """Toggle debug mode"""
        # List of all buttons to control
        buttons = [
            self.scan_button,
            self.connect_button,
            self.read_button,
            self.write_button,
            self.trigger_button,
            self.sham_led_button,
            self.status_led_button
        ]
        
        # Enable/disable all buttons
        for button in buttons:
            button.setEnabled(enabled)
        
        # Also enable/disable the devices combo
        self.devices_combo.setEnabled(enabled)
        
        # Update log
        if enabled:
            self.log("Debug mode enabled")
        else:
            self.log("Debug mode disabled")
            
    def log(self, message: str, max_lines=100):
        """Add message to log output, keeping only the last max_lines lines."""
        self.log_text.append(message)
        self.log_text.ensureCursorVisible()
        # Limit the number of lines
        if self.log_text.document().blockCount() > max_lines:
            cursor = self.log_text.textCursor()
            cursor.movePosition(cursor.Start)
            for _ in range(self.log_text.document().blockCount() - max_lines):
                cursor.select(cursor.LineUnderCursor)
                cursor.removeSelectedText()
                cursor.deleteChar()
    
    def start_scan(self):
        """Start BLE device scanning"""
        # Stop any existing worker
        if self.current_worker and self.current_worker.isRunning():
            self.current_worker.terminate()
            self.current_worker.wait()
            self.current_worker = None
        
        self.log("Scanning for BLE devices containing '-O-'...")
        self.scan_button.setText("Scanning...")
        self.scan_button.setEnabled(False)
        
        self.current_worker = AsyncWorker(self.scan_devices())
        self.current_worker.finished.connect(self.on_scan_complete)
        self.current_worker.error.connect(self.on_scan_error)
        self.current_worker.start()
    
    async def scan_devices(self) -> List[BLEDevice]:
        """Scan for OptoGrid devices with optimized timeout"""
        try:
            # Reduced scan time from default 10s to 3s for faster operation
            all_devices = await BleakScanner.discover(timeout=4, return_adv=False)
            return [d for d in all_devices if d.name and "-O-" in d.name]
        except Exception as e:
            # Re-raise with more context
            raise Exception(f"BLE scan failed: {str(e)}")
    
    def on_scan_complete(self, devices: List[BLEDevice]):
        """Handle scan completion"""
        self.device_list = devices
        self.devices_combo.clear()
        
        device_names = [f"{d.name}" for d in devices]
        self.devices_combo.addItems(device_names)
        
        if devices:
            self.devices_combo.setCurrentIndex(0)
        
        self.scan_button.setText("Scan")
        self.scan_button.setEnabled(True)
        self.log(f"Found {len(devices)} matching devices.")
    
    def on_scan_error(self, error: str):
        """Handle scan error"""
        self.log(f"Scan failed: {error}")
        self.scan_button.setText("Scan")
        self.scan_button.setEnabled(True)
    
    def connect_to_device(self):
        """Connect to selected device"""
        if not self.device_list:
            QMessageBox.warning(self, "No Devices", "Scan first!")
            return
        
        index = self.devices_combo.currentIndex()
        if index == -1:
            QMessageBox.warning(self, "No Selection", "Select a device first!")
            return
        
        # Stop any existing worker
        if self.current_worker and self.current_worker.isRunning():
            self.current_worker.terminate()
            self.current_worker.wait()
            self.current_worker = None
        
        self.selected_device = self.device_list[index]
        self.log(f"Connecting to {self.selected_device.name}...")
        self.connect_button.setText("Connecting...")
        self.connect_button.setEnabled(False)
        
        self.current_worker = AsyncWorker(self.connect_and_browse())
        self.current_worker.finished.connect(self.on_connect_complete)
        self.current_worker.error.connect(self.on_connect_error)
        self.current_worker.start()
    
    async def connect_and_browse(self):
        """Connect to device and discover services"""
        try:
            if self.client and self.client.is_connected:
                await self.client.disconnect()
            
            self.client = BleakClient(
                self.selected_device.address,
                disconnected_callback=self.on_disconnect_callback  # Add disconnection callback
            )
            await self.client.connect()
            await self.populate_gatt_table()
            
            # Enable notifications for device log
            device_log_uuid = "56781509-5678-1234-1234-5678abcdeff0"
            imu_data_uuid = "56781703-5678-1234-1234-5678abcdeff0"
            led_check_uuid = "56781504-5678-1234-1234-5678abcdeff0"

            # Find the characteristic object and check if it supports notifications
            for service in self.client.services:
                for char in service.characteristics:
                    if str(char.uuid).lower() == device_log_uuid.lower():
                        if "notify" in char.properties:
                            await self.client.start_notify(char.uuid, self.handle_device_log_notification)
                            self.log("Device log notifications enabled")
                        else:
                            self.log("Device log characteristic does not support notifications")
                        break

            # Enable LED check notifications
            for service in self.client.services:
                for char in service.characteristics:
                    if str(char.uuid).lower() == led_check_uuid.lower():
                        if "notify" in char.properties:
                            await self.client.start_notify(char.uuid, self.handle_led_check_notification)
                            self.log("LED check notifications enabled")
                        else:
                            self.log("LED check characteristic does not support notifications")
                        break

            # Enable IMU data notifications
            for service in self.client.services:
                for char in service.characteristics:
                    if str(char.uuid).lower() == imu_data_uuid.lower():
                        if "notify" in char.properties:
                            await self.client.start_notify(char.uuid, self.handle_imu_data_notification)
                            self.log("IMU data notifications enabled")
                        else:
                            self.log("IMU data characteristic does not support notifications")
                        break
            
            # After services are discovered in connect_and_browse:
            imu_sample_rate_uuid = "56781701-5678-1234-1234-5678abcdeff0"
            try:
                val = await self.client.read_gatt_char(imu_sample_rate_uuid)
                imu_sample_rate = int.from_bytes(val[:2], byteorder='little')
                if imu_sample_rate > 0:
                    self.fusion_filter = EKF(
                        frequency=imu_sample_rate,  # Base sample rate
                        var_acc=self.var_acc,   # Lower value = trust accelerometer more for tilt
                        var_gyro=self.var_gyro,   # Higher value = less gyro drift
                        var_mag=self.var_mag,    # Lower value = trust magnetometer more for heading
                        declination=self.var_declination # Set local magnetic declination here
                    )
                    self.log(f"EKF filter frequency set to {imu_sample_rate} Hz")
            except Exception as e:
                self.log(f"Could not read IMU sample rate: {e}")
            
            return True
        
        except Exception as e:
            self.client = None
            raise e
    
    def on_disconnect_callback(self, client):
        """Handle unexpected disconnections"""
        self.log(f"BLE device disconnected unexpectedly at sample {self.imu_counter}")
        
        # Stop battery timer on disconnect
        self.battery_timer.stop()

        # Flush any remaining IMU data to CSV
        if hasattr(self, "imu_data_buffer") and self.imu_data_buffer:
            self.flush_imu_buffer()
            self.log(f"Flushed {len(self.imu_data_buffer)} remaining samples")
        
        # Close IMU file if open
        if hasattr(self, "imu_csv_file") and self.imu_csv_file:
            self.imu_csv_file.close()
            self.imu_csv_file = None
            self.imu_csv_writer = None
            self.imu_enable_state = False
            self.imu_enable_button.setStyleSheet("background-color: #888888; font-weight: bold;")

        # Attempt reconnection after 2 seconds
        # QTimer.singleShot(2000, self.attempt_reconnection)

    # def attempt_reconnection(self):
    #     """Attempt to reconnect to the device"""
    #     if self.selected_device:
    #         self.log("Attempting to reconnect...")
    #         self.connect_to_device()

    def on_connect_complete(self, result):
        """Handle connection completion"""
        self.connect_button.setText("Connect")
        self.connect_button.setEnabled(True)
        self.read_button.setEnabled(True)
        self.write_button.setEnabled(True)
        self.trigger_button.setEnabled(True)
        self.sham_led_button.setEnabled(True)
        self.status_led_button.setEnabled(True)
        self.battery_voltage_button.setEnabled(True)
        self.imu_enable_button.setEnabled(True)
        self.log("Connected. Services discovered.")
        
        # Load magnetometer calibration for this device
        if self.selected_device and self.selected_device.name:
            self.load_magnetometer_calibration(self.selected_device.name)
        
        # self.battery_timer.start(60000)  # Read every 60 seconds
        self.read_battery_voltage()
    
    def on_connect_error(self, error: str):
        """Handle connection error"""
        self.log(f"Connection failed: {error}")
        self.connect_button.setText("Connect")
        self.connect_button.setEnabled(True)
        self.read_button.setEnabled(False)
        self.write_button.setEnabled(False)
        self.trigger_button.setEnabled(False)
        self.sham_led_button.setEnabled(False)
        self.status_led_button.setEnabled(False)
        self.battery_voltage_button.setEnabled(False)
        self.imu_enable_button.setEnabled(False)

        # Stop battery timer on connection failure
        self.battery_timer.stop()

        # Clean up worker
        if self.current_worker:
            self.current_worker.quit()
            self.current_worker.wait()
            self.current_worker = None
    
    async def populate_gatt_table(self):
        """Populate the GATT characteristics table"""
        self.char_uuid_map.clear()
        self.char_writable_map.clear()
        self.gatt_tree.clear()
        self.item_counter = 0  # Reset counter
        
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
                    # Update SHAM LED state
                    elif char_uuid == "56781508-5678-1234-1234-5678abcdeff0":  # SHAM LED state
                        try:
                            self.sham_led_state = val[0] == 1
                        except:
                            self.sham_led_state = False

                    # Update STATUS LED state
                    elif char_uuid == "56781507-5678-1234-1234-5678abcdeff0":  # STATUS LED state
                        try:
                            self.status_led_state = val[0] == 1
                        except:
                            self.status_led_state = False       
                            
                except Exception:
                    val_display = "<not readable>"
                
                unit_name = uuid_to_unit.get(char_uuid, '')
                service_display = svc_name if svc_name != past_svc_name else ""
                write_value_display = val_display if is_writable else "<read-only>"
                
                # Create tree item
                item = QTreeWidgetItem([
                    service_display, char_name, val_display, write_value_display, unit_name
                ])
                
                # Bold the Service column
                if service_display:  # Only if there's text (not empty)
                    font = item.font(0)
                    font.setBold(True)
                    item.setFont(0, font)
                
                # Color only the Write Value column based on writability
                if is_writable:
                    item.setBackground(3, QColor(245, 245, 245))  # Light green for Write Value
                else:
                    item.setBackground(3, QColor(255, 255, 255))   # White for non-writable
                
                # Store item ID and mappings
                item_id = self.item_counter
                item.setData(0, Qt.UserRole, item_id)
                self.char_uuid_map[item_id] = char_uuid
                self.char_writable_map[item_id] = is_writable
                self.item_counter += 1
                
                self.gatt_tree.addTopLevelItem(item)
                past_svc_name = svc_name
        
        # Update LED visualization
        self.brain_map.update_led_selection(self.led_selection_value)
        
        # Update Sham and Status LED state
        self.update_led_button_states()
        return True
    
    async def handle_device_log_notification(self, sender: int, data: bytearray):
        """Handle device log notifications"""
        try:
            # Find the first null byte and decode only up to that point
            null_index = data.find(0)
            if null_index != -1:
                message = data[:null_index].decode('utf-8', errors='replace')
            else:
                message = data.decode('utf-8', errors='replace')
            self.log(f"ble_log: {message}")
        except Exception as e:
            self.log(f"Error in device log handler: {str(e)}")

    async def handle_led_check_notification(self, sender: int, data: bytearray):
        """Handle LED check notifications (64-bit, each bit: 0=broken, 1=intact)"""
        try:
            # 56781504-5678-1234-1234-5678abcdeff0 is uint64
            led_check_val = int.from_bytes(data[:8], byteorder='little')
            # Store for overlay use
            self.led_check_mask = led_check_val
            # Update brain map overlay
            if hasattr(self, "brain_map"):
                self.brain_map.update_led_check_overlay(led_check_val)
            self.log(f"LED check updated: {led_check_val:064b}")
        except Exception as e:
            self.log(f"Error in LED check handler: {str(e)}")


    async def handle_imu_data_notification(self, sender: int, data: bytearray):
        try:
            imu_uuid = "56781703-5678-1234-1234-5678abcdeff0"
            imu_values_str = decode_value(imu_uuid, data)
            imu_values = [int(x.strip()) for x in imu_values_str.split(",")]
            self.imu_counter += 1
            if self.imu_counter % 100 == 0:  # Log every 100th message
                self.log(f"IMU Data: {imu_values_str}")

            

            # --- Update 3D orientation widget using AHRS sensor fusion ---
            if hasattr(self, 'imu_3d_widget') and self.imu_3d_widget:
                smooth_roll, smooth_pitch, smooth_yaw = self.process_imu_orientation(imu_values)

                # Update 3D visualization
                self.imu_3d_widget.set_orientation(smooth_roll, smooth_pitch, smooth_yaw)
            if self.imu_counter % 100 == 0:  # Log every 100th message (1 Hz)
                self.log(f"roll: {int(smooth_roll)}, pitch: {int(smooth_pitch)}, yaw: {int(smooth_yaw)}")
                # self.imu_counter = 0  # Reset counter after logging


            # Buffer IMU data for later processing
            if getattr(self, "imu_enable_state", False):


                # Get uncertainty from fusion_filter (EKF)
                uncertainty = None
                if hasattr(self.fusion_filter, "P"):
                    try:
                        # Use trace of covariance as a simple uncertainty metric
                        uncertainty = float(np.trace(self.fusion_filter.P))
                    except Exception:
                        uncertainty = None

                # Add sync value (default 0)
                imu_data_with_sync = imu_values + [0]
 

                # Add smoothed roll, pitch, yaw and uncertainty to CSV
                if self.current_battery_voltage is not None:
                    battery_v = self.current_battery_voltage
                    self.current_battery_voltage = None # Reset after reading
                else:
                    battery_v = ""

                row = imu_data_with_sync + [smooth_roll, smooth_pitch, smooth_yaw, uncertainty, battery_v]
                self.imu_data_buffer.append(row)
                if len(self.imu_data_buffer) >= 100:
                    self.flush_imu_buffer()

            # --- Update IMU plot ---
            if hasattr(self, 'imu_plot_widget') and self.imu_plot_widget:
                # Pass the raw imu_values to the plot widget
                self.imu_plot_widget.update_plot(imu_values)


        except Exception as e:
            self.log(f"Error in IMU data handler: {str(e)}")

    def flush_imu_buffer(self):
        if hasattr(self, "imu_csv_writer") and self.imu_csv_writer and self.imu_data_buffer:
            self.imu_csv_writer.writerows(self.imu_data_buffer)
            self.imu_data_buffer = []


    def edit_characteristic_value(self, item: QTreeWidgetItem, column: int):
        """Handle double-click to edit characteristic value"""
        if column != 3:  # Only allow editing Write Value column
            return
        
        # Get item ID from stored data
        item_id = item.data(0, Qt.UserRole)
        if item_id is None:
            return
        
        if not self.char_writable_map.get(item_id, False):
            return  # Don't allow editing read-only characteristics
        
        char_name = item.text(1)
        current_value = item.text(3)
        
        dialog = EditValueDialog(char_name, current_value, self)
        if dialog.exec_() == QDialog.Accepted:
            new_value = dialog.get_value()
            item.setText(3, new_value)
            
            # If this is LED Selection, update visualization
            char_uuid = self.char_uuid_map.get(item_id)
            if char_uuid == "56781601-5678-1234-1234-5678abcdeff0":  # LED Selection
                try:
                    self.led_selection_value = int(new_value)
                    self.brain_map.update_led_selection(self.led_selection_value)
                except ValueError:
                    pass
    
    def toggle_led(self, bit_position: int):
        """Toggle LED selection when clicked on brain map"""
        # Toggle the bit
        self.led_selection_value ^= (1 << bit_position)
        
        # Update LED Selection in GATT table
        led_selection_uuid = "56781601-5678-1234-1234-5678abcdeff0"
        
        for i in range(self.gatt_tree.topLevelItemCount()):
            item = self.gatt_tree.topLevelItem(i)
            item_id = item.data(0, Qt.UserRole)
            if item_id is not None:
                char_uuid = self.char_uuid_map.get(item_id)
                if char_uuid == led_selection_uuid:
                    item.setText(3, str(self.led_selection_value))
                    break
        
        # Update visualization
        self.brain_map.update_led_selection(self.led_selection_value)
    
    def read_all_values(self):
        """Read all values from the device"""
        if not self.client or not self.client.is_connected:
            QMessageBox.warning(self, "Not Connected", "Please connect to a device first!")
            return
        
        # Stop any existing worker
        if self.current_worker and self.current_worker.isRunning():
            self.current_worker.terminate()
            self.current_worker.wait()
            self.current_worker = None
        
        self.log("Reading all values...")
        self.read_button.setText("Reading...")
        self.read_button.setEnabled(False)
        
        self.current_worker = AsyncWorker(self.do_read_all())
        self.current_worker.finished.connect(self.on_read_complete)
        self.current_worker.error.connect(self.on_read_error)
        self.current_worker.start()
    
    async def do_read_all(self):
        """Perform the actual read operation"""
        return await self.populate_gatt_table()
    
    def on_read_complete(self, result):
        """Handle read completion"""
        self.read_button.setText("Read All Values")
        self.read_button.setEnabled(True)
        self.log("All values read successfully.")
    
    def on_read_error(self, error: str):
        """Handle read error"""
        self.log(f"Error reading values: {error}")
        self.read_button.setText("Read All Values")
        self.read_button.setEnabled(True)
    
    def write_values(self):
        """Write all modified values to the device"""
        if not self.client or not self.client.is_connected:
            QMessageBox.warning(self, "Not Connected", "Please connect to a device first!")
            return
        
        # Stop any existing worker
        if self.current_worker and self.current_worker.isRunning():
            self.current_worker.terminate()
            self.current_worker.wait()
            self.current_worker = None
        
        self.log("Writing values...")
        self.write_button.setText("Writing...")
        self.write_button.setEnabled(False)
        
        self.current_worker = AsyncWorker(self.do_write_values())
        self.current_worker.finished.connect(self.on_write_complete)
        self.current_worker.error.connect(self.on_write_error)
        self.current_worker.start()
    
    async def do_write_values(self):
        """Perform the actual write operations"""
        write_count = 0
        error_count = 0
        skipped_count = 0
        
        for i in range(self.gatt_tree.topLevelItemCount()):
            item = self.gatt_tree.topLevelItem(i)
            item_id = item.data(0, Qt.UserRole)
            
            if item_id is None:
                continue
            
            current_value = item.text(2)  # Current Value
            write_value = item.text(3)    # Write Value
            char_name = item.text(1)      # Characteristic Name
            
            # Skip if not writable
            if not self.char_writable_map.get(item_id, False):
                if write_value != "<read-only>" and write_value != current_value and write_value.strip():
                    self.log(f"Skipping read-only characteristic: {char_name}")
                    skipped_count += 1
                continue
            
            # Only write if values differ and write value is not empty
            if write_value != current_value and write_value.strip() and write_value != "<read-only>":
                char_uuid = self.char_uuid_map.get(item_id)
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
                    
                    # Double-check writability
                    if "write" not in char_obj.properties and "write-without-response" not in char_obj.properties:
                        self.log(f"Characteristic not writable: {char_name}")
                        skipped_count += 1
                        continue
                    
                    # Encode and write the value
                    encoded_value = encode_value(char_uuid, write_value)
                    await self.client.write_gatt_char(char_obj.uuid, encoded_value)
                    
                    self.log(f"Written to {char_name}: {write_value}")
                    write_count += 1
                    
                    # Update current value to match written value
                    item.setText(2, write_value)
                    
                    # If this is LED Selection, update visualization
                    if char_uuid == "56781601-5678-1234-1234-5678abcdeff0":  # LED Selection
                        try:
                            self.led_selection_value = int(write_value)
                        except ValueError:
                            pass
                    
                except Exception as e:
                    self.log(f"Error writing to {char_name}: {e}")
                    error_count += 1
        
        # Log summary
        summary_parts = []
        if write_count > 0:
            summary_parts.append(f"{write_count} written")
        if skipped_count > 0:
            summary_parts.append(f"{skipped_count} skipped (read-only)")
        if error_count > 0:
            summary_parts.append(f"{error_count} errors")
        
        summary = ", ".join(summary_parts) if summary_parts else "no operations performed"
        return f"Write operation complete: {summary}"
    
    def on_write_complete(self, result: str):
        """Handle write completion"""
        self.write_button.setText("Write Values")
        self.write_button.setEnabled(True)
        self.log(result)
        
        # Update LED visualization
        self.brain_map.update_led_selection(self.led_selection_value)
    
    def on_write_error(self, error: str):
        """Handle write error"""
        self.log(f"Error writing values: {error}")
        self.write_button.setText("Write Values")
        self.write_button.setEnabled(True)
    
    def send_trigger(self):
        """Send trigger signal to the device"""
        if not self.client or not self.client.is_connected:
            QMessageBox.warning(self, "Not Connected", "Please connect to a device first!")
            return
        
        # Stop any existing worker
        if self.current_worker and self.current_worker.isRunning():
            self.current_worker.terminate()
            self.current_worker.wait()
            self.current_worker = None
        
        self.current_worker = AsyncWorker(self.do_send_trigger())
        self.current_worker.finished.connect(self.on_trigger_complete)
        self.current_worker.error.connect(self.on_trigger_error)
        self.current_worker.start()

        self.log("Sending opto trigger...")
        self.trigger_button.setText("Triggering...")
        self.trigger_button.setEnabled(False)
    
    async def do_send_trigger(self):
        """Perform the actual trigger operation"""
        trigger_uuid = "56781609-5678-1234-1234-5678abcdeff0"  # Trigger characteristic UUID
        
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
            raise Exception("Trigger characteristic not found!")
        
        # Check if it's writable
        if "write" not in char_obj.properties and "write-without-response" not in char_obj.properties:
            raise Exception("Trigger characteristic is not writable!")
        
        # Encode "True" as boolean value and write
        encoded_value = encode_value(trigger_uuid, "True")
        await self.client.write_gatt_char(char_obj.uuid, encoded_value)
        
        # Update the GATT table
        for i in range(self.gatt_tree.topLevelItemCount()):
            item = self.gatt_tree.topLevelItem(i)
            item_id = item.data(0, Qt.UserRole)
            if item_id is not None:
                char_uuid = self.char_uuid_map.get(item_id)
                if char_uuid == trigger_uuid:
                    item.setText(2, "True")  # Update Current Value
                    item.setText(3, "True")  # Update Write Value
                    break
        
        return "Sent an opto trigger!"
    
    def update_led_button_states(self):
        """Update the visual state of LED buttons based on current values"""
        # Update SHAM LED button
        if self.sham_led_state:
            self.sham_led_button.setStyleSheet("background-color: #87CEEB; font-weight: bold;")  # Light blue
        else:
            self.sham_led_button.setStyleSheet("background-color: #888888; font-weight: bold;")  # Grey
        
        # Update STATUS LED button
        if self.status_led_state:
            self.status_led_button.setStyleSheet("background-color: #FFB6C1; font-weight: bold;")  # Light red
        else:
            self.status_led_button.setStyleSheet("background-color: #888888; font-weight: bold;")  # Grey

    def read_battery_voltage(self):
        """Read the battery voltage characteristic and log the value"""
        if not self.client or not self.client.is_connected:
            # Don't show warning popup for auto-reads, just log silently
            self.log("Battery auto-read skipped: not connected")
            return

        # Battery Voltage UUID
        battery_voltage_uuid = "56781506-5678-1234-1234-5678abcdeff0"
        self.log("Reading battery voltage...")
        self.battery_voltage_button.setText("Reading...")
        self.battery_voltage_button.setEnabled(False)

        async def do_read():
            try:
                # Double-check connection before attempting read
                if not self.client or not self.client.is_connected:
                    raise Exception("Device disconnected during read attempt")
                    
                val = await self.client.read_gatt_char(battery_voltage_uuid)
                voltage = decode_value(battery_voltage_uuid, val)
                voltage = int(voltage)  # voltage in mV
                self.battery_voltage_read.emit(voltage)

            except Exception as e:
                # Stop timer on any error to prevent repeated failures
                if hasattr(self, 'battery_timer') and self.battery_timer.isActive():
                    self.battery_timer.stop()
                    self.log("Battery auto-read stopped due to error")
                self.log(f"Error reading battery voltage: {e}")
            finally:
                self.battery_voltage_button.setText("Read Battery Voltage")
                self.battery_voltage_button.setEnabled(True)

        self.current_worker = AsyncWorker(do_read())
        self.current_worker.finished.connect(lambda _: None)
        self.current_worker.error.connect(lambda error: self.log(f"Error: {error}"))
        self.current_worker.start()


    def update_battery_voltage_bar(self, voltage):
        self.battery_voltage_bar.setValue(voltage)
        self.battery_voltage_bar.setFormat("%.2f V" % (voltage / 1000.0))
        self.current_battery_voltage = voltage/1000
        self.log(f"Battery Voltage: {voltage} mV")

    def toggle_imu_enable(self):
        """Toggle IMU Enable state"""
        if not self.client or not self.client.is_connected:
            QMessageBox.warning(self, "Not Connected", "Please connect to a device first!")
            return

        # Toggle state (store in self.imu_enable_state)
        if not hasattr(self, "imu_enable_state"):
            self.imu_enable_state = False
        self.imu_enable_state = not self.imu_enable_state

        # Update button appearance
        if self.imu_enable_state:
            self.imu_enable_button.setStyleSheet("background-color: #90EE90; font-weight: bold;")  # Light green
            # --- Start IMU logging ---
            try:
                import os
                # Ensure data directory exists
                os.makedirs("data", exist_ok=True)
                # Read values for file naming
                animal_uuid = "56781502-5678-1234-1234-5678abcdeff0"
                device_id_uuid = "56781500-5678-1234-1234-5678abcdeff0"
                animal_val = self.read_gatt_value_sync(animal_uuid)
                device_id_val = self.read_gatt_value_sync(device_id_uuid)
                now_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"data/{animal_val}_{device_id_val}_{now_str}.csv"
                self.imu_csv_file = open(filename, "w", newline="")
                self.imu_csv_writer = csv.writer(self.imu_csv_file)
                # Write header
                self.imu_csv_writer.writerow([
                    "sample", 
                    "acc_x", "acc_y", "acc_z", 
                    "gyro_x", "gyro_y", "gyro_z",
                    "mag_x", "mag_y", "mag_z", "sync",
                    "roll", "pitch", "yaw", "uncertainty", "bat_v"
                ])
                self.log(f"IMU logging started: {filename}")
            except Exception as e:
                self.log(f"Error starting IMU logging: {e}")
                self.imu_enable_state = False
                self.imu_enable_button.setStyleSheet("background-color: #888888; font-weight: bold;")
        else:
            self.imu_enable_button.setStyleSheet("background-color: #888888; font-weight: bold;")  # Grey
            # --- Stop IMU logging ---
            try:
                if hasattr(self, "imu_csv_file") and self.imu_csv_file:
                    self.imu_csv_file.close()
                    self.log("IMU logging stopped and file closed.")
                    self.imu_csv_file = None
                    self.imu_csv_writer = None
            except Exception as e:
                self.log(f"Error closing IMU log file: {e}")

        # Write to IMU Enable characteristic
        imu_enable_uuid = "56781700-5678-1234-1234-5678abcdeff0"
        new_value = "True" if self.imu_enable_state else "False"
        self.write_single_characteristic(imu_enable_uuid, new_value, "IMU ENABLE")

    def read_gatt_value_sync(self, uuid):
        """Synchronously read a GATT value (for file naming) using BLEManager's event loop"""
        future = self.ble_manager.run_async(self.client.read_gatt_char(uuid))
        val = future.result(timeout=5)  # Wait up to 5 seconds
        return decode_value(uuid, val)
    
    def toggle_sham_led(self):
        """Toggle SHAM LED state"""
        if not self.client or not self.client.is_connected:
            QMessageBox.warning(self, "Not Connected", "Please connect to a device first!")
            return
        
        # Toggle state
        self.sham_led_state = not self.sham_led_state
        
        # Update GATT table
        sham_led_uuid = "56781508-5678-1234-1234-5678abcdeff0"
        new_value = "True" if self.sham_led_state else "False"
        
        for i in range(self.gatt_tree.topLevelItemCount()):
            item = self.gatt_tree.topLevelItem(i)
            item_id = item.data(0, Qt.UserRole)
            if item_id is not None:
                char_uuid = self.char_uuid_map.get(item_id)
                if char_uuid == sham_led_uuid:
                    item.setText(3, new_value)  # Update Write Value
                    break
        
        # Update button appearance
        self.update_led_button_states()
        
        # Write the value immediately
        self.write_single_characteristic(sham_led_uuid, new_value, "SHAM LED")

    def toggle_status_led(self):
        """Toggle STATUS LED state"""
        if not self.client or not self.client.is_connected:
            QMessageBox.warning(self, "Not Connected", "Please connect to a device first!")
            return
        
        # Toggle state
        self.status_led_state = not self.status_led_state
        
        # Update GATT table
        status_led_uuid = "56781507-5678-1234-1234-5678abcdeff0"
        new_value = "True" if self.status_led_state else "False"
        
        for i in range(self.gatt_tree.topLevelItemCount()):
            item = self.gatt_tree.topLevelItem(i)
            item_id = item.data(0, Qt.UserRole)
            if item_id is not None:
                char_uuid = self.char_uuid_map.get(item_id)
                if char_uuid == status_led_uuid:
                    item.setText(3, new_value)  # Update Write Value
                    break
        
        # Update button appearance
        self.update_led_button_states()
        
        # Write the value immediately
        self.write_single_characteristic(status_led_uuid, new_value, "STATUS LED")

    def write_single_characteristic(self, char_uuid: str, value: str, char_name: str):
        """Write a single characteristic value"""
        if self.current_worker and self.current_worker.isRunning():
            self.current_worker.terminate()
            self.current_worker.wait()
            self.current_worker = None
        
        self.log(f"Writing {char_name}: {value}")
        
        self.current_worker = AsyncWorker(self.do_write_single(char_uuid, value, char_name))
        self.current_worker.finished.connect(lambda result: self.log(result))
        self.current_worker.error.connect(lambda error: self.log(f"Error writing {char_name}: {error}"))
        self.current_worker.start()

    async def do_write_single(self, char_uuid: str, value: str, char_name: str):
        """Perform single characteristic write operation"""
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
            raise Exception(f"Characteristic {char_name} not found!")
        
        # Check if it's writable
        if "write" not in char_obj.properties and "write-without-response" not in char_obj.properties:
            raise Exception(f"Characteristic {char_name} is not writable!")
        
        # Encode and write the value
        encoded_value = encode_value(char_uuid, value)
        await self.client.write_gatt_char(char_obj.uuid, encoded_value)

        # If IMU Sample Rate was changed, update Madgwick filter frequency
        if char_uuid == "56781701-5678-1234-1234-5678abcdeff0":
            try:
                # Option 1: Use the value just written
                imu_sample_rate = int(value)
                if imu_sample_rate > 0:
                    self.fusion_filter = EKF(
                        frequency=imu_sample_rate,  # Base sample rate
                        var_acc=self.var_acc,   # Lower value = trust accelerometer more for tilt
                        var_gyro=self.var_gyro,   # Higher value = less gyro drift
                        var_mag=self.var_mag,    # Lower value = trust magnetometer more for heading
                        declination=self.var_declination # Set local magnetic declination here
                    )
                    self.log(f"EKF filter frequency updated to {imu_sample_rate} Hz")
            except Exception as e:
                self.log(f"Failed to update Madgwick frequency: {e}")

        return f"Successfully wrote {char_name}: {value}"
        
    def on_trigger_complete(self, result: str):
        """Handle trigger completion"""
        self.trigger_button.setText("TRIGGER")
        self.trigger_button.setEnabled(True)
        self.log(result)

    def on_trigger_error(self, error: str):
        """Handle trigger error"""
        self.log(f"Error sending trigger: {error}")
        self.trigger_button.setText("TRIGGER")
        self.trigger_button.setEnabled(True)

    async def cleanup_notifications(self):
        """Clean up BLE notifications"""
        try:
            if self.client and self.client.is_connected:
                device_log_uuid = "56781509-5678-1234-1234-5678abcdeff0"
                await self.client.stop_notify(device_log_uuid)
        except Exception as e:
            self.log(f"Error cleaning up notifications: {e}")



    def handle_zmq_message(self, message: str):
        """Handle ZMQ messages from the listener thread"""
        self.log(f"ZMQ received: {message}")
        
        if "OptoGrid.trigger" in message:
            self.send_trigger()
        elif "OptoGrid.sync = " in message:
            try:
                sync_value = int(message.split('=')[1].strip())
                if hasattr(self, "imu_data_buffer") and self.imu_data_buffer:
                    self.imu_data_buffer[-1][-1] = sync_value
            except Exception as e:
                self.log(f"Error writing sync: {e}")
        elif "OptoGrid.program" in message:
            # Handle program data in next message
            pass

    def closeEvent(self, event):
        """Handle application close"""
        try:
            print("Starting cleanup...")
            
            # Stop the battery timer
            if hasattr(self, 'battery_timer'):
                self.battery_timer.stop()

            # First stop the ZMQ listener
            if hasattr(self, 'zmq_listener'):
                print("Stopping ZMQ listener...")
                self.zmq_listener.stop()
                self.zmq_listener.wait(1000)  # Wait 1 second
                
                # Force quit if still running
                if self.zmq_listener.isRunning():
                    print("Force terminating ZMQ listener...")
                    self.zmq_listener.terminate()
                    self.zmq_listener.wait()
                
                self.zmq_listener = None

            # Wait a moment for socket cleanup
            QThread.msleep(100)
            
            # Now terminate ZMQ context
            if hasattr(self, 'zmq_context'):
                print("Terminating ZMQ context...")
                try:
                    self.zmq_context.term()
                except Exception as e:
                    print(f"Error terminating ZMQ context: {e}")
                self.zmq_context = None

            # Clean up remaining resources
            if hasattr(self, "imu_csv_file") and self.imu_csv_file:
                print("Closing IMU log file...")
                self.imu_csv_file.close()
                self.imu_csv_file = None

            # Clean up all workers at last
            if self.current_worker and self.current_worker.isRunning():
                self.current_worker.quit()
                self.current_worker.wait()
                self.current_worker = None

            if self.client and self.client.is_connected:
                print("Disconnecting BLE...")
                try:
                    future = self.ble_manager.run_async(self.client.disconnect())
                    future.result(timeout=1)
                except Exception as e:
                    print(f"Error disconnecting BLE: {e}")
                self.client = None

            # Cleanup GPIO
            if GPIO_AVAILABLE:
                GPIO.cleanup()
                self.log("GPIO resources cleaned up.")

        except Exception as e:
            print(f"Error during cleanup: {e}")
        finally:
            print("Closing application...")
            event.accept()

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
    
def main():
    """Main application entry point"""
    app = QApplication(sys.argv)
    
    # Set application properties
    app.setApplicationName("OptoGrid BLE Browser")
    app.setApplicationVersion("2.0")
    
    # Create and show main window
    window = OptoGridBLEClient()
    window.show()
    
    # Bring window to front
    window.raise_()
    window.activateWindow()
    
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()