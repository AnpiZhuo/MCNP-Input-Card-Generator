# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import collect_submodules


a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[('app', 'app')],
    hiddenimports=(
        # VTK 动态加载模块——pyvista 运行时才导入
        collect_submodules('vtkmodules')
        + collect_submodules('pyvista')
        # pymcnp 子模块
        + collect_submodules('pymcnp')
    ),
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # PyQt5 模块——项目只用到了 Widgets/Core/Gui
        'PyQt5.QtNfc', 'PyQt5.QtOpenGL', 'PyQt5.QtPrintSupport',
        'PyQt5.QtQml', 'PyQt5.QtQuick', 'PyQt5.QtQuick3D',
        'PyQt5.QtQuickWidgets', 'PyQt5.QtRemoteObjects',
        'PyQt5.QtSensors', 'PyQt5.QtSerialPort', 'PyQt5.QtSql',
        'PyQt5.QtTest', 'PyQt5.QtTextToSpeech', 'PyQt5.QtWebChannel',
        'PyQt5.QtWebSockets', 'PyQt5.QtWinExtras', 'PyQt5.QtXml',
        'PyQt5.QtXmlPatterns', 'PyQt5.QtBluetooth', 'PyQt5.QtPositioning',
        'PyQt5.QtMultimedia', 'PyQt5.QtMultimediaWidgets',
        'PyQt5.QtWebEngineWidgets', 'PyQt5.QtWebEngineCore',
        'PyQt5.QtWebEngine',
    ],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='MCNP输入卡生成器',
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
    name='MCNP输入卡生成器',
)
