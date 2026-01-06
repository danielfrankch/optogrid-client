/**
 * Main application logic for OptoGrid Dashboard
 */
class OptoGridApp {
    constructor() {
        this.deviceList = [];
        this.selectedDevice = null;
        this.charUuidMap = {};
        this.charWritableMap = {};
        this.ledSelectionValue = 0;
        this.itemCounter = 0;
        this.currentBatteryVoltage = null;
        this.imuEnableState = false;
        this.shamLedState = false;
        this.statusLedState = false;
        this.connectionStatus = 'disconnected';
        
        this.initializeElements();
        this.setupEventListeners();
        this.initializeLog();
        
        // Initialize brain map and IMU visualization
        this.brainMap = new BrainMapVisualization('brain-map-canvas');
        this.imuVisualization = new IMUVisualization('imu-3d-canvas', 'imu-plot-canvas');
        
        // Initialize ZMQ client (will be used later for backend communication)
        this.zmqClient = new ZMQClient();
        this.zmqClient.onMessage = this.handleZMQMessage.bind(this);
    }
    
    initializeElements() {
        // Get references to all UI elements
        this.elements = {
            scanButton: document.getElementById('scan-button'),
            devicesCombo: document.getElementById('devices-combo'),
            connectButton: document.getElementById('connect-button'),
            debugButton: document.getElementById('debug-button'),
            readButton: document.getElementById('read-button'),
            writeButton: document.getElementById('write-button'),
            triggerButton: document.getElementById('trigger-button'),
            logText: document.getElementById('log-text'),
            shamLedButton: document.getElementById('sham-led-button'),
            imuEnableButton: document.getElementById('imu-enable-button'),
            statusLedButton: document.getElementById('status-led-button'),
            batteryVoltageButton: document.getElementById('battery-voltage-button'),
            readULEDCheckButton: document.getElementById('read-uLEDCheck-button'),
            readLastStimButton: document.getElementById('read-lastStim-button'),
            batteryFill: document.getElementById('battery-fill'),
            batteryText: document.getElementById('battery-text'),
            gattTableBody: document.getElementById('gatt-table-body')
        };
    }
    
    setupEventListeners() {
        // Device control buttons
        this.elements.scanButton.addEventListener('click', () => this.startScan());
        this.elements.connectButton.addEventListener('click', () => this.connectToDevice());
        this.elements.debugButton.addEventListener('change', (e) => this.toggleDebugMode(e.target.checked));
        
        // Control buttons
        this.elements.readButton.addEventListener('click', () => this.readAllValues());
        this.elements.writeButton.addEventListener('click', () => this.writeValues());
        this.elements.triggerButton.addEventListener('click', () => this.sendTrigger());
        
        // LED state buttons
        this.elements.shamLedButton.addEventListener('click', () => this.toggleShamLed());
        this.elements.imuEnableButton.addEventListener('click', () => this.toggleImuEnable());
        this.elements.statusLedButton.addEventListener('click', () => this.toggleStatusLed());
        
        // Additional control buttons
        this.elements.batteryVoltageButton.addEventListener('click', () => this.readBatteryVoltage());
        this.elements.readULEDCheckButton.addEventListener('click', () => this.readULEDCheck());
        this.elements.readLastStimButton.addEventListener('click', () => this.readLastStim());
        
        // GATT table interactions
        this.elements.gattTableBody.addEventListener('dblclick', (e) => this.editCharacteristicValue(e));
    }
    
    initializeLog() {
        this.log('OptoGrid GUI initialized');
        this.log('Web interface ready');
        this.log('Waiting for backend connection...');
    }
    
    log(message, maxLines = 100) {
        const timestamp = new Date().toTimeString().split(' ')[0];
        const formattedMessage = `[${timestamp}] ${message}`;
        
        const logText = this.elements.logText;
        logText.value += formattedMessage + '\n';
        
        // Limit log size
        const lines = logText.value.split('\n');
        if (lines.length > maxLines) {
            logText.value = lines.slice(-maxLines).join('\n');
        }
        
        // Auto-scroll to bottom
        logText.scrollTop = logText.scrollHeight;
    }
    
    // Device control methods
    startScan() {
        this.log('Scanning for devices...');
        this.elements.scanButton.disabled = true;
        this.elements.devicesCombo.innerHTML = '<option value="">Scanning...</option>';
        
        // TODO: Send scan command to backend via ZMQ
        // For now, simulate scan completion
        setTimeout(() => {
            this.onScanComplete([
                { name: 'OptoGrid-001', address: '00:11:22:33:44:55' },
                { name: 'OptoGrid-002', address: '00:11:22:33:44:56' }
            ]);
        }, 2000);
    }
    
    onScanComplete(devices) {
        this.elements.scanButton.disabled = false;
        this.deviceList = devices;
        
        const combo = this.elements.devicesCombo;
        combo.innerHTML = '<option value="">Select device...</option>';
        
        if (devices.length > 0) {
            devices.forEach((device, index) => {
                const option = document.createElement('option');
                option.value = index;
                option.textContent = `${device.name} (${device.address})`;
                combo.appendChild(option);
            });
            this.elements.connectButton.disabled = false;
            this.log(`Found ${devices.length} OptoGrid devices`);
        } else {
            this.log('No OptoGrid devices found');
            this.elements.connectButton.disabled = true;
        }
    }
    
    connectToDevice() {
        const selectedIndex = this.elements.devicesCombo.value;
        if (selectedIndex === '') return;
        
        this.selectedDevice = this.deviceList[selectedIndex];
        this.log(`Connecting to ${this.selectedDevice.name}...`);
        this.elements.connectButton.disabled = true;
        this.elements.scanButton.disabled = true;
        this.connectionStatus = 'connecting';
        
        // TODO: Send connect command to backend via ZMQ
        // For now, simulate successful connection
        setTimeout(() => {
            this.onConnected(this.selectedDevice.name, this.selectedDevice.address);
        }, 1500);
    }
    
    onConnected(name, address) {
        this.log(`Connected to ${name}`);
        this.connectionStatus = 'connected';
        this.elements.connectButton.disabled = false;
        this.elements.scanButton.disabled = false;
        
        // Enable control buttons
        this.setControlButtonsEnabled(true);
        
        // Populate GATT table with sample data
        this.populateGattTable();
        
        // Update battery display
        this.updateBatteryDisplay(4100);
    }
    
    onConnectionFailed(error) {
        this.log(`Connection failed: ${error}`);
        this.connectionStatus = 'disconnected';
        this.elements.connectButton.disabled = false;
        this.elements.scanButton.disabled = false;
    }
    
    onDisconnected() {
        this.log('Device disconnected');
        this.connectionStatus = 'disconnected';
        this.elements.connectButton.disabled = false;
        this.elements.scanButton.disabled = false;
        
        // Disable control buttons
        this.setControlButtonsEnabled(false);
    }
    
    setControlButtonsEnabled(enabled) {
        this.elements.readButton.disabled = !enabled;
        this.elements.writeButton.disabled = !enabled;
        this.elements.triggerButton.disabled = !enabled;
        this.elements.shamLedButton.disabled = !enabled;
        this.elements.imuEnableButton.disabled = !enabled;
        this.elements.statusLedButton.disabled = !enabled;
        this.elements.batteryVoltageButton.disabled = !enabled;
        this.elements.readULEDCheckButton.disabled = !enabled;
        this.elements.readLastStimButton.disabled = !enabled;
    }
    
    // Control methods
    toggleDebugMode(enabled) {
        this.log(`Debug mode: ${enabled ? 'enabled' : 'disabled'}`);
    }
    
    readAllValues() {
        this.log('Reading all values...');
        this.elements.readButton.disabled = true;
        
        // TODO: Send read all command to backend
        setTimeout(() => {
            this.elements.readButton.disabled = false;
            this.log('Read all complete');
        }, 1000);
    }
    
    writeValues() {
        this.log('Writing modified values...');
        this.elements.writeButton.disabled = true;
        
        // TODO: Send write values command to backend
        setTimeout(() => {
            this.elements.writeButton.disabled = false;
            this.log('Wrote 5 values');
        }, 1000);
    }
    
    sendTrigger() {
        this.log('Sending trigger...');
        this.elements.triggerButton.disabled = true;
        
        // TODO: Send trigger command to backend
        setTimeout(() => {
            this.elements.triggerButton.disabled = false;
            this.log('Trigger sent successfully');
        }, 500);
    }
    
    toggleShamLed() {
        this.shamLedState = !this.shamLedState;
        this.updateLedButtonState(this.elements.shamLedButton, this.shamLedState);
        this.log(`SHAM LED: ${this.shamLedState ? 'True' : 'False'}`);
    }
    
    toggleImuEnable() {
        this.imuEnableState = !this.imuEnableState;
        this.updateLedButtonState(this.elements.imuEnableButton, this.imuEnableState);
        this.log(`IMU Enable: ${this.imuEnableState ? 'True' : 'False'}`);
    }
    
    toggleStatusLed() {
        this.statusLedState = !this.statusLedState;
        this.updateLedButtonState(this.elements.statusLedButton, this.statusLedState);
        this.log(`STATUS LED: ${this.statusLedState ? 'True' : 'False'}`);
    }
    
    updateLedButtonState(button, isActive) {
        if (isActive) {
            button.classList.add('active');
        } else {
            button.classList.remove('active');
        }
    }
    
    readBatteryVoltage() {
        this.log('Reading battery voltage...');
        this.elements.batteryVoltageButton.disabled = true;
        
        // TODO: Send battery read command to backend
        setTimeout(() => {
            this.elements.batteryVoltageButton.disabled = false;
            const voltage = 3900 + Math.random() * 300; // Simulate voltage reading
            this.updateBatteryDisplay(Math.round(voltage));
            this.log(`Battery: ${Math.round(voltage)} mV`);
        }, 500);
    }
    
    readULEDCheck() {
        this.log('Reading uLED check...');
        this.elements.readULEDCheckButton.disabled = true;
        
        // TODO: Send uLED check command to backend
        setTimeout(() => {
            this.elements.readULEDCheckButton.disabled = false;
            this.log('uLED Check: 0xFFFFFFFFFFFFFFFF');
        }, 500);
    }
    
    readLastStim() {
        this.log('Reading last stim time...');
        this.elements.readLastStimButton.disabled = true;
        
        // TODO: Send last stim read command to backend
        setTimeout(() => {
            this.elements.readLastStimButton.disabled = false;
            this.log('Last Stim: 1234 ms');
        }, 500);
    }
    
    updateBatteryDisplay(voltage) {
        this.currentBatteryVoltage = voltage;
        const minVoltage = 3500;
        const maxVoltage = 4200;
        const percentage = Math.max(0, Math.min(100, ((voltage - minVoltage) / (maxVoltage - minVoltage)) * 100));
        
        this.elements.batteryFill.style.width = `${percentage}%`;
        this.elements.batteryText.textContent = `${voltage} mV`;
    }
    
    populateGattTable() {
        // Sample GATT data for demonstration
        const sampleGattData = [
            { service: 'Device Information', characteristic: 'Device Name', value: 'OptoGrid-001', writeValue: '', unit: '' },
            { service: '', characteristic: 'Manufacturer', value: 'OptoGrid Inc.', writeValue: '', unit: '' },
            { service: 'OptoGrid Service', characteristic: 'LED Selection', value: '0', writeValue: '0', unit: 'bitmap' },
            { service: '', characteristic: 'Battery Voltage', value: '4100', writeValue: '', unit: 'mV' },
            { service: '', characteristic: 'IMU Enable', value: 'False', writeValue: 'False', unit: 'bool' },
            { service: '', characteristic: 'SHAM LED', value: 'False', writeValue: 'False', unit: 'bool' },
            { service: '', characteristic: 'Status LED', value: 'False', writeValue: 'False', unit: 'bool' }
        ];
        
        this.elements.gattTableBody.innerHTML = '';
        
        sampleGattData.forEach(item => {
            const row = document.createElement('tr');
            
            const serviceCell = document.createElement('td');
            serviceCell.textContent = item.service;
            if (item.service) serviceCell.classList.add('service-cell');
            row.appendChild(serviceCell);
            
            const charCell = document.createElement('td');
            charCell.textContent = item.characteristic;
            row.appendChild(charCell);
            
            const valueCell = document.createElement('td');
            valueCell.textContent = item.value;
            row.appendChild(valueCell);
            
            const writeCell = document.createElement('td');
            writeCell.textContent = item.writeValue;
            if (item.writeValue !== '') writeCell.classList.add('writable-cell');
            row.appendChild(writeCell);
            
            const unitCell = document.createElement('td');
            unitCell.textContent = item.unit;
            row.appendChild(unitCell);
            
            this.elements.gattTableBody.appendChild(row);
        });
        
        this.log('GATT table populated');
    }
    
    editCharacteristicValue(event) {
        const cell = event.target;
        if (!cell.classList.contains('writable-cell')) return;
        
        const currentValue = cell.textContent;
        const newValue = prompt('Enter new value:', currentValue);
        
        if (newValue !== null && newValue !== currentValue) {
            cell.textContent = newValue;
            this.log(`Set write value: ${newValue}`);
        }
    }
    
    // Handle ZMQ messages from backend
    handleZMQMessage(message) {
        try {
            const data = JSON.parse(message);
            
            switch (data.type) {
                case 'scan_complete':
                    this.onScanComplete(data.devices);
                    break;
                case 'connected':
                    this.onConnected(data.name, data.address);
                    break;
                case 'connection_failed':
                    this.onConnectionFailed(data.error);
                    break;
                case 'disconnected':
                    this.onDisconnected();
                    break;
                case 'device_log':
                    this.log(`Device: ${data.message}`);
                    break;
                case 'imu_update':
                    this.imuVisualization.updateIMU(data.roll, data.pitch, data.yaw, data.imu_values);
                    break;
                case 'battery_update':
                    this.updateBatteryDisplay(data.voltage);
                    break;
                case 'led_check':
                    this.brainMap.updateLedCheckOverlay(data.value);
                    break;
                default:
                    console.log('Unknown message type:', data.type);
            }
        } catch (e) {
            console.error('Error parsing ZMQ message:', e);
        }
    }
    
    // LED toggle from brain map
    onLedClicked(bitPosition) {
        this.ledSelectionValue ^= (1 << bitPosition);
        this.brainMap.updateLedSelection(this.ledSelectionValue);
        this.log(`LED ${bitPosition} toggled. Selection: ${this.ledSelectionValue}`);
        
        // TODO: Send LED selection to backend via ZMQ
    }
}

// Initialize the application when the page loads
document.addEventListener('DOMContentLoaded', () => {
    window.optoGridApp = new OptoGridApp();
});