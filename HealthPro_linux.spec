from pathlib import Path
root = Path(SPECPATH)
a = Analysis([str(root/'health_app.py')], pathex=[str(root)], binaries=[],
             datas=[(str(root/'icon.png'), '.'), (str(root/'assets'), 'assets'),
                    (str(root/'healthpro/version.txt'), 'healthpro')],
             hiddenimports=['PyQt6.QtSvg'], hookspath=[], hooksconfig={}, runtime_hooks=[],
             excludes=[], noarchive=False, optimize=0)
pyz = PYZ(a.pure)
exe = EXE(pyz,a.scripts,[],exclude_binaries=True,name='healthpro',debug=False,
          bootloader_ignore_signals=False,strip=False,upx=False,console=False,
          icon=str(root/'icon.png'))
coll = COLLECT(exe,a.binaries,a.datas,strip=False,upx=False,name='healthpro')
