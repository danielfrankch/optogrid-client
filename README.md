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



## Deploy the headless_optogrid_backend on RPi:
### You can set up using either of the following two pathway
A -> C

B -> C

#### A. Setup RPi 4 Model B using disk image
1. You need RPi to be connected to ethernet
2. Clone the disk image "rpi_clone_V1.img" to a 16GB SD card, and plug in to RPi then boot
3. ```cd repos/optogrid_client```
4. ```git pull```


B. Setup RPi4 from clean-installed rpi-os
1. Clone this repo
```
cd ~
mkdir repos
cd repos
```

```
git clone https://github.com/danielfrankch/optogrid_client.git
```
2.  Run auto-setup
```
chmod +x env_setup_linux.sh
./env_setup_linux.sh
```


C. Common steps to make sure BLE works
1. Plug in the BLE USB dongle into RPi's non-blue USB port! Important
2. check the usb dongle is properly recognized
```
lsusb
hciconfig
bluetoothctl list
```
These command should all show that there is a second ble avaiable 

3. Disable internal BLE, so that the USB BLE dongle can be in use


```
sudo nano /boot/firmware/config.txt
```
go to bottom, and add this line:
```dtoverlay=disable-bt```
"ctrl+o", then "enter" to save the file
```sudo reboot```

4. Confirm the BLE in use is USB BLE:
```hciconfig```
You should only see a USB BLE

5. Remember to turn on Bluetooth on RPi's upper-right before starting




## On Bpod computer
1. Clone this repo
```
cd repos
git clone https://github.com/danielfrankch/optogrid_client.git
pip install zmq
```
2. In MATLAB: use system python3 executable for MATLAB's python
```
pyenv(Version="/usr/bin/python3")
```
3. Add optogrid class to path
```
addpath('~/repos/optogrid_client/matlab-optogrid')
```

4. In .dbconfig, you should add
[optogrid]
url = 172.xxx.xx.xxx:5555
This should match RPi's ipv4 address

5. Add .opto file with 1 inside, to home directory

6. Connect BNC1 Output to BNC1 Input to pass that weird Opto data saving check

7. For now, Caution that rigtest_fm will give error, as there will not be PulsePal connected for this opto rig

8. For now, caution start_bpod will give error for PulsePal not connected.


## Appendix Cloning and Loading RPi disk image on MacOS
