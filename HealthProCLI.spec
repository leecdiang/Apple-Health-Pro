from pathlib import Path
root = Path(SPECPATH)
a = Analysis([str(root/'healthpro_cli.py')], pathex=[str(root)], binaries=[],
             datas=[(str(root/'healthpro/version.txt'), 'healthpro')],
             hiddenimports=[], hookspath=[], hooksconfig={}, runtime_hooks=[],
             excludes=['PyQt6', 'psutil'], noarchive=False, optimize=0)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, a.binaries, a.datas, [], name='healthpro-cli',
          debug=False, bootloader_ignore_signals=False, strip=False, upx=False,
          console=True)
