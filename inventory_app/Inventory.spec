044# -*- mode: python ; coding: utf-8 -*-
# PyInstaller ONE-FILE spec for Inventory App
# Produces a single Inventory.exe that runs standalone.
# Build with:  pyinstaller Inventory.spec --noconfirm

block_cipher = None

a = Analysis(
    ['app.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('templates', 'templates'),
        ('static',    'static'),
    ],
    hiddenimports=[
        'flask',
        'werkzeug',
        'werkzeug.security',
        'werkzeug.routing',
        'werkzeug.exceptions',
        'jinja2',
        'jinja2.ext',
        'click',
        'sqlalchemy',
        'sqlalchemy.dialects.sqlite',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# --onefile: everything packed into a single EXE
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='Inventory',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,   # shows server IP in the black window
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
