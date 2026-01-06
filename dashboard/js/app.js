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
        this.log('Scanning for devices containing "O"...');
        this.elements.scanButton.disabled = true;
        this.elements.devicesCombo.innerHTML = '<option value="">Scanning...</option>';
        
        // Send scan command to backend via ZMQ
        this.zmqClient.sendRequest('optogrid.scan')
            .then(response => {
                this.onScanComplete(response);
            })
            .catch(error => {
                this.log(`Scan failed: ${error}`);
                this.elements.scanButton.disabled = false;
                this.elements.devicesCombo.innerHTML = '<option value="">Scan failed</option>';
            });
    }
    
    onScanComplete(response) {
        this.elements.scanButton.disabled = false;
        
        // Parse ZMQ response - backend returns newline-separated device strings
        let devices = [];
        try {
            if (typeof response === 'string') {
                if (response.trim() === 'No Bluetooth devices found') {
                    devices = [];
                } else {
                    // Split by newlines and filter out empty lines
                    const deviceLines = response.split('\n').filter(line => line.trim() !== '');
                    devices = deviceLines.map(line => {
                        // Parse "DeviceName (Address)" format
                        const match = line.match(/^(.+?)\s*\(([^)]+)\)$/);
                        if (match) {
                            return {
                                name: match[1].trim(),
                                address: match[2].trim()
                            };
                        } else {
                            // Fallback for simple device name
                            return {
                                name: line.trim(),
                                address: 'Unknown'
                            };
                        }
                    });
                }
            } else if (Array.isArray(response)) {
                devices = response;
            }
        } catch (error) {
            this.log(`Error parsing scan response: ${error}`);
            devices = [];
        }
        
        this.deviceList = devices;
        
        const combo = this.elements.devicesCombo;
        combo.innerHTML = '<option value="">Select device...</option>';
        
        if (devices.length > 0) {
            devices.forEach((device, index) => {
                const option = document.createElement('option');
                option.value = device.name;
                // Display only device name, not the address
                option.textContent = device.name;
                combo.appendChild(option);
            });
            this.elements.connectButton.disabled = false;
            this.log(`Found ${devices.length} Bluetooth devices`);
        } else {
            this.log('No Bluetooth devices found');
            this.elements.connectButton.disabled = true;
        }
    }
    
    connectToDevice() {
        const selectedDeviceName = this.elements.devicesCombo.value;
        if (selectedDeviceName === '') return;
        
        // Find the selected device from the list
        this.selectedDevice = this.deviceList.find(device => 
            (device.name === selectedDeviceName) || (device === selectedDeviceName)
        ) || { name: selectedDeviceName };
        
        this.log(`Connecting to ${selectedDeviceName}...`);
        this.elements.connectButton.disabled = true;
        this.elements.scanButton.disabled = true;
        this.connectionStatus = 'connecting';
        
        // Send connect command to backend via ZMQ using device UUID/address
        const deviceAddress = this.selectedDevice.address || selectedDeviceName;
        this.zmqClient.sendRequest(`optogrid.connect = ${deviceAddress}`)
            .then(response => {
                if (response.includes('Connected') || response.includes('success')) {
                    this.onConnected(selectedDeviceName, this.selectedDevice.address || 'Unknown');
                } else {
                    this.onConnectionFailed(response);
                }
            })
            .catch(error => {
                this.onConnectionFailed(`Connection error: ${error}`);
            });
    }
    
    onConnected(name, address) {
        this.log(`Connected to ${name}`);
        this.connectionStatus = 'connected';
        this.elements.connectButton.disabled = false;
        this.elements.scanButton.disabled = false;
        
        // Enable control buttons
        this.setControlButtonsEnabled(true);
        
        // Populate GATT table with Opto Control Parameters and update device status
        this.zmqClient.sendRequest('optogrid.gattread')
            .then(response => {
                this.parseAndPopulateGattTable(response);
                this.updateDeviceStatus(response);
            })
            .catch(error => {
                this.log(`GATT read failed: ${error}`);
                // Fallback to empty table or error display
                this.elements.gattTableBody.innerHTML = '<tr><td colspan="4">Failed to read GATT table</td></tr>';
            });
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
        
        // Send GATT read command to refresh the table
        this.zmqClient.sendRequest('optogrid.gattread')
            .then(response => {
                this.parseAndPopulateGattTable(response);
                this.elements.readButton.disabled = false;
                this.log('Read all complete');
            })
            .catch(error => {
                this.log(`GATT read failed: ${error}`);
                this.elements.readButton.disabled = false;
            });
    }
    
    writeValues() {
        this.log('Writing modified values...');
        this.elements.writeButton.disabled = true;
        
        // Collect the full Opto Control Settings from the table
        const optoSettings = this.collectOptoSettings();
        
        if (Object.keys(optoSettings).length === 0) {
            this.log('No modified values to write');
            this.elements.writeButton.disabled = false;
            return;
        }
        
        // Send optogrid.program command first
        this.zmqClient.sendRequest('optogrid.program')
            .then(response => {
                if (response === 'Ready for program data') {
                    // Send the OptoSetting data as JSON
                    return this.zmqClient.sendRequest(JSON.stringify(optoSettings));
                } else {
                    throw new Error(`Unexpected response: ${response}`);
                }
            })
            .then(response => {
                if (response.includes('Opto Programmed')) {
                    this.log(`Successfully wrote ${Object.keys(optoSettings).length} values`);
                    // Refresh the table to show updated values
                    return this.zmqClient.sendRequest('optogrid.gattread');
                } else {
                    throw new Error(`Programming failed: ${response}`);
                }
            })
            .then(response => {
                // Update the table with fresh values
                this.parseAndPopulateGattTable(response);
                this.elements.writeButton.disabled = false;
                this.log('Write complete, table refreshed');
            })
            .catch(error => {
                this.log(`Write failed: ${error}`);
                this.elements.writeButton.disabled = false;
            });
    }
    
    collectOptoSettings() {
        const optoSettings = {};
        const writableCells = this.elements.gattTableBody.querySelectorAll('.writable-cell');
        
        // Mapping from characteristic names to OptoSetting keys
        const charToSettingMap = {
            'Sequence Length': 'sequence_length',
            'LED Selection': 'led_selection', 
            'Duration': 'duration',
            'Period': 'period',
            'Pulse Width': 'pulse_width',
            'Amplitude': 'amplitude',
            'PWM Frequency': 'pwm_frequency',
            'Ramp Up Time': 'ramp_up',
            'Ramp Down Time': 'ramp_down'
        };
        
        writableCells.forEach(cell => {
            const value = cell.textContent.trim();
            if (value === '') return; // Skip empty write values
            
            // Get the characteristic name from the same row
            const row = cell.closest('tr');
            const charCell = row.querySelector('td:first-child');
            const charName = charCell.textContent.trim();
            
            const settingKey = charToSettingMap[charName];
            if (settingKey) {
                // Convert value to appropriate type
                let convertedValue;
                if (settingKey === 'led_selection') {
                    // LED Selection should be uint64
                    convertedValue = parseInt(value);
                } else if (settingKey === 'sequence_length' || settingKey === 'amplitude') {
                    // These are typically integers
                    convertedValue = parseInt(value);
                } else {
                    // Duration, period, pulse_width, pwm_frequency, ramp_up, ramp_down are numbers
                    convertedValue = parseFloat(value);
                }
                
                if (!isNaN(convertedValue)) {
                    optoSettings[settingKey] = convertedValue;
                }
            }
        });
        
        return optoSettings;
    }
    
    sendTrigger() {
        this.log('Sending trigger...');
        this.elements.triggerButton.disabled = true;
        
        // Send trigger command to backend via ZMQ
        this.zmqClient.sendRequest('optogrid.trigger')
            .then(response => {
                if (response.includes('Opto Triggered')) {
                    this.log('Trigger sent successfully');
                } else {
                    this.log(`Trigger response: ${response}`);
                }
                this.elements.triggerButton.disabled = false;
            })
            .catch(error => {
                this.log(`Trigger failed: ${error}`);
                this.elements.triggerButton.disabled = false;
            });
    }
    
    toggleShamLed() {
        this.shamLedState = !this.shamLedState;
        this.updateLedButtonState(this.elements.shamLedButton, this.shamLedState);
        
        // Send toggleShamLED command via ZMQ (assuming similar pattern to toggleStatusLED)
        const state = this.shamLedState ? 1 : 0;
        this.zmqClient.sendRequest(`optogrid.toggleShamLED = ${state}`)
            .then(response => {
                const expectedResponse = this.shamLedState ? 'Sham LED turned on' : 'Sham LED turned off';
                if (response.includes(expectedResponse)) {
                    this.log(`SHAM LED: ${this.shamLedState ? 'True' : 'False'}`);
                } else {
                    this.log(`SHAM LED response: ${response}`);
                }
            })
            .catch(error => {
                this.log(`SHAM LED toggle failed: ${error}`);
                // Revert state on error
                this.shamLedState = !this.shamLedState;
                this.updateLedButtonState(this.elements.shamLedButton, this.shamLedState);
            });
    }
    
    toggleImuEnable() {
        const newState = !this.imuEnableState;
        this.updateLedButtonState(this.elements.imuEnableButton, newState);
        
        // Send appropriate IMU command based on new state
        const command = newState ? 'optogrid.enableIMU' : 'optogrid.disableIMU';
        const expectedResponse = newState ? 'IMU enabled, and logging started' : 'IMU disabled, and logging stopped';
        
        this.zmqClient.sendRequest(command)
            .then(response => {
                if (response.includes(expectedResponse)) {
                    this.imuEnableState = newState;
                    this.log(`IMU Enable: ${this.imuEnableState ? 'True' : 'False'}`);
                } else {
                    this.log(`IMU response: ${response}`);
                    // Revert button state if unexpected response
                    this.updateLedButtonState(this.elements.imuEnableButton, this.imuEnableState);
                }
            })
            .catch(error => {
                this.log(`IMU toggle failed: ${error}`);
                // Revert button state on error
                this.updateLedButtonState(this.elements.imuEnableButton, this.imuEnableState);
            });
    }
    
    toggleStatusLed() {
        this.statusLedState = !this.statusLedState;
        this.updateLedButtonState(this.elements.statusLedButton, this.statusLedState);
        
        // Send toggleStatusLED command via ZMQ (following MATLAB pattern)
        const state = this.statusLedState ? 1 : 0;
        this.zmqClient.sendRequest(`optogrid.toggleStatusLED = ${state}`)
            .then(response => {
                const expectedResponse = this.statusLedState ? 'Status LED turned on' : 'Status LED turned off';
                if (response.includes(expectedResponse)) {
                    this.log(`STATUS LED: ${this.statusLedState ? 'True' : 'False'}`);
                } else {
                    this.log(`STATUS LED response: ${response}`);
                }
            })
            .catch(error => {
                this.log(`STATUS LED toggle failed: ${error}`);
                // Revert state on error
                this.statusLedState = !this.statusLedState;
                this.updateLedButtonState(this.elements.statusLedButton, this.statusLedState);
            });
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
        
        // Send battery read command to backend via ZMQ
        this.zmqClient.sendRequest('optogrid.readbattery')
            .then(response => {
                // Parse battery response: "DeviceName Battery Voltage = XXXX mV"
                const voltageMatch = response.match(/Battery Voltage = (\d+) mV/);
                if (voltageMatch) {
                    const voltage = parseInt(voltageMatch[1]);
                    this.updateBatteryDisplay(voltage);
                    this.log(`Battery: ${voltage} mV`);
                } else {
                    this.log(`Battery response: ${response}`);
                }
                this.elements.batteryVoltageButton.disabled = false;
            })
            .catch(error => {
                this.log(`Battery read failed: ${error}`);
                this.elements.batteryVoltageButton.disabled = false;
            });
    }
    
    readULEDCheck() {
        this.log('Reading uLED check...');
        this.elements.readULEDCheckButton.disabled = true;
        
        // Send uLED check command to backend via ZMQ
        this.zmqClient.sendRequest('optogrid.readuLEDCheck')
            .then(response => {
                // Parse uLED response: "DeviceName uLED Check = VALUE"
                const uledMatch = response.match(/uLED Check = (.+)$/);
                if (uledMatch) {
                    const uledValue = uledMatch[1].trim();
                    this.log(`uLED Check: ${uledValue}`);
                    // Update brain map with uLED check value if needed
                    if (this.brainMap && typeof this.brainMap.updateLedCheckOverlay === 'function') {
                        // Convert hex string to number if needed
                        try {
                            const numericValue = uledValue.startsWith('0x') ? 
                                parseInt(uledValue, 16) : parseInt(uledValue);
                            this.brainMap.updateLedCheckOverlay(numericValue);
                        } catch (e) {
                            // If parsing fails, just log the value
                        }
                    }
                } else {
                    this.log(`uLED response: ${response}`);
                }
                this.elements.readULEDCheckButton.disabled = false;
            })
            .catch(error => {
                this.log(`uLED Check read failed: ${error}`);
                this.elements.readULEDCheckButton.disabled = false;
            });
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
    
    updateDeviceStatus(gattData = null) {
        // Parse device states from provided GATT data or read fresh data if not provided
        if (gattData) {
            this.parseDeviceStates(gattData);
        } else {
            // Read GATT characteristics for LED states and IMU state
            this.zmqClient.sendRequest('optogrid.gattread')
                .then(response => {
                    this.parseDeviceStates(response);
                })
                .catch(error => {
                    this.log(`Failed to read device states: ${error}`);
                });
        }
        
        // Read battery voltage
        this.readBatteryVoltage();
        
        // Read uLED check
        this.readULEDCheck();
    }
    
    parseDeviceStates(csvData) {
        try {
            // Parse CSV response to get LED and IMU states
            const lines = csvData.trim().split('\n');
            const dataLines = lines.slice(1); // Skip header
            
            dataLines.forEach(line => {
                const columns = line.split(',');
                if (columns.length >= 5) {
                    const characteristic = columns[1].trim();
                    const value = columns[3].trim();
                    
                    // Update button states based on device values
                    switch (characteristic) {
                        case 'Status LED state':
                            const statusState = value.toLowerCase() === 'true' || value === '1';
                            if (this.statusLedState !== statusState) {
                                this.statusLedState = statusState;
                                this.updateLedButtonState(this.elements.statusLedButton, this.statusLedState);
                            }
                            break;
                            
                        case 'Sham LED state':
                            const shamState = value.toLowerCase() === 'true' || value === '1';
                            if (this.shamLedState !== shamState) {
                                this.shamLedState = shamState;
                                this.updateLedButtonState(this.elements.shamLedButton, this.shamLedState);
                            }
                            break;
                            
                        case 'IMU Enable':
                            const imuState = value.toLowerCase() === 'true' || value === '1';
                            if (this.imuEnableState !== imuState) {
                                this.imuEnableState = imuState;
                                this.updateLedButtonState(this.elements.imuEnableButton, this.imuEnableState);
                            }
                            break;
                    }
                }
            });
        } catch (error) {
            this.log(`Error parsing device states: ${error}`);
        }
    }
    
    populateGattTable() {
        this.log('Reading GATT table from device...');
        
        // Send GATT read command to backend via ZMQ
        this.zmqClient.sendRequest('optogrid.gattread')
            .then(response => {
                this.parseAndPopulateGattTable(response);
            })
            .catch(error => {
                this.log(`GATT read failed: ${error}`);
                // Fallback to empty table or error display
                this.elements.gattTableBody.innerHTML = '<tr><td colspan="5">Failed to read GATT table</td></tr>';
            });
    }
    
    parseAndPopulateGattTable(csvData) {
        this.elements.gattTableBody.innerHTML = '';
        
        try {
            // Parse CSV response from backend
            const lines = csvData.trim().split('\n');
            
            // Skip header line (Service,Characteristic,UUID,Value,Unit)
            const dataLines = lines.slice(1);
            
            let displayedRows = 0;
            
            dataLines.forEach(line => {
                // Parse CSV line
                const columns = line.split(',');
                if (columns.length >= 5) {
                    const service = columns[0].trim();
                    const characteristic = columns[1].trim();
                    const uuid = columns[2].trim();
                    const value = columns[3].trim();
                    const unit = columns[4].trim();
                    
                    // Skip error entries
                    if (value.startsWith('ERROR:')) {
                        this.log(`GATT read error for ${characteristic}: ${value}`);
                        return;
                    }
                    
                    // Skip device state characteristics from table display
                    if (characteristic === 'Status LED state' || 
                        characteristic === 'Sham LED state' || 
                        characteristic === 'IMU Enable') {
                        return;
                    }
                    
                    const row = document.createElement('tr');
                    
                    // Characteristic cell (no service column displayed)
                    const charCell = document.createElement('td');
                    charCell.textContent = characteristic;
                    row.appendChild(charCell);
                    
                    // Value cell
                    const valueCell = document.createElement('td');
                    valueCell.textContent = value;
                    row.appendChild(valueCell);
                    
                    // Write value cell (empty for now, could be made editable)
                    const writeCell = document.createElement('td');
                    writeCell.textContent = '';
                    // Make certain characteristics writable
                    if (this.isWritableCharacteristic(characteristic)) {
                        writeCell.textContent = value; // Use current value as default
                        writeCell.classList.add('writable-cell');
                        writeCell.setAttribute('data-uuid', uuid); // Store UUID for writing
                    }
                    row.appendChild(writeCell);
                    
                    // Unit cell
                    const unitCell = document.createElement('td');
                    unitCell.textContent = unit;
                    row.appendChild(unitCell);
                    
                    this.elements.gattTableBody.appendChild(row);
                    displayedRows++;
                }
            });
            
            this.log(`GATT table populated with ${displayedRows} characteristics`);
            
        } catch (error) {
            this.log(`Error parsing GATT table: ${error}`);
            this.elements.gattTableBody.innerHTML = '<tr><td colspan="4">Error parsing GATT data</td></tr>';
        }
    }
    
    isWritableCharacteristic(charName) {
        // Define which characteristics are writable
        const writableChars = [
            'LED Selection',
            'Duration', 
            'Period',
            'Pulse Width',
            'Amplitude',
            'PWM Frequency',
            'Ramp Up Time',
            'Ramp Down Time',
            'IMU Enable',
            'Status LED state',
            'Sham LED state',
            'Sequence Length'
        ];
        return writableChars.includes(charName);
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