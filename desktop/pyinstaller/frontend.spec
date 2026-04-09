# -*- mode: python ; coding: utf-8 -*-
#
# PyInstaller spec for the Dublin City Dashboard frontend Flask server.
#
# Build command (run from repo root):
#   pyinstaller desktop/pyinstaller/frontend.spec --distpath desktop/dist --workpath desktop/build/pyinstaller
#
# The resulting binary is named `frontend-server` (or `frontend-server.exe` on
# Windows) and is picked up by electron-builder as an extraResource.

import os
import sys
from PyInstaller.utils.hooks import collect_submodules, collect_data_files

# --------------------------------------------------------------------------
# Paths
# --------------------------------------------------------------------------
repo_root = os.path.abspath(os.path.join(SPECPATH, '..', '..'))
frontend_dir = os.path.join(repo_root, 'frontend')

# --------------------------------------------------------------------------
# Data files — Jinja2 templates and static assets MUST be bundled
# --------------------------------------------------------------------------
datas = [
    (os.path.join(frontend_dir, 'templates'), 'frontend/templates'),
    (os.path.join(frontend_dir, 'static'),    'frontend/static'),
]

# --------------------------------------------------------------------------
# Hidden imports
# --------------------------------------------------------------------------
hidden_imports = (
    collect_submodules('flask')
    + collect_submodules('flask_cors')
    + collect_submodules('requests')
    + collect_submodules('frontend')
    + [
        'frontend.app',
        'frontend.dashboard.overview',
        'frontend.dashboard.analytics',
        'frontend.dashboard.recommendations',
        'frontend.dashboard.routing',
        'werkzeug',
        'werkzeug.serving',
        'jinja2',
        'jinja2.ext',
        'click',
        'itsdangerous',
    ]
)

# --------------------------------------------------------------------------
# Entry point wrapper
# --------------------------------------------------------------------------
entry_script = os.path.join(SPECPATH, '_frontend_entry.py')
with open(entry_script, 'w') as f:
    f.write("""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'frontend'))

# Adjust template and static folder paths to the bundled location
import frontend.app as _fa
_fa._TEMPLATE_FOLDER = os.path.join(sys._MEIPASS, 'frontend', 'templates')
_fa._STATIC_FOLDER   = os.path.join(sys._MEIPASS, 'frontend', 'static')

from frontend.app import create_app

app = create_app()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', '5002'))
    app.run(host='0.0.0.0', port=port, debug=False)
""")

# --------------------------------------------------------------------------
# Analysis
# --------------------------------------------------------------------------
a = Analysis(
    [entry_script],
    pathex=[repo_root, frontend_dir],
    binaries=[],
    datas=datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['firebase_admin', 'google.cloud'],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='frontend-server',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
