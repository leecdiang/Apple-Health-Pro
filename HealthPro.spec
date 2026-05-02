# -*- mode: python ; coding: utf-8 -*-

a = Analysis(
    ['health_app.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[], # 保持清空，不乱删依赖
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='HealthPro',
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
    icon=['icon.icns'],
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='HealthPro',
)

# 关键修复点：这里必须是 coll，把 100MB 的核心依赖装进去！
app = BUNDLE(
    coll, 
    name='HealthPro.app',
    icon='icon.icns',
    bundle_identifier='com.leecdiang.healthpro',
    info_plist={
        'NSPrincipalClass': 'NSApplication',
        'NSAppleScriptEnabled': False,
        'CFBundleShortVersionString': '8.6.0',
        'CFBundleVersion': '1',
        'NSHumanReadableCopyright': 'Copyright © 2026 LEEcDiang. All rights reserved.'
    },
)