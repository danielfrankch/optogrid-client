#!/bin/bash

# OptoGrid Dashboard Startup Script
# This script starts the web-based dashboard server

echo "=== Starting OptoGrid Dashboard ==="
echo ""

# Check if Node.js is installed
if ! command -v node &> /dev/null; then
    echo "Error: Node.js is not installed."
    echo "Please install Node.js from https://nodejs.org/"
    exit 1
fi

# Get the script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Start the server
echo "Starting dashboard server..."
node server.js