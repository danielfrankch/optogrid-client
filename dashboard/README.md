# OptoGrid Web Dashboard

A web-based interface for the OptoGrid BLE device control system, built with HTML, CSS, and JavaScript.

## Features

- **Device Management**: Scan, connect, and manage OptoGrid BLE devices
- **Brain Map Visualization**: Interactive LED selection on brain map
- **IMU Data Display**: Real-time 3D orientation and sensor data plots
- **GATT Table**: View and edit BLE characteristics
- **Real-time Communication**: ZMQ integration for backend communication
- **Responsive Design**: Works on desktop and mobile browsers

## Quick Start

### Prerequisites
- Node.js (version 12 or higher)
- A modern web browser (Chrome, Firefox, Safari, Edge)

### Running the Dashboard

1. **Start the dashboard server:**
   ```bash
   cd dashboard
    npm init -y
    npm install ws zeromq
   ./start.sh
   ```
   
   Or manually:
   ```bash
   cd dashboard
   node server.js
   ```

2. **Access the dashboard:**
   - Local: http://localhost:3000
   - Network: http://[your-ip]:3000

3. **The dashboard will be available on your local network**, allowing access from any device with a web browser.

## Architecture

### Frontend Components
- **`index.html`**: Main application structure
- **`styles.css`**: Complete styling and responsive design
- **`js/app.js`**: Main application logic and state management
- **`js/brainMap.js`**: Brain map visualization and LED interaction
- **`js/imuVisualization.js`**: IMU 3D display and data plotting
- **`js/zmqClient.js`**: WebSocket client for backend communication

### Backend Integration
The dashboard communicates with the `headless_bluetooth_backend` via ZMQ messages over WebSocket. The backend handles:
- BLE device scanning and connection
- Characteristic reading/writing
- IMU data streaming
- Device control commands

## GUI Components

### Main Interface
- **Device Controls**: Scan, device selection, connect/disconnect
- **Debug Mode**: Toggle for verbose logging
- **Connection Status**: Visual feedback for device connection state

### Brain Map Section
- **Interactive LED Grid**: Click LEDs to toggle selection (64 LEDs total)
- **LED State Indicators**: Visual feedback for selected LEDs
- **LED Health Check**: Red X overlay for broken LEDs
- **Brain Map Background**: Placeholder for brain anatomy image

### Control Buttons
- **SHAM LED**: Toggle sham stimulation LED
- **IMU ENABLE**: Enable/disable IMU data streaming
- **STATUS LED**: Toggle status indicator LED
- **TRIGGER**: Send stimulation trigger command

### Data Monitoring
- **Battery Voltage**: Real-time battery level display
- **uLED Check**: Scan for broken LEDs
- **Last Stim**: Read last stimulation timestamp

### GATT Table
- **Characteristic Browser**: View all BLE services and characteristics
- **Live Values**: Real-time characteristic value updates
- **Write Interface**: Double-click writable cells to modify values
- **Unit Display**: Shows units for each characteristic

### IMU Visualization
- **3D Orientation**: Real-time 3D cube showing device orientation
- **Data Plots**: Scrolling plots for accelerometer and gyroscope data
- **Roll/Pitch/Yaw**: Numeric orientation display

## Customization

### Styling
Edit `styles.css` to customize:
- Color scheme
- Font sizes and families
- Layout proportions
- Component styling

### Brain Map
To add a custom brain map image:
1. Place `brainmap.png` in the dashboard directory
2. The image will automatically load and scale to fit the display

### Network Configuration
The server automatically binds to all network interfaces (`0.0.0.0`) and displays both local and network URLs for easy access from any device.

## Development

### File Structure
```
dashboard/
├── index.html              # Main HTML structure
├── styles.css              # Complete CSS styling
├── package.json            # Node.js configuration
├── server.js               # HTTP server with CORS
├── start.sh                # Startup script
└── js/
    ├── app.js              # Main application logic
    ├── brainMap.js         # Brain map visualization
    ├── imuVisualization.js # IMU display components
    └── zmqClient.js        # Backend communication
```

### Browser Compatibility
- Chrome 60+
- Firefox 55+
- Safari 12+
- Edge 79+

### Mobile Support
The dashboard is responsive and works on:
- iOS Safari (iPhone/iPad)
- Android Chrome
- Mobile Firefox

## Integration with Backend

The dashboard expects ZMQ messages from `headless_bluetooth_backend` in the following format:

```javascript
// Device scan results
{
  "type": "scan_complete",
  "devices": [
    {"name": "OptoGrid-001", "address": "00:11:22:33:44:55"}
  ]
}

// Connection status
{
  "type": "connected",
  "name": "OptoGrid-001",
  "address": "00:11:22:33:44:55"
}

// IMU updates
{
  "type": "imu_update",
  "roll": 15.2,
  "pitch": -5.7,
  "yaw": 32.1,
  "imu_values": [0.1, 0.2, 9.8, 5.0, 3.0, 2.0]
}

// Battery updates
{
  "type": "battery_update",
  "voltage": 4100
}
```

## Troubleshooting

### Dashboard Not Loading
1. Check Node.js installation: `node --version`
2. Verify port 8080 is available
3. Check firewall settings for network access

### Device Connection Issues
1. Ensure `headless_bluetooth_backend` is running
2. Check ZMQ WebSocket proxy is available
3. Verify device is in pairing mode

### Performance Issues
1. Close other browser tabs using WebGL/Canvas
2. Reduce IMU update rate if needed
3. Clear browser cache and reload

## Future Enhancements

- [ ] WebRTC direct device communication
- [ ] Data export functionality
- [ ] Custom brain map uploads
- [ ] Multi-device support
- [ ] Session recording/playback
- [ ] Advanced data analysis tools

## License

This project is part of the OptoGrid system. See main repository for license details.