# Build on the target platform. No external font folder is required.
from pathlib import Path
import sys

root = Path(SPECPATH)
version = (root / 'healthpro/version.txt').read_text().strip()
preview = 'rc' in version
icon = str(root / ('icon.icns' if sys.platform == 'darwin' else 'icon.ico'))
native_binaries = []
if sys.platform == 'darwin':
    import runpy
    native_path = runpy.run_path(str(root / 'scripts/build_native.py'))['build'](root)
    native_binaries.append((str(native_path), 'native'))
a = Analysis(
    [str(root / 'health_app.py')], pathex=[str(root)],
    binaries=native_binaries, datas=[(str(root / 'assets'), 'assets'),
                       (str(root / 'healthpro/version.txt'), 'healthpro')],
    hiddenimports=['PyQt6.QtSvg'], hookspath=[], hooksconfig={}, runtime_hooks=[],
    excludes=[], noarchive=False, optimize=0,
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='HealthPro',
          debug=False, bootloader_ignore_signals=False, strip=False, upx=False,
          console=False, argv_emulation=False, target_arch=None,
          codesign_identity=None, entitlements_file=None, icon=icon)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name='HealthPro')
if sys.platform == 'darwin':
    app = BUNDLE(coll, name='HealthPro Preview.app' if preview else 'HealthPro.app', icon=icon,
        bundle_identifier='com.leecdiang.healthpro.preview' if preview else 'com.leecdiang.healthpro',
        info_plist={'NSPrincipalClass': 'NSApplication',
                    'CFBundleDisplayName': 'HealthPro Preview' if preview else 'HealthPro',
                    'CFBundleShortVersionString': version.split('rc')[0],
                    'CFBundleVersion': version.replace('rc', 'b'),
                    'NSHighResolutionCapable': True,
                    'NSHumanReadableCopyright': 'Copyright © 2026 LEEcDiang'})
