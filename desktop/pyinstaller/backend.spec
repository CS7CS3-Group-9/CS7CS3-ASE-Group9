# -*- mode: python ; coding: utf-8 -*-
#
# PyInstaller spec for the Dublin City Dashboard backend Flask server.
#
# Build command (run from repo root):
#   pyinstaller desktop/pyinstaller/backend.spec --distpath desktop/dist --workpath desktop/build/pyinstaller
#
# The resulting binary is named `backend-server` (or `backend-server.exe` on
# Windows) and is picked up by electron-builder as an extraResource.

import os
import sys
from PyInstaller.utils.hooks import collect_submodules, collect_data_files

# --------------------------------------------------------------------------
# Paths
# --------------------------------------------------------------------------
repo_root = os.path.abspath(os.path.join(SPECPATH, '..', '..'))
backend_dir = os.path.join(repo_root, 'backend')

# --------------------------------------------------------------------------
# Data files (GTFS bus data, etc.)
# --------------------------------------------------------------------------
datas = []

# Include any CSV / JSON data files shipped with the backend
for dirpath, _dirs, files in os.walk(backend_dir):
    for fname in files:
        if fname.endswith(('.csv', '.json', '.txt')) and '__pycache__' not in dirpath:
            src = os.path.join(dirpath, fname)
            rel = os.path.relpath(dirpath, repo_root)
            datas.append((src, rel))

# --------------------------------------------------------------------------
# Hidden imports (Flask plugins and dynamic imports that PyInstaller misses)
# --------------------------------------------------------------------------
hidden_imports = (
    collect_submodules('flask')
    + collect_submodules('flask_cors')
    + collect_submodules('requests')
    + collect_submodules('backend')
    + [
        'backend.app',
        'backend.api.endpoints.example',
        'backend.api.endpoints.snapshot',
        'backend.api.endpoints.bikes',
        'backend.api.endpoints.traffic',
        'backend.api.endpoints.airquality',
        'backend.api.endpoints.tours',
        'backend.api.endpoints.health',
        'backend.api.endpoints.routing',
        'backend.api.endpoints.buses',
        'backend.api.endpoints.desktop',
        'backend.services.snapshot_service',
        'backend.adapters.bikes_adapter',
        'backend.adapters.traffic_adapter',
        'backend.adapters.airquality_adapter',
        'backend.adapters.airquality_location_adapter',
        'backend.adapters.tour_adapter',
        'backend.adapters.routes_adapter',
        'backend.fallback.cache',
        'backend.fallback.resolver',
        'backend.fallback.predictor',
        'werkzeug',
        'werkzeug.serving',
        'jinja2',
        'click',
        'itsdangerous',
    ]
)

# --------------------------------------------------------------------------
# Entry point wrapper
# --------------------------------------------------------------------------
# PyInstaller needs a plain Python script as the entry point.
# We write one inline that starts Flask via Gunicorn.
entry_script = os.path.join(SPECPATH, '_backend_entry.py')
with open(entry_script, 'w') as f:
    f.write("""
import os
import sys

# Ensure repo root is on the path so `backend.*` imports resolve
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend.app import create_app

app = create_app()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', '5001'))
    app.run(host='0.0.0.0', port=port, debug=False)
""")

# --------------------------------------------------------------------------
# Analysis
# --------------------------------------------------------------------------
a = Analysis(
    [entry_script],
    pathex=[repo_root],
    binaries=[],
    datas=datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['firebase_admin', 'google.cloud', 'grpc'],  # excluded: desktop mode disables Firestore
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='backend-server',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,   # keep console visible for debugging; set False for production
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
