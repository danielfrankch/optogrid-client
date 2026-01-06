#!/usr/bin/env node

/**
 * Simple HTTP server for OptoGrid Dashboard
 * Serves static files and provides WebSocket proxy for ZMQ communication
 */

const http = require('http');
const fs = require('fs');
const path = require('path');
const os = require('os');

// Configuration
const HTTP_PORT = 8080;
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

// Start server
const localIP = getLocalIP();

server.listen(HTTP_PORT, '0.0.0.0', () => {
    console.log('\\n=== OptoGrid Dashboard Server ===');
    console.log(`Local access:   http://localhost:${HTTP_PORT}`);
    console.log(`Network access: http://${localIP}:${HTTP_PORT}`);
    console.log('\\nServer started successfully!');
    console.log('\\nNote: For full functionality, start the headless_bluetooth_backend');
    console.log('      which will provide ZMQ messages for device communication.');
    console.log('\\nPress Ctrl+C to stop the server');
});

// Graceful shutdown
process.on('SIGINT', () => {
    console.log('\\nShutting down server...');
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