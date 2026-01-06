/**
 * ZMQ Client for OptoGrid Dashboard
 * Handles WebSocket connection to ZMQ proxy for backend communication
 */
class ZMQClient {
    constructor() {
        this.socket = null;
        this.isConnected = false;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 10;
        this.reconnectDelay = 1000; // Start with 1 second
        this.maxReconnectDelay = 30000; // Max 30 seconds
        this.onMessage = null;
        this.onConnectionChange = null;
        
        // Auto-connect on initialization
        this.connect();
    }
    
    connect() {
        try {
            // Get local IP address and connect to ZMQ proxy WebSocket
            this.getLocalIP().then(ip => {
                const wsUrl = `ws://${ip}:8080/ws`;
                console.log(`Connecting to ZMQ proxy at ${wsUrl}`);
                
                this.socket = new WebSocket(wsUrl);
                this.setupSocketHandlers();
            }).catch(err => {
                console.error('Failed to get local IP:', err);
                // Fallback to localhost
                const wsUrl = 'ws://localhost:8080/ws';
                console.log(`Connecting to ZMQ proxy at ${wsUrl} (fallback)`);
                
                this.socket = new WebSocket(wsUrl);
                this.setupSocketHandlers();
            });
        } catch (error) {
            console.error('Error creating WebSocket connection:', error);
            this.scheduleReconnect();
        }
    }
    
    setupSocketHandlers() {
        if (!this.socket) return;
        
        this.socket.onopen = (event) => {
            console.log('Connected to ZMQ proxy');
            this.isConnected = true;
            this.reconnectAttempts = 0;
            this.reconnectDelay = 1000;
            
            if (this.onConnectionChange) {
                this.onConnectionChange(true);
            }
            
            // Send initial handshake
            this.send({
                type: 'handshake',
                clientType: 'web_dashboard',
                timestamp: Date.now()
            });
        };
        
        this.socket.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                console.log('Received ZMQ message:', data);
                
                if (this.onMessage) {
                    this.onMessage(data);
                }
            } catch (error) {
                console.error('Error parsing ZMQ message:', error);
            }
        };
        
        this.socket.onclose = (event) => {
            console.log('Disconnected from ZMQ proxy');
            this.isConnected = false;
            
            if (this.onConnectionChange) {
                this.onConnectionChange(false);
            }
            
            // Attempt to reconnect unless explicitly closed
            if (!event.wasClean) {
                this.scheduleReconnect();
            }
        };
        
        this.socket.onerror = (error) => {
            console.error('ZMQ WebSocket error:', error);
        };
    }
    
    scheduleReconnect() {
        if (this.reconnectAttempts >= this.maxReconnectAttempts) {
            console.error('Max reconnection attempts reached. Giving up.');
            return;
        }
        
        this.reconnectAttempts++;
        
        console.log(`Scheduling reconnect attempt ${this.reconnectAttempts} in ${this.reconnectDelay}ms`);
        
        setTimeout(() => {
            this.connect();
        }, this.reconnectDelay);
        
        // Exponential backoff with jitter
        this.reconnectDelay = Math.min(
            this.maxReconnectDelay,
            this.reconnectDelay * 2 + Math.random() * 1000
        );
    }
    
    send(data) {
        if (!this.isConnected || !this.socket) {
            console.warn('Cannot send message: not connected to ZMQ proxy');
            return false;
        }
        
        try {
            this.socket.send(JSON.stringify(data));
            return true;
        } catch (error) {
            console.error('Error sending ZMQ message:', error);
            return false;
        }
    }
    
    disconnect() {
        if (this.socket) {
            this.socket.close();
            this.socket = null;
        }
        this.isConnected = false;
    }
    
    // Commands to send to backend
    sendScanCommand() {
        return this.send({
            type: 'command',
            action: 'scan',
            timestamp: Date.now()
        });
    }
    
    sendConnectCommand(deviceAddress) {
        return this.send({
            type: 'command',
            action: 'connect',
            device_address: deviceAddress,
            timestamp: Date.now()
        });
    }
    
    sendDisconnectCommand() {
        return this.send({
            type: 'command',
            action: 'disconnect',
            timestamp: Date.now()
        });
    }
    
    sendReadAllCommand() {
        return this.send({
            type: 'command',
            action: 'read_all',
            timestamp: Date.now()
        });
    }
    
    sendWriteCommand(characteristics) {
        return this.send({
            type: 'command',
            action: 'write',
            characteristics: characteristics,
            timestamp: Date.now()
        });
    }
    
    sendTriggerCommand() {
        return this.send({
            type: 'command',
            action: 'trigger',
            timestamp: Date.now()
        });
    }
    
    sendLedSelectionCommand(selection) {
        return this.send({
            type: 'command',
            action: 'set_led_selection',
            value: selection,
            timestamp: Date.now()
        });
    }
    
    sendLedStateCommand(ledType, state) {
        return this.send({
            type: 'command',
            action: 'set_led_state',
            led_type: ledType, // 'sham', 'status'
            state: state,
            timestamp: Date.now()
        });
    }
    
    sendImuEnableCommand(enabled) {
        return this.send({
            type: 'command',
            action: 'set_imu_enable',
            enabled: enabled,
            timestamp: Date.now()
        });
    }
    
    sendBatteryReadCommand() {
        return this.send({
            type: 'command',
            action: 'read_battery',
            timestamp: Date.now()
        });
    }
    
    sendULedCheckCommand() {
        return this.send({
            type: 'command',
            action: 'read_uled_check',
            timestamp: Date.now()
        });
    }
    
    sendLastStimCommand() {
        return this.send({
            type: 'command',
            action: 'read_last_stim',
            timestamp: Date.now()
        });
    }
    
    // Utility method to get local IP address
    async getLocalIP() {
        try {
            // Use WebRTC to get local IP
            const pc = new RTCPeerConnection({
                iceServers: []
            });
            
            pc.createDataChannel('');
            pc.createOffer().then(offer => pc.setLocalDescription(offer));
            
            return new Promise((resolve, reject) => {
                pc.onicecandidate = (event) => {
                    if (event.candidate) {
                        const candidate = event.candidate.candidate;
                        const ipMatch = candidate.match(/(\d+\.\d+\.\d+\.\d+)/);
                        if (ipMatch) {
                            pc.close();
                            resolve(ipMatch[1]);
                        }
                    }
                };
                
                // Timeout after 5 seconds
                setTimeout(() => {
                    pc.close();
                    reject(new Error('Timeout getting local IP'));
                }, 5000);
            });
        } catch (error) {
            throw new Error('Failed to get local IP via WebRTC');
        }
    }
}