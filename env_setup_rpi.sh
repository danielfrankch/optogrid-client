#!/bin/bash
# Setup script for OptoGrid client environment on RPi

echo "=========================================="
echo "  OptoGrid Client Environment Setup"
echo "=========================================="

echo "[0/7] Installing pyenv build dependencies..."
sudo apt update && sudo apt install -y \
  make build-essential libssl-dev zlib1g-dev \
  libbz2-dev libreadline-dev libsqlite3-dev wget curl llvm \
  libncursesw5-dev xz-utils tk-dev libxml2-dev \
  libxmlsec1-dev libffi-dev liblzma-dev

echo "[1/7] Installing pyenv..."
curl https://pyenv.run | bash

echo "[2/7] Adding pyenv to ~/.zshrc..."
cat << 'EOF' >> ~/.zshrc

# Pyenv configuration for OptoGrid
export PYENV_ROOT="$HOME/.pyenv"
export PATH="$PYENV_ROOT/bin:$PATH"
eval "$(pyenv init --path)"
eval "$(pyenv init -)"
eval "$(pyenv virtualenv-init -)"
EOF

echo "[3/7] Restarting shell to activate pyenv..."
source ~/.zshrc

echo "[4/7] Installing Python 3.12.4 with pyenv..."
pyenv install 3.12.4

echo "[5/7] Setting local Python version to 3.12.4 in this folder..."
pyenv local 3.12.4

echo "[6/7] Creating Python virtual environment..."
python3 -m venv optogrid-client-env

if [ ! -d "optogrid-client-env" ]; then
    echo "ERROR: Failed to create virtual environment!"
    echo "Make sure Python 3 is installed and in your PATH."
    exit 1
fi

echo "Activating virtual environment..."
source optogrid-client-env/bin/activate

if [ -z "$VIRTUAL_ENV" ]; then
    echo "ERROR: Failed to activate virtual environment!"
    exit 1
fi

echo "Installing dependencies from requirements-headless.txt..."
if [ -f "requirements-headless.txt" ]; then
    pip install --upgrade pip
    pip install -r requirements-headless.txt
    if [ $? -ne 0 ]; then
        echo "ERROR: Failed to install some dependencies."
        echo "Check the error messages above for details."
    else
        echo "Dependencies installed successfully!"
    fi
else
    echo "ERROR: requirements-headless.txt not found in the current directory."
    exit 1
fi

echo "[7/7] Setting up systemd service to run OptoGrid backend on boot..."
SERVICE_FILE="/etc/systemd/system/optogrid.service"

sudo bash -c "cat > $SERVICE_FILE" << EOF
[Unit]
Description=OptoGrid Headless Backend
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=/home/$USER/repos/optogrid-client
ExecStart=/bin/bash -c 'source /home/$USER/repos/optogrid-client/optogrid-client-env/bin/activate && python3 /home/$USER/repos/optogrid-client/headless_optogrid_backend.py'
Restart=always

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable optogrid.service

echo "Systemd service created and enabled. The backend will now run on boot."

echo ""
echo "=========================================="
echo "  Setup Complete!"
echo "=========================================="
echo "The virtual environment is now active in this terminal session."
echo ""
echo "To activate this environment in future terminal sessions:"
echo "  source optogrid-client-env/bin/activate"
echo ""
echo "To run the OptoGrid client:"
echo "  python pyqt_optogrid_python_client.py"
echo ""
echo "To run the headless backend:"
echo "  python3 headless_optogrid_backend.py"
echo "==========================================