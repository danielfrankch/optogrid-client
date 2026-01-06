#!/usr/bin/env node

/**
 * Simple HTTP server for OptoGrid Dashboard
 * Serves static files and provides WebSocket proxy for ZMQ communication
 */

const http = require('http');
const fs = require('fs');
const path = require('path');
const os = require('os');
const WebSocket = require('ws');
const zmq = require('zeromq');

// Configuration
const HTTP_PORT = 3000;  // Changed from 8080 to avoid conflict
const WS_PORT = 8080;    // WebSocket server for ZMQ bridge
const ZMQ_REQ_PORT = 5555;  // Backend ZMQ REP socket
const ZMQ_PUB_PORT = 5556;  // Backend ZMQ PUB socket
const STATIC_DIR = __dirname;

// MIME types
const mimeTypes = {
    '.html': 'text/html',
    '.css': 'text/css',
    '.js': 'application/javascript',
    '.json': 'application/json',
    '.png': 'image/png',
    '.jpg': 'image/jpeg',
    '.gif': 'image/gif',
    '.svg': 'image/svg+xml',
    '.ico': 'image/x-icon'
};

// Get local IP address
function getLocalIP() {
    const interfaces = os.networkInterfaces();
    for (const name of Object.keys(interfaces)) {
        for (const iface of interfaces[name]) {
            if (iface.family === 'IPv4' && !iface.internal) {
                return iface.address;
            }
        }
    }
    return 'localhost';
}

// ZMQ to WebSocket Bridge
class ZMQWebSocketBridge {
    constructor() {
        this.wsServer = null;
        this.zmqReqSocket = null;
        this.zmqSubSocket = null;
        this.clients = new Set();
        this.pendingRequests = new Map();
    }
    
    async initialize() {
        try {
            // Create ZMQ REQ socket (client to backend's REP)
            this.zmqReqSocket = new zmq.Request();
            await this.zmqReqSocket.connect(`tcp://localhost:${ZMQ_REQ_PORT}`);
            console.log(`Connected ZMQ REQ to tcp://localhost:${ZMQ_REQ_PORT}`);
            
            // Create ZMQ SUB socket (subscribe to backend's PUB)
            this.zmqSubSocket = new zmq.Subscriber();
            await this.zmqSubSocket.connect(`tcp://localhost:${ZMQ_PUB_PORT}`);
            this.zmqSubSocket.subscribe(''); // Subscribe to all messages
            console.log(`Connected ZMQ SUB to tcp://localhost:${ZMQ_PUB_PORT}`);
            
            // Start listening for PUB messages
            this.listenForPubMessages();
            
            // Create WebSocket server
            this.wsServer = new WebSocket.Server({ port: WS_PORT });
            console.log(`WebSocket server listening on port ${WS_PORT}`);
            
            this.wsServer.on('connection', (ws) => {
                console.log('WebSocket client connected');
                this.clients.add(ws);
                
                // Send connection confirmation
                ws.send(JSON.stringify({
                    type: 'connection',
                    status: 'connected',
                    message: 'Connected to OptoGrid ZMQ bridge'
                }));
                
                ws.on('message', async (data) => {
                    await this.handleWebSocketMessage(ws, data);
                });
                
                ws.on('close', () => {
                    console.log('WebSocket client disconnected');
                    this.clients.delete(ws);
                });
                
                ws.on('error', (error) => {
                    console.error('WebSocket error:', error);
                    this.clients.delete(ws);
                });
            });
            
        } catch (error) {
            console.error('Failed to initialize ZMQ bridge:', error);
        }
    }
    
    async handleWebSocketMessage(ws, data) {
        try {
            const message = JSON.parse(data.toString());
            const { requestId, command } = message;
            
            if (!command) {
                this.sendError(ws, 'Missing command', requestId);
                return;
            }
            
            console.log(`Forwarding command to ZMQ: ${command}`);
            
            // Send to ZMQ REQ socket
            await this.zmqReqSocket.send(command);
            
            // Wait for ZMQ response
            const [zmqResponse] = await this.zmqReqSocket.receive();
            const responseText = zmqResponse.toString();
            
            console.log(`Received from ZMQ: ${responseText}`);
            
            // Send response back to WebSocket client
            const response = {
                requestId: requestId,
                success: true,
                data: responseText,
                timestamp: Date.now()
            };
            
            if (ws.readyState === WebSocket.OPEN) {
                ws.send(JSON.stringify(response));
            }
            
        } catch (error) {
            console.error('Error handling WebSocket message:', error);
            this.sendError(ws, error.message);
        }
    }
    
    async listenForPubMessages() {
        try {
            for await (const [msg] of this.zmqSubSocket) {
                const messageText = msg.toString();
                console.log(`Received PUB message: ${messageText}`);
                
                // Broadcast to all WebSocket clients
                this.broadcastToClients(messageText);
            }
        } catch (error) {
            console.error('Error listening for PUB messages:', error);
            // Restart listening after delay
            setTimeout(() => this.listenForPubMessages(), 2000);
        }
    }
    
    broadcastToClients(message) {
        const deadClients = [];
        
        for (const client of this.clients) {
            try {
                if (client.readyState === WebSocket.OPEN) {
                    client.send(message);
                } else {
                    deadClients.push(client);
                }
            } catch (error) {
                console.error('Error broadcasting to client:', error);
                deadClients.push(client);
            }
        }
        
        // Remove dead clients
        deadClients.forEach(client => this.clients.delete(client));
    }
    
    sendError(ws, errorMessage, requestId = null) {
        if (ws.readyState === WebSocket.OPEN) {
            const error = {
                requestId: requestId,
                success: false,
                error: errorMessage,
                timestamp: Date.now()
            };
            ws.send(JSON.stringify(error));
        }
    }
    
    async close() {
        console.log('Closing ZMQ bridge...');
        
        if (this.wsServer) {
            this.wsServer.close();
        }
        
        if (this.zmqReqSocket) {
            this.zmqReqSocket.close();
        }
        
        if (this.zmqSubSocket) {
            this.zmqSubSocket.close();
        }
    }
}

// Serve static files
function serveStaticFile(req, res, filePath) {
    const extname = path.extname(filePath).toLowerCase();
    const contentType = mimeTypes[extname] || 'application/octet-stream';

    fs.readFile(filePath, (err, content) => {
        if (err) {
            if (err.code === 'ENOENT') {
                res.writeHead(404, { 'Content-Type': 'text/plain' });
                res.end('File not found');
            } else {
                res.writeHead(500, { 'Content-Type': 'text/plain' });
                res.end('Server error');
            }
        } else {
            res.writeHead(200, { 'Content-Type': contentType });
            res.end(content, 'utf-8');
        }
    });
}

// Create HTTP server
const server = http.createServer((req, res) => {
    // Enable CORS
    res.setHeader('Access-Control-Allow-Origin', '*');
    res.setHeader('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');
    res.setHeader('Access-Control-Allow-Headers', 'Origin, X-Requested-With, Content-Type, Accept');

    if (req.method === 'OPTIONS') {
        res.writeHead(200);
        res.end();
        return;
    }

    // Parse URL
    let filePath = req.url === '/' ? '/index.html' : req.url;
    
    // Security: prevent directory traversal
    if (filePath.includes('..')) {
        res.writeHead(400, { 'Content-Type': 'text/plain' });
        res.end('Invalid path');
        return;
    }

    // Construct full file path
    const fullPath = path.join(STATIC_DIR, filePath);

    // Check if file exists
    fs.access(fullPath, fs.constants.F_OK, (err) => {
        if (err) {
            res.writeHead(404, { 'Content-Type': 'text/plain' });
            res.end('File not found');
        } else {
            serveStaticFile(req, res, fullPath);
        }
    });
});

// Start servers
const localIP = getLocalIP();
const bridge = new ZMQWebSocketBridge();

server.listen(HTTP_PORT, '0.0.0.0', async () => {
    console.log('\n=== OptoGrid Dashboard Server ===');
    console.log(`HTTP Server:    http://localhost:${HTTP_PORT}`);
    console.log(`Network access: http://${localIP}:${HTTP_PORT}`);
    console.log(`WebSocket:      ws://localhost:${WS_PORT}`);
    console.log('\nInitializing ZMQ bridge...');
    
    try {
        await bridge.initialize();
        console.log('\nServer started successfully!');
        console.log('\nNote: Make sure headless_optogrid_backend_gui_messaging.py is running');
        console.log('      to provide ZMQ REP/PUB endpoints.');
    } catch (error) {
        console.error('Failed to initialize ZMQ bridge:', error);
        console.log('\nHTTP server started, but ZMQ bridge failed.');
        console.log('Make sure the Python backend is running first.');
    }
    
    console.log('\nPress Ctrl+C to stop the server');
});

// Graceful shutdown
process.on('SIGINT', async () => {
    console.log('\nShutting down server...');
    
    // Close ZMQ bridge first
    await bridge.close();
    
    // Then close HTTP server
    server.close(() => {
        console.log('Server stopped.');
        process.exit(0);
    });
});

// Handle uncaught exceptions
process.on('uncaughtException', (err) => {
    console.error('Uncaught Exception:', err);
    process.exit(1);
});

process.on('unhandledRejection', (reason, promise) => {
    console.error('Unhandled Rejection at:', promise, 'reason:', reason);
});

module.exports = server;