# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['pyqt_optogrid_python_client.py'],
    pathex=[],
    binaries=[],
    datas=[('/Users/danielmac/repos/optogrid-client/brainmap.png', '.'), ('/Users/danielmac/repos/optogrid-client/optogrid-client-env/lib/python3.12/site-packages/ahrs/utils/WMM2020/WMM.COF', 'ahrs/utils/WMM2020')],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='pyqt_optogrid_python_client',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='pyqt_optogrid_python_client',
)
app = BUNDLE(
    coll,
    name='pyqt_optogrid_python_client.app',
    icon=None,
    bundle_identifier=None,
)
