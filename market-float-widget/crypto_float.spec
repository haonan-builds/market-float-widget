# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['crypto_float.py'],
    pathex=[],
    binaries=[],
    datas=[('LICENSE', '.'), ('DISTRIBUTION.md', '.'),
           ('THIRD_PARTY_NOTICES.md', '.'), ('licenses', 'licenses')],
    hiddenimports=['websocket'],
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
    a.binaries,
    a.datas,
    [],
    name='crypto_float',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    version='version-info.txt',
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
