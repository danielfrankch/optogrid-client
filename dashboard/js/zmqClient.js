/**
 * ZMQ Client for OptoGrid Dashboard
 * Handles ZMQ REQ/REP and PUB/SUB communication with backend
 */
class ZMQClient {
    constructor() {
        this.reqSocket = null;
        this.subSocket = null;
        this.isReqConnected = false;
        this.isSubConnected = false;
        this.requestTimeout = 10000; // 10 second timeout for requests
        this.pendingRequests = new Map(); // Track pending requests with timeouts
        this.requestId = 0;
        
        // Callbacks
        this.onMessage = null;
        this.onConnectionChange = null;
        this.onPubMessage = null; // For PUB/SUB messages
        
        // Get local IP and connect
        this.initializeConnections();
    }
    
    async initializeConnections() {
        try {
            // Use localhost for ZMQ connections as specified
            const zmqHost = 'localhost';
            console.log(`Using ZMQ host: ${zmqHost}`);
            
            // Initialize REQ socket for commands
            this.initReqSocket(zmqHost);
            
            // Initialize SUB socket for streaming updates
            this.initSubSocket(zmqHost);
            
        } catch (error) {
            console.error('Failed to initialize ZMQ connections:', error);
            // Fallback to localhost
            this.initReqSocket('localhost');
            this.initSubSocket('localhost');
        }
    }
    
    initReqSocket(host) {
        try {
            // Note: WebSocket cannot directly connect to ZMQ sockets
            // This requires a WebSocket-to-ZMQ bridge/proxy on the backend
            // The backend should provide a WebSocket endpoint that forwards to ZMQ REQ socket
            const reqUrl = `ws://${host}:8080/zmq-req`; // WebSocket proxy for ZMQ REQ
            console.log(`Connecting REQ socket to ${reqUrl}`);
            console.log('Note: Backend must provide WebSocket-to-ZMQ bridge');
            
            this.reqSocket = new WebSocket(reqUrl);
            
            this.reqSocket.onopen = () => {
                console.log('REQ socket connected');
                this.isReqConnected = true;
                this.notifyConnectionChange();
            };
            
            this.reqSocket.onmessage = (event) => {
                this.handleReqResponse(event.data);
            };
            
            this.reqSocket.onclose = () => {
                console.log('REQ socket disconnected');
                this.isReqConnected = false;
                this.notifyConnectionChange();
                this.scheduleReqReconnect(host);
            };
            
            this.reqSocket.onerror = (error) => {
                console.error('REQ socket error:', error);
            };
            
        } catch (error) {
            console.error('Error creating REQ socket:', error);
            this.scheduleReqReconnect(host);
        }
    }
    
    initSubSocket(host) {
        try {
            // WebSocket proxy for ZMQ SUB socket
            const subUrl = `ws://${host}:8080/zmq-sub`; // WebSocket proxy for ZMQ SUB
            console.log(`Connecting SUB socket to ${subUrl}`);
            
            this.subSocket = new WebSocket(subUrl);
            
            this.subSocket.onopen = () => {
                console.log('SUB socket connected');
                this.isSubConnected = true;
                this.notifyConnectionChange();
                
                // Subscribe to all topics (or specific ones)
                this.subscribe('IMU');
                this.subscribe('STATUS');
                this.subscribe('BATTERY');
                this.subscribe('LED');
            };
            
            this.subSocket.onmessage = (event) => {
                this.handleSubMessage(event.data);
            };
            
            this.subSocket.onclose = () => {
                console.log('SUB socket disconnected');
                this.isSubConnected = false;
                this.notifyConnectionChange();
                this.scheduleSubReconnect(host);
            };
            
            this.subSocket.onerror = (error) => {
                console.error('SUB socket error:', error);
            };
            
        } catch (error) {
            console.error('Error creating SUB socket:', error);
            this.scheduleSubReconnect(host);
        }
    }
    
    scheduleReqReconnect(host, delay = 2000) {
        setTimeout(() => {
            if (!this.isReqConnected) {
                console.log('Attempting REQ socket reconnection...');
                this.initReqSocket(host);
            }
        }, delay);
    }
    
    scheduleSubReconnect(host, delay = 2000) {
        setTimeout(() => {
            if (!this.isSubConnected) {
                console.log('Attempting SUB socket reconnection...');
                this.initSubSocket(host);
            }
        }, delay);
    }
    
    notifyConnectionChange() {
        if (this.onConnectionChange) {
            this.onConnectionChange(this.isReqConnected && this.isSubConnected);
        }
    }
    
    // Handle REQ/REP responses
    handleReqResponse(data) {
        try {
            const response = JSON.parse(data);
            const requestId = response.requestId;
            
            if (this.pendingRequests.has(requestId)) {
                const { resolve, timeoutId } = this.pendingRequests.get(requestId);
                clearTimeout(timeoutId);
                this.pendingRequests.delete(requestId);
                resolve(response.data || response.message);
            }
        } catch (error) {
            console.error('Error parsing REQ response:', error);
        }
    }
    
    // Handle PUB/SUB messages
    handleSubMessage(data) {
        try {
            const parts = data.split(' ', 2); // Topic and JSON data
            if (parts.length >= 2) {
                const topic = parts[0];
                const jsonData = parts.slice(1).join(' ');
                const message = JSON.parse(jsonData);
                
                console.log(`Received ${topic} message:`, message);
                
                if (this.onPubMessage) {
                    this.onPubMessage(topic, message);
                }
            }
        } catch (error) {
            console.error('Error parsing SUB message:', error);
        }
    }
    
    // Send REQ with timeout and promise-based response
    sendRequest(command, data = null) {
        return new Promise((resolve, reject) => {
            if (!this.isReqConnected || !this.reqSocket) {
                reject(new Error('REQ socket not connected'));
                return;
            }
            
            const requestId = ++this.requestId;
            const message = {
                requestId: requestId,
                command: command,
                data: data,
                timestamp: Date.now()
            };
            
            // Set timeout
            const timeoutId = setTimeout(() => {
                if (this.pendingRequests.has(requestId)) {
                    this.pendingRequests.delete(requestId);
                    reject(new Error(`Request timeout: ${command}`));
                }
            }, this.requestTimeout);
            
            // Store pending request
            this.pendingRequests.set(requestId, { resolve, reject, timeoutId });
            
            // Send request
            try {
                this.reqSocket.send(JSON.stringify(message));
            } catch (error) {
                clearTimeout(timeoutId);
                this.pendingRequests.delete(requestId);
                reject(error);
            }
        });
    }
    
    // Subscribe to PUB topics
    subscribe(topic) {
        if (this.isSubConnected && this.subSocket) {
            const message = {
                type: 'subscribe',
                topic: topic
            };
            this.subSocket.send(JSON.stringify(message));
            console.log(`Subscribed to topic: ${topic}`);
        }
    }
    
    // Unsubscribe from PUB topics
    unsubscribe(topic) {
        if (this.isSubConnected && this.subSocket) {
            const message = {
                type: 'unsubscribe',
                topic: topic
            };
            this.subSocket.send(JSON.stringify(message));
            console.log(`Unsubscribed from topic: ${topic}`);
        }
    }
    
    disconnect() {
        // Clear all pending requests
        for (const [requestId, { reject, timeoutId }] of this.pendingRequests) {
            clearTimeout(timeoutId);
            reject(new Error('Client disconnecting'));
        }
        this.pendingRequests.clear();
        
        // Close sockets
        if (this.reqSocket) {
            this.reqSocket.close();
            this.reqSocket = null;
        }
        if (this.subSocket) {
            this.subSocket.close();
            this.subSocket = null;
        }
        
        this.isReqConnected = false;
        this.isSubConnected = false;
    }
    
    // Command methods using REQ/REP pattern
    sendScanCommand() {
        return this.sendRequest('optogrid.scan');
    }
    
    sendConnectCommand(deviceName) {
        return this.sendRequest(`optogrid.connect = ${deviceName}`);
    }
    
    sendDisconnectCommand() {
        return this.sendRequest('optogrid.disconnect');
    }
    
    sendReadAllCommand() {
        return this.sendRequest('optogrid.read_all');
    }
    
    sendWriteCommand(uuid, value) {
        return this.sendRequest('optogrid.write', { uuid, value });
    }
    
    sendTriggerCommand() {
        return this.sendRequest('optogrid.trigger');
    }
    
    sendLedSelectionCommand(selection) {
        return this.sendRequest('optogrid.led_selection', { value: selection });
    }
    
    sendLedStateCommand(ledType, state) {
        return this.sendRequest(`optogrid.${ledType}_led`, { state });
    }
    
    sendImuEnableCommand(enabled) {
        return this.sendRequest('optogrid.imu_enable', { enabled });
    }
    
    sendBatteryReadCommand() {
        return this.sendRequest('optogrid.read_battery');
    }
    
    sendULedCheckCommand() {
        return this.sendRequest('optogrid.read_uled_check');
    }
    
    sendLastStimCommand() {
        return this.sendRequest('optogrid.read_last_stim');
    }
    
    // Utility method to get local IP address
    async getLocalIP() {
        try {
            // Use WebRTC to get local IP
            const pc = new RTCPeerConnection({
                iceServers: []
            });
            
            pc.createDataChannel('');
            const offer = await pc.createOffer();
            await pc.setLocalDescription(offer);
            
            return new Promise((resolve, reject) => {
                pc.onicecandidate = (event) => {
                    if (event.candidate) {
                        const candidate = event.candidate.candidate;
                        const ipMatch = candidate.match(/(\d+\.\d+\.\d+\.\d+)/);
                        if (ipMatch && !ipMatch[1].startsWith('127.')) {
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