pyinstaller --onedir --windowed \
--add-data="/Users/danielmac/repos/optogrid-client/brainmap.png:." \
--add-data="/Users/danielmac/repos/optogrid-client/optogrid-client-env/lib/python3.12/site-packages/ahrs/utils/WMM2020/WMM.COF:ahrs/utils/WMM2020" \
pyqt_optogrid_python_client.py