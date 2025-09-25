# -*- mode: python ; coding: utf-8 -*-
import sys
from PyInstaller.utils.hooks import collect_submodules

block_cipher = None

# Include the local SQLite DB used by the app (if present in repo root)
datas = []
db_path = 'multi-agent_mcp_context_manager.db'
try:
    import os
    if os.path.exists(db_path):
        datas.append((db_path, '.'))
except Exception:
    pass

# Collect some commonly missed dynamic imports from frameworks used
hiddenimports = []
hiddenimports += collect_submodules('uvicorn') if 'uvicorn' in sys.modules or True else []
hiddenimports += collect_submodules('fastapi') if 'fastapi' in sys.modules or True else []
hiddenimports += collect_submodules('websockets') if 'websockets' in sys.modules or True else []
hiddenimports += collect_submodules('keyring') if 'keyring' in sys.modules or True else []
hiddenimports += collect_submodules('cachetools') if 'cachetools' in sys.modules or True else []

# Analysis: include the project entry point
a = Analysis(
    ['main.py'],
    pathex=['.'],
    binaries=[],
    datas=datas,
    hiddenimports=list(set(hiddenimports)),
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='mcp_gui',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    target_arch=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    name='mcp_gui',
)
