#!/bin/bash
# Setup script for OptoGrid client environment on Windows

echo "=========================================="
echo "  OptoGrid Client Environment Setup"
echo "=========================================="

# Create virtual environment
echo "[1/3] Creating Python virtual environment..."
python -m venv optogrid-client-env

# Check if venv creation was successful
if [ ! -d "optogrid-client-env" ]; then
    echo "ERROR: Failed to create virtual environment!"
    echo "Make sure Python 3 is installed and in your PATH."
    exit 1
fi

# Activate the virtual environment
echo "[2/3] Activating virtual environment..."
source optogrid-client-env/Scripts/activate

# Verify activation
if [ -z "$VIRTUAL_ENV" ]; then
    echo "ERROR: Failed to activate virtual environment!"
    exit 1
fi

# Install dependencies
echo "[3/3] Installing dependencies..."
if [ -f "requirements.txt" ]; then
    pip install -r requirements.txt
    if [ $? -ne 0 ]; then
        echo "ERROR: Failed to install some dependencies."
        echo "Check the error messages above for details."
    else
        echo "Dependencies installed successfully!"
    fi
else
    echo "WARNING: requirements.txt not found in the current directory."
    echo "You'll need to install dependencies manually with pip."
    
    # Install essential packages based on imports in the code
    echo "Installing essential packages based on code imports..."
    pip install bleak pyqt5 numpy matplotlib pyqtgraph pandas ahrs zmq tornado pyopengl pillow
fi

echo ""
echo "=========================================="
echo "  Setup Complete!"
echo "=========================================="
echo "The virtual environment is now active in this terminal session."
echo ""
echo "To activate this environment in future terminal sessions:"
echo "  source optogrid-client-env/Scripts/activate"
echo ""
echo "To run the OptoGrid client:"
echo "  python pyqt_optogrid_python_client.py"
echo "=========================================="