# desktop.spec  — PyInstaller build spec for Dublin City Dashboard
# Build: (desktop\.venv) pyinstaller desktop.spec

import sys
from pathlib import Path
import importlib.util

ROOT = Path(SPECPATH)

# Locate webview package regardless of whether a venv is active or not
_webview_spec = importlib.util.find_spec("webview")
WEBVIEW_DIR = Path(_webview_spec.origin).parent

block_cipher = None

a = Analysis(
    [str(ROOT / "launch_desktop.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=[
        # pywebview JS helpers
        (str(WEBVIEW_DIR / "js"),            "webview/js"),
        # bundled MarkerCluster CSS + any other local vendor files
        (str(ROOT / "desktop" / "assets"),   "desktop/assets"),
    ],
    hiddenimports=[
        # pywebview Windows backend
        "webview.platforms.winforms",
        # pystray Windows tray
        "pystray._win32",
        # PIL formats needed for tray icon
        "PIL.PngImagePlugin",
        "PIL.IcoImagePlugin",
        # sqlite3 is stdlib — included automatically, listed for clarity
        "sqlite3",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "tkinter",
        "unittest",
        "xmlrpc",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="DublinCityDashboard",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,          # no console window
    icon=str(ROOT / "desktop" / "assets" / "tray-icon.ico"),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="DublinCityDashboard",
)
