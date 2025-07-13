# optogrid_client

On Linux:
1. Install pyenv dependency
sudo apt update && sudo apt install -y \
  make build-essential libssl-dev zlib1g-dev \
  libbz2-dev libreadline-dev libsqlite3-dev wget curl llvm \
  libncursesw5-dev xz-utils tk-dev libxml2-dev \
  libxmlsec1-dev libffi-dev liblzma-dev

2. Install pyenv
curl https://pyenv.run | bash

3. copy this to ~/.zshrc
export PYENV_ROOT="$HOME/.pyenv"
export PATH="$PYENV_ROOT/bin:$PATH"
eval "$(pyenv init --path)"
eval "$(pyenv init -)"
eval "$(pyenv virtualenv-init -)"

4. restart shell
source ~/.zshrc


5. install python 3.12.4
pyenv install 3.12.4


6. Set optogrid-client local folder to use python 3.12.4
pyenv local 3.12.4


7. Install pyqt dependency:
sudo apt update && sudo apt install -y \
  libxcb-xinerama0 libxcb-icccm4 libxcb-image0 libxcb-keysyms1 libxcb-randr0 \
  libxcb-render-util0 libxcb-xkb1 libxkbcommon-x11-0 libx11-xcb1
sudo apt install qt5-qmake qtbase5-dev build-essential

7.5 Install pyqt5 separatly in RPi instead of using pip install requirements
sudo apt install python3-pyqt5

7.6 If you are on RPI, to install lgpio, you need this:
sudo apt update
sudo apt install python3-lgpio

8. run setup script
chmod +x env_setup_linux.sh
./env_setup_linux.sh

9. activate virtual enviornment

888 For RPi, just run
python3 headless_optogrid_backend.py

10. run the pyqt client server

11. For MATLAB, use a separate compatible python
pyenv install 3.9.18

12. On MATLAB, you will need to load python in, to run the matlab zmq functions, in matlab run:
pyenv('Version', '/home/delab/.pyenv/versions/3.9.18/bin/python');

13. use this to check MATLAB python is correct
pyevn

14. Go to repos/bpod-protocol
pyenv local 3.9.18
pip install zmq

15. 




## Windows to make MATLAB support zmq
1. 
